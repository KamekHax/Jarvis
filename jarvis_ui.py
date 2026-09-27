"""Desktop chat and voice interface for JARVIS Local (Tkinter only)."""
from __future__ import annotations

import json
import os
import queue
import platform
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter import filedialog, simpledialog
from typing import Any

from jarvis import JarvisAssistant, LocalChat, ROOT, SpeechOutput, asset_path, load_config
from memory import MemoryStore
from desktop_settings import load_settings, save_settings, set_startup_enabled
from hotkeys import GlobalHotkeys, tkinter_sequence
from hud import HudController
from app_paths import user_data_root
from themes import DEFAULT_THEME, get_theme
from theme_manager import load_themes
from voices import VOICE_STYLES, discover_voices, find_voice_id
from permissions import add_approved_app
from music_player import LocalMusicPlayer
from skill_catalog import install_skill as install_catalog_skill
from voicepacks import (VOICE_CHOICES, VOICE_LABELS, configure_voice_data, download_voice_pack,
                        ensure_voice_runtime, is_voice_pack_installed, voice_pack_paths)

BG = "#0b1018"
PANEL = "#111a26"
PANEL_2 = "#172333"
BORDER = "#26364a"
TEXT = "#e8eef7"
MUTED = "#8fa1b7"
CYAN = "#69d9ff"
GREEN = "#56d6a2"
USER_BUBBLE = "#172b40"
BOT_BUBBLE = "#131f2c"


class JarvisDesktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JARVIS LOCAL  |  Personal assistant")
        self.root.geometry("1120x760")
        self.root.minsize(820, 600)
        self.root.configure(bg=BG)
        self.desktop_settings = load_settings()
        self.themes = load_themes()
        if self.desktop_settings.get("theme") not in self.themes:
            self.desktop_settings["theme"] = DEFAULT_THEME
        self.theme_colors = get_theme(self.desktop_settings["theme"])
        self._set_theme_constants(self.theme_colors)
        self.root.configure(bg=BG)
        self.base_tk_scale = float(self.root.tk.call("tk", "scaling"))
        self._apply_ui_scale()

        self.config = load_config()
        self.memory = MemoryStore(user_data_root() / "data" / "jarvis_memory.sqlite3")
        self.voice_pack_dir = user_data_root() / "models" / "kokoro"
        self.voice_runtime_dir = user_data_root() / "models" / "kokoro-runtime"
        if self.voice_runtime_dir.is_dir() and str(self.voice_runtime_dir) not in sys.path:
            sys.path.insert(0, str(self.voice_runtime_dir))
        voice_runtime_ready = False
        if self.voice_runtime_dir.is_dir():
            try:
                voice_runtime_ready = configure_voice_data(self.voice_runtime_dir)
            except Exception as exc:
                print(f"[optional local voice resources unavailable: {exc}]", file=sys.stderr)
        self.voice_runtime_ready = voice_runtime_ready
        neural_model_path, neural_voices_path = voice_pack_paths(self.voice_pack_dir)
        voice_pack_ready = is_voice_pack_installed(self.voice_pack_dir) and voice_runtime_ready
        self.sessions = self.memory.list_sessions()
        self.current_session_id = self.sessions[0]["id"]
        self.chat: LocalChat | None = None
        if self.config.get("use_local_chat", False):
            self.chat = LocalChat(
                asset_path(str(self.config.get("local_model_path", "models/Qwen2.5-3B-Instruct-Q4_K_M.gguf"))),
                int(self.config.get("chat_history_turns", 6)),
                int(self.config.get("model_threads", 4)),
            )
        speech = SpeechOutput(
            enabled=True,
            on_speak=lambda _text: self.root.after(
                0, self._set_status, "JARVIS IS SPEAKING", GREEN
            ),
            on_speech_state=lambda active: self.root.after(0, self._set_speaking, active),
            voice_id=str(self.desktop_settings.get("voice_id", "")),
            voice_style=str(self.desktop_settings.get("voice_style", "Balanced")),
            neural_model_path=neural_model_path,
            neural_voices_path=neural_voices_path,
            neural_voice_id=(str(self.desktop_settings.get("neural_voice_id", ""))
                             if voice_pack_ready else ""),
        )
        self.speech = speech
        self.installed_voices = discover_voices(speech.engine) if speech.engine else []
        self.assistant = JarvisAssistant(self.config, speech, chat=self.chat)
        self.assistant.desktop_settings = self.desktop_settings
        self.assistant.refresh_user_skills()
        self.assistant.local_actions = {
            "choose_file_to_learn": lambda: self.root.after(0, self._choose_file_to_learn),
            "set_theme": self._set_theme_from_voice,
            "set_voice": self._set_voice_from_voice,
            "set_timer": self._set_timer,
            "cancel_timers": self._cancel_timers,
            "search_web": self.assistant._search_web,
            "install_skill": self._install_catalog_skill,
            "music_player": LocalMusicPlayer(self.desktop_settings.get("music_folder", "")),
        }
        self.timers: dict[str, str] = {}
        self.timer_serial = 0
        self.turn_lock = threading.Lock()
        self.listen_thread: threading.Thread | None = None
        self.listen_stop = threading.Event()
        self.listen_mode: str | None = None
        self.busy = False
        self.speaking = False
        self._build_ui()
        self._refresh_sessions()
        self._load_session(self.current_session_id)
        self.hud = HudController(
            self.root, self.desktop_settings, self.assistant.skills,
            on_voice=self._hotkey_voice, on_chat=self._show_chat,
            on_settings=self._open_settings, on_mode=self._save_mode,
            on_skill_toggle=self._toggle_skill_from_node,
            state_getter=self._hud_state,
        )
        self.hotkeys = self._start_hotkeys()
        self._local_hotkey_sequences: list[str] = []
        self._bind_local_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(180, self._restore_mode)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=39, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#1b3550")], foreground=[("selected", TEXT)])
        style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=BG, bordercolor=BG)

        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        sidebar = tk.Frame(outer, bg=PANEL, width=270, highlightbackground=BORDER, highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=PANEL)
        brand.pack(fill="x", padx=18, pady=(18, 16))
        tk.Label(brand, text="J", bg=PANEL, fg=CYAN, font=("Segoe UI", 27, "bold")).pack(side="left")
        brand_text = tk.Frame(brand, bg=PANEL)
        brand_text.pack(side="left", padx=(10, 0))
        tk.Label(brand_text, text="J.A.R.V.I.S.", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(brand_text, text="PERSONAL SYSTEM", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(1, 0))

        self._button(sidebar, "+   New conversation", self._new_session, primary=True).pack(
            fill="x", padx=14, pady=(0, 16), ipady=8
        )
        tk.Label(sidebar, text="YOUR CONVERSATIONS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=17, pady=(0, 8))
        self.session_list = ttk.Treeview(sidebar, columns=("title",), show="", selectmode="browse")
        self.session_list.column("title", anchor="w", width=230)
        self.session_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.session_list.bind("<<TreeviewSelect>>", self._on_select_session)

        search_row = tk.Frame(sidebar, bg=PANEL)
        search_row.pack(fill="x", padx=12, pady=(0, 12))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_row, textvariable=self.search_var, bg=BG, fg=TEXT,
                                     insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(4, 7))
        self.search_entry.bind("<Return>", lambda _event: self._search_memory())
        self._button(search_row, "Search", self._search_memory).pack(side="right", ipady=5)

        self._button(sidebar, "About · Open Source (MIT)", self._open_about).pack(
            fill="x", padx=12, pady=(0, 12), ipady=4
        )

        main = tk.Frame(outer, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=(16, 0))

        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", pady=(0, 14))
        self.chat_title = tk.Label(header, text="JARVIS", bg=BG, fg=TEXT,
                                   font=("Segoe UI", 17, "bold"))
        self.chat_title.pack(side="left")
        self.status = tk.Label(header, text="●  LOCAL & PRIVATE", bg=BG, fg=GREEN,
                               font=("Segoe UI", 9, "bold"))
        self.status.pack(side="right", pady=(5, 0))
        mode_menu = tk.Menu(self.root, tearoff=False, bg=PANEL_2, fg=TEXT,
                            activebackground="#1d4059", activeforeground=CYAN)
        mode_menu.add_command(label="Everyday desktop", command=self._show_everyday)
        mode_menu.add_command(label="Floating HUD overlay", command=self._show_overlay)
        mode_menu.add_command(label="Fullscreen command center", command=self._show_command_center)
        mode_button = tk.Menubutton(header, text="Display modes ▾", menu=mode_menu, bg=PANEL_2,
                                    fg=TEXT, activebackground="#1d4059", activeforeground=CYAN,
                                    relief="flat", padx=11, pady=6, font=("Segoe UI", 9, "bold"))
        mode_button.pack(side="right", padx=(0, 8), pady=(1, 0))
        self._button(header, "Settings", self._open_settings).pack(side="right", padx=(0, 8), ipady=5)
        self._button(header, "Skills", self._open_skills).pack(side="right", padx=(0, 12), ipady=5)

        voice_panel = tk.Frame(main, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        voice_panel.pack(fill="x", pady=(0, 12))
        voice_copy = tk.Frame(voice_panel, bg=PANEL)
        voice_copy.pack(side="left", fill="x", expand=True, padx=16, pady=10)
        tk.Label(voice_copy, text="TALK TO JARVIS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(voice_copy, text="On-device voice chat · tap to start, tap again to stop", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        self.primary_voice_button = tk.Button(
            voice_panel, text="◉  START VOICE CHAT", command=self._toggle_voice_chat,
            bg="#143a50", fg=CYAN, activebackground="#1d4059", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 10, "bold"), padx=18, pady=11,
        )
        self.primary_voice_button.pack(side="right", padx=12, pady=9)

        transcript_panel = tk.Frame(main, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        transcript_panel.pack(fill="both", expand=True)
        self.transcript = tk.Text(
            transcript_panel, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
            wrap="word", padx=22, pady=18, spacing1=3, spacing3=7,
            font=("Segoe UI", 11), state="disabled",
        )
        scrollbar = ttk.Scrollbar(transcript_panel, orient="vertical", command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.transcript.pack(side="left", fill="both", expand=True)
        self.transcript.tag_configure("user_name", foreground=CYAN, font=("Segoe UI", 9, "bold"), justify="right")
        self.transcript.tag_configure("assistant_name", foreground=GREEN, font=("Segoe UI", 9, "bold"))
        self.transcript.tag_configure("user_body", foreground=TEXT, background=USER_BUBBLE,
                                      lmargin1=90, lmargin2=90, rmargin=5, spacing1=7, spacing3=15)
        self.transcript.tag_configure("assistant_body", foreground=TEXT, background=BOT_BUBBLE,
                                      lmargin1=5, lmargin2=5, rmargin=90, spacing1=7, spacing3=15)
        self.transcript.tag_configure("welcome", foreground=MUTED, justify="center", spacing1=18, spacing3=18)

        self._append_message("assistant", "Systems online. I'm JARVIS, running locally on this computer.")
        self._append_message(
            "assistant",
            "Type a message, use Start mic with the ‘Jarvis’ wake word, or choose Voice Chat for a continuous spoken conversation.",
        )

        compose = tk.Frame(main, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        compose.pack(fill="x", pady=(13, 0))
        self.message_entry = tk.Entry(compose, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                                      font=("Segoe UI", 11))
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(15, 8), pady=14)
        self.message_entry.insert(0, "Message JARVIS…")
        self.message_entry.bind("<FocusIn>", self._clear_placeholder)
        self.message_entry.bind("<Return>", self._send_from_key)
        self.mic_button = self._button(compose, "Start mic", self._toggle_mic)
        self.mic_button.pack(side="right", padx=5, pady=7, ipady=8)
        self.voice_chat_button = self._button(compose, "Voice Chat", self._toggle_voice_chat, primary=True)
        self.voice_chat_button.pack(side="right", padx=5, pady=7, ipady=8)
        self.send_button = self._button(compose, "Send", self._send_message, primary=True)
        self.send_button.pack(side="right", padx=(5, 9), pady=7, ipady=8)
        tk.Label(main, text="Saved only on this device  ·  History stays local  ·  Voice is the primary control",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(9, 0))

    def _button(self, parent: tk.Widget, text: str, command: Any, primary: bool = False) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command,
            bg=("#143a50" if primary else PANEL_2), fg=(CYAN if primary else TEXT),
            activebackground="#1d4059", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"), padx=12, pady=6,
        )

    def _open_about(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("About JARVIS Local")
        window.geometry("560x360")
        window.minsize(460, 320)
        window.configure(bg=BG)
        window.transient(self.root)
        tk.Label(window, text="J.A.R.V.I.S. LOCAL", bg=BG, fg=CYAN,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(window, text="Open-source desktop assistant · MIT License", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=22, pady=(0, 14))
        policy = (
            "You may fork and modify JARVIS under the MIT License; retain its notice. "
            "The maintainer reviews addons before they are included in the official catalog or releases. "
            "Forks and modified builds must not be presented as official or endorsed. "
            "Project guidance does not override the redistribution rights granted by MIT."
        )
        tk.Label(window, text=policy, bg=BG, fg=TEXT, wraplength=510,
                 justify="left", font=("Segoe UI", 10)).pack(fill="x", padx=22, pady=(0, 14))
        tk.Label(window, text="Offline: source and policy documents are included with this app. "
                 "Local addons run with your account's OS permissions.", bg=BG, fg=MUTED,
                 wraplength=510, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=22)
        controls = tk.Frame(window, bg=BG)
        controls.pack(fill="x", padx=18, pady=18)
        for filename, label in (("LICENSE", "MIT License"), ("TERMS_OF_USE.md", "Terms of Use"),
                                ("CONTRIBUTING.md", "Addon review policy"),
                                ("THIRD_PARTY_NOTICES.md", "Third-party notices")):
            self._button(controls, label,
                         lambda name=filename, title=label: self._open_project_document(name, title)).pack(
                             side="left", padx=3, ipady=4
                         )

    def _open_project_document(self, filename: str, title: str) -> None:
        try:
            text = asset_path(filename).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(title, f"The bundled document could not be opened: {exc}", parent=self.root)
            return
        window = tk.Toplevel(self.root)
        window.title(f"JARVIS Local · {title}")
        window.geometry("760x640")
        window.configure(bg=BG)
        viewer = tk.Text(window, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         relief="flat", padx=18, pady=16, font=("Segoe UI", 10))
        scroll = ttk.Scrollbar(window, orient="vertical", command=viewer.yview)
        viewer.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        viewer.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        viewer.insert("1.0", text)
        viewer.configure(state="disabled")

    def _append_message(self, role: str, content: str) -> None:
        self.transcript.configure(state="normal")
        if role == "user":
            self.transcript.insert("end", "YOU\n", "user_name")
            self.transcript.insert("end", content.strip() + "\n\n", "user_body")
        else:
            self.transcript.insert("end", "JARVIS\n", "assistant_name")
            self.transcript.insert("end", content.strip() + "\n\n", "assistant_body")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _clear_transcript(self) -> None:
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")

    def _refresh_sessions(self) -> None:
        self.sessions = self.memory.list_sessions()
        self.session_list.delete(*self.session_list.get_children())
        for session in self.sessions:
            title = session["title"] or "New conversation"
            preview = session.get("preview") or ""
            label = title if len(title) < 31 else title[:28] + "…"
            if preview and title == "New conversation":
                label = preview[:30] + ("…" if len(preview) > 30 else "")
            self.session_list.insert("", "end", iid=session["id"], values=(label,))
        if self.current_session_id in {item["id"] for item in self.sessions}:
            self.session_list.selection_set(self.current_session_id)
            self.session_list.see(self.current_session_id)

    def _load_session(self, session_id: str) -> None:
        self.current_session_id = session_id
        self._clear_transcript()
        history = self.memory.messages(session_id)
        if history:
            for item in history:
                self._append_message(item["role"], item["content"])
        else:
            self._append_message("assistant", "A new conversation. What would you like to do?")
        session = next((item for item in self.sessions if item["id"] == session_id), None)
        self.chat_title.configure(text=(session["title"] if session else "JARVIS")[:48])

    def _on_select_session(self, _event: Any = None) -> None:
        selection = self.session_list.selection()
        if selection and selection[0] != self.current_session_id:
            self._load_session(selection[0])

    def _new_session(self) -> None:
        session_id = self.memory.create_session()
        self.current_session_id = session_id
        self._refresh_sessions()
        self._load_session(session_id)

    def _clear_placeholder(self, _event: Any = None) -> None:
        if self.message_entry.get() == "Message JARVIS…":
            self.message_entry.delete(0, "end")

    def _send_from_key(self, _event: Any = None) -> str:
        self._send_message()
        return "break"

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_button.configure(state=("disabled" if busy else "normal"))
        if busy:
            self.status.configure(text="●  THINKING LOCALLY", fg=CYAN)
        elif self.listen_mode == "voice_chat":
            self.status.configure(text="●  VOICE CHAT · LISTENING", fg=CYAN)
        elif self.listen_mode == "wake":
            self.status.configure(text="●  LISTENING FOR JARVIS", fg=CYAN)
        else:
            self.status.configure(text="●  LOCAL & PRIVATE", fg=GREEN)

    def _send_message(self) -> None:
        text = self.message_entry.get().strip()
        if not text or text == "Message JARVIS…" or self.busy:
            return
        self.message_entry.delete(0, "end")
        self._append_message("user", text)
        self._set_busy(True)
        session_id = self.current_session_id
        threading.Thread(target=self._process_turn, args=(text, session_id, False), daemon=True).start()

    def _process_turn(self, text: str, session_id: str, require_wake: bool) -> None:
        try:
            with self.turn_lock:
                self.assistant.bind_memory(self.memory, session_id)
                response = self.assistant.handle_text(text, require_wake=require_wake)
            if response is not None:
                if self.current_session_id == session_id:
                    self.root.after(0, self._append_message, "assistant", response)
                self.root.after(0, self._refresh_sessions)
            elif require_wake and text.strip():
                # Ignore background speech without the wake phrase; never persist it.
                pass
        except Exception as exc:
            self.root.after(0, self._append_message, "assistant", f"I ran into a local error: {exc}")
        finally:
            self.root.after(0, self._set_busy, False)

    def _toggle_mic(self) -> None:
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_stop.set()
            self.mic_button.configure(text="Stopping…", state="disabled")
            return
        self._start_listener("wake")

    def _toggle_voice_chat(self) -> None:
        if self.listen_thread and self.listen_thread.is_alive():
            restart_as_voice_chat = self.listen_mode != "voice_chat"
            self.listen_stop.set()
            self.voice_chat_button.configure(text="Stopping…", state="disabled")
            self.primary_voice_button.configure(text="◉  SWITCHING TO VOICE CHAT…", state="disabled")
            if restart_as_voice_chat:
                self._start_voice_chat_when_stopped = True
            return
        self._start_listener("voice_chat")

    def _start_listener(self, mode: str) -> None:
        self.assistant.stop_requested = False
        self.listen_stop.clear()
        self.listen_mode = mode
        self.mic_button.configure(text="Stop mic" if mode == "wake" else "Mic ready", state="normal")
        self.voice_chat_button.configure(text="End Voice Chat" if mode == "voice_chat" else "Voice Chat",
                                         state="normal")
        self.primary_voice_button.configure(
            text=("◉  END VOICE CHAT" if mode == "voice_chat" else "◉  VOICE CHAT READY"), state="normal"
        )
        status = "VOICE CHAT · LISTENING" if mode == "voice_chat" else "LISTENING FOR JARVIS"
        self.status.configure(text=f"●  {status}", fg=CYAN)
        self.listen_thread = threading.Thread(target=self._listen_loop, args=(mode,), daemon=True)
        self.listen_thread.start()

    def _listen_loop(self, mode: str) -> None:
        model_path = asset_path(str(self.config.get("vosk_model_path", "models/vosk-model-small-en-us-0.15")))
        try:
            if not model_path.is_dir():
                raise RuntimeError("Offline speech model is missing. Rerun setup or open Settings to repair the installation.")
            import sounddevice as sd  # type: ignore
            from vosk import KaldiRecognizer, Model  # type: ignore
            model = Model(str(model_path))
            recognizer = KaldiRecognizer(model, 16000)
            audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=40)

            def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    self.root.after(0, self._set_status, f"Microphone: {status}", CYAN)
                try:
                    audio_queue.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                                   channels=1, callback=callback):
                while not self.listen_stop.is_set():
                    try:
                        audio = audio_queue.get(timeout=0.4)
                    except queue.Empty:
                        continue
                    if not recognizer.AcceptWaveform(audio):
                        continue
                    phrase = json.loads(recognizer.Result()).get("text", "").strip()
                    if not phrase:
                        continue
                    session_id = self.current_session_id
                    self.root.after(0, self._set_busy, True)
                    try:
                        response = self._process_voice_turn(
                            phrase, session_id, require_wake=(mode != "voice_chat")
                        )
                    finally:
                        self.root.after(0, self._set_busy, False)
                    if response is not None:
                        self.root.after(0, self._append_message, "user", phrase)
                        self.root.after(0, self._append_message, "assistant", response)
                        self.root.after(0, self._refresh_sessions)
                    if mode == "voice_chat" and not self.listen_stop.is_set():
                        self.root.after(0, self._set_status, "VOICE CHAT · LISTENING", CYAN)
                    # Flush captured TTS echo and reset phrase state before listening again.
                    recognizer.Reset()
                    while True:
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            break
                    if self.assistant.stop_requested:
                        self.listen_stop.set()
            self.root.after(0, self._mic_stopped)
        except Exception as exc:
            self.root.after(0, self._mic_error, str(exc))

    def _process_voice_turn(self, phrase: str, session_id: str,
                            require_wake: bool = True) -> str | None:
        with self.turn_lock:
            self.assistant.bind_memory(self.memory, session_id)
            response = self.assistant.handle_text(phrase, require_wake=require_wake)
        return response

    def _set_status(self, text: str, color: str) -> None:
        self.status.configure(text=f"●  {text.upper()}", fg=color)

    def _mic_stopped(self) -> None:
        continue_voice = bool(getattr(self, "_start_voice_chat_when_stopped", False))
        self._start_voice_chat_when_stopped = False
        self.listen_mode = None
        self.mic_button.configure(text="Start mic", state="normal")
        self.voice_chat_button.configure(text="Voice Chat", state="normal")
        self.primary_voice_button.configure(text="◉  START VOICE CHAT", state="normal")
        self.status.configure(text="●  LOCAL & PRIVATE", fg=GREEN)
        if continue_voice:
            self.root.after(150, self._start_listener, "voice_chat")

    def _mic_error(self, error: str) -> None:
        self._mic_stopped()
        messagebox.showerror("Microphone unavailable", error)

    def _search_memory(self) -> None:
        query = self.search_var.get().strip()
        if not query:
            return
        results = self.memory.search_messages(query)
        dialog = tk.Toplevel(self.root)
        dialog.title("Search conversation memory")
        dialog.geometry("720x430")
        dialog.configure(bg=BG)
        tk.Label(dialog, text=f"Saved messages matching “{query}”", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        listbox = tk.Listbox(dialog, bg=PANEL, fg=TEXT, selectbackground="#1b3550",
                             relief="flat", font=("Segoe UI", 10), activestyle="none")
        listbox.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        if not results:
            listbox.insert("end", "No saved messages matched that text.")
        for item in results:
            stamp = item["created_at"].replace("T", " ")[:16]
            preview = " ".join(item["content"].split())
            listbox.insert("end", f"{stamp}  ·  {item['title']}  ·  {item['role']}: {preview[:160]}")
        tk.Label(dialog, text="Double-click a result to open its conversation.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))

        def open_result(_event: Any = None) -> None:
            selected = listbox.curselection()
            if selected and results:
                session_id = results[selected[0]]["session_id"]
                self._refresh_sessions()
                self.session_list.selection_set(session_id)
                self._load_session(session_id)
                dialog.destroy()

        listbox.bind("<Double-Button-1>", open_result)

    def _open_skills(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("JARVIS Skills & Add-ons")
        window.geometry("620x560")
        window.minsize(500, 430)
        window.configure(bg=BG)
        tk.Label(window, text="Skills & Add-ons", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(window, text="Choose which local capabilities JARVIS can use.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 14))

        panel = tk.Frame(window, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        canvas = tk.Canvas(panel, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=PANEL)
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=550)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        choices: dict[str, tk.BooleanVar] = {}
        for skill in self.assistant.skills.list_skills():
            card = tk.Frame(content, bg=PANEL_2, padx=13, pady=10)
            card.pack(fill="x", padx=10, pady=(10, 0))
            variable = tk.BooleanVar(value=skill["enabled"])
            choices[skill["name"]] = variable
            row = tk.Frame(card, bg=PANEL_2)
            row.pack(fill="x")
            tk.Label(row, text=skill["name"].replace("_", " ").title(), bg=PANEL_2, fg=TEXT,
                     font=("Segoe UI", 11, "bold")).pack(side="left")
            tk.Checkbutton(row, text="Enabled", variable=variable, bg=PANEL_2, fg=CYAN,
                           activebackground=PANEL_2, activeforeground=TEXT, selectcolor=BG,
                           font=("Segoe UI", 9)).pack(side="right")
            tk.Label(card, text=skill["description"], bg=PANEL_2, fg=MUTED,
                     font=("Segoe UI", 9), wraplength=485, justify="left").pack(anchor="w", pady=(5, 0))
            if skill["examples"]:
                tk.Label(card, text="Try: " + "  ·  ".join(skill["examples"]), bg=PANEL_2,
                         fg=CYAN, font=("Segoe UI", 8), wraplength=485,
                         justify="left").pack(anchor="w", pady=(4, 0))

        if self.assistant.skills.load_errors:
            tk.Label(content, text="Some add-ons could not be loaded:\n" + "\n".join(self.assistant.skills.load_errors),
                     bg=PANEL, fg="#ff9c8f", font=("Segoe UI", 8), justify="left",
                     wraplength=500).pack(anchor="w", padx=14, pady=12)
        tk.Label(window, text="Add trusted *_skill.py modules to skills/ or user_skills/ and press Rescan. Integrations named *_integration.py stay unloaded until both plugin and integration permissions are enabled.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=570,
                 justify="left").pack(anchor="w", padx=22, pady=(2, 8))

        controls = tk.Frame(window, bg=BG)
        controls.pack(fill="x", padx=18, pady=(0, 16))
        tk.Button(controls, text="Rescan plugins", command=lambda: self._rescan_plugins(window),
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(controls, text="Cancel", command=window.destroy, bg=PANEL_2, fg=TEXT,
                  relief="flat", padx=18, pady=8).pack(side="right", padx=(8, 0))

        def save() -> None:
            for skill_name, variable in choices.items():
                self.assistant.skills.set_enabled(skill_name, variable.get())
            self._persist_skills()
            window.destroy()
            self.status.configure(text="●  SKILLS UPDATED", fg=GREEN)

        tk.Button(controls, text="Save skills", command=save, bg="#143a50", fg=CYAN,
                  activebackground="#1d4059", relief="flat", padx=18, pady=8,
                  font=("Segoe UI", 9, "bold")).pack(side="right")

    def _persist_skills(self) -> None:
        self.config["enabled_skills"] = sorted(self.assistant.skills.enabled)
        config_path = ROOT / "config.json"
        temporary = config_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, config_path)
        self.hud.refresh_skills()

    def _rescan_plugins(self, window: tk.Toplevel) -> None:
        window.destroy()
        self.assistant.skills.reload()
        self.assistant.skills.enabled.intersection_update(self.assistant.skills.skills)
        self.hud.refresh_skills()
        self._open_skills()

    def _toggle_skill_from_node(self, name: str) -> None:
        skill = next(item for item in self.assistant.skills.list_skills() if item["name"] == name)
        self.assistant.skills.set_enabled(name, not skill["enabled"])
        self._persist_skills()
        self.status.configure(text=f"●  {name.replace('_', ' ').upper()} {'ENABLED' if not skill['enabled'] else 'DISABLED'}",
                              fg=GREEN)

    def _apply_ui_scale(self) -> None:
        scale = float(self.desktop_settings.get("scale", 1.0))
        self.root.tk.call("tk", "scaling", self.base_tk_scale * scale)

    def _set_theme_constants(self, colors: dict[str, str]) -> None:
        global BG, PANEL, PANEL_2, BORDER, TEXT, MUTED, CYAN, GREEN, USER_BUBBLE, BOT_BUBBLE
        BG, PANEL, PANEL_2, BORDER = colors["background"], colors["panel"], colors["panel_alt"], colors["border"]
        TEXT, MUTED, CYAN, GREEN = colors["text"], colors["muted"], colors["accent"], colors["success"]
        USER_BUBBLE, BOT_BUBBLE = colors["user_bubble"], colors["bot_bubble"]
        import hud as hud_module
        hud_module.apply_theme(colors)

    def _apply_theme_name(self, name: str) -> None:
        if name not in self.themes:
            return
        old = self.theme_colors
        self.theme_colors = dict(self.themes[name])
        self._set_theme_constants(self.theme_colors)
        replacements = {
            old.get("background"): self.theme_colors["background"],
            old.get("panel"): self.theme_colors["panel"],
            old.get("panel_alt"): self.theme_colors["panel_alt"],
            old.get("border"): self.theme_colors["border"],
            old.get("text"): self.theme_colors["text"],
            old.get("muted"): self.theme_colors["muted"],
            old.get("accent"): self.theme_colors["accent"],
            old.get("success"): self.theme_colors["success"],
            old.get("user_bubble"): self.theme_colors["user_bubble"],
            old.get("bot_bubble"): self.theme_colors["bot_bubble"],
            "#143a50": self.theme_colors["accent"],
            "#1d4059": self.theme_colors["panel_alt"],
            "#1b3550": self.theme_colors["panel_alt"],
            "#ff9c8f": self.theme_colors["success"],
        }
        def recolor(widget: tk.Widget) -> None:
            for option in ("bg", "background", "fg", "foreground", "insertbackground",
                           "activebackground", "activeforeground", "selectcolor", "troughcolor"):
                try:
                    value = str(widget.cget(option))
                    if value in replacements:
                        widget.configure(**{option: replacements[value]})
                except (tk.TclError, TypeError):
                    pass
            for child in widget.winfo_children():
                recolor(child)
        recolor(self.root)
        try:
            self.transcript.tag_configure("user_name", foreground=CYAN)
            self.transcript.tag_configure("assistant_name", foreground=GREEN)
            self.transcript.tag_configure("user_body", foreground=TEXT, background=USER_BUBBLE)
            self.transcript.tag_configure("assistant_body", foreground=TEXT, background=BOT_BUBBLE)
            style = ttk.Style(self.root)
            style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT)
            style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED)
        except tk.TclError:
            pass
        if hasattr(self, "hud"):
            self.hud.apply_settings(self.desktop_settings)

    def _set_theme_from_voice(self, name: str) -> str:
        match = next((theme for theme in self.themes if theme.casefold() == name.casefold()), None)
        if not match:
            return "I couldn't find that installed theme. Available themes: " + ", ".join(self.themes)
        self.root.after(0, self._apply_theme_name, match)
        self.desktop_settings["theme"] = match
        save_settings(self.desktop_settings)
        return f"Switching the local appearance to {match}."

    def _set_voice_from_voice(self, name: str) -> str:
        styles = {profile.casefold(): profile for profile in VOICE_STYLES}
        styles.update({voice["name"].casefold(): voice["name"] for voice in self.installed_voices})
        if is_voice_pack_installed(self.voice_pack_dir) and self.voice_runtime_ready:
            styles.update({label.casefold(): f"Neural · {label}" for label in VOICE_CHOICES})
        match = styles.get(name.casefold())
        if not match:
            return "I couldn't find that installed voice. Available styles and local voices: " + ", ".join(styles.values())
        self.root.after(0, self._apply_voice_name, match)
        return f"Switching to the local {match} voice profile."

    def _apply_voice_name(self, name: str) -> None:
        neural_voice_id = next(
            (voice_id for label, (voice_id, _lang) in VOICE_CHOICES.items()
             if name == f"Neural · {label}"), ""
        )
        profile = name if name in VOICE_STYLES else str(self.desktop_settings.get("voice_style", "Balanced"))
        voice = next((item for item in self.installed_voices if item["name"] == name), None)
        self.desktop_settings["voice_style"] = profile
        self.desktop_settings["voice_id"] = voice["id"] if voice else ""
        self.desktop_settings["neural_voice_id"] = neural_voice_id or str(
            self.desktop_settings.get("neural_voice_id", "") if name in VOICE_STYLES else ""
        )
        self.speech.set_voice(self.desktop_settings["voice_id"], profile)
        if neural_voice_id or name not in VOICE_STYLES:
            self.speech.set_neural_voice(neural_voice_id)
        save_settings(self.desktop_settings)
        self.status.configure(text=f"●  LOCAL VOICE: {name.upper()}", fg=GREEN)

    def _import_theme(self, selector: ttk.Combobox | None = None) -> None:
        source = filedialog.askopenfilename(
            title="Import a local JARVIS theme", filetypes=[("Theme JSON", "*.json")]
        )
        if not source:
            return
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            from theme_manager import save_theme
            name = str(data.get("name", Path(source).stem))
            save_theme(name, data)
            self.themes = load_themes()
            if selector is not None:
                selector.configure(values=tuple(self.themes))
            messagebox.showinfo("Theme imported", f"{name} is ready to select in Settings.")
        except Exception as exc:
            messagebox.showerror("Theme import failed", str(exc))

    def _choose_workspace(self, variable: tk.StringVar | None = None) -> None:
        folder = filedialog.askdirectory(title="Choose JARVIS code workspace")
        if folder:
            if variable is not None:
                variable.set(folder)
            self.desktop_settings["workspace_dir"] = str(Path(folder).resolve())
            save_settings(self.desktop_settings)

    def _choose_music_folder(self, variable: tk.StringVar | None = None) -> None:
        folder = filedialog.askdirectory(title="Choose the local folder containing your music")
        if not folder:
            return
        resolved = str(Path(folder).resolve())
        if variable is not None:
            variable.set(resolved)
        self.desktop_settings["music_folder"] = resolved
        player = self.assistant.local_actions.get("music_player")
        if player:
            player.set_folder(resolved)
        save_settings(self.desktop_settings)

    def _install_catalog_skill(self, name: str) -> str:
        """Install a hash-pinned bundled addon; this function does no Tk calls on the worker."""
        message, installed_path = install_catalog_skill(name)
        if installed_path is None:
            return message
        from skill_catalog import normalize_name
        canonical = normalize_name(name)
        if canonical is None:
            return message
        installed = set(self.desktop_settings.get("installed_catalog_skills", []))
        installed.add(canonical)
        self.desktop_settings["installed_catalog_skills"] = sorted(installed)
        save_settings(self.desktop_settings)
        self.assistant.refresh_user_skills()
        if canonical in self.assistant.skills.skills:
            self.assistant.skills.set_enabled(canonical, True)
            self.config["enabled_skills"] = sorted(self.assistant.skills.enabled)
            config_path = ROOT / "config.json"
            temporary = config_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, config_path)
        if hasattr(self, "hud"):
            self.root.after(0, self._refresh_plugin_tree)
        return message.replace("ready to enable in Skills", "installed and enabled")

    def _refresh_plugin_tree(self) -> None:
        if not hasattr(self, "hud"):
            return
        self.hud.skills = self.assistant.skills
        self.hud.refresh_skills()

    def _add_approved_app(self, approved_apps: dict[str, str] | None = None,
                          app_list: tk.Listbox | None = None) -> None:
        if platform.system() == "Darwin":
            target = filedialog.askdirectory(title="Select the app bundle to approve", mustexist=True)
        else:
            target = filedialog.askopenfilename(
                title="Select an app executable/launcher to approve",
                filetypes=[("Applications", "*.exe *.lnk *.desktop"), ("All files", "*.*")],
            )
        if not target:
            return
        name = simpledialog.askstring("Approve application", "Voice command name (for example, ‘calculator’):", parent=self.root)
        if not name:
            return
        try:
            holder = self.desktop_settings if approved_apps is None else {"approved_apps": approved_apps}
            add_approved_app(holder, name, target)
            if app_list is not None:
                app_list.delete(0, "end")
                for app_name, app_path in sorted(holder["approved_apps"].items()):
                    app_list.insert("end", f"{app_name}  ·  {app_path}")
            else:
                save_settings(self.desktop_settings)
            self.status.configure(text=f"●  APPROVED APP ADDED: {name.upper()}", fg=GREEN)
        except Exception as exc:
            messagebox.showerror("App approval failed", str(exc))

    def _choose_file_to_learn(self) -> None:
        if not self.desktop_settings.get("allow_local_file_learning", False):
            messagebox.showwarning("File learning blocked", "Enable ‘Learn from files I explicitly select’ in Settings first.")
            return
        path = filedialog.askopenfilename(
            title="Choose a text or source file to remember locally",
            filetypes=[("Readable text and source", "*.txt *.md *.py *.js *.ts *.json *.yaml *.yml *.csv *.html *.css *.xml *.log"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > 200_000:
                raise ValueError("The selected file exceeds the 200 KB limit.")
            content = source.read_text(encoding="utf-8")
            parts = self.memory.save_knowledge_document(source.name, content)
            messagebox.showinfo("Learned locally", f"Added {source.name} to local memory ({parts} part(s)).\n\nThe file contents remain on this device and may be used as context by the local model.")
            self.status.configure(text=f"●  LEARNED LOCALLY: {source.name.upper()}", fg=GREEN)
        except Exception as exc:
            messagebox.showerror("Could not learn file", str(exc))

    def _set_timer(self, seconds: float, label: str) -> str:
        self.root.after(0, self._schedule_timer_ui, seconds, label)
        return f"Timer set for {label}. I'll alert you locally when it's done."

    def _schedule_timer_ui(self, seconds: float, label: str) -> None:
        self.timer_serial += 1
        timer_id = f"timer-{self.timer_serial}"
        handle = self.root.after(int(seconds * 1000), self._timer_finished, timer_id, label)
        self.timers[timer_id] = handle

    def _timer_finished(self, timer_id: str, label: str) -> None:
        self.timers.pop(timer_id, None)
        self.status.configure(text=f"●  TIMER COMPLETE: {label.upper()}", fg=GREEN)
        self._append_message("assistant", f"Timer complete: {label}.")
        threading.Thread(target=self.speech.say, args=(f"Your timer for {label} is complete.",), daemon=True).start()

    def _cancel_timers(self) -> str:
        self.root.after(0, self._cancel_timers_ui)
        return "I cancelled all active timers."  # Timer callback runs on the UI thread.

    def _cancel_timers_ui(self) -> None:
        for handle in tuple(self.timers.values()):
            try:
                self.root.after_cancel(handle)
            except tk.TclError:
                pass
        self.timers.clear()

    def _open_settings(self) -> None:
        owner = self.hud.overlay if self.hud.overlay and self.hud.overlay.winfo_exists() else (
            self.hud.center if self.hud.center and self.hud.center.winfo_exists() else self.root
        )
        window = tk.Toplevel(owner)
        window.title("JARVIS Desktop Settings")
        window.geometry("680x790")
        window.minsize(570, 630)
        window.configure(bg=BG)
        window.transient(owner)
        tk.Label(window, text="HUD Settings", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(18, 3))
        tk.Label(window, text="Tune the desktop to your display and hardware.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 12))

        body_shell = tk.Frame(window, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        body_shell.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        body_canvas = tk.Canvas(body_shell, bg=PANEL, highlightthickness=0)
        body_scroll = ttk.Scrollbar(body_shell, orient="vertical", command=body_canvas.yview)
        body = tk.Frame(body_canvas, bg=PANEL)
        body_window = body_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: body_canvas.configure(scrollregion=body_canvas.bbox("all")))
        body_canvas.bind("<Configure>", lambda event: body_canvas.itemconfigure(body_window, width=event.width))
        body_canvas.configure(yscrollcommand=body_scroll.set)
        body_scroll.pack(side="right", fill="y")
        body_canvas.pack(side="left", fill="both", expand=True)
        scale_value = tk.DoubleVar(value=self.desktop_settings["scale"])
        opacity_value = tk.DoubleVar(value=self.desktop_settings["opacity"])
        animations_value = tk.BooleanVar(value=self.desktop_settings.get("animations_enabled", True))
        topmost_value = tk.BooleanVar(value=self.desktop_settings.get("always_on_top", True))
        click_value = tk.BooleanVar(value=self.desktop_settings.get("click_through", False))
        startup_value = tk.BooleanVar(value=self.desktop_settings.get("launch_on_startup", False))
        performance_value = tk.StringVar(value=self.desktop_settings.get("animation_performance", "medium"))
        selected_theme = tk.StringVar(value=self.desktop_settings.get("theme", DEFAULT_THEME))
        voice_styles = tk.StringVar(value=self.desktop_settings.get("voice_style", "Balanced"))
        installed_voice_names = [item["name"] for item in self.installed_voices]
        voice_options = ["System default"] + installed_voice_names
        active_voice_id = self.desktop_settings.get("voice_id", "")
        active_voice_name = next((item["name"] for item in self.installed_voices
                                  if item["id"] == active_voice_id), "System default")
        saved_neural_id = str(self.desktop_settings.get("neural_voice_id", ""))
        if is_voice_pack_installed(self.voice_pack_dir) and self.voice_runtime_ready:
            voice_options.extend(f"Neural · {label}" for label in VOICE_CHOICES)
            if saved_neural_id in VOICE_LABELS:
                active_voice_name = f"Neural · {VOICE_LABELS[saved_neural_id]}"
        selected_voice = tk.StringVar(value=active_voice_name)
        permission_values = {
            key: tk.BooleanVar(value=bool(self.desktop_settings.get(key, False)))
            for key in ("allow_app_launching", "allow_internet_search", "allow_skill_installation",
                        "allow_local_music", "allow_workspace_writes", "allow_local_file_learning",
                        "allow_user_plugins", "allow_external_integrations")
        }
        workspace_value = tk.StringVar(value=str(self.desktop_settings.get("workspace_dir", "")))
        music_folder_value = tk.StringVar(value=str(self.desktop_settings.get("music_folder", "")))
        browser_engine_value = tk.StringVar(value=str(self.desktop_settings.get("browser_search_engine", "Google")))

        def section(title: str) -> None:
            tk.Label(body, text=title.upper(), bg=PANEL, fg=CYAN,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(14, 5))

        section("Interface")
        self._setting_scale(body, "UI scale", scale_value, .65, 1.5, "×")
        self._setting_scale(body, "Overlay opacity", opacity_value, .45, 1.0, "%", percent=True)
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", padx=14, pady=(8, 3))
        tk.Label(row, text="Animation detail", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Combobox(row, textvariable=performance_value, values=("low", "medium", "high"),
                     state="readonly", width=11).pack(side="right")
        self._setting_check(body, "Enable reactive animations", animations_value)
        self._setting_check(body, "Keep the HUD above other windows", topmost_value)
        hotkeys_available = bool(getattr(self.hotkeys, "listener", None))
        self._setting_check(body, "Click-through overlay (Windows; use hotkey to restore)", click_value,
                            enabled=(platform.system() == "Windows" and hotkeys_available))
        self._setting_check(body, "Launch JARVIS when I sign in", startup_value)

        section("Themes & offline voices")
        theme_row = tk.Frame(body, bg=PANEL); theme_row.pack(fill="x", padx=14, pady=3)
        tk.Label(theme_row, text="Appearance theme", bg=PANEL, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        theme_box = ttk.Combobox(theme_row, textvariable=selected_theme,
                                 values=tuple(self.themes), state="readonly", width=22)
        theme_box.pack(side="right")
        tk.Button(body, text="Import local theme JSON…", command=lambda: self._import_theme(theme_box),
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=10, pady=5).pack(anchor="e", padx=14, pady=(2, 4))
        if not self.speech.engine:
            tk.Label(body, text="No local TTS engine is currently available on this OS.",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=15, pady=2)
        voice_row = tk.Frame(body, bg=PANEL); voice_row.pack(fill="x", padx=14, pady=3)
        tk.Label(voice_row, text="Installed local voice", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        voice_box = ttk.Combobox(voice_row, textvariable=selected_voice, values=voice_options,
                                 state="readonly", width=26)
        voice_box.pack(side="right")
        voice_files_ready = is_voice_pack_installed(self.voice_pack_dir)
        voice_state = ("Ready · 11 included choices" if voice_files_ready and self.voice_runtime_ready
                       else "Files present · runtime/data incomplete" if voice_files_ready
                       else "Not installed · download ~146 MB")
        self._model_row(body, "Enhanced local neural voices", voice_state,
                        lambda: self._download_voice_pack(voice_box))
        tk.Label(body, text="Install downloads ~146 MB of model files from Hugging Face, runtime packages from PyPI, "
                 "and small English tokenizer resources from NLTK data. "
                 "This starts only when you press Install. Speech is synthesized on this PC; spoken text is not uploaded. "
                 "See Third-party notices.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=545,
                 justify="left").pack(anchor="w", padx=15, pady=(0, 4))
        profile_row = tk.Frame(body, bg=PANEL); profile_row.pack(fill="x", padx=14, pady=3)
        tk.Label(profile_row, text="Speaking style", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Combobox(profile_row, textvariable=voice_styles, values=tuple(VOICE_STYLES),
                     state="readonly", width=16).pack(side="right")

        section("Security & permissions")
        tk.Label(body, text="Everything is off until you opt in. Python add-ons run with this account's OS privileges; enabling them is not a sandbox.",
                 bg=PANEL, fg="#ffc46b", font=("Segoe UI", 8), wraplength=545,
                 justify="left").pack(anchor="w", padx=15, pady=(0, 5))
        self._setting_check(body, "Allow launching approved apps", permission_values["allow_app_launching"])
        self._setting_check(body, "Allow explicitly requested web searches (query sent to search provider)",
                            permission_values["allow_internet_search"])
        browser_row = tk.Frame(body, bg=PANEL); browser_row.pack(fill="x", padx=14, pady=3)
        tk.Label(browser_row, text="Open search in default browser", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Combobox(browser_row, textvariable=browser_engine_value,
                     values=("Google", "Bing", "DuckDuckGo"), state="readonly", width=18).pack(side="right")
        tk.Label(body, text="The app retrieves short Bing result snippets; it never fetches full pages. Only the explicit query is sent. Personal-file, chat-history, and sensitive details are not attached.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=545, justify="left").pack(anchor="w", padx=15, pady=(0, 4))
        self._setting_check(body, "Allow installing reviewed bundled skills by voice command",
                            permission_values["allow_skill_installation"])
        self._setting_check(body, "Allow local music playback from my chosen folder",
                            permission_values["allow_local_music"])
        music_row = tk.Frame(body, bg=PANEL); music_row.pack(fill="x", padx=14, pady=4)
        tk.Label(music_row, text="Local music folder", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(music_row, textvariable=music_folder_value, bg=BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", width=35).pack(side="left", padx=8, ipady=4, fill="x", expand=True)
        tk.Button(music_row, text="Choose…", command=lambda: self._choose_music_folder(music_folder_value),
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=9, pady=4).pack(side="right")
        self._setting_check(body, "Allow code writes to chosen workspace", permission_values["allow_workspace_writes"])
        self._setting_check(body, "Learn from files I explicitly select", permission_values["allow_local_file_learning"])
        self._setting_check(body, "Allow user-installed Python skill plugins", permission_values["allow_user_plugins"])
        self._setting_check(body, "Allow third-party/local app integrations", permission_values["allow_external_integrations"])
        workspace_row = tk.Frame(body, bg=PANEL); workspace_row.pack(fill="x", padx=14, pady=4)
        tk.Label(workspace_row, text="Approved code workspace", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(workspace_row, textvariable=workspace_value, bg=BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", width=35).pack(side="left", padx=8, ipady=4, fill="x", expand=True)
        tk.Button(workspace_row, text="Choose…", command=lambda: self._choose_workspace(workspace_value),
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=9, pady=4).pack(side="right")
        app_row = tk.Frame(body, bg=PANEL); app_row.pack(fill="x", padx=14, pady=5)
        tk.Label(app_row, text="Approved applications", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(app_row, text="Add app…", command=lambda: self._add_approved_app(approved_apps, app_list),
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=10, pady=5).pack(side="right")
        app_list = tk.Listbox(body, bg=BG, fg=MUTED, relief="flat", height=3,
                              selectbackground="#1b3550", font=("Segoe UI", 8))
        app_list.pack(fill="x", padx=14, pady=(1, 4))
        approved_apps = dict(self.desktop_settings.get("approved_apps", {}))
        for app_name, app_path in sorted(approved_apps.items()):
            app_list.insert("end", f"{app_name}  ·  {app_path}")
        def remove_approved_app() -> None:
            selected = app_list.curselection()
            entries = sorted(approved_apps.items())
            if selected and selected[0] < len(entries):
                name, _path = entries[selected[0]]
                approved_apps.pop(name, None)
                app_list.delete(selected[0])
        tk.Button(body, text="Remove selected app", command=remove_approved_app,
                  bg=PANEL_2, fg=TEXT, relief="flat", padx=9, pady=4).pack(anchor="e", padx=14, pady=(0, 5))

        section("On-device models")
        speech_path = asset_path(str(self.config.get("vosk_model_path", "models/vosk-model-small-en-us-0.15")))
        chat_path = asset_path(str(self.config.get("local_model_path", "models/Qwen2.5-3B-Instruct-Q4_K_M.gguf")))
        self._model_row(body, "Voice recognition", "Ready" if speech_path.is_dir() else "Missing · ~40 MB",
                        self._download_speech_model if not speech_path.is_dir() else None)
        self._model_row(body, "Local AI chat", "Ready" if chat_path.is_file() else "Missing · ~1.93 GB",
                        self._download_chat_model if not chat_path.is_file() else None)

        section("Global shortcuts")
        shortcuts = {}
        for key, label in (("hotkey_overlay", "Toggle floating overlay"),
                           ("hotkey_command", "Toggle command center"),
                           ("hotkey_everyday", "Return to everyday mode"),
                           ("hotkey_voice", "Toggle continuous Voice Chat")):
            item = tk.Frame(body, bg=PANEL)
            item.pack(fill="x", padx=14, pady=3)
            tk.Label(item, text=label, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 9)).pack(side="left")
            entry = tk.Entry(item, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", width=18)
            entry.insert(0, str(self.desktop_settings.get(key, "")))
            entry.pack(side="right", ipady=5)
            shortcuts[key] = entry
        tk.Label(body, text="Examples: ctrl+alt+o  ·  ctrl+shift+j  ·  alt+f10",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=15, pady=(4, 8))

        controls = tk.Frame(window, bg=BG)
        controls.pack(fill="x", padx=18, pady=(0, 16))
        tk.Button(controls, text="Cancel", command=window.destroy, bg=PANEL_2, fg=TEXT,
                  relief="flat", padx=16, pady=8).pack(side="right", padx=(8, 0))

        def save() -> None:
            old_startup = bool(self.desktop_settings.get("launch_on_startup", False))
            old_user_plugins = bool(self.desktop_settings.get("allow_user_plugins", False))
            old_integrations = bool(self.desktop_settings.get("allow_external_integrations", False))
            selected_voice_name = selected_voice.get()
            selected_voice_id = find_voice_id(self.installed_voices, selected_voice_name)
            selected_neural_voice = next(
                (voice_id for label, (voice_id, _lang) in VOICE_CHOICES.items()
                 if selected_voice_name == f"Neural · {label}"), ""
            )
            self.desktop_settings.update({
                "scale": scale_value.get(), "opacity": opacity_value.get(),
                "animation_performance": performance_value.get(),
                "animations_enabled": animations_value.get(),
                "always_on_top": topmost_value.get(), "click_through": click_value.get(),
                "launch_on_startup": startup_value.get(),
                "theme": selected_theme.get(), "voice_style": voice_styles.get(),
                "browser_search_engine": browser_engine_value.get(),
                "voice_id": selected_voice_id, "workspace_dir": workspace_value.get().strip(),
                "neural_voice_id": selected_neural_voice,
                "music_folder": music_folder_value.get().strip(),
                "approved_apps": approved_apps,
                **{key: variable.get() for key, variable in permission_values.items()},
                **{key: entry.get().strip().lower() for key, entry in shortcuts.items()},
            })
            save_settings(self.desktop_settings)
            self._apply_ui_scale()
            self._apply_theme_name(selected_theme.get())
            self.speech.set_voice(selected_voice_id, voice_styles.get())
            self.speech.set_neural_voice(selected_neural_voice)
            self.hud.apply_settings(self.desktop_settings)
            self.assistant.desktop_settings = self.desktop_settings
            player = self.assistant.local_actions.get("music_player")
            if player:
                try:
                    player.set_folder(self.desktop_settings.get("music_folder", ""))
                except (OSError, RuntimeError, ValueError):
                    messagebox.showwarning("Music folder", "Choose an existing local music folder or clear this field.", parent=window)
            if (old_user_plugins != permission_values["allow_user_plugins"].get()
                    or old_integrations != permission_values["allow_external_integrations"].get()):
                self.assistant.refresh_user_skills()
                self.hud.skills = self.assistant.skills
                self._persist_skills()
            self.hotkeys.stop()
            self.hotkeys = self._start_hotkeys()
            self._bind_local_hotkeys()
            if old_startup != startup_value.get():
                try:
                    set_startup_enabled(startup_value.get(), ROOT)
                except Exception as exc:
                    messagebox.showwarning("Startup setting", f"Could not update login startup: {exc}", parent=window)
            window.destroy()

        tk.Button(controls, text="Apply settings", command=save, bg="#143a50", fg=CYAN,
                  activebackground="#1d4059", relief="flat", padx=18, pady=8,
                  font=("Segoe UI", 9, "bold")).pack(side="right")

    @staticmethod
    def _setting_check(parent: tk.Widget, label: str, variable: tk.BooleanVar,
                       enabled: bool = True) -> None:
        tk.Checkbutton(parent, text=label, variable=variable, state="normal" if enabled else "disabled",
                       bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=CYAN,
                       selectcolor=BG, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=2)

    @staticmethod
    def _setting_scale(parent: tk.Widget, label: str, variable: tk.DoubleVar,
                       minimum: float, maximum: float, unit: str, percent: bool = False) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=14, pady=(2, 4))
        tk.Label(row, text=label, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        scale = tk.Scale(row, from_=minimum, to=maximum, resolution=.01, orient="horizontal",
                         variable=variable, length=230, bg=PANEL, fg=CYAN, troughcolor=BG,
                         highlightthickness=0, showvalue=False)
        scale.pack(side="right")
        value = tk.Label(row, bg=PANEL, fg=MUTED, width=6, font=("Segoe UI", 8))
        value.place(relx=.45, rely=.5, anchor="e")

        def update(*_args: Any) -> None:
            number = variable.get()
            value.configure(text=f"{round(number*100)}%" if percent else f"{number:.2f}×")

        variable.trace_add("write", update)
        update()

    def _model_row(self, parent: tk.Widget, name: str, state: str,
                   command: Any | None) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=14, pady=3)
        tk.Label(row, text=f"{name}: {state}", bg=PANEL, fg=GREEN if state == "Ready" else MUTED,
                 font=("Segoe UI", 8)).pack(side="left")
        if command:
            tk.Button(row, text="Install", command=command, bg="#132b3b", fg=CYAN,
                      relief="flat", padx=10, pady=4, font=("Segoe UI", 8, "bold")).pack(side="right")

    def _download_speech_model(self) -> None:
        self._download_model_task("speech", "Installing offline voice-recognition model…")

    def _download_chat_model(self) -> None:
        self._download_model_task("chat", "Downloading local AI model (~1.93 GB)…")

    def _download_voice_pack(self, selector: ttk.Combobox) -> None:
        if getattr(self, "_voice_download_in_progress", False):
            return
        self._voice_download_in_progress = True
        self.status.configure(text="●  DOWNLOADING LOCAL VOICE PACK", fg=CYAN)

        def work() -> None:
            error = None
            try:
                from voicepacks import download_voice_pack, ensure_voice_runtime
                download_voice_pack(
                    self.voice_pack_dir,
                    progress=lambda text: self.root.after(0, self._set_status, text, CYAN),
                )
                self.root.after(0, self._set_status, "Installing local voice runtime…", CYAN)
                ensure_voice_runtime(self.voice_runtime_dir)
                if not configure_voice_data(self.voice_runtime_dir):
                    raise RuntimeError("The voice runtime or required English language data is incomplete.")
            except Exception as exc:
                error = str(exc)
            self.root.after(0, self._voice_pack_finished, selector, error)

        threading.Thread(target=work, daemon=True).start()

    def _voice_pack_finished(self, selector: ttk.Combobox, error: str | None) -> None:
        self._voice_download_in_progress = False
        if error:
            self.voice_runtime_ready = False
            self.status.configure(text="●  VOICE PACK INSTALL FAILED", fg="#ff9c8f")
            messagebox.showerror("Local voice setup failed", error)
            return
        self.voice_runtime_ready = True
        try:
            values = ["System default", *(item["name"] for item in self.installed_voices)]
            values.extend(f"Neural · {label}" for label in VOICE_CHOICES)
            selector.configure(values=values)
            selected_id = str(self.desktop_settings.get("neural_voice_id", "")) or "af"
            label = VOICE_LABELS.get(selected_id, "American · Default")
            selector.set(f"Neural · {label}")
        except tk.TclError:
            pass  # Settings may have been closed while the background download completed.
        self.status.configure(text="●  LOCAL VOICES READY", fg=GREEN)
        messagebox.showinfo(
            "Local voices ready",
            "The neural voice pack is installed. Choose a ‘Neural · …’ voice in Settings and save. "
            "Speech is generated locally; no text is sent to the voice provider.",
        )

    def _download_model_task(self, kind: str, label: str) -> None:
        self.status.configure(text=f"●  {label.upper()}", fg=CYAN)

        def work() -> None:
            error = None
            model_module = None
            try:
                if kind == "speech":
                    from setup_model import main as download
                else:
                    import download_local_model
                    model_module = download_local_model
                    download_local_model.PROGRESS_CALLBACK = lambda text: self.root.after(
                        0, self._set_status, text, CYAN
                    )
                    download = download_local_model.main
                result = download()
                if result:
                    raise RuntimeError(f"Model installer exited with code {result}.")
            except Exception as exc:
                error = str(exc)
            finally:
                if model_module is not None:
                    model_module.PROGRESS_CALLBACK = None
            self.root.after(0, self._model_download_finished, kind, error)

        threading.Thread(target=work, daemon=True).start()

    def _model_download_finished(self, kind: str, error: str | None) -> None:
        if error:
            self.status.configure(text="●  MODEL INSTALL FAILED", fg="#ff9c8f")
            messagebox.showerror("Model setup failed", error)
            return
        if kind == "chat":
            model_path = user_data_root() / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
            if self.chat is None:
                self.chat = LocalChat(model_path,
                                      int(self.config.get("chat_history_turns", 6)),
                                      int(self.config.get("model_threads", 4)))
                self.assistant.chat = self.chat
            else:
                self.chat.model_path = model_path
            self.config["use_local_chat"] = True
            config_path = ROOT / "config.json"
            temporary = config_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, config_path)
        self.status.configure(text="●  LOCAL MODEL READY", fg=GREEN)
        messagebox.showinfo("JARVIS setup", "The local model is ready. It will run on this device.")

    def _start_hotkeys(self) -> GlobalHotkeys:
        if not hasattr(self, "hud"):
            return GlobalHotkeys({})
        actions = {
            "overlay": (self.desktop_settings.get("hotkey_overlay", "ctrl+alt+o"),
                        lambda: self.root.after(0, self.hud.toggle_overlay)),
            "command": (self.desktop_settings.get("hotkey_command", "ctrl+alt+k"),
                        lambda: self.root.after(0, self.hud.toggle_center)),
            "everyday": (self.desktop_settings.get("hotkey_everyday", "ctrl+alt+j"),
                          lambda: self.root.after(0, self.hud.show_everyday)),
            "voice": (self.desktop_settings.get("hotkey_voice", "ctrl+alt+v"),
                      lambda: self.root.after(0, self._hotkey_voice)),
        }
        hotkeys = GlobalHotkeys(actions)
        if hotkeys.error:
            self.root.after(600, self._set_status, "GLOBAL HOTKEYS UNAVAILABLE", MUTED)
        return hotkeys

    def _bind_local_hotkeys(self) -> None:
        for sequence in getattr(self, "_local_hotkey_sequences", []):
            self.root.unbind_all(sequence)
        actions = (
            ("hotkey_overlay", self.hud.toggle_overlay),
            ("hotkey_command", self.hud.toggle_center),
            ("hotkey_everyday", self.hud.show_everyday),
            ("hotkey_voice", self._hotkey_voice),
        )
        self._local_hotkey_sequences = []
        for key, action in actions:
            try:
                sequence = tkinter_sequence(str(self.desktop_settings.get(key, "")))
            except ValueError:
                continue
            self.root.bind_all(sequence, lambda _event, fn=action: (fn(), "break")[1])
            self._local_hotkey_sequences.append(sequence)

    def _save_mode(self, mode: str) -> None:
        self.desktop_settings["mode"] = mode
        save_settings(self.desktop_settings)

    def _restore_mode(self) -> None:
        mode = self.desktop_settings.get("mode", "everyday")
        if mode == "overlay":
            self.hud.show_overlay()
        elif mode == "command_center":
            self.hud.show_command_center()

    def _show_everyday(self) -> None:
        self.hud.show_everyday()

    def _show_overlay(self) -> None:
        self.hud.show_overlay()

    def _show_command_center(self) -> None:
        self.hud.show_command_center()

    def _show_chat(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()

    def _hotkey_voice(self) -> None:
        self._toggle_voice_chat()

    def _hud_state(self) -> str:
        if self.speaking:
            return "speaking"
        if self.busy:
            return "thinking"
        if self.listen_mode == "voice_chat":
            return "listening"
        if self.listen_mode == "wake":
            return "listening"
        return "standby"

    def _set_speaking(self, speaking: bool) -> None:
        self.speaking = speaking
        if not speaking:
            self._set_busy(self.busy)

    def _close(self) -> None:
        self.listen_stop.set()
        self._cancel_timers_ui()
        player = self.assistant.local_actions.get("music_player")
        if player:
            player.close()
        try:
            self.desktop_settings["overlay_geometry"] = (
                self.hud.overlay.geometry() if self.hud.overlay and self.hud.overlay.winfo_exists()
                else self.desktop_settings.get("overlay_geometry", "380x380+40+40")
            )
            save_settings(self.desktop_settings)
            self.hotkeys.stop()
            self.hud.shutdown()
        except Exception:
            pass
        self.root.destroy()


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Could not start the desktop interface: {exc}")
        return 1
    JarvisDesktop(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
