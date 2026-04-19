# Smart Audio Translator README

## 项目概述 / Project Overview

本项目实现了一个实时双语翻译系统，支持：
- 🎤 系统音频实时识别（如浏览器TTS、应用通知等）
- 🌐 实时语音翻译（中文到英文）
- 📱 友好的图形界面

This project implements a real-time bilingual translation system that supports:
- 🎤 Real-time system audio recognition (e.g., browser TTS, app notifications, etc.)
- 🌐 Real-time speech translation (Chinese to English)
- 📱 User-friendly graphical interface

## 依赖项 / Dependencies

- Python 3.10+
- PyAudio
- NumPy
- Faster-Whisper
- Requests (for LLM API calls)
- PulseAudio (for system audio capture)
- Tkinter (GUI interface)

## 配置文件说明 / Configuration File

### config.json 配置 / config.json Configuration

```json
{
  "whisper": {
    "model_path": "/home/yuan/.cache/modelscope/hub/models/pengzhendong/faster-whisper-medium",
    "device": "cuda",
    "compute_type": "float16",
    "language": null,
    "beam_size": 5
  },
  "llm": {
    "base_url": "http://localhost:1234/v1",
    "model_name": "gemma-4-26b-a4b-it-uncensored",
    "temperature": 0.1,
    "max_tokens": 500,
    "timeout": 30
  },
  "translation": {
    "target_lang": "en"
  }
}
```

### 配置说明 / Configuration Explanation

1. **Whisper 配置 / Whisper Configuration**
   - `model_path`: Local path to the faster-whisper model
   - `device`: Running device ("cuda" or "cpu")
   - `compute_type`: Compute type ("float16" or "int8")

