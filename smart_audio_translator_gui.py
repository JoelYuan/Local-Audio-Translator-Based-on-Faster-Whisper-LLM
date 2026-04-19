#!/usr/bin/env python3
"""
Smart Audio Translator (New Architecture)
Architecture:
1. Audio Capture Thread - WebRTC VAD, save audio files
2. Speech Recognition Thread - Context-aware to prevent truncation
3. Translation Thread - Independent parallel processing
4. Two-layer GUI - Top: Original text, Bottom: Translation, Language selector
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import numpy as np
import wave
import os
import time
import queue
import json
from faster_whisper import WhisperModel
import requests
import webrtcvad


class AudioCapture:
    def __init__(self, monitor_name, on_audio_saved=None, sample_rate=16000):
        self.monitor_name = monitor_name
        self.sample_rate = sample_rate
        self.on_audio_saved = on_audio_saved
        self.vad = webrtcvad.Vad(3)
        self.is_running = False

        self.last_speech_time = time.time()
        self.silence_threshold = 0.5
        self.max_buffer_duration = 12.0
        self.buffer_start_time = time.time()
        self.speech_active = False
        self.frame_size = int(sample_rate * 30 / 1000)

        self.audio_buffer = bytearray()
        self.output_dir = os.path.join(os.path.dirname(__file__), "audio_recordings")
        os.makedirs(self.output_dir, exist_ok=True)

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2)

    def _run(self):
        cmd = [
            'parec', '-d', self.monitor_name,
            '--format=s16le', '--rate=' + str(self.sample_rate), '--channels=1'
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.buffer_start_time = time.time()
        self.last_speech_time = time.time()

        while self.is_running:
            chunk = process.stdout.read(self.frame_size * 2)
            if not chunk:
                break

            try:
                is_speech = self.vad.is_speech(chunk, self.sample_rate)
            except:
                is_speech = False

            current_time = time.time()

            if is_speech:
                self.last_speech_time = current_time
                self.speech_active = True
                self.audio_buffer.extend(chunk)

                if current_time - self.buffer_start_time >= self.max_buffer_duration:
                    self._save_audio()
            elif self.speech_active:
                if current_time - self.last_speech_time >= self.silence_threshold:
                    if len(self.audio_buffer) >= self.frame_size * 2:
                        self._save_audio()

        process.terminate()

    def _save_audio(self):
        if len(self.audio_buffer) < self.frame_size * 2:
            self.audio_buffer = bytearray()
            self.speech_active = False
            return

        audio_data = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16)
        timestamp = int(time.time())
        wav_path = os.path.join(self.output_dir, f"audio_{timestamp}.wav")

        try:
            with wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())

            duration = len(audio_data) / self.sample_rate
            if self.on_audio_saved:
                self.on_audio_saved(wav_path, duration)
        except Exception as e:
            print(f"[Error] Save audio failed: {e}")
        finally:
            self.audio_buffer = bytearray()
            self.speech_active = False
            self.buffer_start_time = time.time()


class SpeechRecognizer:
    def __init__(self, whisper_config, on_recognition=None):
        self.whisper_config = whisper_config
        self.on_recognition = on_recognition
        self.model = None
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.prev_text = ""
        self.prev_lang = None

    def load_model(self):
        self.model = WhisperModel(
            self.whisper_config["model_path"],
            device=self.whisper_config["device"],
            compute_type=self.whisper_config.get("compute_type", "float16")
        )

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def add_audio(self, wav_path, duration):
        self.audio_queue.put((wav_path, duration))

    def _run(self):
        while self.is_running:
            try:
                wav_path, duration = self.audio_queue.get(timeout=0.5)
                self._recognize(wav_path, duration)
                self.audio_queue.task_done()
            except queue.Empty:
                continue

    def _recognize(self, wav_path, duration):
        try:
            transcribe_kwargs = {
                "beam_size": self.whisper_config.get("beam_size", 5),
                "vad_filter": True
            }
            lang = self.whisper_config.get("language")
            if lang:
                transcribe_kwargs["language"] = lang

            segments, info = self.model.transcribe(wav_path, **transcribe_kwargs)

            text_parts = []
            for seg in segments:
                text_parts.append(seg.text.strip())

            if text_parts:
                full_text = ' '.join(text_parts)
                detected_lang = info.language if hasattr(info, 'language') else None

                if self.prev_text and self.prev_lang == detected_lang:
                    context_text = self.prev_text + " " + full_text
                else:
                    context_text = full_text

                if self.on_recognition:
                    self.on_recognition(wav_path, context_text, detected_lang, full_text)

                self.prev_text = full_text
                self.prev_lang = detected_lang

                if detected_lang != self.prev_lang:
                    self.prev_text = ""
                self.prev_lang = detected_lang

        except Exception as e:
            print(f"[Error] Recognition failed: {e}")


class Translator:
    def __init__(self, llm_config, tgt_lang, on_translation=None):
        self.llm_config = llm_config
        self.tgt_lang = tgt_lang
        self.on_translation = on_translation
        self.text_buffer = []
        self.is_running = False
        self.lock = threading.Lock()

    def set_target_lang(self, lang):
        self.tgt_lang = lang

    def add_text(self, text, src_lang):
        with self.lock:
            self.text_buffer.append((text, src_lang))

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def _run(self):
        while self.is_running:
            with self.lock:
                if self.text_buffer:
                    text, src_lang = self.text_buffer.pop(0)
                else:
                    text = None
                    src_lang = None

            if text:
                translation = self._translate(text, src_lang, self.tgt_lang)
                if self.on_translation:
                    self.on_translation(text, translation, src_lang, self.tgt_lang)
            else:
                time.sleep(0.1)

    def _translate(self, text, src_lang, tgt_lang):
        lang_map = {
            "zh": "Chinese", "en": "English", "ja": "Japanese",
            "ko": "Korean", "fr": "French", "de": "German",
            "es": "Spanish", "it": "Italian", "ru": "Russian"
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
            return f"Translation API Error: {response.status_code}"
        except Exception as e:
            return f"Translation Error: {str(e)}"


class SmartAudioTranslatorGUI:
    LANGUAGE_NAMES = {
        "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
        "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
        "ru": "Russian", "ar": "Arabic", "pt": "Portuguese", "vi": "Vietnamese",
        "th": "Thai", "id": "Indonesian", "ms": "Malay", "hi": "Hindi",
        "nl": "Dutch", "sv": "Swedish", "pl": "Polish", "tr": "Turkish",
        "fil": "Filipino"
    }

    # Font configuration
    font_family = "song ti"
    font_size = 14
    
    # Padding configuration
    padding = {
        "button": (12, 6),
        "text": (10, 8)
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Smart Audio Translator")
        # Set window size and position to bottom center
        width, height = 1600, 320
        self.root.geometry(f"{width}x{height}")
        
        # Calculate position to center horizontally and place at bottom
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = screen_height - height - 50  # 50px from bottom
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.is_running = False
        self.audio_capture = None
        self.recognizer = None
        self.translator = None

        self.log_file = None
        self.session_start = None

        self.load_config()
        self.create_widgets()
        self.initialize_system()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.llm_config = self.config["llm"]
        self.whisper_config = self.config["whisper"]
        self.tgt_lang = self.config.get("translation", {}).get("target_lang", "en")

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(
            "TFrame",
            background="#f0f0f0"
        )

        style.configure(
            "TButton",
            background="#4a90e2",
            foreground="white",
            padding=self.padding["button"],
            font=(self.font_family, self.font_size)
        )

        style.configure(
            "Accent.TButton",
            background="#2c3e50",
            foreground="white",
            font=(self.font_family, self.font_size, "bold")
        )

        style.map("TButton",
                  background=[('active', '#5a9ff2')],
                  foreground=[('active', 'white')])

        style.map("Accent.TButton",
                  background=[('active', '#34495e')],
                  foreground=[('active', 'white')])

        style.configure(
            "TLabel",
            background="#f0f0f0",
            font=(self.font_family, self.font_size)
        )

        style.configure(
            "TCombobox",
            font=(self.font_family, self.font_size)
        )

    def create_widgets(self):
        self._setup_style()

        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Control bar (single line)
        control_frame = ttk.Frame(main_frame, style="TFrame")
        control_frame.pack(fill=tk.X, pady=(0, 5))

        # Left side: buttons
        left_control = ttk.Frame(control_frame)
        left_control.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.start_button = ttk.Button(left_control, text="Start", command=self.start_system,
                                        state=tk.DISABLED, width=8, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=3)

        self.stop_button = ttk.Button(left_control, text="Stop", command=self.stop_system,
                                       state=tk.DISABLED, width=8)
        self.stop_button.pack(side=tk.LEFT, padx=3)

        # Right side: language and status
        right_control = ttk.Frame(control_frame)
        right_control.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        lang_frame = ttk.Frame(right_control)
        lang_frame.pack(side=tk.RIGHT, padx=5)

        ttk.Label(lang_frame, text="Target:", font=(self.font_family, self.font_size)).pack(side=tk.LEFT, padx=2)
        self.tgt_lang_var = tk.StringVar(value=self.tgt_lang)
        self.tgt_lang_combo = ttk.Combobox(lang_frame, textvariable=self.tgt_lang_var,
                                            values=list(self.LANGUAGE_NAMES.keys()),
                                            state="readonly", width=10, font=(self.font_family, self.font_size))
        self.tgt_lang_combo.pack(side=tk.LEFT, padx=2)
        self.tgt_lang_combo.bind("<<ComboboxSelected>>", self.on_lang_changed)

        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(right_control, textvariable=self.status_var,
                                  foreground="#27ae60", font=(self.font_family, self.font_size, "bold"))
        status_label.pack(side=tk.RIGHT, padx=10)

        # Original section
        original_frame = ttk.Frame(main_frame, style="TFrame")
        original_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 2))

        original_header = ttk.Frame(original_frame, style="TFrame")
        original_header.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(original_header, text="ORIGINAL", font=(self.font_family, self.font_size, "bold"), foreground="#34495e").pack(side=tk.LEFT)

        self.original_duration_var = tk.DoubleVar(value=0)
        self.original_duration_label = ttk.Label(original_header, text="0.0s",
                  font=(self.font_family, self.font_size), foreground="#7f8c8d")
        self.original_duration_label.pack(side=tk.RIGHT)

        # Progress bar
        self.original_progress_canvas = tk.Canvas(original_frame, height=4, bg="#e0e0e0",
                                                   highlightthickness=0, relief=tk.FLAT)
        self.original_progress_canvas.pack(fill=tk.X, pady=(0, 2))
        self.original_progress_canvas.create_rectangle(0, 0, 0, 4, fill="#3498db", width=0, tags="progress")

        # Text area
        original_text_frame = ttk.Frame(original_frame, style="TFrame")
        original_text_frame.pack(fill=tk.BOTH, expand=False)

        self.original_text = tk.Text(original_text_frame, wrap=tk.WORD,
                                      font=(self.font_family, self.font_size),
                                      bg="#ffffff", relief=tk.FLAT, bd=1, borderwidth=1, highlightthickness=0,
                                      padx=self.padding["text"][0], pady=self.padding["text"][1], state=tk.DISABLED, height=3)
        original_scroll = ttk.Scrollbar(original_text_frame, orient=tk.VERTICAL, command=self.original_text.yview)
        self.original_text.configure(yscrollcommand=original_scroll.set)
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Translation section
        translation_frame = ttk.Frame(main_frame, style="TFrame")
        translation_frame.pack(fill=tk.BOTH, expand=False, pady=(2, 0))

        translation_header = ttk.Frame(translation_frame, style="TFrame")
        translation_header.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(translation_header, text="TRANSLATION", font=(self.font_family, self.font_size, "bold"), foreground="#27ae60").pack(side=tk.LEFT)

        self.translation_duration_var = tk.DoubleVar(value=0)
        self.translation_duration_label = ttk.Label(translation_header, text="0.0s",
                  font=(self.font_family, self.font_size), foreground="#7f8c8d")
        self.translation_duration_label.pack(side=tk.RIGHT)

        # Progress bar
        self.translation_progress_canvas = tk.Canvas(translation_frame, height=4, bg="#e0e0e0",
                                                      highlightthickness=0, relief=tk.FLAT)
        self.translation_progress_canvas.pack(fill=tk.X, pady=(0, 2))
        self.translation_progress_canvas.create_rectangle(0, 0, 0, 4, fill="#27ae60", width=0, tags="progress")

        # Text area
        translation_text_frame = ttk.Frame(translation_frame, style="TFrame")
        translation_text_frame.pack(fill=tk.BOTH, expand=False)

        self.translation_text = tk.Text(translation_text_frame, wrap=tk.WORD,
                                         font=(self.font_family, self.font_size),
                                         bg="#ffffff", relief=tk.FLAT, bd=1, borderwidth=1, highlightthickness=0,
                                         padx=self.padding["text"][0], pady=self.padding["text"][1], state=tk.DISABLED, height=5)
        translation_scroll = ttk.Scrollbar(translation_text_frame, orient=tk.VERTICAL, command=self.translation_text.yview)
        self.translation_text.configure(yscrollcommand=translation_scroll.set)
        self.translation_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        translation_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def initialize_system(self):
        self.status_var.set("Initializing...")

        def init_thread():
            try:
                monitor_name = self._detect_default_monitor()
                if not monitor_name:
                    monitor_name = "@DEFAULT_MONITOR@"

                self.audio_capture = AudioCapture(
                    monitor_name,
                    on_audio_saved=self.on_audio_saved
                )

                self.recognizer = SpeechRecognizer(
                    self.whisper_config,
                    on_recognition=self.on_recognition
                )
                self.recognizer.load_model()

                self.translator = Translator(
                    self.llm_config,
                    self.tgt_lang_var.get(),
                    on_translation=self.on_translation
                )

                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.status_var.set("Ready"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Init failed: {e}"))

        threading.Thread(target=init_thread, daemon=True).start()

    def _detect_default_monitor(self):
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, text=True, check=True)
            for line in result.stdout.split('\n'):
                if 'Default Sink:' in line:
                    return line.split('Default Sink:')[1].strip() + ".monitor"
            return None
        except:
            return None

    def _open_log_file(self):
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_start = timestamp
        log_path = os.path.join(log_dir, f"translation_{timestamp}.txt")
        self.log_file = open(log_path, "w", encoding="utf-8")
        self.log_file.write(f"=== Smart Audio Translator Log ===\n")
        self.log_file.write(f"Session: {timestamp}\n")
        self.log_file.write(f"Target Language: {self.tgt_lang_var.get()}\n")
        self.log_file.write("=" * 50 + "\n\n")

    def _close_log_file(self):
        if self.log_file:
            self.log_file.write(f"\n=== Session Ended: {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            self.log_file.close()
            self.log_file = None

    def _write_to_log(self, original_text, translation, src_lang, tgt_lang):
        if self.log_file:
            timestamp = time.strftime("%H:%M:%S")
            src_name = self.LANGUAGE_NAMES.get(src_lang, src_lang)
            tgt_name = self.LANGUAGE_NAMES.get(tgt_lang, tgt_lang)
            self.log_file.write(f"[{timestamp}] {src_name} -> {tgt_name}\n")
            self.log_file.write(f"Original: {original_text}\n")
            self.log_file.write(f"Translation: {translation}\n")
            self.log_file.write("-" * 40 + "\n")
            self.log_file.flush()

    def start_system(self):
        if not self.audio_capture or not self.recognizer or not self.translator:
            messagebox.showerror("Error", "System not initialized")
            return

        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Running")

        self._enable_text(self.original_text)
        self._enable_text(self.translation_text)
        self.original_text.delete("1.0", tk.END)
        self.translation_text.delete("1.0", tk.END)
        self._disable_text(self.original_text)
        self._disable_text(self.translation_text)

        self._open_log_file()

        self.recognizer.start()
        self.translator.start()
        self.audio_capture.start()

        self.log("System started")

    def stop_system(self):
        if not self.is_running:
            return

        self.is_running = False
        self.stop_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.NORMAL)
        self.status_var.set("Stopped")

        if self.audio_capture:
            self.audio_capture.stop()
        if self.recognizer:
            self.recognizer.stop()
        if self.translator:
            self.translator.stop()

        self._close_log_file()
        self.log("System stopped")

    def _enable_text(self, text_widget):
        text_widget.config(state=tk.NORMAL)

    def _disable_text(self, text_widget):
        text_widget.config(state=tk.DISABLED)

    def on_lang_changed(self, event=None):
        new_lang = self.tgt_lang_var.get()
        if self.translator:
            self.translator.set_target_lang(new_lang)
        self.log(f"Target language: {self.LANGUAGE_NAMES.get(new_lang, new_lang)}")

    def on_audio_saved(self, wav_path, duration):
        if self.recognizer:
            self.recognizer.add_audio(wav_path, duration)
        self.root.after(0, lambda: self._update_original_progress(duration))
        self.log(f"Audio saved: {os.path.basename(wav_path)}, {duration:.1f}s")

    def on_recognition(self, wav_path, context_text, detected_lang, raw_text):
        if self.translator and context_text:
            self.translator.add_text(context_text, detected_lang)

        lang_name = self.LANGUAGE_NAMES.get(detected_lang, detected_lang) if detected_lang else "Unknown"
        self.root.after(0, lambda: self._update_original_text(raw_text, lang_name))
        self.root.after(0, lambda: self.log(f"Recognized: {lang_name}, {len(raw_text.split())} words"))

    def on_translation(self, original_text, translation, src_lang, tgt_lang):
        self._write_to_log(original_text, translation, src_lang, tgt_lang)

        src_name = self.LANGUAGE_NAMES.get(src_lang, src_lang) if src_lang else "Unknown"
        tgt_name = self.LANGUAGE_NAMES.get(tgt_lang, tgt_lang) if tgt_lang else "Unknown"
        self.root.after(0, lambda: self._update_translation_text(translation, tgt_name))
        self.root.after(0, lambda: self.log(f"Translated: {src_name} -> {tgt_name}"))

    def _update_original_progress(self, duration):
        self.original_duration_var.set(duration)
        self.original_duration_label.config(text=f"Duration: {duration:.1f}s")
        canvas_width = self.original_progress_canvas.winfo_width()
        if canvas_width > 0:
            max_duration = 30
            fill_width = int((duration / max_duration) * canvas_width)
            fill_width = min(fill_width, canvas_width)
            self.original_progress_canvas.coords("progress", 0, 0, fill_width, 8)
            self.original_progress_canvas.itemconfig("progress", fill="#3498db")

    def _update_translation_progress(self, duration):
        self.translation_duration_var.set(duration)
        self.translation_duration_label.config(text=f"Duration: {duration:.1f}s")
        canvas_width = self.translation_progress_canvas.winfo_width()
        if canvas_width > 0:
            max_duration = 30
            fill_width = int((duration / max_duration) * canvas_width)
            fill_width = min(fill_width, canvas_width)
            self.translation_progress_canvas.coords("progress", 0, 0, fill_width, 8)
            self.translation_progress_canvas.itemconfig("progress", fill="#27ae60")

    def _update_original_text(self, text, lang_name):
        self._enable_text(self.original_text)
        self.original_text.delete("1.0", tk.END)
        self.original_text.insert("1.0", f"[{lang_name}]\n{text}")
        self._disable_text(self.original_text)

    def _update_translation_text(self, text, lang_name):
        self._enable_text(self.translation_text)
        self.translation_text.delete("1.0", tk.END)
        self.translation_text.insert("1.0", f"[{lang_name}]\n{text}")
        self._disable_text(self.translation_text)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        if hasattr(self, 'log_text') and self.log_text:
            self._enable_text(self.log_text)
            self.log_text.insert(tk.END, log_message + "\n")
            self.log_text.see(tk.END)
            self._disable_text(self.log_text)
        else:
            # Fallback to console if log_text doesn't exist
            print(log_message)


def main():
    root = tk.Tk()
    app = SmartAudioTranslatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
