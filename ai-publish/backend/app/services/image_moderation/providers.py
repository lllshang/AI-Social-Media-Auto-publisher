from __future__ import annotations

import base64
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.services.system_config_service import SystemConfigService
from app.utils.alibaba_green import post_green_image_scan
from app.utils.tencent_tc3 import post_tencent_api


@dataclass
class ModerationOutcome:
    passed: bool
    provider: str
    message: str
    labels: list[str] | None = None
    billable: bool = False

    def to_detail(self) -> dict:
        return {
            "provider": self.provider,
            "message": self.message,
            "labels": self.labels or [],
            "billable": self.billable,
        }


class ImageModerationProvider(ABC):
    @abstractmethod
    async def moderate(self, file_path: str) -> ModerationOutcome:
        raise NotImplementedError


class StubImageModerationProvider(ImageModerationProvider):
    async def moderate(self, file_path: str) -> ModerationOutcome:
        path = Path(file_path)
        if not path.exists():
            return ModerationOutcome(
                passed=False,
                provider="stub",
                message="图片文件不存在",
                billable=False,
            )
        return ModerationOutcome(
            passed=True,
            provider="stub",
            message="Stub 审核通过（不产生云审费用）",
            billable=False,
        )


class TencentImageModerationProvider(ImageModerationProvider):
    def __init__(self, config: SystemConfigService) -> None:
        self.config = config

    async def moderate(self, file_path: str) -> ModerationOutcome:
        secret_id = (self.config.get_value("image_moderation_tencent_secret_id") or "").strip()
        secret_key = (self.config.get_value("image_moderation_tencent_secret_key") or "").strip()
        region = (self.config.get_value("image_moderation_tencent_region") or "ap-guangzhou").strip()
        if not secret_id or not secret_key:
            return ModerationOutcome(
                passed=False,
                provider="tencent",
                message="未配置腾讯云 SecretId/SecretKey",
                billable=False,
            )
        path = Path(file_path)
        if not path.exists():
            return ModerationOutcome(
                passed=False,
                provider="tencent",
                message="图片文件不存在",
                billable=False,
            )
        raw = path.read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            return ModerationOutcome(
                passed=False,
                provider="tencent",
                message="图片超过 10MB，无法送审",
                billable=False,
            )
        payload = {
            "BizType": "TencentCloudDefault",
            "DataId": str(uuid.uuid4()),
            "FileContent": base64.b64encode(raw).decode("ascii"),
        }
        try:
            data = await post_tencent_api(
                secret_id=secret_id,
                secret_key=secret_key,
                service="ims",
                region=region,
                action="ImageModeration",
                version="2020-12-29",
                payload=payload,
            )
        except Exception as exc:
            logger.warning("Tencent IMS request failed: {}", exc)
            return ModerationOutcome(
                passed=False,
                provider="tencent",
                message=f"腾讯云审核调用失败: {exc}",
                billable=True,
            )

        response = data.get("Response") or {}
        if response.get("Error"):
            err = response["Error"]
            return ModerationOutcome(
                passed=False,
                provider="tencent",
                message=f"腾讯云审核错误: {err.get('Code')} {err.get('Message')}",
                billable=True,
            )
        suggestion = str(response.get("Suggestion") or "Pass")
        label = str(response.get("Label") or "")
        passed = suggestion == "Pass"
        message = f"腾讯云审核: {suggestion}" + (f" ({label})" if label else "")
        return ModerationOutcome(
            passed=passed,
            provider="tencent",
            message=message,
            labels=[label] if label else [],
            billable=True,
        )


class AlibabaImageModerationProvider(ImageModerationProvider):
    def __init__(self, config: SystemConfigService) -> None:
        self.config = config

    async def moderate(self, file_path: str) -> ModerationOutcome:
        access_key_id = (self.config.get_value("image_moderation_alibaba_access_key_id") or "").strip()
        access_key_secret = (self.config.get_value("image_moderation_alibaba_access_key_secret") or "").strip()
        region = (self.config.get_value("image_moderation_alibaba_region") or "cn-shanghai").strip()
        if not access_key_id or not access_key_secret:
            return ModerationOutcome(
                passed=False,
                provider="alibaba",
                message="未配置阿里云 AccessKey",
                billable=False,
            )
        path = Path(file_path)
        if not path.exists():
            return ModerationOutcome(
                passed=False,
                provider="alibaba",
                message="图片文件不存在",
                billable=False,
            )
        raw = path.read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            return ModerationOutcome(
                passed=False,
                provider="alibaba",
                message="图片超过 10MB，无法送审",
                billable=False,
            )
        try:
            data = await post_green_image_scan(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                region=region,
                image_base64=base64.b64encode(raw).decode("ascii"),
            )
        except Exception as exc:
            logger.warning("Alibaba Green request failed: {}", exc)
            return ModerationOutcome(
                passed=False,
                provider="alibaba",
                message=f"阿里云审核调用失败: {exc}",
                billable=True,
            )

        code = data.get("code")
        if code != 200:
            return ModerationOutcome(
                passed=False,
                provider="alibaba",
                message=f"阿里云审核错误: {code} {data.get('msg') or data.get('message')}",
                billable=True,
            )
        labels: list[str] = []
        blocked = False
        review = False
        for item in data.get("data") or []:
            for result in item.get("results") or []:
                scene = str(result.get("scene") or "")
                suggestion = str(result.get("suggestion") or "pass").lower()
                if scene:
                    labels.append(f"{scene}:{suggestion}")
                if suggestion == "block":
                    blocked = True
                elif suggestion == "review":
                    review = True
        passed = not blocked and not review
        if blocked:
            message = "阿里云审核: block"
        elif review:
            message = "阿里云审核: review（建议人工复核）"
        else:
            message = "阿里云审核: pass"
        return ModerationOutcome(
            passed=passed,
            provider="alibaba",
            message=message,
            labels=labels,
            billable=True,
        )


PROVIDER_REGISTRY: dict[str, type[ImageModerationProvider]] = {
    "stub": StubImageModerationProvider,
    "tencent": TencentImageModerationProvider,
    "alibaba": AlibabaImageModerationProvider,
}

PAID_PROVIDERS = {"tencent", "alibaba"}


def build_provider(name: str, config: SystemConfigService) -> ImageModerationProvider:
    provider_cls = PROVIDER_REGISTRY.get(name, StubImageModerationProvider)
    if provider_cls in {TencentImageModerationProvider, AlibabaImageModerationProvider}:
        return provider_cls(config)
    return provider_cls()
