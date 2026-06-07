"""Step 1：把 input/brief.txt 的主題 → A-Roll 旁白 + 每段 N 張 B-Roll 分鏡。

- A-Roll：每個 scene 的 narration（旁白文字）
- B-Roll：每個 scene 配 broll.per_scene 張支援畫面，不同鏡位/角度
"""
from __future__ import annotations

import json

from google import genai
from google.genai import types

from . import config


def _schema(per_scene: int) -> dict:
    """storyboard JSON schema：每個 scene 含 N 個 b_rolls。"""
    b_roll_item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},                # 例：1a / 1b / 1c
            "shot_type": {"type": "string"},         # wide / medium / close-up / detail / over-shoulder / POV / cutaway
            "with_character": {"type": "boolean"},   # 這張是否要帶角色圖當參考
            "image_prompt": {"type": "string"},      # 英文出圖描述
        },
        "required": ["id", "shot_type", "with_character", "image_prompt"],
    }
    scene = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "summary": {"type": "string"},      # 中文場景說明
            "narration": {"type": "string"},    # 繁中旁白（A-Roll）
            "duration_sec": {"type": "number"}, # 該段預期秒數
            "b_rolls": {
                "type": "array",
                "minItems": per_scene,
                "maxItems": per_scene,
                "items": b_roll_item,
            },
        },
        "required": ["id", "summary", "narration", "duration_sec", "b_rolls"],
    }
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "logline": {"type": "string"},
            "scenes": {"type": "array", "items": scene},
        },
        "required": ["title", "logline", "scenes"],
    }


def _character_rule(strategy: str, per_scene: int) -> str:
    if strategy == "all":
        return f"所有 {per_scene} 張 B-Roll 的 with_character 都必須為 true（每張都要看到主角，但用不同鏡位）。"
    if strategy == "none":
        return f"所有 {per_scene} 張 B-Roll 的 with_character 都必須為 false（純環境/物件/隱喻/細節，不要出現主角）。"
    # mixed
    if per_scene == 1:
        return "with_character 自由選擇（true 或 false）。"
    half = per_scene // 2
    return (
        f"每個 scene 的 {per_scene} 張 B-Roll 中，恰好有 {half} 張 with_character=true（帶主角的鏡頭），"
        f"其餘 {per_scene - half} 張 with_character=false（不帶主角的環境/物件/隱喻/細節）。"
    )


def _build_prompt(brief: str, cfg: dict) -> str:
    n_scenes = cfg["scenes"]["count"]
    total = cfg["scenes"]["target_total_sec"]
    lang = cfg["language"]
    per = cfg["broll"]["per_scene"]
    sec_per = cfg["broll"]["sec_per_shot_target"]
    strat = cfg["broll"]["character_strategy"]
    char_rule = _character_rule(strat, per)
    scene_sec = round(per * sec_per, 1)

    return f"""你是一位專業的短影音導演與編劇，熟悉電影敘事中 A-Roll / B-Roll 的剪輯邏輯。
請依下列「主題」構思一支短影片的劇情，並依此架構：
- A-Roll = 每個 scene 的 narration（旁白）。
- B-Roll = 每個 scene 底下的 b_rolls 陣列，是用來「視覺化、補強、隱喻」該段旁白的多張支援畫面（不同鏡位/角度）。

主題 / 想法：
\"\"\"{brief}\"\"\"

整體規格：
- 共 {n_scenes} 個 scene（A-Roll 段落）；影片總長度約 {total} 秒。
- 每段 duration_sec ≈ {scene_sec} 秒（= {per} 張 B-Roll × {sec_per}s）。
- title、logline、每個 scene 的 summary 與 narration 請用「{lang}（繁體中文）」。

A-Roll（narration）要求：
- 該 scene 的旁白，1~2 句，口語、有畫面感、適合被朗讀。
- 段落之間要有敘事連貫（開場 → 鋪陳 → 高潮 → 收尾）。

B-Roll 要求（每個 scene 恰好 {per} 張）：
- 每張要用「不同鏡位」，從以下挑選並交替：wide（廣角全景）/ medium（中景）/ close-up（特寫）/ detail（細節極特寫）/ over-shoulder（過肩）/ POV（主觀視角）/ cutaway（插入畫面，例如物件、環境、隱喻）。
- 每張 image_prompt 用「英文」描述：場景、構圖、光線、情緒、相機角度、鏡頭距離；直向 9:16 構圖；不要包含任何文字/字幕/浮水印。
- 視覺上要呼應、補強同一段旁白的情境（B-Roll 不必字面化複述旁白，可以用環境、物件、手部動作、光影、隱喻去傳達情緒）。
- 角色策略：{char_rule}
- id 格式：scene 編號 + 小寫字母，例如 scene 1 的兩張就是 "1a"、"1b"；scene 5 的三張就是 "5a"、"5b"、"5c"。

只輸出 JSON，符合給定 schema。"""


def run() -> dict:
    cfg = config.load_config()
    config.ensure_dirs()

    if not config.BRIEF_FILE.exists() or not config.BRIEF_FILE.read_text(encoding="utf-8").strip():
        raise SystemExit(
            f"\n[錯誤] 請先在 {config.BRIEF_FILE} 填入你的主題/想法（純文字）。\n"
        )
    brief = config.BRIEF_FILE.read_text(encoding="utf-8").strip()
    per = int(cfg["broll"]["per_scene"])

    client = genai.Client(api_key=config.get_api_key())
    print(f"[Step1] 用 {cfg['models']['text']} 生成 A-Roll(旁白) 與 B-Roll(每段 {per} 張) 分鏡 …")

    resp = client.models.generate_content(
        model=cfg["models"]["text"],
        contents=_build_prompt(brief, cfg),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_schema(per),
            temperature=0.9,
        ),
    )

    data = json.loads(resp.text)
    config.STORYBOARD_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    n_scenes = len(data.get("scenes", []))
    total_imgs = sum(len(s.get("b_rolls", [])) for s in data["scenes"])
    print(f"[Step1] 完成 → {config.STORYBOARD_FILE}")
    print(f"        片名：{data.get('title')}（{n_scenes} 段旁白，共 {total_imgs} 張 B-Roll）")
    return data


if __name__ == "__main__":
    run()
