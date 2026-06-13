from app.config import get_settings

BILIBILI_DISABLED_MESSAGE = "B站功能未启用，请在环境变量设置 BILIBILI_ENABLED=true 后重启服务"


def bilibili_enabled() -> bool:
    return get_settings().bilibili_enabled


def assert_bilibili_enabled() -> None:
    if not bilibili_enabled():
        raise ValueError(BILIBILI_DISABLED_MESSAGE)
