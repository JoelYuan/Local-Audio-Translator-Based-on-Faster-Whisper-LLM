#!/usr/bin/env python3
"""
系统音频录制与识别任务排队系统
功能：
1. 录制系统音频并保存为 WAV 文件
2. 支持任务排队处理
3. 自动检测语音活动
4. 控制音频片段长度 (3-20秒)
"""

import subprocess
import threading
import numpy as np
import wave
import os
import time
import queue
import json
import requests
from collections import deque
import webrtcvad
from faster_whisper import WhisperModel

class SystemAudioProcessor:
    def __init__(self, whisper_model_path, sample_rate=44100):
        self.sample_rate = sample_rate
        self.whisper_model_path = whisper_model_path
        self.model = None
        self.is_running = False
        self.audio_buffer = deque()
        
        # 输出目录
        self.output_dir = os.path.join(os.path.dirname(__file__), "audio_recordings")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 配置参数
        self.min_segment_duration = 0.3
        self.max_segment_duration = 30  # 最大 30 秒
        self.min_segment_samples = int(self.sample_rate * self.min_segment_duration)
        self.max_segment_samples = int(self.sample_rate * self.max_segment_duration)
        
        # 任务队列
        self.task_queue = queue.Queue()
        self.processing_thread = None
        self.processing_active = False

        # 翻译配置
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.llm_config = config.get("llm", {})
            self.whisper_config = config.get("whisper", {})
            self.tgt_lang = config.get("translation", {}).get("target_lang", "en")
        else:
            self.llm_config = {
                "base_url": "http://localhost:1234/v1",
                "model_name": "gemma-4-26b-a4b-it-uncensored",
                "temperature": 0.1,
                "max_tokens": 500,
                "timeout": 30
            }
            self.whisper_config = {}
            self.tgt_lang = "en"

        # 语音检测参数
        self.last_speech_time = time.time()
        self.silence_threshold = 0.5
        
        # 音频监视器
        self.monitor_name = self._detect_default_monitor()
        if not self.monitor_name:
            print("[警告] 无法检测到默认音频监视器，使用 @DEFAULT_MONITOR@")
            self.monitor_name = "@DEFAULT_MONITOR@"
    
    def load_model(self):
        """加载 Whisper 模型"""
        print("[系统] 加载 Whisper 模型...")
        self.model = WhisperModel(
            self.whisper_model_path,
            device='cuda',
            compute_type='float16'
        )
        self.vad = webrtcvad.Vad(3)
        print("[系统] 模型加载完成！")

    def _translate_with_lms(self, text, src_lang, tgt_lang):
        """使用 LMS API 翻译"""
        lang_map = {
            "zh": "Chinese", "en": "English", "ja": "Japanese",
            "ko": "Korean", "fr": "French", "de": "German",
            "es": "Spanish", "it": "Italian", "ru": "Russian",
            "pt": "Portuguese", "nl": "Dutch", "sv": "Swedish",
            "pl": "Polish", "tr": "Turkish", "ar": "Arabic",
            "hi": "Hindi", "th": "Thai", "vi": "Vietnamese",
            "id": "Indonesian", "ms": "Malay", "fil": "Filipino"
        }
        src_name = lang_map.get(src_lang, src_lang)
        tgt_name = lang_map.get(tgt_lang, tgt_lang)

        prompt = f"""Translate the following text from {src_name} to {tgt_name}.
Only output the translation, nothing else.

Text: {text}

Translation:"""

        try:
            response = requests.post(
                f"{self.llm_config['base_url']}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.llm_config["model_name"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.llm_config.get("temperature", 0.1),
                    "max_tokens": self.llm_config.get("max_tokens", 2000)
                },
                timeout=self.llm_config.get("timeout", 60)
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            return f"翻译API错误: {response.status_code}"
        except Exception as e:
            return f"翻译错误: {str(e)}"

    def _detect_default_monitor(self):
        """自动检测默认音频监视器"""
        try:
            # 执行 pactl 命令获取默认信宿
            result = subprocess.run(
                ['pactl', 'info'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 解析输出找到默认信宿
            for line in result.stdout.split('\n'):
                if 'Default Sink:' in line:
                    sink_name = line.split('Default Sink:')[1].strip()
                    # 监视器名称是信宿名称加上 .monitor 后缀
                    monitor_name = f"{sink_name}.monitor"
                    print(f"[系统] 检测到默认音频监视器: {monitor_name}")
                    return monitor_name
            return None
        except Exception as e:
            print(f"[错误] 检测默认监视器失败: {e}")
            return None
    
    def _capture_audio(self):
        """捕获系统音频（使用 WebRTC VAD）"""
        vad_sample_rate = 16000
        frame_duration_ms = 30
        frame_size = int(vad_sample_rate * frame_duration_ms / 1000)

        cmd = [
            'parec',
            '-d', self.monitor_name,
            '--format=s16le',
            '--rate=' + str(vad_sample_rate),
            '--channels=1'
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        print(f"[系统] 开始捕获系统音频 (监视器: {self.monitor_name})... (按 Ctrl+C 停止)")

        self.last_speech_time = time.time()
        self.speech_active = False
        self.silence_threshold = 0.5
        self.max_buffer_duration = 12.0
        self.buffer_start_time = time.time()

        speech_buffer = bytearray()

        while self.is_running:
            chunk = process.stdout.read(frame_size * 2)
            if not chunk:
                break

            try:
                is_speech = self.vad.is_speech(chunk, vad_sample_rate)
            except:
                is_speech = False

            current_time = time.time()

            if is_speech:
                self.last_speech_time = current_time
                self.speech_active = True
                speech_buffer.extend(chunk)

                if current_time - self.buffer_start_time >= self.max_buffer_duration:
                    audio_data = np.frombuffer(bytes(speech_buffer), dtype=np.int16).astype(np.float32) / 32768.0
                    self._save_audio_segment(audio_data, vad_sample_rate)
                    speech_buffer = bytearray()
                    self.buffer_start_time = current_time
            elif self.speech_active:
                if current_time - self.last_speech_time >= self.silence_threshold:
                    if len(speech_buffer) >= frame_size * 2:
                        audio_data = np.frombuffer(bytes(speech_buffer), dtype=np.int16).astype(np.float32) / 32768.0
                        self._save_audio_segment(audio_data, vad_sample_rate)
                        speech_buffer = bytearray()
                        self.speech_active = False
                        self.buffer_start_time = current_time

        process.terminate()
        print("[系统] 音频捕获已停止")

    def _save_audio_segment(self, audio_data, sample_rate):
        """保存音频片段"""
        min_samples = int(0.3 * sample_rate)
        max_samples = int(self.max_segment_duration * sample_rate)

        if len(audio_data) < min_samples:
            return

        if len(audio_data) > max_samples:
            audio_data = audio_data[:max_samples]

        timestamp = int(time.time())
        wav_path = os.path.join(self.output_dir, f"system_audio_{timestamp}.wav")

        try:
            with wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes((audio_data * 32768).astype(np.int16).tobytes())

            duration = len(audio_data) / sample_rate
            print(f"\n[系统] 保存音频片段: {os.path.basename(wav_path)}")
            print(f"[系统] 时长: {duration:.1f}秒")
            print(f"[系统] 大小: {os.path.getsize(wav_path)/1024:.1f} KB")

            self.task_queue.put((wav_path, duration))
            print(f"[系统] 已添加到识别队列，当前队列长度: {self.task_queue.qsize()}")
        except Exception as e:
            print(f"[错误] 保存音频失败: {e}")
    
    def _process_queue(self):
        """处理识别任务队列"""
        self.processing_active = True
        print("[系统] 开始处理识别任务...")
        
        while self.processing_active:
            try:
                # 从队列获取任务，超时 1 秒
                wav_path, duration = self.task_queue.get(timeout=1)
                
                print(f"\n[处理] 开始识别: {os.path.basename(wav_path)}")
                print(f"[处理] 时长: {duration:.1f}秒")
                
                # 使用 Whisper 识别
                transcribe_kwargs = {
                    "beam_size": self.whisper_config.get("beam_size", 5),
                    "vad_filter": True
                }
                lang = self.whisper_config.get("language")
                if lang:
                    transcribe_kwargs["language"] = lang

                segments, info = self.model.transcribe(wav_path, **transcribe_kwargs)
                
                # 收集识别结果
                text_parts = []
                for seg in segments:
                    text_parts.append(seg.text.strip())
                
                if text_parts:
                    full_text = ' '.join(text_parts)
                    detected_lang = info.language if hasattr(info, 'language') else 'zh'
                    print(f"[结果] 识别语言: {detected_lang}")
                    print(f"[结果] 识别文本: {full_text}")

                    if full_text.strip():
                        print(f"\n[翻译] 开始翻译，源语言: {detected_lang} → 目标语言: {self.tgt_lang}")
                        translation = self._translate_with_lms(full_text, detected_lang, self.tgt_lang)
                        print(f"[翻译] 翻译结果: {translation}")
                else:
                    print("[结果] 未识别到有效内容")

                # 标记任务完成
                self.task_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"[错误] 处理任务失败: {e}")
                # 即使失败也标记任务完成
                try:
                    self.task_queue.task_done()
                except:
                    pass
    
    def start(self):
        """启动系统"""
        if self.is_running:
            print("[系统] 系统已在运行中！")
            return
        
        # 加载模型
        if self.model is None:
            self.load_model()
        
        # 启动捕获线程
        self.is_running = True
        capture_thread = threading.Thread(target=self._capture_audio, daemon=True)
        capture_thread.start()
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        
        print("[系统] 系统已启动")
        print("[系统] 正在监听系统音频...")
    
    def stop(self):
        """停止系统"""
        if not self.is_running:
            return

        print("\n[系统] 正在停止...")
        self.is_running = False
        self.processing_active = False

        # 等待线程结束
        if hasattr(self, 'processing_thread') and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=3)

        print("[系统] 已停止")

        # 显示队列状态
        if not self.task_queue.empty():
            print(f"[系统] 队列中还有 {self.task_queue.qsize()} 个任务未处理")

def main():
    """主函数"""
    # 模型路径
    model_path = '/home/yuan/.cache/modelscope/hub/models/pengzhendong/faster-whisper-medium'
    
    # 创建处理器
    processor = SystemAudioProcessor(model_path)
    
    # 启动系统
    processor.start()
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[系统] 接收到停止信号")
        processor.stop()

if __name__ == "__main__":
    main()