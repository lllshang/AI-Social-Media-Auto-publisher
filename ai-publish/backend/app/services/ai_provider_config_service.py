import json
import re
import uuid
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, get_settings
from app.utils.crypto import decrypt_text, encrypt_text

PROVIDER_FIELDS: dict[str, dict[str, Any]] = {
    "tongyi": {
        "label": "通义千问 / 万相 (DashScope)",
        "key_field": "dashscope_api_key",
        "base_url_field": None,
        "default_base_url": "",
        "kind": "both",
    },
    "hunyuan": {
        "label": "腾讯混元 (OpenAI 兼容)",
        "key_field": "hunyuan_api_key",
        "base_url_field": "hunyuan_base_url",
        "default_base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "kind": "both",
        "image_base_url_field": "hunyuan_image_base_url",
        "default_image_base_url": "https://api.cloudai.tencent.com/v1",
    },
    "tencent_maas": {
        "label": "腾讯 MaaS (TokenHub)",
        "key_field": "tencent_maas_api_key",
        "base_url_field": "tencent_maas_base_url",
        "default_base_url": "https://tokenhub.tencentmaas.com/v1",
        "kind": "both",
    },
    "zhipu": {
        "label": "智谱 AI (GLM)",
        "key_field": "zhipu_api_key",
        "base_url_field": "zhipu_base_url",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "kind": "text",
    },
    "doubao": {
        "label": "字节豆包 (火山方舟)",
        "key_field": "doubao_api_key",
        "base_url_field": "doubao_base_url",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "kind": "both",
    },
    "baidu": {
        "label": "百度千帆 (文心)",
        "key_field": "baidu_api_key",
        "base_url_field": "baidu_base_url",
        "default_base_url": "https://qianfan.baidubce.com/v2",
        "kind": "text",
    },
    "siliconflow": {
        "label": "硅基流动 (SiliconFlow)",
        "key_field": "siliconflow_api_key",
        "base_url_field": "siliconflow_base_url",
        "default_base_url": "https://api.siliconflow.cn/v1",
        "kind": "both",
    },
    "minimax": {
        "label": "MiniMax",
        "key_field": "minimax_api_key",
        "base_url_field": "minimax_base_url",
        "default_base_url": "https://api.minimax.chat/v1",
        "kind": "text",
    },
    "kling": {
        "label": "可灵 AI (Kling)",
        "key_field": "kling_api_key",
        "base_url_field": "kling_base_url",
        "default_base_url": "https://api.klingai.com",
        "kind": "video",
    },
    "dreamina": {
        "label": "即梦 Dreamina",
        "key_field": "dreamina_api_key",
        "base_url_field": "dreamina_base_url",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_field": "dreamina_model",
        "default_model": "doubao-seedance-2-0-mini-260615",
        "kind": "video",
    },
    "baidu_video": {
        "label": "百度文心一格/千帆视频",
        "key_field": "baidu_api_key",
        "base_url_field": "baidu_video_base_url",
        "default_base_url": "https://qianfan.baidubce.com/v2",
        "kind": "video",
    },
    "tencent_vod_video": {
        "label": "腾讯 VOD AIGC 视频",
        "key_field": "tencent_vod_secret_id",
        "secret_key_field": "tencent_vod_secret_key",
        "sub_app_id_field": "tencent_vod_sub_app_id",
        "base_url_field": None,
        "default_base_url": "",
        "model_field": "tencent_vod_model",
        "default_model": "Hailuo|H3",
        "kind": "video",
    },
    "openai": {
        "label": "OpenAI",
        "key_field": "openai_api_key",
        "base_url_field": "openai_base_url",
        "default_base_url": "https://api.openai.com/v1",
        "kind": "both",
    },
    "deepseek": {
        "label": "DeepSeek",
        "key_field": "deepseek_api_key",
        "base_url_field": "deepseek_base_url",
        "default_base_url": "https://api.deepseek.com/v1",
        "kind": "text",
    },
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "key_field": "moonshot_api_key",
        "base_url_field": "moonshot_base_url",
        "default_base_url": "https://api.moonshot.cn/v1",
        "kind": "text",
    },
    "ollama": {
        "label": "Ollama (本地)",
        "key_field": None,
        "base_url_field": "ollama_base_url",
        "default_base_url": "http://127.0.0.1:11434",
        "kind": "text",
    },
}