2. **LLM 配置 / LLM Configuration**
   - `base_url`: LLM API service address (default: http://localhost:1234/v1, suitable for LM Studio)
   - `model_name`: Model name to use
   - `temperature`: Generation temperature
   - `max_tokens`: Maximum number of tokens to generate
   - `timeout`: API timeout in seconds

3. **使用其他 API / Using Other APIs**
   - To use other LLM APIs (such as OpenAI, Anthropic, etc.), simply modify the `base_url` and corresponding API parameters
   - For example, using OpenAI API:
     ```json
     "llm": {
       "base_url": "https://api.openai.com/v1",
       "model_name": "gpt-4",
       "api_key": "your-api-key",
       "temperature": 0.1,
       "max_tokens": 500,
       "timeout": 30
     }
     ```
   - Note: Different APIs may have different request formats, and you may need to modify the API call part in the code

## 运行指南 / Running Guide

### 步骤 1: 运行测试脚本 / Step 1: Run Test Scripts

#### 1.1 测试字体（test_fonts.py） / Test Fonts (test_fonts.py)

```bash
cd /home/yuan/文档/Python_Project/双语翻译器
python test_fonts.py
```

- 功能：检测系统中可用的中文字体
- 输出：系统中所有可用字体，特别是中文字体

- Function: Detect available Chinese fonts in the system
- Output: All available fonts in the system, especially Chinese fonts

#### 1.2 测试音频录制（test_audio_record.py） / Test Audio Recording (test_audio_record.py)

```bash
cd /home/yuan/文档/Python_Project/双语翻译器
python test_audio_record.py
```

- 功能：录制3秒系统音频并保存为WAV文件
- 输出：测试系统音频捕获功能是否正常
- 注意：可能需要修改脚本中的`monitor_name`为实际的系统音频监视器名称

- Function: Record 3 seconds of system audio and save as WAV file
- Output: Test whether the system audio capture function is normal
- Note: You may need to modify the `monitor_name` in the script to the actual system audio monitor name

#### 1.3 测试音频翻译（test_audio_translator_lms.py） / Test Audio Translation (test_audio_translator_lms.py)

```bash
cd /home/yuan/文档/Python_Project/双语翻译器
python test_audio_translator_lms.py
```

- 功能：图形界面的音频文件翻译工具
- 操作：选择音频文件，设置源语种和目标语种，点击"开始翻译"
- 输出：显示语音识别结果和翻译结果

- Function: Graphical interface audio file translation tool
- Operation: Select audio file, set source and target languages, click "Start Translation"
- Output: Display speech recognition results and translation results

### 步骤 2: 运行系统音频处理器 / Step 2: Run System Audio Processor

```bash
cd /home/yuan/文档/Python_Project/双语翻译器
python system_audio_processor.py
```

- 功能：实时捕获系统音频并进行处理
- 注意：这是一个后台处理脚本，为GUI提供音频数据

- Function: Real-time capture and processing of system audio
- Note: This is a background processing script that provides audio data for the GUI

### 步骤 3: 运行主应用 / Step 3: Run Main Application

```bash
cd /home/yuan/文档/Python_Project/双语翻译器
python smart_audio_translator_gui.py
```

- 功能：完整的实时双语翻译GUI应用
- 操作：
  1. 点击"Start"按钮开始系统
  2. 系统会自动初始化（加载模型、设置音频捕获）
  3. 开始实时捕获系统音频并进行翻译
  4. 点击"Stop"按钮停止系统

- Function: Complete real-time bilingual translation GUI application
- Operation:
  1. Click the "Start" button to start the system
  2. The system will automatically initialize (load models, set up audio capture)
  3. Start real-time capture of system audio and perform translation
  4. Click the "Stop" button to stop the system

## 核心文件说明 / Core Files

| 文件 / File | 功能 / Function | 说明 / Description |
|------|------|------|
| `config.json` | 配置文件 | 存储模型路径和参数 |
| `smart_audio_translator_gui.py` | 主应用 | 完整的实时双语翻译GUI |
| `system_audio_processor.py` | 音频处理器 | 实时捕获系统音频 |
| `test_fonts.py` | 字体测试 | 检测系统中可用的中文字体 |
| `test_audio_record.py` | 音频录制测试 | 测试系统音频捕获功能 |
| `test_audio_translator_lms.py` | 音频翻译测试 | 测试音频文件翻译功能 |

| File | Function | Description |
|------|------|------|
| `config.json` | Configuration file | Store model paths and parameters |
| `smart_audio_translator_gui.py` | Main application | Complete real-time bilingual translation GUI |
| `system_audio_processor.py` | Audio processor | Real-time capture of system audio |
| `test_fonts.py` | Font test | Detect available Chinese fonts in the system |
| `test_audio_record.py` | Audio recording test | Test system audio capture function |
| `test_audio_translator_lms.py` | Audio translation test | Test audio file translation function |

## 设备检测与配置 / Device Detection and Configuration

### 1. 确定系统音频监视器 / 1. Determine System Audio Monitor

```bash
# 查看所有音频源
pactl list sources | grep -E "Name:|Description:|Monitor of"

# 测试默认监视器
parec -d @DEFAULT_MONITOR@ --format=s16le --rate=44100 --channels=1 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "系统音频监视器可用"
else
    echo "系统音频监视器不可用"
fi
```

```bash
# List all audio sources
pactl list sources | grep -E "Name:|Description:|Monitor of"

# Test default monitor
parec -d @DEFAULT_MONITOR@ --format=s16le --rate=44100 --channels=1 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "System audio monitor is available"
else
    echo "System audio monitor is not available"
fi
```

### 2. 验证系统音频捕获 / 2. Verify System Audio Capture

```bash
# 录制 3 秒系统音频
timeout 3 parec -d @DEFAULT_MONITOR@ --format=s16le --rate=44100 --channels=1 > test_system.raw

# 检查文件大小
ls -la test_system.raw
```

```bash
# Record 3 seconds of system audio
timeout 3 parec -d @DEFAULT_MONITOR@ --format=s16le --rate=44100 --channels=1 > test_system.raw

# Check file size
ls -la test_system.raw
```

## 故障排除 / Troubleshooting

### 1. 系统音频捕获失败 / 1. System Audio Capture Failure

- 检查 PulseAudio 服务：`systemctl status pulseaudio`
- 检查 PipeWire 服务：`systemctl status pipewire`
- 尝试使用不同的监视器设备：`pactl list sources | grep -E "Name:|Description:|Monitor of"`

- Check PulseAudio service: `systemctl status pulseaudio`
- Check PipeWire service: `systemctl status pipewire`
- Try using a different monitor device: `pactl list sources | grep -E "Name:|Description:|Monitor of"`

### 2. 模型加载失败 / 2. Model Loading Failure

- 检查模型路径是否正确
- 确保 CUDA 可用（如果使用 GPU）
- 检查 faste-whisper 库是否正确安装

- Check if the model path is correct
- Ensure CUDA is available (if using GPU)
- Check if the faster-whisper library is installed correctly

### 3. 翻译 API 连接失败 / 3. Translation API Connection Failure

- 确保 LM Studio 或其他 LLM 服务正在运行
- 检查 `base_url` 配置是否正确
- 测试 API 连接：`curl http://localhost:1234/v1/models`

- Ensure LM Studio or other LLM service is running
- Check if the `base_url` configuration is correct
- Test API connection: `curl http://localhost:1234/v1/models`

### 4. 编码错误 / 4. Encoding Error

- 如果遇到编码错误（如 'ascii' codec can't decode byte），可能是因为路径包含中文字符
- 确保系统环境变量设置正确：`export LANG=en_US.UTF-8`

- If you encounter encoding errors (e.g., 'ascii' codec can't decode byte), it may be because the path contains Chinese characters
- Ensure system environment variables are set correctly: `export LANG=en_US.UTF-8`

## 模型配置 / Model Configuration

- **Whisper 模型**: `faster-whisper-medium` (本地路径: `/home/yuan/.cache/modelscope/hub/models/pengzhendong/faster-whisper-medium`)
- **LLM 模型**: 可配置为任何支持 OpenAI 兼容 API 的模型
  - 推荐：`gemma-4-26b-a4b-it-uncensored`（使用 LM Studio 本地运行）
  - 可选：`gpt-4`、`claude-3` 等（需要相应的 API 密钥）

- **Whisper Model**: `faster-whisper-medium` (local path: `/home/yuan/.cache/modelscope/hub/models/pengzhendong/faster-whisper-medium`)
- **LLM Model**: Can be configured to any model that supports OpenAI compatible API
  - Recommended: `gemma-4-26b-a4b-it-uncensored` (run locally with LM Studio)
  - Optional: `gpt-4`, `claude-3`, etc. (requires corresponding API key)

## 性能优化 / Performance Optimization

- **GPU 加速**: 确保 CUDA 可用
- **批处理**: 合并短音频片段减少推理次数
- **VAD (语音活动检测)**: 只处理有声音的部分
- **缓冲区管理**: 使用双端队列管理音频数据

- **GPU Acceleration**: Ensure CUDA is available
- **Batch Processing**: Combine short audio segments to reduce inference times
- **VAD (Voice Activity Detection)**: Only process parts with sound
- **Buffer Management**: Use double-ended queue to manage audio data

## 常见问题 / Frequently Asked Questions

### Q: 为什么系统音频捕获没有声音？
A: 检查系统音量是否静音，或尝试不同的监视器设备。

### Q: Why is there no sound in system audio capture?
A: Check if the system volume is muted, or try a different monitor device.

### Q: 为什么翻译延迟高？
A: 减小音频片段长度，或使用更轻量的 Whisper 模型。

### Q: Why is translation delay high?
A: Reduce audio segment length, or use a lighter Whisper model.

### Q: 如何使用其他 LLM API？
A: 修改 `config.json` 中的 `llm` 配置，设置相应的 `base_url` 和 API 参数。

### Q: How to use other LLM APIs?
A: Modify the `llm` configuration in `config.json` to set the corresponding `base_url` and API parameters.

### Q: 如何更改目标语言？
A: 修改 `config.json` 中的 `translation.target_lang` 字段，支持的语言代码：en（英语）、zh（中文）、ja（日语）等。

### Q: How to change the target language?
A: Modify the `translation.target_lang` field in `config.json`. Supported language codes: en (English), zh (Chinese), ja (Japanese), etc.

