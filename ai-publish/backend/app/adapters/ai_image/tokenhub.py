from pathlib import Path

import httpx
import yaml

from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.config import get_settings


class TokenHubImageAdapter:
    """腾讯 MaaS TokenHub 轻量文生图（hy-image-lite）。"""

    provider = "tencent_maas"

    def __init__(self, model: str = "hy-image-lite") -> None:
        self.settings = get_settings()
        self.model = model
        self.prompt_template = self._load_template()

    def _load_template(self) -> str:
        template_path = Path(__file__).resolve().parents[2] / "templates" / "prompts" / "xhs_image.yaml"
        if template_path.exists():
            data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
            return data.get("template", "")
        return "为{platform}生成{ratio}比例封面图，主题：{topic}，风格：{style}"

    def _build_prompt(self, data: ImageGenerateInput) -> str:
        if len(data.topic) > 30:
            return data.topic
        return self.prompt_template.replace("{platform}", data.platform).replace("{topic}", data.topic).replace(
            "{ratio}", data.ratio
        ).replace("{style}", data.style)

    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult:
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        prompt = self._build_prompt(data)
        storage = get_adapter_factory().get_storage_adapter()
        config = AiProviderConfigService()
        api_key = config.get_field_value("tencent_maas_api_key")
        if not api_key:
            from app.adapters.ai_image.stub import StubImageAdapter

            result = await StubImageAdapter().generate(data)
            result.provider = self.provider
            result.prompt = prompt
            return result

        base_url = (
            config.get_field_value("tencent_maas_base_url") or self.settings.tencent_maas_base_url
        ).rstrip("/")
        url = f"{base_url}/api/image/lite"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "prompt": prompt,
            "rsp_img_type": "url",
        }

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()

        urls: list[str] = []
        for item in payload.get("data") or []:
            if isinstance(item, dict) and item.get("url"):
                urls.append(str(item["url"]))

        if not urls:
            raise RuntimeError(f"TokenHub 生图未返回 URL: {payload}")

        paths: list[str] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for image_url in urls[: max(1, data.count)]:
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                suffix = ".jpg" if ".jpg" in image_url.lower() else ".png"
                file_path, _ = storage.save_bytes(img_resp.content, suffix=suffix)
                paths.append(file_path)

        usage = payload.get("usage") or {}
        cost = float(usage.get("credits") or len(paths))

        return ImageGenerateResult(
            image_paths=paths,
            provider=self.provider,
            prompt=prompt,
            cost=cost,
        )
