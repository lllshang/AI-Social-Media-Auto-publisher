from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.adapters.ai_image.wanxiang import WanxiangImageAdapter
from app.adapters.ai_text.openai_compatible import OpenAiCompatibleTextAdapter
from app.adapters.ai_text.stub import StubTextAdapter
from app.adapters.ai_text.tongyi import TongyiTextAdapter
from app.adapters.base import AiImageAdapter, AiTextAdapter, AiVideoAdapter
from app.config import BACKEND_DIR, get_settings
from app.services.ai_provider_config_service import AiProviderConfigService


@dataclass
class ModelOption:
    provider: str
    model: str
    label: str
    source: str  # local | remote
    kind: str  # text | image
    ready: bool = True
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeSelection:
    mode: str = "auto"  # auto | manual
    text_provider: str = "auto"
    text_model: str = ""
    image_provider: str = "auto"
    image_model: str = ""
    video_provider: str = "auto"
    video_model: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionResult:
    detected_at: str
    text: dict[str, Any]
    image: dict[str, Any]
    video: dict[str, Any]
    runtime: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AiModelService:
    REMOTE_TEXT_PROVIDERS = (
        {
            "provider": "tongyi",
            "label": "通义千问 (DashScope)",
            "key_field": "dashscope_api_key",
            "models": [
                ("qwen-plus", "qwen-plus"),
                ("qwen-max", "qwen-max"),
                ("qwen-turbo", "qwen-turbo"),
            ],
        },
        {
            "provider": "openai",
            "label": "OpenAI",
            "key_field": "openai_api_key",
            "base_url_field": "openai_base_url",
            "default_base_url": "https://api.openai.com/v1",
            "models": [
                ("gpt-4o-mini", "gpt-4o-mini"),
                ("gpt-4o", "gpt-4o"),
            ],
        },
        {
            "provider": "deepseek",
            "label": "DeepSeek",
            "key_field": "deepseek_api_key",
            "base_url_field": "deepseek_base_url",
            "default_base_url": "https://api.deepseek.com/v1",
            "models": [
                ("deepseek-chat", "deepseek-chat"),
                ("deepseek-reasoner", "deepseek-reasoner"),
            ],
        },
        {
            "provider": "moonshot",
            "label": "Moonshot (Kimi)",
            "key_field": "moonshot_api_key",
            "base_url_field": "moonshot_base_url",
            "default_base_url": "https://api.moonshot.cn/v1",
            "models": [
                ("moonshot-v1-8k", "moonshot-v1-8k"),
                ("moonshot-v1-32k", "moonshot-v1-32k"),
            ],
        },
        {
            "provider": "tencent_maas",
            "label": "腾讯 MaaS (TokenHub)",
            "key_field": "tencent_maas_api_key",
            "base_url_field": "tencent_maas_base_url",
            "default_base_url": "https://tokenhub.tencentmaas.com/v1",
            "models": [
                ("qwen3.5-flash", "qwen3.5-flash"),
                ("qwen3.5-plus", "qwen3.5-plus"),
                ("deepseek-v3", "deepseek-v3"),
            ],
        },
        {
            "provider": "hunyuan",
            "label": "腾讯混元 (OpenAI 兼容)",
            "key_field": "hunyuan_api_key",
            "base_url_field": "hunyuan_base_url",
            "default_base_url": "https://api.hunyuan.cloud.tencent.com/v1",
            "models": [
                ("hunyuan-turbos-latest", "hunyuan-turbos-latest"),
                ("hunyuan-turbo", "hunyuan-turbo"),
                ("hunyuan-pro", "hunyuan-pro"),
                ("hunyuan-standard", "hunyuan-standard"),
                ("hunyuan-lite", "hunyuan-lite"),
            ],
        },
        {
            "provider": "zhipu",
            "label": "智谱 AI (GLM)",
            "key_field": "zhipu_api_key",
            "base_url_field": "zhipu_base_url",
            "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": [
                ("glm-4-plus", "glm-4-plus"),
                ("glm-4-flash", "glm-4-flash"),
                ("glm-4-air", "glm-4-air"),
            ],
        },
        {
            "provider": "doubao",
            "label": "字节豆包",
            "key_field": "doubao_api_key",
            "base_url_field": "doubao_base_url",
            "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "models": [
                ("doubao-seed-1.6", "doubao-seed-1.6"),
                ("doubao-1.5-pro-32k", "doubao-1.5-pro-32k"),
                ("doubao-1.5-lite-32k", "doubao-1.5-lite-32k"),
            ],
        },
        {
            "provider": "baidu",
            "label": "百度千帆",
            "key_field": "baidu_api_key",
            "base_url_field": "baidu_base_url",
            "default_base_url": "https://qianfan.baidubce.com/v2",
            "models": [
                ("ernie-4.0-8k", "ernie-4.0-8k"),
                ("ernie-3.5-8k", "ernie-3.5-8k"),
            ],
        },
        {
            "provider": "siliconflow",
            "label": "硅基流动",
            "key_field": "siliconflow_api_key",
            "base_url_field": "siliconflow_base_url",
            "default_base_url": "https://api.siliconflow.cn/v1",
            "models": [
                ("deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-V3"),
                ("Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-72B-Instruct"),
            ],
        },
        {
            "provider": "minimax",
            "label": "MiniMax",
            "key_field": "minimax_api_key",
            "base_url_field": "minimax_base_url",
            "default_base_url": "https://api.minimax.chat/v1",
            "models": [
                ("abab6.5s-chat", "abab6.5s-chat"),
                ("abab6.5-chat", "abab6.5-chat"),
            ],
        },
    )

    REMOTE_IMAGE_PROVIDERS = (
        {
            "provider": "doubao",
            "label": "字节豆包 生图",
            "key_field": "doubao_api_key",
            "base_url_field": "doubao_base_url",
            "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "models": [
                ("doubao-seedream-4.0", "seedream-4.0"),
            ],
        },
        {
            "provider": "wanxiang",
            "label": "通义万相 (DashScope)",
            "key_field": "dashscope_api_key",
            "models": [
                ("wanx-v1", "wanx-v1"),
                ("wanx2.1-t2i-turbo", "wanx2.1-t2i-turbo"),
            ],
        },
        {
            "provider": "tencent_maas",
            "label": "腾讯 MaaS 生图",
            "key_field": "tencent_maas_api_key",
            "base_url_field": "tencent_maas_base_url",
            "default_base_url": "https://tokenhub.tencentmaas.com/v1",
            "models": [
                ("hy-image-lite", "hy-image-lite"),
            ],
        },
        {
            "provider": "hunyuan",
            "label": "腾讯混元生图",
            "key_field": "hunyuan_api_key",
            "base_url_field": "hunyuan_image_base_url",
            "default_base_url": "https://api.cloudai.tencent.com/v1",
            "models": [
                ("HY-Image-V3.0", "HY-Image-V3.0"),
            ],
        },
        {
            "provider": "openai",
            "label": "OpenAI DALL·E",
            "key_field": "openai_api_key",
            "base_url_field": "openai_base_url",
            "default_base_url": "https://api.openai.com/v1",
            "models": [
                ("dall-e-3", "dall-e-3"),
            ],
        },
        {
            "provider": "siliconflow",
            "label": "硅基流动生图",
            "key_field": "siliconflow_api_key",
            "base_url_field": "siliconflow_base_url",
            "default_base_url": "https://api.siliconflow.cn/v1",
            "models": [
                ("black-forest-labs/FLUX.1-schnell", "black-forest-labs/FLUX.1-schnell"),
            ],
        },
        {
            "provider": "tencent_vod_image",
            "label": "腾讯 VOD AIGC 生图",
            "key_field": "tencent_vod_secret_id",
            "secret_key_field": "tencent_vod_secret_key",
            "sub_app_id_field": "tencent_vod_sub_app_id",
            "cost_field": "tencent_vod_cost_per_image",
            "models": [
                ("Hunyuan|3.0", "混元 Hunyuan 3.0"),
                ("OG", "OG"),
                ("GG", "GG"),
                ("Qwen", "Qwen"),
            ],
        },
    )

    REMOTE_VIDEO_PROVIDERS = (
        {
            "provider": "wanxiang_video",
            "label": "通义万相视频 (DashScope)",
            "key_field": "dashscope_api_key",
            "models": [
                ("video-synthesis-v1", "通义视频 V1"),
            ],
        },
        {
            "provider": "minimax_video",
            "label": "MiniMax 海螺视频",
            "key_field": "minimax_api_key",
            "models": [
                ("MiniMax-Hailuo-2.3", "海螺 2.3 (文生+图生)"),
                ("MiniMax-Hailuo-02", "海螺 02"),
                ("T2V-01", "T2V-01 (纯文生)"),
                ("I2V-01", "I2V-01 (纯图生)"),
                ("S2V-01", "S2V-01 (主体参考)"),
            ],
        },
        {
            "provider": "kling_video",
            "label": "可灵 AI 视频",
            "key_field": "kling_api_key",
            "base_url_field": "kling_base_url",
            "default_base_url": "https://api.klingai.com",
            "models": [
                ("kling-v1", "可灵 V1"),
                ("kling-v1-5", "可灵 V1.5"),
            ],
        },
        {
            "provider": "dreamina_video",
            "label": "即梦 Dreamina 视频",
            "key_field": "dreamina_api_key",
            "fallback_key_field": "doubao_api_key",
            "base_url_field": "dreamina_base_url",
            "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "models": [
                ("doubao-seedance-2-0-mini-260615", "Seedance 2.0 Mini"),
                ("doubao-seedance-2-0-260128", "Seedance 2.0"),
                ("doubao-seedance-2-0-pro-260528", "Seedance 2.0 Pro"),
            ],
        },
        {
            "provider": "baidu_video",
            "label": "百度文心一格/千帆视频",
            "key_field": "baidu_api_key",
            "base_url_field": "baidu_video_base_url",
            "default_base_url": "https://qianfan.baidubce.com/v2",
            "models": [
                ("bilibili-index", "文心视频"),
            ],
        },
        {
            "provider": "hunyuan_video",
            "label": "腾讯混元视频（占位）",
            "key_field": "hunyuan_api_key",
            "models": [
                ("hunyuan-video-v1", "混元视频 V1（未公开）"),
            ],
        },
        {
            "provider": "tencent_vod_video",
            "label": "腾讯 VOD AIGC 视频",
            "key_field": "tencent_vod_secret_id",
            "fallback_key_field": "tencent_secret_id",
            "secret_key_field": "tencent_vod_secret_key",
            "fallback_secret_key_field": "tencent_secret_key",
            "sub_app_id_field": "tencent_vod_sub_app_id",
            "models": [
                ("Hailuo|H3", "海螺 H3"),
                ("Hailuo|2.0", "海螺 2.0"),
                ("Hunyuan|1.5", "混元 1.5"),
                ("Kling|2.6", "可灵 2.6"),
                ("Kling|2.0", "可灵 2.0"),
                ("Vidu|1.5", "Vidu 1.5"),
                ("PixVerse|2.0", "PixVerse 2.0"),
                ("Mingmou|1.0", "明眸 1.0"),
                ("GV|1.0", "GV 1.0"),
                ("OS|1.0", "OS 1.0"),
            ],
        },
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self.runtime_path = BACKEND_DIR / "data" / "ai_runtime.json"
        self.provider_config = AiProviderConfigService()

    def _config_value(self, field: str | None) -> str:
        if not field:
            return ""
        return self.provider_config.get_field_value(field)

    def _runtime_path(self) -> Path:
        path = self.runtime_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def load_runtime(self) -> RuntimeSelection:
        path = self._runtime_path()
        if not path.exists():
            runtime = RuntimeSelection(
                mode="auto",
                text_provider=self.settings.ai_text_provider,
                text_model=self.settings.ai_text_model,
                image_provider=self.settings.ai_image_provider,
                image_model=self.settings.ai_image_model,
            )
            self.save_runtime(runtime)
            return runtime
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return RuntimeSelection(**data)
        except Exception:
            runtime = RuntimeSelection(
                mode="auto",
                text_provider="auto",
                text_model="",
                image_provider="auto",
                image_model="",
            )
            self.save_runtime(runtime)
            return runtime

    def save_runtime(self, runtime: RuntimeSelection) -> RuntimeSelection:
        runtime.updated_at = datetime.now(timezone.utc).isoformat()
        self._runtime_path().write_text(
            json.dumps(runtime.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return runtime

    def set_selection(
        self,
        *,
        mode: str | None = None,
        text_provider: str | None = None,
        text_model: str | None = None,
        image_provider: str | None = None,
        image_model: str | None = None,
        video_provider: str | None = None,
        video_model: str | None = None,
    ) -> RuntimeSelection:
        runtime = self.load_runtime()
        if mode is not None:
            runtime.mode = mode
        if text_provider is not None:
            runtime.text_provider = text_provider
        if text_model is not None:
            runtime.text_model = text_model
        if image_provider is not None:
            runtime.image_provider = image_provider
        if image_model is not None:
            runtime.image_model = image_model
        if video_provider is not None:
            runtime.video_provider = video_provider
        if video_model is not None:
            runtime.video_model = video_model
        return self.save_runtime(runtime)

    async def detect_ollama_models(self) -> list[ModelOption]:
        base_url = self._config_value("ollama_base_url") or self.settings.ollama_base_url
        base_url = base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{base_url}/api/tags")
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:
            return [
                ModelOption(
                    provider="ollama",
                    model="",
                    label="Ollama (未连接)",
                    source="local",
                    kind="text",
                    ready=False,
                    reason=str(exc),
                )
            ]

        options: list[ModelOption] = []
        for item in payload.get("models", []):
            name = item.get("name") or item.get("model")
            if not name:
                continue
            caps = item.get("capabilities") or []
            if caps and "completion" not in caps and "vision" in caps:
                continue
            options.append(
                ModelOption(
                    provider="ollama",
                    model=name,
                    label=f"{name} (本地 Ollama)",
                    source="local",
                    kind="text",
                    ready=True,
                )
            )
        return sorted(options, key=lambda x: x.model, reverse=True)

    def _custom_text_options(self) -> list[ModelOption]:
        options: list[ModelOption] = []
        for item in self.provider_config.list_custom_providers():
            if item.get("kind") not in {"text", "both"}:
                continue
            key_field = self.provider_config._custom_key_field(item["provider"])
            api_key = self._config_value(key_field)
            ready = bool(api_key)
            reason = None if ready else "未配置 API Key"
            models = item.get("text_models") or ["default"]
            label = item.get("label") or item["provider"]
            for model_name in models:
                options.append(
                    ModelOption(
                        provider=item["provider"],
                        model=model_name,
                        label=f"{label} / {model_name}",
                        source="remote",
                        kind="text",
                        ready=ready,
                        reason=reason,
                    )
                )
        return options

    def _custom_image_options(self) -> list[ModelOption]:
        options: list[ModelOption] = []
        for item in self.provider_config.list_custom_providers():
            if item.get("kind") not in {"image", "both"}:
                continue
            key_field = self.provider_config._custom_key_field(item["provider"])
            api_key = self._config_value(key_field)
            ready = bool(api_key)
            reason = None if ready else "未配置 API Key"
            models = item.get("image_models") or ["default"]
            label = item.get("label") or item["provider"]
            for model_name in models:
                options.append(
                    ModelOption(
                        provider=item["provider"],
                        model=model_name,
                        label=f"{label} / {model_name}",
                        source="remote",
                        kind="image",
                        ready=ready,
                        reason=reason,
                    )
                )
        return options

    def _remote_text_options(self) -> list[ModelOption]:
        options: list[ModelOption] = []
        for spec in self.REMOTE_TEXT_PROVIDERS:
            api_key = self._config_value(spec["key_field"])
            ready = bool(api_key)
            reason = None if ready else "未配置 API Key"
            for model_id, model_name in spec["models"]:
                options.append(
                    ModelOption(
                        provider=spec["provider"],
                        model=model_name,
                        label=f"{spec['label']} / {model_name}",
                        source="remote",
                        kind="text",
                        ready=ready,
                        reason=reason,
                    )
                )
        options.extend(self._custom_text_options())
        options.append(
            ModelOption(
                provider="stub",
                model="stub",
                label="Stub 占位文案",
                source="local",
                kind="text",
                ready=True,
                reason="无 Key 或未匹配到可用模型时使用",
            )
        )
        return options

    def _remote_image_options(self) -> list[ModelOption]:
        options: list[ModelOption] = []
        for spec in self.REMOTE_IMAGE_PROVIDERS:
            api_key = self._config_value(spec["key_field"])
            ready = bool(api_key)
            reason = None if ready else "未配置 API Key"
            secret_key_field = spec.get("secret_key_field")
            sub_app_id_field = spec.get("sub_app_id_field")
            if secret_key_field:
                if not self._config_value(secret_key_field):
                    ready = False
                    reason = reason or "未配置 SecretKey"
            if sub_app_id_field:
                if not self._config_value(sub_app_id_field):
                    ready = False
                    reason = reason or "未配置 SubAppId"
            for _, model_name in spec["models"]:
                options.append(
                    ModelOption(
                        provider=spec["provider"],
                        model=model_name,
                        label=f"{spec['label']} / {model_name}",
                        source="remote",
                        kind="image",
                        ready=ready,
                        reason=reason,
                    )
                )
        options.extend(self._custom_image_options())
        options.append(
            ModelOption(
                provider="stub",
                model="stub",
                label="Stub 占位图",
                source="local",
                kind="image",
                ready=True,
                reason="无 Key 时使用 1x1 PNG",
            )
        )
        return options

    def _remote_video_options(self) -> list[ModelOption]:
        options: list[ModelOption] = []
        for spec in self.REMOTE_VIDEO_PROVIDERS:
            api_key = self._config_value(spec["key_field"])
            fallback_key_field = spec.get("fallback_key_field")
            if not api_key and fallback_key_field:
                api_key = self._config_value(fallback_key_field)
            ready = bool(api_key)
            reason = None if ready else "未配置 API Key"
            for model_id, model_name in spec["models"]:
                options.append(
                    ModelOption(
                        provider=spec["provider"],
                        model=model_id,
                        label=f"{spec['label']} / {model_name}",
                        source="remote",
                        kind="video",
                        ready=ready,
                        reason=reason,
                    )
                )
        options.append(
            ModelOption(
                provider="stub",
                model="stub",
                label="Stub 占位视频",
                source="local",
                kind="video",
                ready=True,
                reason="无 Key 时生成黑屏占位视频",
            )
        )
        return options

    def _pick_best_video(self, options: list[ModelOption]) -> ModelOption:
        ready = [o for o in options if o.ready and o.provider != "stub"]

        # 优先级：可灵 > 即梦 > MiniMax > 通义万相 > 腾讯混元 > stub
        for provider in ("kling_video", "dreamina_video", "minimax_video", "wanxiang_video", "hunyuan_video"):
            choice = next((o for o in ready if o.provider == provider), None)
            if choice:
                return choice

        return next(o for o in options if o.provider == "stub")

    def _rank_ollama_model(self, model: str) -> tuple[int, str]:
        preferred = (self.settings.ollama_text_model or "").lower()
        name = model.lower()
        if preferred and name == preferred:
            return (0, model)
        if "latest" in name:
            return (1, model)
        if "3.6" in name or "3.5" in name:
            return (2, model)
        if "14b" in name or "30b" in name:
            return (3, model)
        return (4, model)

    def _pick_best_text(self, options: list[ModelOption]) -> ModelOption:
        ready = [o for o in options if o.ready and o.provider != "stub"]
        local = [o for o in ready if o.source == "local"]
        if local:
            local.sort(key=lambda o: self._rank_ollama_model(o.model))
            return local[0]
        remote = [o for o in ready if o.source == "remote"]
        if remote:
            tongyi = next((o for o in remote if o.provider == "tongyi"), None)
            if tongyi:
                return tongyi
            hunyuan = next((o for o in remote if o.provider == "hunyuan"), None)
            if hunyuan:
                return hunyuan
            tencent_maas = next((o for o in remote if o.provider == "tencent_maas"), None)
            if tencent_maas:
                return tencent_maas
            return remote[0]
        return next(o for o in options if o.provider == "stub")

    def _pick_best_image(self, options: list[ModelOption]) -> ModelOption:
        ready = [o for o in options if o.ready and o.provider != "stub"]
        wanxiang = next((o for o in ready if o.provider == "wanxiang"), None)
        if wanxiang:
            return wanxiang
        tencent_maas = next((o for o in ready if o.provider == "tencent_maas"), None)
        if tencent_maas:
            return tencent_maas
        hunyuan = next((o for o in ready if o.provider == "hunyuan"), None)
        if hunyuan:
            return hunyuan
        tencent_maas = next((o for o in ready if o.provider == "tencent_maas"), None)
        if tencent_maas:
            return tencent_maas
        openai = next((o for o in ready if o.provider == "openai"), None)
        if openai:
            return openai
        return next(o for o in options if o.provider == "stub")

    async def detect_all(self) -> DetectionResult:
        ollama = await self.detect_ollama_models()
        text_options = ollama + self._remote_text_options()
        image_options = self._remote_image_options()
        video_options = self._remote_video_options()
        runtime = self.load_runtime()

        if runtime.mode == "auto" or runtime.text_provider in {"", "auto"}:
            recommended_text = self._pick_best_text(text_options)
            runtime.text_provider = recommended_text.provider
            runtime.text_model = recommended_text.model
        if runtime.mode == "auto" or runtime.image_provider in {"", "auto"}:
            recommended_image = self._pick_best_image(image_options)
            runtime.image_provider = recommended_image.provider
            runtime.image_model = recommended_image.model
        if runtime.mode == "auto" or runtime.video_provider in {"", "auto"}:
            recommended_video = self._pick_best_video(video_options)
            runtime.video_provider = recommended_video.provider
            runtime.video_model = recommended_video.model
        if runtime.mode == "auto":
            self.save_runtime(runtime)

        current_text = next(
            (
                o
                for o in text_options
                if o.provider == runtime.text_provider and o.model == runtime.text_model
            ),
            self._pick_best_text(text_options),
        )
        current_image = next(
            (
                o
                for o in image_options
                if o.provider == runtime.image_provider and o.model == runtime.image_model
            ),
            self._pick_best_image(image_options),
        )
        current_video = next(
            (
                o
                for o in video_options
                if o.provider == runtime.video_provider and o.model == runtime.video_model
            ),
            self._pick_best_video(video_options),
        )

        return DetectionResult(
            detected_at=datetime.now(timezone.utc).isoformat(),
            text={
                "current": current_text.to_dict(),
                "recommended": self._pick_best_text(text_options).to_dict(),
                "available": [o.to_dict() for o in text_options],
            },
            image={
                "current": current_image.to_dict(),
                "recommended": self._pick_best_image(image_options).to_dict(),
                "available": [o.to_dict() for o in image_options],
            },
            video={
                "current": current_video.to_dict(),
                "recommended": self._pick_best_video(video_options).to_dict(),
                "available": [o.to_dict() for o in video_options],
            },
            runtime=runtime.to_dict(),
        )

    def _resolve_text_target(self) -> tuple[str, str]:
        runtime = self.load_runtime()
        provider = runtime.text_provider or self.settings.ai_text_provider
        model = runtime.text_model or self.settings.ai_text_model
        if provider in {"", "auto"}:
            provider = self.settings.ai_text_provider
        if provider in {"", "auto"}:
            provider = "stub"
        if not model and provider == "tongyi":
            model = "qwen-plus"
        if not model and provider == "tencent_maas":
            model = "qwen3.5-flash"
        if not model and provider == "hunyuan":
            model = "hunyuan-turbos-latest"
        if not model and provider == "ollama":
            model = self.settings.ollama_text_model or "qwen3.6:latest"
        if not model and provider != "stub":
            model = "default"
        return provider, model

    def _resolve_image_target(self) -> tuple[str, str]:
        runtime = self.load_runtime()
        provider = runtime.image_provider or self.settings.ai_image_provider
        model = runtime.image_model or self.settings.ai_image_model
        if provider in {"", "auto"}:
            provider = self.settings.ai_image_provider
        if provider in {"", "auto"}:
            provider = "stub"
        if not model and provider == "wanxiang":
            model = "wanx-v1"
        if not model and provider == "tencent_maas":
            model = "hy-image-lite"
        if not model and provider == "hunyuan":
            model = "HY-Image-V3.0"
        if not model and provider != "stub":
            model = "default"
        return provider, model

    def get_text_adapter(self) -> AiTextAdapter:
        provider, model = self._resolve_text_target()
        if provider == "stub":
            return StubTextAdapter()
        if provider == "tongyi":
            return TongyiTextAdapter(model=model or "qwen-plus")
        if provider == "ollama":
            ollama_base = self._config_value("ollama_base_url") or self.settings.ollama_base_url
            return OpenAiCompatibleTextAdapter(
                provider="ollama",
                api_key="ollama",
                base_url=f"{ollama_base.rstrip('/')}/v1",
                model=model,
            )
        remote_map = {spec["provider"]: spec for spec in self.REMOTE_TEXT_PROVIDERS}
        spec = remote_map.get(provider)
        if spec:
            key_field = spec["key_field"]
            base_field = spec.get("base_url_field")
            base_url = self._config_value(base_field) if base_field else spec["default_base_url"]
            if not base_url and base_field:
                base_url = getattr(self.settings, base_field, spec["default_base_url"])
            return OpenAiCompatibleTextAdapter(
                provider=provider,
                api_key=self._config_value(key_field),
                base_url=base_url,
                model=model,
            )
        custom = self.provider_config.get_custom_provider(provider)
        if custom:
            key_field = self.provider_config._custom_key_field(provider)
            return OpenAiCompatibleTextAdapter(
                provider=provider,
                api_key=self._config_value(key_field),
                base_url=custom.get("base_url") or "",
                model=model,
            )
        return StubTextAdapter()

    def get_image_adapter(self) -> AiImageAdapter:
        provider, model = self._resolve_image_target()
        if provider == "wanxiang":
            return WanxiangImageAdapter(model=model or "wanx-v1")
        if provider == "tencent_maas":
            from app.adapters.ai_image.tokenhub import TokenHubImageAdapter

            return TokenHubImageAdapter(model=model or "hy-image-lite")
        if provider == "hunyuan":
            from app.adapters.ai_image.hunyuan import HunyuanImageAdapter

            return HunyuanImageAdapter(model=model or "HY-Image-V3.0")
        if provider == "openai":
            from app.adapters.ai_image.openai_dalle import OpenAiDalleImageAdapter

            return OpenAiDalleImageAdapter(model=model or "dall-e-3")
        if provider == "siliconflow":
            from app.adapters.ai_image.openai_dalle import OpenAiDalleImageAdapter

            return OpenAiDalleImageAdapter(model=model or "black-forest-labs/FLUX.1-schnell")
        if provider == "doubao":
            from app.adapters.ai_image.openai_dalle import OpenAiDalleImageAdapter

            return OpenAiDalleImageAdapter(model=model or "doubao-seedream-4.0")
        custom = self.provider_config.get_custom_provider(provider)
        if custom and custom.get("kind") in {"image", "both"}:
            from app.adapters.ai_image.openai_dalle import OpenAiDalleImageAdapter

            return OpenAiDalleImageAdapter(model=model or "default")
        if provider == "tencent_vod_image":
            from app.adapters.ai_image.tencent_vod_image import TencentVodImageAdapter

            secret_id = self._config_value("tencent_vod_secret_id") or self._config_value("tencent_secret_id") or ""
            secret_key = self._config_value("tencent_vod_secret_key") or self._config_value("tencent_secret_key") or ""
            sub_app_id = self._config_value("tencent_vod_sub_app_id") or ""
            try:
                cost_per_image = float(self._config_value("tencent_vod_cost_per_image") or 0)
            except (TypeError, ValueError):
                cost_per_image = 0.0
            model_name, _, model_version = (model or "Hunyuan|3.0").partition("|")
            return TencentVodImageAdapter(
                model_name=model_name or "Hunyuan",
                model_version=model_version or "3.0",
                sub_app_id=sub_app_id,
                secret_id=secret_id,
                secret_key=secret_key,
                cost_per_image=cost_per_image,
            )
        from app.adapters.ai_image.stub import StubImageAdapter

        return StubImageAdapter()

    def get_video_adapter(self) -> AiVideoAdapter:
        """获取当前配置的视频生成适配器"""
        provider, model = self._resolve_video_target()

        if provider == "wanxiang_video":
            from app.adapters.ai_video.wanxiang import WanxiangVideoAdapter

            return WanxiangVideoAdapter(model=model or "video-synthesis-v1")
        elif provider == "minimax_video":
            from app.adapters.ai_video.minimax import MinimaxVideoAdapter

            return MinimaxVideoAdapter(model=model or "MiniMax-Hailuo-2.3")
        elif provider == "kling_video":
            from app.adapters.ai_video.kling import KlingVideoAdapter

            base_url = self._config_value("kling_base_url") or "https://api.klingai.com"
            return KlingVideoAdapter(model=model or "kling-v1", base_url=base_url)
        elif provider == "dreamina_video":
            from app.adapters.ai_video.dreamina import DreaminaVideoAdapter

            base_url = self._config_value("dreamina_base_url") or "https://ark.cn-beijing.volces.com/api/v3"
            dreamina_model = self._config_value("dreamina_model") or model or "doubao-seedance-2-0-mini-260615"
            return DreaminaVideoAdapter(model=dreamina_model, base_url=base_url)
        elif provider == "baidu_video":
            from app.adapters.ai_video.baidu_video import BaiduVideoAdapter

            base_url = self._config_value("baidu_video_base_url") or "https://qianfan.baidubce.com/v2"
            return BaiduVideoAdapter(model=model or "bilibili-index", base_url=base_url)
        elif provider == "hunyuan_video":
            from app.adapters.ai_video.hunyuan import HunyuanVideoAdapter

            return HunyuanVideoAdapter(model=model or "hunyuan-video-v1")
        elif provider == "tencent_vod_video":
            from app.adapters.ai_video.tencent_vod import TencentVodVideoAdapter

            secret_id = self._config_value("tencent_vod_secret_id") or self._config_value("tencent_secret_id") or ""
            secret_key = self._config_value("tencent_vod_secret_key") or self._config_value("tencent_secret_key") or ""
            sub_app_id = self._config_value("tencent_vod_sub_app_id") or ""
            try:
                cost_per_second = float(self._config_value("tencent_vod_cost_per_second") or 0)
            except (TypeError, ValueError):
                cost_per_second = 0.0
            model_name, _, model_version = (model or "Hailuo|H3").partition("|")
            return TencentVodVideoAdapter(
                model_name=model_name or "Hunyuan",
                model_version=model_version or "1.5",
                sub_app_id=sub_app_id,
                secret_id=secret_id,
                secret_key=secret_key,
                cost_per_second=cost_per_second,
            )
        elif provider == "digital_human_video":
            from app.adapters.ai_video.digital_human_stub import DigitalHumanStubVideoAdapter

            return DigitalHumanStubVideoAdapter()
        else:
            from app.adapters.ai_video.stub import StubVideoAdapter

            return StubVideoAdapter()

    def get_digital_human_video_adapter(self) -> AiVideoAdapter:
        """获取数字人视频适配器（占位 stub，待接入真实 provider）"""
        from app.adapters.ai_video.digital_human_stub import DigitalHumanStubVideoAdapter

        return DigitalHumanStubVideoAdapter()

    def _resolve_video_target(self) -> tuple[str, str]:
        """解析视频生成目标（provider, model）"""
        runtime = self.load_runtime()
        provider = runtime.video_provider or "auto"
        model = runtime.video_model or ""

        if provider not in {"", "auto"}:
            return provider, model

        # 自动检测可用提供商（优先级：可灵 > 即梦 > MiniMax > 通义万相 > 腾讯 VOD AIGC > 腾讯混元 > stub）
        if self._config_value("kling_api_key"):
            return "kling_video", "kling-v1"
        elif self._config_value("dreamina_api_key") or self._config_value("doubao_api_key"):
            return "dreamina_video", "seedance-2.0"
        elif self._config_value("minimax_api_key"):
            return "minimax_video", "MiniMax-Hailuo-2.3"
        elif self._config_value("dashscope_api_key"):
            return "wanxiang_video", "video-synthesis-v1"
        elif self._config_value("tencent_vod_secret_id") and self._config_value("tencent_vod_secret_key"):
            return "tencent_vod_video", "Hailuo|H3"
        elif self._config_value("hunyuan_api_key"):
            return "hunyuan_video", "hunyuan-video-v1"
        else:
            return "stub", ""


    def list_provider_configs(self) -> list[dict[str, Any]]:
        return self.provider_config.list_providers()

    def save_provider_config(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        sub_app_id: str | None = None,
        base_url: str | None = None,
        clear_key: bool = False,
    ) -> dict[str, Any]:
        return self.provider_config.save_provider_config(
            provider,
            api_key=api_key,
            secret_key=secret_key,
            sub_app_id=sub_app_id,
            base_url=base_url,
            clear_key=clear_key,
        )

    def add_custom_provider(
        self,
        *,
        label: str,
        base_url: str,
        kind: str = "text",
        text_models: list[str] | None = None,
        image_models: list[str] | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        return self.provider_config.add_custom_provider(
            label=label,
            base_url=base_url,
            kind=kind,
            text_models=text_models,
            image_models=image_models,
            api_key=api_key,
        )

    def delete_custom_provider(self, provider: str) -> None:
        self.provider_config.delete_custom_provider(provider)
