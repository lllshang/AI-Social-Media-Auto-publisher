"""
数字人 / 仿真人视频字幕烧录工具

把「已知的口播文本 + 音频时长」自动生成 ASS 字幕，并用 ffmpeg 把字幕
**硬烧录**（hardcode）进 mp4，使下载/发布的视频自带字幕。

设计要点：
1. 文本已知（口播文案），无需 ASR，按句切分后按音频时长均分时间戳；
2. 字体使用开源中文字体 **Noto Sans CJK SC / 思源黑体**（SIL Open Font License，
   商用免费、无侵权风险）；优先用系统已装字体路径，缺失时可经 env 指定；
3. 默认样式：白字黑描边半透明底，居中底部，兼容抖音/视频号安全区；
4. **按视频实际尺寸自适应**：烧录前用 ffprobe 取视频宽高，将 PlayResX/PlayResY
   设置为视频实际尺寸，避免字号在非 1080x1920 视频上被缩得极小看不见；
5. 保留原视频，新生成 `*_sub.mp4` 烧字幕版本，不覆盖原文件。
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Optional


# ===== 字体探测 =====
# 优先顺序：环境变量指定 > 常见系统路径（Debian/Ubuntu Noto、CentOS/腾讯云等）
_FONT_CANDIDATES = [
    os.getenv("AI_PUBLISH_SUBTITLE_FONT"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def resolve_font_path() -> Optional[str]:
    """探测可用的开源中文字体文件绝对路径。"""
    for p in _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    # 兜底：用 fc-match 询问系统「Noto Sans CJK SC」落在哪
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", "Noto Sans CJK SC"],
            capture_output=True, text=True, timeout=10,
        )
        fp = out.stdout.strip()
        if fp and os.path.exists(fp):
            return fp
    except Exception:
        pass
    return None


def _split_sentences(text: str) -> list[str]:
    """按中文标点切句；长句若过长也按字数截断，避免单条字幕太长。

    切分优先级：。！？…；？  >  ，、  >  空格/换行。
    最终每条尽量 ≤ 40 字（移动端单行可读），超长强行按 ~38 字断行。
    """
    if not text or not text.strip():
        return []

    # 先按强标点切
    raw = re.split(r"(?<=[。！？!?…；;])", text)
    sentences: list[str] = []
    for s in raw:
        s = s.strip()
        if not s:
            continue
        # 长句按 ~38 字再断
        if len(s) > 38:
            for i in range(0, len(s), 38):
                chunk = s[i:i + 38].strip()
                if chunk:
                    sentences.append(chunk)
        else:
            sentences.append(s)
    return sentences


def _format_ts(seconds: float) -> str:
    """SRT 时间格式 HH:MM:SS,mmm。"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(text: str, total_duration: float) -> str:
    """把口播文本按句切分，按音频时长均分时间戳，生成 SRT 字符串。"""
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    if total_duration <= 0:
        # 兜底：每句 3 秒
        total_duration = len(sentences) * 3.0

    n = len(sentences)
    per = total_duration / n
    lines: list[str] = []
    for idx, sent in enumerate(sentences):
        start = idx * per
        end = (idx + 1) * per
        lines.append(str(idx + 1))
        lines.append(f"{_format_ts(start)} --> {_format_ts(end)}")
        lines.append(sent)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _probe_video_size(video_path: str) -> tuple[int, int]:
    """用 ffprobe 取视频宽高；失败回退 1080x1920。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", video_path],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            w, h = out.stdout.strip().split("x")
            return int(w), int(h)
    except Exception:
        pass
    return 1080, 1920


def build_ass(
    text: str,
    total_duration: float,
    fontsize: int = 28,
    *,
    video_width: int = 1080,
    video_height: int = 1920,
) -> str:
    """生成 ASS 字幕（含样式块），样式写在文件里避免 filtergraph 解析 `&H` 颜色出错。

    默认样式：思源黑体/Noto Sans CJK SC，白字黑描边半透明底，居中底部。

    - video_width / video_height: 视频实际宽高，决定 PlayResX/PlayResY 与
      字号自适应基准（避免非 1080x1920 视频上字号被缩得看不见）。
    """
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    if total_duration <= 0:
        total_duration = len(sentences) * 3.0

    # ===== 关键:按视频高度自适应字号与画布 =====
    # libass 以 PlayResX/PlayResY 为坐标系计算字号/MarginV。
    # 注意：之前的版本用 play_h/1920 缩放，导致 1104 高度视频上 56 号字被
    # 缩到 32，肉眼看跟"没放大"一样。这次直接用传入的 fontsize 作为
    # 实际字号（不缩放），并固定 MarginV 为 12% 屏幕高（最小 80px）。
    play_w = int(video_width)
    play_h = int(video_height)
    # 用户期望"放大一倍"：调用方传 56，这里直接用 56 作为 libass 字号
    actual_fontsize = max(32, int(fontsize))
    # 距离底部占屏幕高 12%（用户要求"两倍"，原 6%）。小屏也保证至少 80px
    margin_v = max(80, round(play_h * 0.12))
    # 描边宽度加粗（按字号 1/8），避免 re-encode 后字边缘虚化
    outline_w = max(3, round(actual_fontsize * 0.12))
    # 控制行间距与字符缩放：强制宽度 100、高度 100（libass 默认），
    # Spacing=0 让字符紧贴，避免竖向拉长错觉。
    spacing = 0
    scale_x = 100
    scale_y = 100

    n = len(sentences)
    per = total_duration / n

    font_name = "Noto Sans CJK SC"
    # ASS 颜色格式：&HAABBGGRR（自右向左 R, G, B, A）
    # - PrimaryColour = &H00FFFFFF    白
    # - SecondaryColour = &H00000000  黑（karaoke 用不到，但规格要写）
    # - OutlineColour = &H00000000    黑（决定描边颜色）
    # - BackColour = &H80000000       半透明黑（BorderStyle=1 时用不到）
    # BorderStyle=1 表示"实心描边 + 阴影"风格（最常见、最稳的高对比白字黑边）。
    style_line = (
        f"Style: Default,{font_name},{actual_fontsize},"
        f"&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,{spacing},0,1,{outline_w},2,"
        f"40,20,{margin_v},2"
    )
    events: list[str] = ["[Events]", "Format: Layer, Start, End, Style, Text"]
    for idx, sent in enumerate(sentences):
        start = _format_ts(idx * per).replace(",", ".")
        end = _format_ts((idx + 1) * per).replace(",", ".")
        events.append(f"Dialogue: 0,{start},{end},Default,{sent}")

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_w}",
        f"PlayResY: {play_h}",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
        "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,"
        "BorderStyle,Outline,Shadow,MarginL,MarginR,MarginV,Alignment",
        style_line,
        "",
    ]
    return "\n".join(header + events) + "\n"


def burn_subtitles(
    video_path: str,
    text: str,
    total_duration: float,
    *,
    output_path: Optional[str] = None,
    fontsize: int = 28,
) -> Optional[str]:
    """为视频烧录字幕，返回烧字幕后的视频本地路径；失败返回 None。

    - video_path: 原始 mp4 本地路径
    - text: 口播文本（已知）
    - total_duration: 音频/视频时长（秒）
    - output_path: 输出路径；默认在同级目录生成 ``*_sub.mp4``
    """
    if not video_path or not os.path.exists(video_path):
        return None

    # 1. 取视频实际尺寸 → 自适应 PlayResX/PlayResY 与字号
    w, h = _probe_video_size(video_path)
    ass = build_ass(
        text, total_duration, fontsize=fontsize,
        video_width=w, video_height=h,
    )
    if not ass:
        return None

    font_path = resolve_font_path()
    if not font_path:
        # 无中文字体则放弃烧录（宁可没有字幕也不出乱码）
        return None

    # 2. 写 ASS 到临时文件
    tmp_ass = tempfile.NamedTemporaryFile(
        "w", suffix=".ass", delete=False, encoding="utf-8"
    )
    tmp_ass.write(ass)
    tmp_ass.close()

    if not output_path:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_sub{ext or '.mp4'}"

    # 3. 烧字幕。libass 通过 .ass 内 Fontname + fontconfig 自动匹配中文字体。
    #   注意：ass 文件已显式指定 FontName=Noto Sans CJK SC，且 Style 字段里颜色已正确设置。
    #   如果服务器还装有 Noto Serif CJK，需要在 ffmpeg filter 里强制 fontsdir 让 libass
    #   优先匹配 Sans 版本（避免 fallback 到衬线字）。
    noto_dir = "/usr/share/fonts/opentype/noto"
    sub_filter = (
        f"subtitles='{tmp_ass.name}':fontsdir='{noto_dir}'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        output_path,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
        if proc.returncode != 0:
            print(f"[subtitle] ffmpeg 失败: {proc.stderr[-500:]}")
            return None
        if not os.path.exists(output_path):
            return None
        print(f"[字幕] 烧录成功: {output_path} (video={w}x{h})")
        return output_path
    except Exception as e:
        print(f"[subtitle] 异常: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_ass.name)
        except Exception:
            pass