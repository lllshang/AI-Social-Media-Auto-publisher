import asyncio

import httpx

from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.config import get_settings
from app.utils.prompt_templates import load_prompt_template


class HunyuanImageAdapter:
    """腾讯混元生图 OpenAI 兼容异步接口（HY-Image-V3.0）。"""

    provider = "hunyuan"

    def __init__(self, model: str = "HY-Image-V3.0") -> None:
        self.settings = get_settings()
        self.model = model

    def _build_prompt(self, data: ImageGenerateInput) -> str:
        if len(data.topic) > 30:
            return data.topic
        template = load_prompt_template("image", data.platform)
        return template.replace("{platform}", data.platform).replace("{topic}", data.topic).replace(
            "{ratio}", data.ratio
        ).replace("{style}", data.style)

    def _auth_headers(self, api_key: str) -> dict[str, str]:
        token = api_key.strip()
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        return {"Authorization": token, "Content-Type": "application/json"}

    def _resolve_size(self, ratio: str) -> str:
        size_map = {"3:4": "768:1024", "1:1": "1024:1024", "9:16": "720:1280"}
        return size_map.get(ratio, "768:1024")

    def _extract_job_id(self, payload: dict) -> str:
        for key in ("job_id", "JobId"):
            if payload.get(key):
                return str(payload[key])
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("job_id", "JobId"):
                if data.get(key):
                    return str(data[key])
        raise RuntimeError(f"混元生图提交失败，未返回 job_id: {payload}")

    def _extract_status(self, payload: dict) -> str:
        for key in ("status", "job_status", "JobStatusCode", "JobStatusMsg"):
            value = payload.get(key)
            if value is not None:
                return str(value).lower()
        response = payload.get("Response")
        if isinstance(response, dict):
            code = response.get("JobStatusCode")
            msg = response.get("JobStatusMsg")
            if code is not None:
                return str(code)
            if msg is not None:
                return str(msg).lower()
        return ""

    def _extract_image_urls(self, payload: dict) -> list[str]:
        urls: list[str] = []

        def collect(obj: object) -> None:
            if isinstance(obj, str) and obj.startswith("http"):
                urls.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    collect(item)
            elif isinstance(obj, dict):
                for key in ("url", "image_url", "ImageUrl"):
                    if obj.get(key):
                        urls.append(str(obj[key]))
                for value in obj.values():
                    collect(value)

        for key in ("generations", "data", "ResultImage", "ResultUrls", "images"):
            if payload.get(key) is not None:
                collect(payload[key])
        if isinstance(payload.get("Response"), dict):
            response = payload["Response"]
            for key in ("ResultImage", "ResultUrls"):
                if response.get(key) is not None:
                    collect(response[key])

        # 去重保序
        seen: set[str] = set()
        ordered: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                ordered.append(url)
        return ordered

    async def _poll_result(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        query_url: str,
        job_id: str,
    ) -> list[str]:
        for _ in range(90):
            resp = await client.post(query_url, headers=headers, json={"job_id": job_id})
            resp.raise_for_status()
            payload = resp.json()
            status = self._extract_status(payload)
            if status in {"5", "done", "completed", "succeeded", "success", "处理完成"}:
                urls = self._extract_image_urls(payload)
                if urls:
                    return urls
                raise RuntimeError(f"混元生图已完成但未返回图片 URL: {payload}")
            if status in {"4", "fail", "failed", "error", "处理失败"}:
                err = payload.get("JobErrorMsg") or payload.get("message") or payload
                raise RuntimeError(f"混元生图失败: {err}")
            await asyncio.sleep(2)
        raise TimeoutError("混元生图查询超时，请稍后重试")

    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult:
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        prompt = self._build_prompt(data)
        storage = get_adapter_factory().get_storage_adapter()
        config = AiProviderConfigService()
        api_key = config.get_field_value("hunyuan_api_key")
        if not api_key:
            from app.adapters.ai_image.stub import StubImageAdapter

            result = await StubImageAdapter().generate(data)
            result.provider = self.provider
            result.prompt = prompt
            return result

        base_url = (
            config.get_field_value("hunyuan_image_base_url") or self.settings.hunyuan_image_base_url
        ).rstrip("/")
        headers = self._auth_headers(api_key)
        size = self._resolve_size(data.ratio)
        submit_url = f"{base_url}/aiart/submit"
        query_url = f"{base_url}/aiart/query"

        async with httpx.AsyncClient(timeout=180) as client:
            submit_resp = await client.post(
                submit_url,
                headers=headers,
                json={"model": self.model, "prompt": prompt, "size": size},
            )
            submit_resp.raise_for_status()
            job_id = self._extract_job_id(submit_resp.json())
            image_urls = await self._poll_result(client, headers, query_url, job_id)

        paths: list[str] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for url in image_urls[: max(1, data.count)]:
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
