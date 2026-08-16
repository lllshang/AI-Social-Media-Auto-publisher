from pathlib import Path

import yaml

_DEFAULT_TEXT = "请为{platform}平台围绕主题「{topic}」生成标题、正文、标签和封面文案，以JSON返回。"
_DEFAULT_IMAGE = "为{platform}生成{ratio}比例封面图，主题：{topic}，风格：{style_label}"
_DEFAULT_IMAGE_EN = "Cover image for {platform}, ratio {ratio}, topic: {topic}, style: {style_en}"
_DEFAULT_VIDEO = "生成一段{duration}秒的短视频，主题：{topic}。要求：画面流畅、内容吸引人、适合{platform}平台。"
_DEFAULT_VIDEO_EN = "Generate a {duration}-second short video about: {topic}. Requirements: smooth motion, engaging content, suitable for {platform}."
_DEFAULT_NEGATIVE = "blurry, low quality, watermark, logo, text garbled, deformed, ugly"

IMAGE_STYLE_ALIASES: dict[str, str] = {
    "fresh": "default",
    "natural": "default",
    "clean": "minimal",
    "bold": "vivid",
}

IMAGE_STYLES: dict[str, dict[str, str]] = {
    "default": {"zh": "清新自然", "en": "fresh and natural"},
    "minimal": {"zh": "极简留白", "en": "minimal with clean whitespace"},
    "vivid": {"zh": "鲜艳醒目", "en": "vivid and eye-catching"},
    "elegant": {"zh": "典雅精致", "en": "elegant and refined"},
    "retro": {"zh": "复古文艺", "en": "retro and artistic"},
}

IMAGE_RATIO_HINTS: dict[str, str] = {
    "1:1": "正方形构图，主体居中，适合头像式封面",
    "3:4": "竖版 3:4，适合小红书图文封面",
    "4:5": "竖版 4:5，适合信息流单图展示",
    "4:3": "横版 4:3，适合横向展示",
    "9:16": "竖屏全屏，适合短视频封面",
    "16:9": "横屏宽画幅，适合横版视频封面",
}


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


def _load_yaml_template(template_name: str | None) -> dict:
    if not template_name:
        return {}
    path = _prompts_dir() / template_name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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
        data = _load_yaml_template(template_name)
        return str(data.get("template", fallback))
    return fallback


def _style_labels(style: str) -> tuple[str, str]:
    style = IMAGE_STYLE_ALIASES.get(style, style)
    meta = IMAGE_STYLES.get(style, IMAGE_STYLES["default"])
    return meta["zh"], meta["en"]


def _format_template(
    template: str,
    *,
    platform: str,
    topic: str,
    ratio: str,
    style: str,
    content_type: str,
    brand_color: str | None = None,
    brand_hint: str | None = None,
) -> str:
    style_label, style_en = _style_labels(style)
    ratio_hint = IMAGE_RATIO_HINTS.get(ratio, ratio)
    return (
        template.replace("{platform}", platform)
        .replace("{topic}", topic)
        .replace("{ratio}", ratio)
        .replace("{ratio_hint}", ratio_hint)
        .replace("{style}", style)
        .replace("{style_label}", style_label)
        .replace("{style_en}", style_en)
        .replace("{content_type}", content_type)
        .replace("{brand_color}", brand_color or "未指定")
        .replace("{brand_hint}", brand_hint or "无")
    )


def build_prompt(
    kind: str,
    platform: str,
    topic: str,
    *,
    content_type: str = "note",
    ratio: str = "3:4",
    style: str = "default",
    cover_text: str | None = None,
    brand_color: str | None = None,
    brand_hint: str | None = None,
) -> tuple[str, str]:
    """Format platform template into a concrete prompt (zh only, backward compatible)."""
    details = build_prompt_details(
        kind,
        platform,
        topic,
        content_type=content_type,
        ratio=ratio,
        style=style,
        cover_text=cover_text,
        brand_color=brand_color,
        brand_hint=brand_hint,
    )
    return details["template_name"], details["prompt_zh"]


def build_prompt_details(
    kind: str,
    platform: str,
    topic: str,
    *,
    content_type: str = "note",
    ratio: str = "3:4",
    style: str = "default",
    cover_text: str | None = None,
    brand_color: str | None = None,
    brand_hint: str | None = None,
) -> dict[str, str | None]:
    """Build zh/en/negative prompts from templates (LLM-free, template fallback)."""
    template_name = resolve_prompt_template_name(kind, platform, content_type) or f"{platform}_{kind}.yaml"
    data = _load_yaml_template(resolve_prompt_template_name(kind, platform, content_type))

    prompt_topic = topic
    if kind == "image" and cover_text:
        prompt_topic = f"{topic}，封面文字：{cover_text}"

    zh_template = str(data.get("template", _DEFAULT_TEXT if kind == "text" else _DEFAULT_IMAGE))
    en_template = str(data.get("template_en", _DEFAULT_IMAGE_EN if kind == "image" else ""))
    negative = str(data.get("negative_prompt", _DEFAULT_NEGATIVE if kind == "image" else ""))

    prompt_zh = _format_template(
        zh_template,
        platform=platform,
        topic=prompt_topic,
        ratio=ratio,
        style=style,
        content_type=content_type,
        brand_color=brand_color,
        brand_hint=brand_hint,
    )
    prompt_en = (
        _format_template(
            en_template,
            platform=platform,
            topic=prompt_topic,
            ratio=ratio,
            style=style,
            content_type=content_type,
            brand_color=brand_color,
            brand_hint=brand_hint,
        )
        if en_template
        else None
    )
    negative_prompt = negative.strip() or None if kind == "image" else None

    return {
        "template_name": template_name,
        "prompt_zh": prompt_zh,
        "prompt_en": prompt_en,
        "negative_prompt": negative_prompt,
        "prompt": prompt_zh,
    }


def build_image_generation_prompt(data) -> tuple[str, str | None]:
    """Adapter helper: build final zh prompt + negative prompt for image generation."""
    details = build_prompt_details(
        "image",
        data.platform,
        data.topic,
        ratio=data.ratio,
        style=getattr(data, "style", "default") or "default",
        cover_text=getattr(data, "cover_text", None),
        brand_color=getattr(data, "brand_color", None),
        brand_hint=getattr(data, "brand_hint", None),
    )
    return details["prompt_zh"], details["negative_prompt"]


def build_video_generation_prompt(data) -> str:
    """Adapter helper: build final prompt for video generation."""
    template = load_prompt_template("video", data.platform, default=_DEFAULT_VIDEO)

    # 简化的模板格式化（仅支持基本变量）
    prompt = (
        template.replace("{platform}", data.platform)
        .replace("{topic}", data.topic)
        .replace("{duration}", str(data.duration))
        .replace("{style}", getattr(data, "style", "default"))
    )

    return prompt

