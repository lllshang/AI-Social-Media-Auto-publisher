from pathlib import Path

import yaml

_DEFAULT_TEXT = "请为{platform}平台围绕主题「{topic}」生成标题、正文、标签和封面文案，以JSON返回。"
_DEFAULT_IMAGE = "为{platform}生成{ratio}比例封面图，主题：{topic}，风格：{style}"


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "prompts"


def resolve_prompt_template_name(
    kind: str,
    platform: str,
    content_type: str | None = None,
) -> str | None:
    candidates: list[str] = []
    if content_type and content_type != "note":
        candidates.append(f"{platform}_{content_type}_{kind}.yaml")
    candidates.extend((f"{platform}_{kind}.yaml", f"xhs_{kind}.yaml"))
    for name in candidates:
        if (_prompts_dir() / name).exists():
            return name
    return None


def load_prompt_template(
    kind: str,
    platform: str,
    default: str | None = None,
    content_type: str | None = None,
) -> str:
    """Load YAML prompt template by platform/content_type with xhs fallback."""
    fallback = default or (_DEFAULT_TEXT if kind == "text" else _DEFAULT_IMAGE)
    template_name = resolve_prompt_template_name(kind, platform, content_type)
    if template_name:
        path = _prompts_dir() / template_name
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return str(data.get("template", fallback))
    return fallback


def build_prompt(
    kind: str,
    platform: str,
    topic: str,
    *,
    content_type: str = "note",
    ratio: str = "3:4",
    style: str = "default",
    cover_text: str | None = None,
) -> tuple[str, str]:
    """Format platform template into a concrete prompt."""
    template_name = resolve_prompt_template_name(kind, platform, content_type) or f"{platform}_{kind}.yaml"
    template = load_prompt_template(kind, platform, content_type=content_type)
    prompt_topic = topic
    if kind == "image" and cover_text:
        prompt_topic = f"{topic}，封面文字：{cover_text}"
    prompt = (
        template.replace("{platform}", platform)
        .replace("{topic}", prompt_topic)
        .replace("{ratio}", ratio)
        .replace("{style}", style)
        .replace("{content_type}", content_type)
    )
    return template_name, prompt
