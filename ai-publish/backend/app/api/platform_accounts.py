import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.dependencies import require_permission
from app.models import User
from app.utils.permissions import PERM_ACCOUNTS_READ, PERM_ACCOUNTS_WRITE
from app.models import PlatformAccount
from app.utils.proxy_utils import mask_proxy_url
from app.schemas import (
    AccountGroupAssignRequest,
    CookieCheckResponse,
    LoginAccountResponse,
    LoginSessionResponse,
    PlatformAccountCreate,
    PlatformAccountResponse,
    PlatformAccountUpdate,
)
from app.services.account_group_service import AccountGroupService
from app.services.log_service import LogService
from app.utils.request_ip import get_client_ip
from app.services.login_session_service import login_session_service
from app.services.platform_account_service import PlatformAccountService
from app.utils.runtime_env import docker_login_hint, platform_scan_hint, qr_login_supported

router = APIRouter(prefix="/api/platform-accounts", tags=["platform-accounts"])


def _account_response(
    account: PlatformAccount,
    group_service: AccountGroupService,
    account_service: PlatformAccountService,
) -> PlatformAccountResponse:
    proxy = account.publish_proxy
    return PlatformAccountResponse(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        remark=account.remark,
        group_id=account.group_id,
        group_name=group_service.get_group_name(account.group_id),
        worker_id=account.worker_id,
        worker_name=account_service.get_worker_name(account.worker_id),
        publish_proxy_masked=mask_proxy_url(proxy),
        has_publish_proxy=bool(proxy),
        status=account.status,
        created_at=account.created_at,
    )


@router.get("", response_model=list[PlatformAccountResponse])
def list_accounts(
    platform: str | None = Query(default=None),
    group_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_ACCOUNTS_READ)),
):
    service = PlatformAccountService(db)
    group_service = AccountGroupService(db)
    accounts = service.list_accounts(platform, group_id)
    return [_account_response(account, group_service, service) for account in accounts]


