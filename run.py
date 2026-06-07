"""B-Roll 生成系統 — 一鍵入口。

用法：
  python run.py                 # 全跑：劇情 → 出圖 → 配音 → 合成影片
  python run.py --from images   # 從某階段續跑（手改 storyboard.json 後常用）
  python run.py --only video    # 只重跑單一階段（換音樂/調轉場時用）

階段名稱：story / images / tts / video
"""
from __future__ import annotations

import argparse
import sys

# Windows 終端機預設可能是 cp950，輸出中文/emoji 會報錯，強制改成 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src import step1_story, step2_images, step3_tts, step4_video

STAGES = ["story", "images", "tts", "video"]
RUNNERS = {
    "story": step1_story.run,
    "images": step2_images.run,
    "tts": step3_tts.run,
    "video": step4_video.run,
}


def main() -> None:
    ap = argparse.ArgumentParser(description="B-Roll 生成系統")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--from", dest="from_stage", choices=STAGES,
                   help="從此階段開始一路跑到最後")
    g.add_argument("--only", dest="only_stage", choices=STAGES,
                   help="只執行此單一階段")
    args = ap.parse_args()

    if args.only_stage:
        todo = [args.only_stage]
    elif args.from_stage:
        todo = STAGES[STAGES.index(args.from_stage):]
    else:
        todo = STAGES

    print(f"=== 將執行階段：{' → '.join(todo)} ===")
    for stage in todo:
        RUNNERS[stage]()
    print("\n✅ 全部完成！影片在 output/broll.mp4")


if __name__ == "__main__":
    main()
