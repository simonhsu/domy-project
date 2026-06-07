"""產生字幕（ASS 格式，供 ffmpeg 燒錄）。

字幕文字取自每個鏡頭的旁白，依旁白語音長度自動分配時間。
"""
from __future__ import annotations

import re

# 用來斷句的標點（會在這些符號後切segment）
_PUNCT = "，。！？；：、…,!?;:"


def _fmt_time(sec: float) -> str:
    """秒 → ASS 時間格式 H:MM:SS.cc"""
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _split_narration(text: str) -> list[str]:
    """依標點把旁白切成較短的字幕段。"""
    text = text.strip()
    segs, buf = [], ""
    for ch in text:
        buf += ch
        if ch in _PUNCT:
            seg = buf.strip().strip(_PUNCT + " ")
            if seg:
                segs.append(seg)
            buf = ""
    last = buf.strip().strip(_PUNCT + " ")
    if last:
        segs.append(last)
    return segs or [text]


def _wrap(text: str, max_chars: int) -> str:
    """太長的段落每 max_chars 字插入 ASS 換行 \\N。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    return "\\N".join(lines)


def build_events(scene_text: str, start: float, end: float,
                 max_chars: int, split: bool) -> list[tuple[float, float, str]]:
    """把一個鏡頭的旁白切成 (start, end, text) 事件，依字數比例分配時間。"""
    window = max(end - start, 0.1)
    if not split:
        return [(start, end, _wrap(scene_text, max_chars))]
    segs = _split_narration(scene_text)
    total = sum(len(s) for s in segs) or 1
    events, t = [], start
    for i, seg in enumerate(segs):
        dur = window * (len(seg) / total)
        seg_end = end if i == len(segs) - 1 else t + dur
        events.append((t, seg_end, _wrap(seg, max_chars)))
        t = seg_end
    return events


def write_ass(path, width: int, height: int, events: list[tuple[float, float, str]],
              cfg: dict) -> None:
    """寫出 ASS 字幕檔。"""
    font = cfg.get("font", "Microsoft JhengHei")
    size = cfg.get("font_size", 54)
    primary = cfg.get("primary_color", "&H00FFFFFF")   # 白字 (ASS 為 BGR)
    outline_c = cfg.get("outline_color", "&H00000000")  # 黑邊
    outline = cfg.get("outline", 3)
    shadow = cfg.get("shadow", 0)
    margin_v = cfg.get("margin_v", 180)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,{outline_c},&H64000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for start, end, text in events:
        text = text.replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}\n"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
