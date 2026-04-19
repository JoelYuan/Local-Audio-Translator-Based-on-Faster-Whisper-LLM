#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import os
import numpy as np
import librosa
from faster_whisper import WhisperModel
import requests

class AudioTranslatorApp:
    SUPPORTED_FORMATS = [
        ("音频文件", "*.wav *.mp3 *.m4a *.flac *.ogg *.wma *.aac"),
        ("WAV文件", "*.wav"),
        ("MP3文件", "*.mp3"),
        ("所有文件", "*.*")
    ]

    LANGUAGE_NAMES = {
        "zh": "中文",
        "en": "英语",
        "ja": "日语",
        "ko": "韩语",
        "fr": "法语",
        "de": "德语",
        "es": "西班牙语",
        "it": "意大利语",
        "ru": "俄语",
        "ar": "阿拉伯语",
        "pt": "葡萄牙语",
        "vi": "越南语",
        "th": "泰语",
        "id": "印尼语",
        "ms": "马来语",
        "hi": "印地语"
    }

    def __init__(self, root):
        self.root = root
        self.root.title("音频翻译器 - LMS版")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        self.audio_file_path = None
        self.whisper_model = None
        self.is_processing = False

        self.load_config()
        self.load_whisper_model()
        self.create_widgets()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.llm_config = self.config["llm"]
        self.whisper_config = self.config["whisper"]

    def load_whisper_model(self):
        threading.Thread(target=self._load_whisper_model_thread, daemon=True).start()

    def _load_whisper_model_thread(self):
        try:
            self.root.after(0, lambda: self.status_var.set("正在加载 Whisper 模型..."))
            self.whisper_model = WhisperModel(
                self.whisper_config["model_path"],
                device=self.whisper_config["device"],
                compute_type=self.whisper_config.get("compute_type", "float16")
            )
            self.root.after(0, lambda: self.status_var.set("Whisper 模型加载完成"))
            self.root.after(0, lambda: self.select_button.config(state=tk.NORMAL))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"模型加载失败: {str(e)}"))

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="🎙️ 音频翻译器", font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 15))

        file_frame = ttk.LabelFrame(main_frame, text="音频文件选择", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 15))

        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.pack(fill=tk.X)

        self.file_path_var = tk.StringVar(value="未选择文件")
        ttk.Label(file_select_frame, text="文件:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(file_select_frame, textvariable=self.file_path_var, foreground="blue").pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.select_button = ttk.Button(file_select_frame, text="选择音频文件", command=self.select_audio_file, state=tk.DISABLED)
        self.select_button.pack(side=tk.RIGHT, padx=(10, 0))

        lang_frame = ttk.LabelFrame(main_frame, text="翻译设置", padding="10")
        lang_frame.pack(fill=tk.X, pady=(0, 15))

        lang_inner = ttk.Frame(lang_frame)
        lang_inner.pack(fill=tk.X)

        ttk.Label(lang_inner, text="源语种检测:").pack(side=tk.LEFT, padx=(0, 10))
        self.auto_detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lang_inner, text="自动检测", variable=self.auto_detect_var, command=self.on_auto_detect_toggle).pack(side=tk.LEFT)

        ttk.Label(lang_inner, text="源语种:").pack(side=tk.LEFT, padx=(20, 5))
        self.src_lang_var = tk.StringVar(value="zh")
        self.src_lang_combo = ttk.Combobox(lang_inner, textvariable=self.src_lang_var, width=8, state="readonly")
        self.src_lang_combo['values'] = [f"{code} - {name}" for code, name in self.LANGUAGE_NAMES.items()]
        self.src_lang_combo.pack(side=tk.LEFT)
        self.src_lang_combo.current(0)

        ttk.Label(lang_inner, text="目标语种:").pack(side=tk.LEFT, padx=(20, 5))
        self.tgt_lang_var = tk.StringVar(value="en")
        self.tgt_lang_combo = ttk.Combobox(lang_inner, textvariable=self.tgt_lang_var, width=8, state="readonly")
        self.tgt_lang_combo['values'] = [f"{code} - {name}" for code, name in self.LANGUAGE_NAMES.items()]
        self.tgt_lang_combo.pack(side=tk.LEFT)
        self.tgt_lang_combo.current(1)

        self.translate_button = ttk.Button(lang_frame, text="🔄 开始翻译", command=self.start_translation, style="Accent.TButton")
        self.translate_button.pack(pady=(10, 0))

        result_notebook = ttk.Notebook(main_frame)
        result_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        original_frame = ttk.Frame(result_notebook)
        result_notebook.add(original_frame, text="📝 原文")

        self.original_text = tk.Text(original_frame, wrap=tk.WORD, font=("Arial", 11))
        original_scroll = ttk.Scrollbar(original_frame, orient=tk.VERTICAL, command=self.original_text.yview)
        self.original_text.configure(yscrollcommand=original_scroll.set)
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        translation_frame = ttk.Frame(result_notebook)
        result_notebook.add(translation_frame, text="🌐 译文")

        self.translation_text = tk.Text(translation_frame, wrap=tk.WORD, font=("Arial", 11))
        translation_scroll = ttk.Scrollbar(translation_frame, orient=tk.VERTICAL, command=self.translation_text.yview)
        self.translation_text.configure(yscrollcommand=translation_scroll.set)
        self.translation_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        translation_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.original_text.insert("1.0", "识别结果将显示在这里...")
        self.original_text.config(state=tk.DISABLED)
        self.translation_text.insert("1.0", "翻译结果将显示在这里...")
        self.translation_text.config(state=tk.DISABLED)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="正在加载模型...")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)

        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(status_frame, textvariable=self.progress_var)
        self.progress_label.pack(side=tk.RIGHT)

        self.on_auto_detect_toggle()

    def on_auto_detect_toggle(self):
        if self.auto_detect_var.get():
            self.src_lang_combo.config(state=tk.DISABLED)
        else:
            self.src_lang_combo.config(state="readonly")

    def select_audio_file(self):
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=self.SUPPORTED_FORMATS,
            initialdir=os.path.expanduser("~/音乐")
        )
        if file_path:
            self.audio_file_path = file_path
            self.file_path_var.set(os.path.basename(file_path))
            self.status_var.set(f"已选择: {file_path}")

    def start_translation(self):
        if not self.audio_file_path:
            messagebox.showwarning("警告", "请先选择音频文件！")
            return

        if not self.whisper_model:
            messagebox.showerror("错误", "模型正在加载中，请稍候...")
            return

        self.is_processing = True
        self.translate_button.config(state=tk.DISABLED)
        self.progress_var.set("准备中...")
        threading.Thread(target=self.process_audio, daemon=True).start()

    def process_audio(self):
        try:
            self.update_status("正在加载音频文件...")
            self.update_progress("0%")

            audio_data, sample_rate = librosa.load(self.audio_file_path, sr=16000, mono=True)

            self.update_status("正在识别语音...")
            self.update_progress("30%")

            auto_detect = self.auto_detect_var.get()
            src_lang = None if auto_detect else self.src_lang_var.get().split(" - ")[0]

            segments, info = self.whisper_model.transcribe(
                audio_data,
                language=src_lang,
                beam_size=5,
                vad_filter=True
            )

            full_text = ""
            segment_list = []
            for segment in segments:
                full_text += segment.text
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                })

            detected_lang = info.language if hasattr(info, 'language') else src_lang
            detected_lang_name = self.LANGUAGE_NAMES.get(detected_lang, detected_lang)

            self.root.after(0, lambda: self.original_text.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.original_text.delete("1.0", tk.END))
            self.root.after(0, lambda: self.original_text.insert("1.0", f"【语种检测】: {detected_lang_name}\n\n【识别文本】:\n{full_text}"))
            self.root.after(0, lambda: self.original_text.config(state=tk.DISABLED))

            self.update_status("正在翻译...")
            self.update_progress("60%")

            tgt_lang = self.tgt_lang_var.get().split(" - ")[0]
            tgt_lang_name = self.LANGUAGE_NAMES.get(tgt_lang, tgt_lang)
            src_lang_name = self.LANGUAGE_NAMES.get(detected_lang, detected_lang)

            translation = self.translate_with_lms(full_text, src_lang_name, tgt_lang_name)

            self.root.after(0, lambda: self.translation_text.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.translation_text.delete("1.0", tk.END))
            self.root.after(0, lambda: self.translation_text.insert("1.0", translation))
            self.root.after(0, lambda: self.translation_text.config(state=tk.DISABLED))

            self.update_status("翻译完成！")
            self.update_progress("100%")

        except Exception as e:
            self.update_status(f"处理失败: {str(e)}")
            messagebox.showerror("错误", f"处理失败:\n{str(e)}")
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.translate_button.config(state=tk.NORMAL))

    def translate_with_lms(self, text, src_lang, tgt_lang):
        prompt = f"""Translate the following text from {src_lang} to {tgt_lang}.
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
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return f"翻译API错误: {response.status_code} - {response.text}"

        except requests.exceptions.ConnectionError:
            return "错误: 无法连接到 LM Studio，请确保 LMS 正在运行 (默认: http://localhost:1234)"
        except Exception as e:
            return f"翻译错误: {str(e)}"

    def update_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def update_progress(self, text):
        self.root.after(0, lambda: self.progress_var.set(text))

def main():
    root = tk.Tk()
    app = AudioTranslatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()