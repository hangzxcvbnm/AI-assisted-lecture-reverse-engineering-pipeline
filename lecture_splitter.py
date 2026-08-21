#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lecture_splitter.py
用途：
1. 从 MP4 用 faster-whisper 生成带时间戳的中英字幕
2. 自动检测 PPT 页面切换
3. 为每页 PPT 截一张代表性截图
4. 输出每页 start/end 时间，并把对应字幕写入 slides.csv / slides.md

推荐环境：Ubuntu / WSL2
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Slide:
    index: int
    start: float
    end: float
    frame_no: int
    image_path: str


def fmt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def run_cmd(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def transcribe(video: Path, out_dir: Path, model_name: str, device: str, compute_type: str,
               language: str | None):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "缺少 faster-whisper。请先安装：pip install -U faster-whisper"
        ) from e

    print(f"[1/3] Whisper 转录：model={model_name}, device={device}, compute_type={compute_type}")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    kwargs = {
        "beam_size": 5,
        "vad_filter": True,
        "condition_on_previous_text": True,
    }
    if language:
        kwargs["language"] = language

    segments, info = model.transcribe(str(video), **kwargs)

    rows = []
    for seg in segments:
        txt = (seg.text or "").strip()
        if not txt:
            continue
        rows.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": txt,
        })

    (out_dir / "transcript.json").write_text(
        json.dumps({
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "segments": rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # SRT
    def srt_ts(sec: float) -> str:
        ms = int(round((sec - math.floor(sec)) * 1000))
        total = int(math.floor(sec))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if ms >= 1000:
            s += 1
            ms -= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_lines = []
    for i, r in enumerate(rows, 1):
        srt_lines += [
            str(i),
            f"{srt_ts(r['start'])} --> {srt_ts(r['end'])}",
            r["text"],
            "",
        ]
    (out_dir / "transcript.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    (out_dir / "transcript.txt").write_text(
        "\n".join(f"[{fmt_ts(r['start'])}] {r['text']}" for r in rows),
        encoding="utf-8",
    )
    print(f"  转录完成：{len(rows)} 个字幕片段")
    return rows


def get_video_info(cap):
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return fps, frame_count, duration, width, height


def make_feature(frame: np.ndarray, mask_bottom_ratio: float, resize_w: int = 320) -> np.ndarray:
    """提取主要用于比较 PPT 区域的灰度低分辨率特征。
    通过裁掉底部字幕区域，降低字幕变化导致的误判。
    """
    h, w = frame.shape[:2]
    cut_h = int(h * (1.0 - mask_bottom_ratio))
    crop = frame[:cut_h, :]

    # 轻微裁掉边缘，减少黑边/播放器边框的影响
    edge_x = int(crop.shape[1] * 0.02)
    edge_y = int(crop.shape[0] * 0.02)
    if crop.shape[0] > 2 * edge_y and crop.shape[1] > 2 * edge_x:
        crop = crop[edge_y:-edge_y, edge_x:-edge_x]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    scale = resize_w / max(1, gray.shape[1])
    new_h = max(1, int(gray.shape[0] * scale))
    gray = cv2.resize(gray, (resize_w, new_h), interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return gray.astype(np.float32) / 255.0


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """归一化均方误差映射到 0~1，越大越相似。"""
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    mse = float(np.mean((a - b) ** 2))
    return max(0.0, 1.0 - mse * 3.0)


def detect_slides(
    video: Path,
    out_dir: Path,
    sample_every: float = 1.5,
    threshold: float = 0.70,
    min_slide_sec: float = 4.0,
    settle_sec: float = 1.0,
    mask_bottom_ratio: float = 0.23,
):
    print("[2/3] 检测 PPT 页面变化……")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video}")

    fps, frame_count, duration, width, height = get_video_info(cap)
    print(f"  视频：{width}x{height}, {fps:.2f} FPS, {duration/60:.1f} 分钟")

    samples = []
    t = 0.0
    while t < duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if ok:
            feat = make_feature(frame, mask_bottom_ratio)
            samples.append((t, feat))
        t += sample_every

    if not samples:
        raise RuntimeError("没有成功读取到视频帧。")

    # 先找候选切页点
    candidates = [0.0]
    last_change = 0.0
    prev_feat = samples[0][1]

    for i in range(1, len(samples)):
        t, feat = samples[i]
        sim = similarity(prev_feat, feat)

        # 变化很明显，而且距离上次切页足够久
        if sim < threshold and (t - last_change) >= min_slide_sec:
            # 为避免把短暂动画/鼠标移动误识别为新页，
            # 检查后一个样本是否仍和当前样本差异明显。
            if i + 1 < len(samples):
                sim_next = similarity(feat, samples[i + 1][1])
                if sim_next < threshold:
                    candidates.append(t)
                    last_change = t
        prev_feat = feat

    candidates = sorted(set(candidates))
    # 合并太近的候选
    merged = []
    for c in candidates:
        if not merged or c - merged[-1] >= min_slide_sec:
            merged.append(c)

    # 输出页截图
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    slides = []
    for idx, start in enumerate(merged, 1):
        end = merged[idx] - 0.05 if idx < len(merged) else duration
        capture_t = min(start + settle_sec, max(start, end - 0.2))

        cap.set(cv2.CAP_PROP_POS_MSEC, capture_t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            continue

        img_path = slides_dir / f"{idx:03d}.png"
        cv2.imwrite(str(img_path), frame)

        frame_no = int(round(capture_t * fps))
        slides.append(Slide(
            index=idx,
            start=float(start),
            end=float(end),
            frame_no=frame_no,
            image_path=str(img_path.relative_to(out_dir)).replace("\\", "/"),
        ))

    cap.release()

    print(f"  检测到约 {len(slides)} 页 PPT")
    return slides


def attach_transcript(slides: list[Slide], transcript_rows: list[dict]) -> list[dict]:
    output = []
    for s in slides:
        related = []
        for r in transcript_rows:
            # 有重叠就算属于这一页
            overlap = min(s.end, r["end"]) - max(s.start, r["start"])
            if overlap > 0:
                related.append(r)

        output.append({
            "index": s.index,
            "start": s.start,
            "end": s.end,
            "start_ts": fmt_ts(s.start),
            "end_ts": fmt_ts(s.end),
            "image": s.image_path,
            "transcript": " ".join(r["text"] for r in related),
        })
    return output


def save_slide_outputs(out_dir: Path, slide_rows: list[dict]):
    with (out_dir / "slides.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "start_ts", "end_ts", "image", "transcript"]
        )
        writer.writeheader()
        writer.writerows(slide_rows)

    md = ["# PPT 页面与时间轴\n"]
    for r in slide_rows:
        md.append(
            f"## PPT {r['index']:03d}\n"
            f"- 开始：`{r['start_ts']}`\n"
            f"- 结束：`{r['end_ts']}`\n"
            f"- 截图：`{r['image']}`\n\n"
            f"### 对应字幕\n"
            f"{r['transcript'] or '（该时间段没有识别到字幕）'}\n"
        )
    (out_dir / "slides.md").write_text("\n".join(md), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=str, help="MP4 视频路径")
    parser.add_argument("--out", default="lecture_output", help="输出目录")
    parser.add_argument("--model", default="small", help="Whisper 模型，例如 small / medium")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--compute-type", default="float16", dest="compute_type")
    parser.add_argument("--language", default="zh", help="语言，中文用 zh；自动识别可填 auto")
    parser.add_argument("--sample-every", type=float, default=1.5, help="PPT 检测采样间隔（秒）")
    parser.add_argument("--threshold", type=float, default=0.70, help="页面变化阈值，越高越容易判定翻页")
    parser.add_argument("--min-slide-sec", type=float, default=4.0, help="最短 PPT 页面时长")
    parser.add_argument("--settle-sec", type=float, default=1.0, help="翻页后等待多少秒截图")
    parser.add_argument("--mask-bottom-ratio", type=float, default=0.23, help="忽略底部多少比例画面")
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"找不到视频：{video}")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    language = None if args.language.lower() == "auto" else args.language

    transcript_rows = transcribe(
        video, out_dir,
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=language,
    )

    slides = detect_slides(
        video, out_dir,
        sample_every=args.sample_every,
        threshold=args.threshold,
        min_slide_sec=args.min_slide_sec,
        settle_sec=args.settle_sec,
        mask_bottom_ratio=args.mask_bottom_ratio,
    )

    print("[3/3] 将字幕和 PPT 时间轴对应起来……")
    slide_rows = attach_transcript(slides, transcript_rows)
    save_slide_outputs(out_dir, slide_rows)

    print("\n完成。输出文件：")
    for p in [
        out_dir / "transcript.srt",
        out_dir / "transcript.txt",
        out_dir / "transcript.json",
        out_dir / "slides.csv",
        out_dir / "slides.md",
        out_dir / "slides",
    ]:
        print(" ", p)
    print("\n提示：如果 PPT 页数明显偏多/偏少，优先调整 --threshold 和 --min-slide-sec。")


if __name__ == "__main__":
    main()
