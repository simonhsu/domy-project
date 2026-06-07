"""讀取 config.yaml 與 .env，提供全域設定與路徑。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 專案根目錄（src 的上一層）
ROOT = Path(__file__).resolve().parent.parent

# 各資料夾路徑
INPUT_DIR = ROOT / "input"
CHARACTERS_DIR = INPUT_DIR / "characters"
BRIEF_FILE = INPUT_DIR / "brief.txt"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
AUDIO_DIR = OUTPUT_DIR / "audio"
STORYBOARD_FILE = OUTPUT_DIR / "storyboard.json"
VIDEO_FILE = OUTPUT_DIR / "broll.mp4"

_CONFIG_FILE = ROOT / "config.yaml"


def load_config() -> dict:
    """讀取 config.yaml。"""
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key() -> str:
    """從 .env / 環境變數取得 GEMINI_API_KEY。"""
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("在這裡"):
        raise SystemExit(
            "\n[錯誤] 找不到 GEMINI_API_KEY。\n"
            "請把 .env.example 複製成 .env，並在裡面填入你的金鑰。\n"
            "取得金鑰：https://aistudio.google.com/apikey\n"
        )
    return key


def ensure_dirs() -> None:
    """確保所有需要的資料夾存在。"""
    for d in (CHARACTERS_DIR, ASSETS_DIR / "music", OUTPUT_DIR, IMAGES_DIR, AUDIO_DIR):
        d.mkdir(parents=True, exist_ok=True)
