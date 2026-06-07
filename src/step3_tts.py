"""Step 3：把每段旁白 → 語音 WAV (output/audio)。"""
from __future__ import annotations

import json
import wave

from google import genai
from google.genai import types

from . import config


def _save_wav(path, pcm: bytes, channels=1, rate=24000, width=2) -> None:
    """Gemini TTS 回傳的是 24kHz / 16-bit / 單聲道 PCM，包成 WAV。"""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def _extract_pcm(resp) -> bytes | None:
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return part.inline_data.data
    return None


def run() -> None:
    cfg = config.load_config()
    config.ensure_dirs()

    if not config.STORYBOARD_FILE.exists():
        raise SystemExit("[錯誤] 找不到 storyboard.json，請先執行 step1。")
    scenes = json.loads(config.STORYBOARD_FILE.read_text(encoding="utf-8"))["scenes"]

    client = genai.Client(api_key=config.get_api_key())
    voice = cfg["tts"]["voice"]
    style = cfg["tts"]["style"]
    model = cfg["models"]["tts"]

    for scene in scenes:
        sid = scene["id"]
        narration = (scene.get("narration") or "").strip()
        out = config.AUDIO_DIR / f"scene_{sid:02d}.wav"
        if not narration:
            print(f"[Step3] scene {sid:02d} 無旁白，略過。")
            continue
        print(f"[Step3] 配音 scene {sid:02d} …")
        resp = client.models.generate_content(
            model=model,
            contents=f"請以{style}朗讀以下內容：{narration}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )
        pcm = _extract_pcm(resp)
        if not pcm:
            raise SystemExit(f"[錯誤] scene {sid} 沒有取得語音。")
        _save_wav(out, pcm)
        print(f"        → {out}")

    print(f"[Step3] 完成，語音於 {config.AUDIO_DIR}")


if __name__ == "__main__":
    run()
