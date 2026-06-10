import httpx

from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.config import get_settings
from app.utils.prompt_templates import load_prompt_template


class OpenAiDalleImageAdapter:
    provider = "openai"

    def __init__(self, model: str = "dall-e-3") -> None:
        self.settings = get_settings()
        self.model = model

    def _build_prompt(self, data: ImageGenerateInput) -> str:
        if len(data.topic) > 30:
            return data.topic
        template = load_prompt_template("image", data.platform)
        return template.replace("{platform}", data.platform).replace("{topic}", data.topic).replace(
            "{ratio}", data.ratio
        ).replace("{style}", data.style)

    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult:
        from app.adapters.factory import get_adapter_factory

        prompt = self._build_prompt(data)
        storage = get_adapter_factory().get_storage_adapter()
        from app.services.ai_provider_config_service import AiProviderConfigService

        api_key = AiProviderConfigService().get_field_value("openai_api_key")
        if not api_key:
            from app.adapters.ai_image.stub import StubImageAdapter

            result = await StubImageAdapter().generate(data)
            result.provider = self.provider
            result.prompt = prompt
            return result

        size_map = {"3:4": "1024x1792", "1:1": "1024x1024", "9:16": "1024x1792"}
        size = size_map.get(data.ratio, "1024x1024")
        base_url = (
            AiProviderConfigService().get_field_value("openai_base_url") or self.settings.openai_base_url
        ).rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "prompt": prompt,
            "n": min(data.count, 1),
            "size": size,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{base_url}/images/generations", headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()

        paths: list[str] = []
        for item in payload.get("data", []):
            url = item.get("url")
            if not url:
                continue
            async with httpx.AsyncClient(timeout=60) as client:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                file_path, _ = storage.save_bytes(img_resp.content, suffix=".png")
                paths.append(file_path)

        return ImageGenerateResult(
            image_paths=paths,
            provider=self.provider,
            prompt=prompt,
            cost=float(len(paths)),
        )
