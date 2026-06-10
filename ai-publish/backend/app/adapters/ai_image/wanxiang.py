import httpx

from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.config import get_settings
from app.utils.prompt_templates import load_prompt_template


class WanxiangImageAdapter:
    provider = "wanxiang"

    def __init__(self, model: str = "wanx-v1") -> None:
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
        prompt = self._build_prompt(data)
        from app.adapters.factory import get_adapter_factory

        storage = get_adapter_factory().get_storage_adapter()

        from app.services.ai_provider_config_service import AiProviderConfigService

        api_key = AiProviderConfigService().get_field_value("dashscope_api_key")
        if not api_key:
            placeholder = (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            paths = []
            for _ in range(max(1, data.count)):
                file_path, _ = storage.save_bytes(placeholder, suffix=".png")
                paths.append(file_path)
            return ImageGenerateResult(image_paths=paths, provider=self.provider, prompt=prompt, cost=0.0)

        size_map = {"3:4": "768*1024", "1:1": "1024*1024", "9:16": "720*1280"}
        size = size_map.get(data.ratio, "768*1024")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "input": {"prompt": prompt},
            "parameters": {"size": size, "n": min(data.count, 4)},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()

        paths: list[str] = []
        for item in payload.get("output", {}).get("results", []):
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
            cost=float(payload.get("usage", {}).get("image_count", 0)),
        )
