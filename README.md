# 课程视频自动拆分器

## 1. 安装

```bash
sudo apt update
sudo apt install -y ffmpeg python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

如果你用的是 NVIDIA GPU + CUDA，faster-whisper 会走 CUDA；首次运行会自动下载 Whisper 模型。

## 2. 运行

假设 MP4 在：

```text
/mnt/d/lecture.mp4
```

运行：

```bash
python lecture_splitter.py /mnt/d/lecture.mp4 --out lecture_output
```

2060 Super 8GB 推荐先用：

```bash
python lecture_splitter.py /mnt/d/lecture.mp4 \
  --out lecture_output \
  --model small \
  --device cuda \
  --compute-type float16 \
  --language zh
```

## 3. 输出

```text
lecture_output/
├── transcript.srt
├── transcript.txt
├── transcript.json
├── slides.csv
├── slides.md
└── slides/
    ├── 001.png
    ├── 002.png
    └── ...
```

`slides.csv` 的每一行就是一页 PPT：

- start_ts：开始时间
- end_ts：结束时间
- image：截图
- transcript：这一页对应的字幕

## 4. 翻页检测不准怎么办

PPT 页数太少：
```bash
--threshold 0.75
```

PPT 页数太多：
```bash
--threshold 0.65
```

一页 PPT 经常很短：
```bash
--min-slide-sec 2.5
```

如果字幕在画面底部，占比比较大：
```bash
--mask-bottom-ratio 0.30
```

如果老师的视频布局比较特殊（例如 PPT 只占画面中间一小块），告诉我视频画面布局，我可以再改检测算法。
