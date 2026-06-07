# B-Roll 生成系統（Gemini Flash）

放入「角色圖」+ 填一個「主題文字檔」，系統自動產生 **劇情 + 分鏡 → 圖片 → 旁白配音 → 合成影片**。
全程使用 Google Gemini flash 系列模型，輸出 **9:16 直向** 影片（含旁白 + 背景音樂 + 字幕、Ken Burns 動態）。

## 💡 A-Roll / B-Roll 概念
這套系統用電影/短影音的「**A-Roll / B-Roll** 剪輯法」：
- **A-Roll**＝旁白（口述的主軸），每一段是一個 *scene*。
- **B-Roll**＝每段旁白底下的**多張支援畫面**（不同鏡位/角度），用來視覺化、補強、隱喻旁白內容。
- 同一段旁白播放期間，畫面會在 **2~3 秒切換一次** B-Roll，節奏接近電影或 YouTube 短片。

預設：12 段旁白 × 每段 2 張 B-Roll = **24 張圖**，總長約 60 秒。

---

## 📁 資料夾說明

```
domy/
├── .env                  ← 在這裡填你的 GEMINI_API_KEY
├── config.yaml           ← 所有可調參數（比例、模型、聲音、轉場…）
├── run.py                ← 執行入口
├── input/
│   ├── characters/       ← 放角色圖（png/jpg，可多張）
│   └── brief.txt         ← 填你的「主題 / 想法」文字
├── assets/music/         ← （選）放背景音樂 bgm.mp3
└── output/
    ├── storyboard.json   ← 生成的劇情分鏡（可手改後重跑）
    ├── images/           ← 生成的場景圖
    ├── audio/            ← 生成的旁白語音
    └── broll.mp4         ← 🎬 最終影片
```

---

## 🚀 第一次使用（5 步）

1. **填金鑰**：把 `.env.example` 複製成 `.env`，打開填入
   ```
   GEMINI_API_KEY=你的金鑰
   ```
   （金鑰申請：<https://aistudio.google.com/apikey>）

2. **放角色圖**：把角色圖放到 `input/characters/`（png 或 jpg，可多張）。

3. **填主題**：打開 `input/brief.txt`，把內容換成你想做的影片主題/故事。

4. **（選）放音樂**：把背景音樂放到 `assets/music/bgm.mp3`。沒有也可以。

5. **安裝套件並執行**（PowerShell）：
   ```powershell
   pip install -r requirements.txt
   python run.py
   ```
   完成後影片在 **`output/broll.mp4`**。

> 註：本系統需要 `ffmpeg`。若提示找不到，請執行 `winget install Gyan.FFmpeg` 後重開終端機。

---

## 🔧 後續細微調整（最重要）

系統分成 4 個階段，**每階段都能單獨重跑**，所以微調不用整個重來：

| 想做的調整 | 怎麼做 | 指令 |
|---|---|---|
| 改劇情 / 分鏡內容 / 旁白文字 | 直接編輯 `output/storyboard.json` | `python run.py --from images` |
| 只想重出某一張圖 | 改該 scene 的 `image_prompt`（在 storyboard.json） | `python run.py --only images` |
| 換旁白聲音 / 語氣 | 改 `config.yaml` 的 `tts.voice` / `tts.style` | `python run.py --only tts` 然後 `python run.py --only video` |
| 換背景音樂 / 音量 / 轉場 / 縮放幅度 | 改 `config.yaml` 的 `video.*` | `python run.py --only video` |
| 字幕：開關 / 字型 / 大小 / 顏色 / 位置 | 改 `config.yaml` 的 `subtitles.*` | `python run.py --only video` |
| **每段旁白要更多 B-Roll** | 改 `config.yaml` 的 `broll.per_scene`（2→3、3→4） | `python run.py`（要重出全部圖） |
| **B-Roll 都不要出現角色**（純環境/物件） | `broll.character_strategy: none` | `python run.py --from images` |
| **B-Roll 都要出現角色** | `broll.character_strategy: all` | `python run.py --from images` |
| 改某張 B-Roll 的鏡位/內容 | 編輯 `output/storyboard.json` 該段的 `b_rolls[i]` | 刪掉該 `scene_XXy.png` → `python run.py --only images` → `--only video` |
| 切換節奏：每張停留變更長 | 改 `config.yaml` 的 `broll.sec_per_shot_target` 並重出 story（提示用） | `python run.py` |
| 段內切換轉場速度 | 改 `broll.micro_transition_sec`（小→俐落、大→柔和） | `python run.py --only video` |
| 換畫面比例（例如改 16:9） | 改 `config.yaml` 的 `aspect_ratio` 與 `resolution` | `python run.py --from images` |
| 換主題重做 | 改 `input/brief.txt` | `python run.py`（全跑） |

**指令總覽：**
```powershell
python run.py                 # 全跑：story → images → tts → video
python run.py --from images   # 從 images 一路跑到最後
python run.py --only video    # 只重跑 video
```
階段名稱：`story` / `images` / `tts` / `video`

### config.yaml 常用參數
- `scenes.count`：分鏡數量（鏡頭多寡）
- `tts.voice`：旁白聲音（`Kore` / `Puck` / `Charon` / `Aoede` / `Fenrir` …）
- `image.style_suffix`：全片畫面風格（英文，例如 cinematic、anime、watercolor…）
- `video.kenburns_zoom`：Ken Burns 縮放幅度（1.0 不動、1.2 明顯）
- `video.transition_sec`：轉場秒數
- `video.bgm.volume`：背景音樂音量（0~1）

### 字幕（subtitles）
字幕會**自動產生並燒錄進影片**，文字直接取自每個鏡頭的旁白，並依語音長度對齊時間。
- `enabled`：`true`/`false` 開關字幕
- `split_by_punctuation`：依標點把長句切成多段短字幕（短影音較好讀）
- `font` / `font_size`：字型與大小（繁中建議 `Microsoft JhengHei`）
- `primary_color` / `outline_color` / `outline`：字色 / 外框色 / 外框粗細（ASS 顏色格式 `&H00BBGGRR`）
- `margin_v`：字幕距底部高度（像素）

> 想**只調整字幕措辭**而不重配音：編輯 `output/subtitles.ass` 後，用任一影片剪輯軟體把它套到 `broll.mp4`；
> 若改 `config.yaml` 或旁白內容，重跑 `python run.py --only video` 會重新產生字幕並覆蓋。

---

## 💡 小提醒
- 角色一致性：`input/characters/` 的圖會在每次出圖時當參考；圖越清楚、角度越多，一致性越好。
- 生成的圖片含 Google **SynthID 隱形浮水印**（模型內建，無法移除）。
- 想要「真正會動的影片素材」（非靜圖動態）需改用 Veo 模型（非 flash），屬未來升級項目。