@router.post("", response_model=PlatformAccountResponse)
def create_account(
    data: PlatformAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = PlatformAccountService(db)
    group_service = AccountGroupService(db)
    try:
        account = service.create_account(data.platform, data.account_name, current_user.id)
        LogService(db).add_operation(
            "platform_account.create",
            current_user.id,
            "platform_account",
            account.id,
            ip=get_client_ip(request),
        )
        return _account_response(account, group_service, service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{account_id}", response_model=PlatformAccountResponse)
def update_account(
    account_id: int,
    data: PlatformAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = PlatformAccountService(db)
    group_service = AccountGroupService(db)
    try:
        fields_set = data.model_fields_set
        account = service.update_account(
            account_id,
            account_name=data.account_name,
            remark=data.remark,
            worker_id=data.worker_id,
            publish_proxy=data.publish_proxy,
            clear_publish_proxy=data.clear_publish_proxy,
            worker_id_set="worker_id" in fields_set,
            publish_proxy_set="publish_proxy" in fields_set or data.clear_publish_proxy,
        )
        LogService(db).add_operation(
            "platform_account.update",
            current_user.id,
            "platform_account",
            account.id,
            ip=get_client_ip(request),
        )
        return _account_response(account, group_service, service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{account_id}/group", response_model=PlatformAccountResponse)
def assign_account_group(
    account_id: int,
    data: AccountGroupAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    account_service = PlatformAccountService(db)
    group_service = AccountGroupService(db)
    try:
        account = group_service.assign_account(account_id, data.group_id)
        return _account_response(account, group_service, account_service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = PlatformAccountService(db)
    try:
        service.delete_account(account_id)
        LogService(db).add_operation(
            "platform_account.delete",
            current_user.id,
            "platform_account",
            account_id,
            ip=get_client_ip(request),
        )
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _run_login_session(session_id: str, account_id: int) -> None:
    session = await login_session_service.get(session_id)
    if not session:
        return

    db = SessionLocal()
    try:
        service = PlatformAccountService(db)
        account = service.get_account(account_id)
        scan_hint = platform_scan_hint(account.platform if account else "xhs")

        async def on_qrcode(payload: dict) -> None:
            current = await login_session_service.get(session_id)
            if not current:
                return
            current.touch(
                status="waiting_scan",
                qrcode_data_url=payload.get("image_data_url") or "",
                qrcode_path=payload.get("image_path") or "",
                message=scan_hint,
            )

        async def on_progress(message: str, status: str = "waiting_scan") -> None:
            current = await login_session_service.get(session_id)
            if not current:
                return
            current.touch(status=status, message=message)

        starting_message = (
            "正在准备二维码，请稍候..."
            if account and account.platform == "bilibili"
            else "正在启动浏览器，请稍候..."
        )
        await on_progress(starting_message, "starting")
        loop = asyncio.get_running_loop()

        def on_progress_sync(message: str, status: str = "starting") -> None:
            future = asyncio.run_coroutine_threadsafe(on_progress(message, status), loop)
            future.result(timeout=10)

        result = await service.login(
            account_id,
            qrcode_callback=on_qrcode,
            progress_callback=on_progress_sync,
        )
        await login_session_service.finish(session_id, result)
    except Exception as exc:
        current = await login_session_service.get(session_id)
        if current:
            current.touch(status="failed", success=False, message=str(exc))
    finally:
        db.close()


@router.post("/{account_id}/login/start", response_model=LoginSessionResponse)
async def start_login_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    if not qr_login_supported():
        raise HTTPException(status_code=400, detail=docker_login_hint())

    service = PlatformAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    session = await login_session_service.create(account_id)
    task = asyncio.create_task(_run_login_session(session.session_id, account_id))
    session.task = task

    for _ in range(120):
        current = await login_session_service.get(session.session_id)
        if not current:
            break
        if current.qrcode_data_url or current.status in {"success", "failed", "timeout"}:
            return LoginSessionResponse(**current.to_dict())
        await asyncio.sleep(0.5)

    current = await login_session_service.get(session.session_id)
    if not current:
        raise HTTPException(status_code=500, detail="登录会话创建失败")
    return LoginSessionResponse(**current.to_dict())


@router.get("/login-sessions/{session_id}", response_model=LoginSessionResponse)
async def get_login_session(
    session_id: str,
    _: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    session = await login_session_service.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    return LoginSessionResponse(**session.to_dict())


@router.post("/{account_id}/login", response_model=LoginAccountResponse)
async def login_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    if not qr_login_supported():
        raise HTTPException(status_code=400, detail=docker_login_hint())

    session = await login_session_service.create(account_id)
    task = asyncio.create_task(_run_login_session(session.session_id, account_id))
    session.task = task

    for _ in range(120):
        current = await login_session_service.get(session.session_id)
        if not current:
            break
        if current.qrcode_data_url:
            return LoginAccountResponse(
                success=False,
                status=current.status,
                message=current.message,
                qrcode_data_url=current.qrcode_data_url,
                qrcode_path=current.qrcode_path,
                session_id=session.session_id,
            )
        if current.status in {"success", "failed", "timeout"}:
            break
        await asyncio.sleep(0.5)

    current = await login_session_service.get(session.session_id)
    if current and current.qrcode_data_url:
        return LoginAccountResponse(
            success=current.success,
            status=current.status,
            message=current.message,
            qrcode_data_url=current.qrcode_data_url,
            qrcode_path=current.qrcode_path,
            session_id=session.session_id,
        )

    if current and current.status in {"success", "failed", "timeout"}:
        return LoginAccountResponse(
            success=current.success,
            status=current.login_status or current.status,
            message=current.message,
            qrcode_data_url=current.qrcode_data_url,
            qrcode_path=current.qrcode_path,
            session_id=session.session_id,
        )

    return LoginAccountResponse(
        success=False,
        status="starting",
        message="正在启动浏览器，请稍候...",
        session_id=session.session_id,
    )


@router.post("/{account_id}/check-cookie", response_model=CookieCheckResponse)
async def check_cookie(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = PlatformAccountService(db)
    try:
        result = await service.check_cookie(
            account_id,
            user_id=current_user.id,
            ip=get_client_ip(request),
        )
        return CookieCheckResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
