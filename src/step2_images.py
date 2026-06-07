"""Step 2：依 storyboard.json 的 b_rolls + 角色圖 → 場景圖 (output/images)。

每個 scene 會出 N 張圖（N = broll.per_scene），檔名格式：
  scene_01a.png, scene_01b.png, ...
"""
from __future__ import annotations

import json
import mimetypes

from google import genai
from google.genai import types

from . import config

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _load_character_images() -> list[types.Part]:
    parts: list[types.Part] = []
    if not config.CHARACTERS_DIR.exists():
        return parts
    for p in sorted(config.CHARACTERS_DIR.iterdir()):
        if p.suffix.lower() in _IMG_EXTS:
            mime = mimetypes.guess_type(str(p))[0] or "image/png"
            parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
    return parts


def _extract_image_bytes(resp) -> bytes | None:
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return part.inline_data.data
    return None


def _apply_strategy(with_character: bool, strategy: str) -> bool:
    if strategy == "all":
        return True
    if strategy == "none":
        return False
    return bool(with_character)


def run() -> None:
    cfg = config.load_config()
    config.ensure_dirs()

    if not config.STORYBOARD_FILE.exists():
        raise SystemExit("[錯誤] 找不到 storyboard.json，請先執行 step1（或 python run.py）。")
    storyboard = json.loads(config.STORYBOARD_FILE.read_text(encoding="utf-8"))
    scenes = storyboard["scenes"]

    # 防呆：偵測舊 schema
    if scenes and "b_rolls" not in scenes[0]:
        raise SystemExit(
            "[錯誤] storyboard.json 是舊版格式（缺少 b_rolls）。請重跑 `python run.py --only story` 重新生成。"
        )

    char_parts = _load_character_images()
    if not char_parts:
        print(f"[Step2] 警告：{config.CHARACTERS_DIR} 沒有角色圖，將忽略 with_character。")

    client = genai.Client(api_key=config.get_api_key())
    style = cfg["image"]["style_suffix"]
    ar = cfg["aspect_ratio"]
    model = cfg["models"]["image"]
    strategy = cfg["broll"]["character_strategy"]

    total = sum(len(s["b_rolls"]) for s in scenes)
    done = 0
    for scene in scenes:
        sid = scene["id"]
        for shot in scene["b_rolls"]:
            done += 1
            shot_id = shot["id"]                      # 例：1a
            out = config.IMAGES_DIR / f"scene_{sid:02d}{shot_id[-1]}.png"
            use_char = _apply_strategy(shot.get("with_character", False), strategy) and bool(char_parts)
            tag = "（帶角色）" if use_char else "（不帶角色）"
            extra = " Keep the same character appearance, outfit and art style as the reference image(s)." if use_char else ""
            prompt = f"{shot['image_prompt']}. {style}.{extra}"
            contents = [*char_parts, prompt] if use_char else [prompt]
            print(f"[Step2] ({done}/{total}) 出圖 scene {sid:02d}{shot_id[-1]} [{shot.get('shot_type','?')}] {tag}…")
            resp = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=ar),
                ),
            )
            data = _extract_image_bytes(resp)
            if not data:
                raise SystemExit(f"[錯誤] {out.name} 沒有取得圖片，請重試或調整 image_prompt。")
            out.write_bytes(data)
            print(f"        → {out}")

    print(f"[Step2] 完成，共 {total} 張圖於 {config.IMAGES_DIR}")


if __name__ == "__main__":
    run()