class AiProviderConfigService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.config_path = BACKEND_DIR / "data" / "ai_provider_config.json"
        self.custom_path = BACKEND_DIR / "data" / "ai_custom_providers.json"

    def _load_raw(self) -> dict[str, str]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_raw(self, data: dict[str, str]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_custom(self) -> list[dict[str, Any]]:
        if not self.custom_path.exists():
            return []
        try:
            data = json.loads(self.custom_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _save_custom(self, items: list[dict[str, Any]]) -> None:
        self.custom_path.parent.mkdir(parents=True, exist_ok=True)
        self.custom_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _custom_key_field(provider_id: str) -> str:
        return f"custom_{provider_id}_api_key"

    def get_field_value(self, field: str) -> str:
        if not field:
            return ""
        env_val = getattr(self.settings, field, "") or ""
        raw = self._load_raw()
        stored = raw.get(field, "")
        if not stored:
            return env_val
        try:
            return decrypt_text(stored, self.settings.cookie_encryption_key)
        except Exception:
            return env_val

    def _build_builtin_item(self, provider_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        key_field = spec.get("key_field")
        base_field = spec.get("base_url_field")
        model_field = spec.get("model_field")
        api_key = self.get_field_value(key_field) if key_field else ""
        base_url = self.get_field_value(base_field) if base_field else spec.get("default_base_url", "")
        if not base_url and base_field:
            base_url = getattr(self.settings, base_field, spec.get("default_base_url", ""))
        model = self.get_field_value(model_field) if model_field else spec.get("default_model", "")
        if not model and model_field:
            model = getattr(self.settings, model_field, spec.get("default_model", ""))
        raw = self._load_raw()
        return {
            "provider": provider_id,
            "label": spec["label"],
            "kind": spec["kind"],
            "key_field": key_field,
            "secret_key_field": secret_key_field,
            "sub_app_id_field": sub_app_id_field,
            "base_url_field": base_field,
            "model_field": model_field,
            "default_base_url": spec.get("default_base_url", ""),
            "default_model": spec.get("default_model", ""),
            "image_base_url_field": spec.get("image_base_url_field"),
            "default_image_base_url": spec.get("default_image_base_url", ""),
            "configured": bool(api_key) if key_field else bool(base_url),
            "api_key_masked": self._mask_key(api_key),
            "base_url": base_url or spec.get("default_base_url", ""),
            "model": model or spec.get("default_model", ""),
            "source": "runtime" if (key_field and raw.get(key_field)) else "env",
            "custom": False,
        }

    def _build_custom_item(self, item: dict[str, Any]) -> dict[str, Any]:
        provider_id = item["provider"]
        key_field = self._custom_key_field(provider_id)
        api_key = self.get_field_value(key_field)
        base_url = item.get("base_url") or ""
        raw = self._load_raw()
        return {
            "provider": provider_id,
            "label": item.get("label") or provider_id,
            "kind": item.get("kind") or "text",
            "key_field": key_field,
            "base_url_field": None,
            "default_base_url": base_url,
            "text_models": item.get("text_models") or [],
            "image_models": item.get("image_models") or [],
            "configured": bool(api_key),
            "api_key_masked": self._mask_key(api_key),
            "base_url": base_url,
            "source": "runtime" if raw.get(key_field) else "env",
            "custom": True,
        }

    def list_providers(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for provider_id, spec in PROVIDER_FIELDS.items():
            items.append(self._build_builtin_item(provider_id, spec))
        for custom in self._load_custom():
            items.append(self._build_custom_item(custom))
        return items

    def get_custom_provider(self, provider: str) -> dict[str, Any] | None:
        for item in self._load_custom():
            if item.get("provider") == provider:
                return item
        return None

    def list_custom_providers(self) -> list[dict[str, Any]]:
        return self._load_custom()

    def save_provider_config(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        secret_key: str | None = None,
        sub_app_id: str | None = None,
        clear_key: bool = False,
    ) -> dict[str, Any]:
        custom = self.get_custom_provider(provider)
        if custom:
            return self._save_custom_provider_config(
                provider,
                api_key=api_key,
                base_url=base_url,
                model=model,
                clear_key=clear_key,
            )

        spec = PROVIDER_FIELDS.get(provider)
        if not spec:
            raise ValueError(f"不支持的厂商: {provider}")

        raw = self._load_raw()
        key_field = spec.get("key_field")
        base_field = spec.get("base_url_field")
        model_field = spec.get("model_field")
        secret_key_field = spec.get("secret_key_field")
        sub_app_id_field = spec.get("sub_app_id_field")

        if clear_key and key_field:
            raw.pop(key_field, None)
        elif api_key is not None and key_field:
            if api_key.strip():
                raw[key_field] = encrypt_text(api_key.strip(), self.settings.cookie_encryption_key)
            else:
                raw.pop(key_field, None)

        if secret_key is not None and secret_key_field:
            if secret_key.strip():
                raw[secret_key_field] = encrypt_text(secret_key.strip(), self.settings.cookie_encryption_key)
            else:
                raw.pop(secret_key_field, None)

        if sub_app_id is not None and sub_app_id_field:
            if sub_app_id.strip():
                raw[sub_app_id_field] = sub_app_id.strip()
            else:
                raw.pop(sub_app_id_field, None)

        if base_url is not None and base_field:
            if base_url.strip():
                raw[base_field] = base_url.strip()
            else:
                raw.pop(base_field, None)

        if model is not None and model_field:
            if model.strip():
                raw[model_field] = model.strip()
            else:
                raw.pop(model_field, None)

        self._save_raw(raw)
        return next(item for item in self.list_providers() if item["provider"] == provider)

    def _save_custom_provider_config(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        clear_key: bool = False,
    ) -> dict[str, Any]:
        custom = self.get_custom_provider(provider)
        if not custom:
            raise ValueError(f"不支持的厂商: {provider}")

        raw = self._load_raw()
        key_field = self._custom_key_field(provider)

        if clear_key:
            raw.pop(key_field, None)
        elif api_key is not None:
            if api_key.strip():
                raw[key_field] = encrypt_text(api_key.strip(), self.settings.cookie_encryption_key)
            else:
                raw.pop(key_field, None)

        if base_url is not None and base_url.strip():
            custom["base_url"] = base_url.strip()
            items = self._load_custom()
            for idx, item in enumerate(items):
                if item.get("provider") == provider:
                    items[idx] = custom
                    break
            self._save_custom(items)

        self._save_raw(raw)
        return next(item for item in self.list_providers() if item["provider"] == provider)

    @staticmethod
    def _normalize_provider_id(label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        if not slug:
            slug = "custom"
        return f"custom_{slug}_{uuid.uuid4().hex[:6]}"

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
        label = label.strip()
        base_url = base_url.strip()
        if not label:
            raise ValueError("厂商名称不能为空")
        if not base_url:
            raise ValueError("Base URL 不能为空")
        if kind not in {"text", "image", "both"}:
            raise ValueError("类型必须是 text / image / both")

        provider_id = self._normalize_provider_id(label)
        item = {
            "provider": provider_id,
            "label": label,
            "kind": kind,
            "base_url": base_url,
            "text_models": [m.strip() for m in (text_models or []) if m.strip()],
            "image_models": [m.strip() for m in (image_models or []) if m.strip()],
        }
        items = self._load_custom()
        items.append(item)
        self._save_custom(items)

        if api_key and api_key.strip():
            self.save_provider_config(provider_id, api_key=api_key.strip())

        return next(row for row in self.list_providers() if row["provider"] == provider_id)

    def delete_custom_provider(self, provider: str) -> None:
        items = self._load_custom()
        next_items = [item for item in items if item.get("provider") != provider]
        if len(next_items) == len(items):
            raise ValueError(f"自定义厂商不存在: {provider}")
        self._save_custom(next_items)
        raw = self._load_raw()
        raw.pop(self._custom_key_field(provider), None)
        self._save_raw(raw)

    @staticmethod
    def _mask_key(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}****{value[-4:]}"
