from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models import User
from app.utils.runtime_env import get_runtime_info

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/runtime")
def runtime_info(_: User = Depends(get_current_user)):
    return get_runtime_info()
