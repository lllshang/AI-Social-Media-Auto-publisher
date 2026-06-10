from pathlib import Path

import yaml

_DEFAULT_TEXT = "请为{platform}平台围绕主题「{topic}」生成标题、正文、标签和封面文案，以JSON返回。"
_DEFAULT_IMAGE = "为{platform}生成{ratio}比例封面图，主题：{topic}，风格：{style}"


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "prompts"


def load_prompt_template(
    kind: str,
    platform: str,
    default: str | None = None,
    content_type: str | None = None,
) -> str:
    """Load YAML prompt template by platform/content_type with xhs fallback."""
    fallback = default or (_DEFAULT_TEXT if kind == "text" else _DEFAULT_IMAGE)
    candidates: list[str] = []
    if content_type and content_type != "note":
        candidates.append(f"{platform}_{content_type}_{kind}.yaml")
    candidates.extend((f"{platform}_{kind}.yaml", f"xhs_{kind}.yaml"))
    for name in candidates:
        path = _prompts_dir() / name
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return str(data.get("template", fallback))
    return fallback
