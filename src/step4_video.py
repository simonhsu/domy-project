"""Step 4：圖片 + 旁白 + 背景音樂 + 字幕 → 影片 (output/broll.mp4)。

每個 scene 可以有多張 B-Roll（檔名 scene_XXa.png / XXb.png / …）：
- scene 內：用「微轉場 (broll.micro_transition_sec)」串接所有 B-Roll，每張 ≈ 旁白音長 / N。
- scene 之間：用較大的轉場 (video.transition_sec)。
- 音訊 / 字幕仍以 scene 為單位（旁白音檔仍是每段一個）。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

from . import config, subtitles


def _find_ffmpeg(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if base.exists():
        for exe in base.glob(f"Gyan.FFmpeg*/**/bin/{name}.exe"):
            return str(exe)
    raise SystemExit(
        f"[錯誤] 找不到 {name}。請先安裝：winget install Gyan.FFmpeg，重新開啟終端機讓 PATH 生效。"
    )


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _scene_brolls(sid: int) -> list[Path]:
    """找出 scene 的所有 B-Roll 圖檔，依字母排序（a, b, c…）。"""
    pat = re.compile(rf"^scene_{sid:02d}([a-z])\.png$")
    found = []
    for p in sorted(config.IMAGES_DIR.glob(f"scene_{sid:02d}*.png")):
        m = pat.match(p.name)
        if m:
            found.append((m.group(1), p))
    # 回退相容：舊命名 scene_01.png
    if not found:
        old = config.IMAGES_DIR / f"scene_{sid:02d}.png"
        if old.exists():
            found.append(("a", old))
    return [p for _, p in sorted(found, key=lambda x: x[0])]


def run() -> None:
    cfg = config.load_config()
    config.ensure_dirs()
    ffmpeg = _find_ffmpeg("ffmpeg")

    scenes = json.loads(config.STORYBOARD_FILE.read_text(encoding="utf-8"))["scenes"]
    W = cfg["resolution"]["width"]
    H = cfg["resolution"]["height"]
    fps = cfg["video"]["fps"]
    zoom = float(cfg["video"]["kenburns_zoom"])
    D = float(cfg["video"]["transition_sec"])           # 場景之間（大）
    pad = float(cfg["video"]["pad_sec"])
    Dm = float(cfg["broll"]["micro_transition_sec"])    # 場景內 B-Roll 之間（小）

    # 收集每個 scene
    scene_items = []
    for scene in scenes:
        sid = scene["id"]
        imgs = _scene_brolls(sid)
        if not imgs:
            raise SystemExit(f"[錯誤] 缺少圖片 scene_{sid:02d}*.png，請先執行 step2。")
        wav = config.AUDIO_DIR / f"scene_{sid:02d}.wav"
        if wav.exists():
            narr_dur = _wav_duration(wav)
            scene_dur = narr_dur + pad
        else:
            wav = None
            narr_dur = 0.0
            scene_dur = float(scene.get("duration_sec", 5))
        # scene 內每張 B-Roll 的秒數（含 micro xfade 的 overlap），平均分配
        n = len(imgs)
        if n == 1:
            per_dur = scene_dur
        else:
            # 多張時：每張 = scene_dur/n + Dm（補回 xfade overlap），最小值保證 > Dm
            per_dur = max(scene_dur / n + Dm, Dm + 0.6)
            scene_dur = per_dur * n - Dm * (n - 1)  # 反推 scene 真正長度
        scene_items.append({
            "sid": sid, "imgs": imgs, "wav": wav,
            "narration": (scene.get("narration") or "").strip(),
            "narration_dur": narr_dur,
            "scene_dur": scene_dur, "per_dur": per_dur,
        })

    # ---- 組 ffmpeg 輸入 ----
    inputs: list[str] = []
    # 圖片輸入（先放全部圖片）
    img_idx_map: dict[Path, int] = {}
    for s in scene_items:
        for img in s["imgs"]:
            img_idx_map[img] = len(inputs) // 2  # 每張圖 2 個 arg
            inputs += ["-loop", "1", "-t", f"{s['per_dur']:.3f}", "-i", str(img)]
    # 算正確 input index：上面的計法不對(因為每張圖前有 -loop 1 -t T，所以是每張 4 args)
    # 重做：精確紀錄 input 序號
    inputs = []
    img_idx_map = {}
    cur = 0
    for s in scene_items:
        for img in s["imgs"]:
            inputs += ["-loop", "1", "-t", f"{s['per_dur']:.3f}", "-i", str(img)]
            img_idx_map[img] = cur
            cur += 1

    # 音訊輸入
    need_silence = any(s["wav"] is None for s in scene_items)
    silence_idx = None
    if need_silence:
        silence_idx = cur
        inputs += ["-f", "lavfi", "-t", "1", "-i", "anullsrc=r=44100:cl=mono"]
        cur += 1
    audio_map_idx = []
    for s in scene_items:
        if s["wav"] is not None:
            inputs += ["-i", str(s["wav"])]
            audio_map_idx.append(cur)
            cur += 1
        else:
            audio_map_idx.append(silence_idx)

    # ---- filter_complex ----
    fc = []
    big_w, big_h = W * 2, H * 2

    # 每張圖獨立做 Ken Burns，產出 [vi_<input_idx>]
    for img, idx in img_idx_map.items():
        # 找此圖屬於哪個 scene（拿 per_dur）
        per_dur = next(s["per_dur"] for s in scene_items if img in s["imgs"])
        frames = max(int(round(per_dur * fps)), 1)
        zinc = (zoom - 1.0) / frames if zoom > 1.0 else 0
        fc.append(
            f"[{idx}:v]scale={big_w}:{big_h}:force_original_aspect_ratio=increase,"
            f"crop={big_w}:{big_h},"
            f"zoompan=z='min(zoom+{zinc:.6f},{zoom})':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},"
            f"setsar=1,format=yuv420p[vi{idx}]"
        )

    # scene 內：用微轉場把多張 B-Roll 串成 [vs<scene_index>]
    scene_video_labels = []
    for si, s in enumerate(scene_items):
        ids = [img_idx_map[img] for img in s["imgs"]]
        if len(ids) == 1:
            label = f"vs{si}"
            fc.append(f"[vi{ids[0]}]copy[{label}]")
        else:
            cum = s["per_dur"]
            prev = f"vi{ids[0]}"
            for k in range(1, len(ids)):
                out = f"vsx{si}_{k}"
                off = cum - Dm
                fc.append(
                    f"[{prev}][vi{ids[k]}]xfade=transition=fade:duration={Dm}:offset={off:.3f}[{out}]"
                )
                cum += s["per_dur"] - Dm
                prev = out
            label = prev
        scene_video_labels.append(label)

    # scene 之間：用大轉場串接 [vs0][vs1]…→ vfinal
    if len(scene_video_labels) == 1:
        vlast = scene_video_labels[0]
    else:
        cum = scene_items[0]["scene_dur"]
        prev = scene_video_labels[0]
        for i in range(1, len(scene_video_labels)):
            off = cum - D
            out = f"vx{i}"
            fc.append(
                f"[{prev}][{scene_video_labels[i]}]xfade=transition=fade:duration={D}:offset={off:.3f}[{out}]"
            )
            cum += scene_items[i]["scene_dur"] - D
            prev = out
        vlast = prev

    # 音訊串接（仍以 scene 為單位，每段一個音檔，scene 之間用大 acrossfade）
    for i, s in enumerate(scene_items):
        fc.append(
            f"[{audio_map_idx[i]}:a]aresample=44100,apad,atrim=0:{s['scene_dur']:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
    if len(scene_items) == 1:
        alast = "a0"
    else:
        prev = "a0"
        for i in range(1, len(scene_items)):
            out = f"ax{i}"
            fc.append(f"[{prev}][a{i}]acrossfade=d={D}:c1=tri:c2=tri[{out}]")
            prev = out
        alast = prev

    total = sum(s["scene_dur"] for s in scene_items) - (len(scene_items) - 1) * D

    # 背景音樂
    bgm_cfg = cfg["video"].get("bgm", {})
    bgm_file = config.ROOT / bgm_cfg.get("file", "")
    map_audio = alast
    if bgm_cfg.get("file") and bgm_file.exists():
        bgm_idx = cur
        loop_args = ["-stream_loop", "-1"] if bgm_cfg.get("loop", True) else []
        inputs += [*loop_args, "-i", str(bgm_file)]
        cur += 1
        vol = float(bgm_cfg.get("volume", 0.18))
        fc.append(
            f"[{bgm_idx}:a]volume={vol},aresample=44100,atrim=0:{total:.3f},"
            f"asetpts=PTS-STARTPTS[bg]"
        )
        fc.append(
            f"[{alast}][bg]amix=inputs=2:duration=first:dropout_transition=0,"
            f"alimiter=limit=0.95[aout]"
        )
        map_audio = "aout"
        print(f"[Step4] 混入背景音樂：{bgm_file.name}")
    else:
        print("[Step4] 未提供背景音樂（assets/music/bgm.mp3 不存在），只輸出旁白。")

    # 字幕（依 scene 旁白與音長對齊，與 B-Roll 內部切換無關）
    map_video = vlast
    subs_cfg = cfg.get("subtitles", {})
    if subs_cfg.get("enabled", False):
        events = []
        start = 0.0
        for i, s in enumerate(scene_items):
            if s["narration"] and s["narration_dur"] > 0:
                events += subtitles.build_events(
                    s["narration"], start, start + s["narration_dur"],
                    int(subs_cfg.get("max_chars_per_line", 16)),
                    bool(subs_cfg.get("split_by_punctuation", True)),
                )
            start += s["scene_dur"] - D
        if events:
            ass_path = config.OUTPUT_DIR / "subtitles.ass"
            subtitles.write_ass(ass_path, W, H, events, subs_cfg)
            fc.append(f"[{vlast}]ass=output/subtitles.ass[vsub]")
            map_video = "vsub"
            print(f"[Step4] 已產生字幕（{len(events)} 段）→ {ass_path}")

    cmd = [
        ffmpeg, "-y", *inputs,
        "-filter_complex", ";".join(fc),
        "-map", f"[{map_video}]", "-map", f"[{map_audio}]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total:.3f}",
        "-movflags", "+faststart",
        str(config.VIDEO_FILE),
    ]

    n_imgs = sum(len(s["imgs"]) for s in scene_items)
    print(f"[Step4] 合成影片（{len(scene_items)} 段旁白 / {n_imgs} 張 B-Roll，約 {total:.1f} 秒，{W}x{H}）…")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(config.ROOT))
    if proc.returncode != 0:
        print(proc.stderr[-3000:])
        raise SystemExit("[錯誤] ffmpeg 合成失敗，請看上方訊息。")
    print(f"[Step4] 完成 → {config.VIDEO_FILE}")


if __name__ == "__main__":
    run()
