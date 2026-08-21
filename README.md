# Lecture Splitter

从课程视频中自动提取 PPT 页面、生成带时间戳的讲稿，并将 PPT 页面与对应讲稿进行时间轴对齐。

适用于课程、讲座、培训、公开课等包含 **PPT + 老师讲解** 的视频。

支持原生 Windows：
Windows 10
Windows 11
Python 3.10+
NVIDIA GPU
CPU
同时支持：
Ubuntu
WSL2
其他常见 Linux 环境
---

## 📌 项目简介

很多课程视频只有一个 MP4 文件，视频中同时包含：

- PPT 画面
- 老师讲课声音
- 字幕或自动生成的字幕

如果想重新整理这类课程，通常需要手动：

1. 一页一页截取 PPT
2. 记录每页 PPT 出现的时间
3. 把老师讲解内容整理成文字
4. 判断哪些讲稿对应哪一页 PPT
5. 再交给 AI 重新整理课程结构

Lecture Splitter 尝试把这些前处理工作自动完成。

整体流程：

```text
                    MP4 课程视频
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
        faster-whisper            OpenCV
             │                       │
             ▼                       ▼
       带时间戳的讲稿            PPT 页面检测
             │                       │
             │                       ▼
             │                   PPT 截图
             │                       │
             └───────────┬───────────┘
                         ▼
                    时间轴对齐
                         │
                         ▼
              PPT + 对应讲稿结构化数据
                         │
                         ▼
                         AI
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       课程大纲        PPT内容        演讲稿

使用 faster-whisper 对课程视频中的语音进行识别。.支持：
中文
英文
多语言
时间戳
NVIDIA CUDA GPU 加速
CPU 模式
Whisper small / medium 等模型
生成：
transcript.txt
transcript.srt
transcript.json

使用 OpenCV 对视频画面进行采样和分析。
程序会根据视频画面变化判断 PPT 是否发生切换，并记录：
PPT 页码
开始时间
结束时间
对应视频帧

Lecture Splitter 的一个主要用途是作为 AI 重构课程的前处理工具。
假设你有一个课程视频：
lecture.mp4
检测到页面切换后，程序会自动截取该页面的代表性画面。
根据 PPT 页面时间范围和 Whisper 字幕时间戳，将对应的讲稿自动分配到 PPT 页面。
Lecture Splitter 的一个主要用途是作为 AI 重构课程的前处理工具。

假设你有一个课程视频：
lecture.mp4
运行：
lecture.mp4
      │
      ▼
Lecture Splitter
      │
      ├── transcript.txt
      ├── transcript.json
      ├── transcript.srt
      ├── slides/*.png
      ├── slides.csv
      └── slides.md

然后可以把：
slides.md
transcript.txt
slides/*.png
提供给 AI。
AI 可以进一步分析：
课程结构
课程主题
├── 第一部分
│   ├── 知识点 1
│   ├── 知识点 2
│   └── 知识点 3
│
├── 第二部分
│   ├── 知识点 4
│   └── 知识点 5
│
└── 总结
PPT 结构
PPT 01 → 课程介绍
PPT 02 → 基本概念
PPT 03 → 核心知识
PPT 04 → 案例分析
...
演讲稿
AI 可以根据原始讲稿进一步整理成：
更完整的演讲稿
更自然的讲解语言
PPT 每页对应讲稿
课程笔记
教学大纲

🗺️ Roadmap
未来可以考虑加入：
 OCR 自动提取 PPT 文字
 自动识别 PPT 标题
 自动识别 PPT 内容区域
 更准确的 PPT 页面检测
 PPT 动画检测
 自动生成可编辑 PPTX
 AI 自动生成课程大纲
 AI 自动整理讲稿
 批量处理多个课程视频
 Web UI
 Docker 支持
