from app.config import Settings


def login_poll_params(settings: Settings) -> tuple[int, int]:
    interval = max(1, settings.login_poll_interval_seconds)
    max_checks = max(1, settings.login_timeout_seconds // interval)
    return interval, max_checks
