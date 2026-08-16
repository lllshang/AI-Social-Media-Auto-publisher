"""腾讯云 API 3.0 TC3-HMAC-SHA256 签名（用于 IMS 等）。"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import httpx


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_tc3_authorization(
    *,
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    payload: str,
    timestamp: int,
    date: str,
) -> str:
    canonical_headers = (
        f"content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        "POST\n/\n\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{hashed_payload}"
    )
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )
    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        "TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )


async def post_tencent_api(
    *,
    secret_id: str,
    secret_key: str,
    service: str,
    region: str,
    action: str,
    version: str,
    payload: dict,
    timeout: float = 30.0,
) -> dict:
    host = f"{service}.tencentcloudapi.com"
    endpoint = f"https://{host}"
    body = json.dumps(payload, ensure_ascii=False)
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    authorization = build_tc3_authorization(
        secret_id=secret_id,
        secret_key=secret_key,
        service=service,
        host=host,
        action=action,
        payload=body,
        timestamp=timestamp,
        date=date,
    )
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(endpoint, content=body, headers=headers)
        response.raise_for_status()
        return response.json()
