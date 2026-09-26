# JARVIS Local

An offline-first, Python desktop voice assistant inspired by movie-style assistants. Voice Chat is the primary control surface; a separate local chat/history window remains available. Speech recognition uses an on-device Vosk model; open-ended conversation runs in-process through `llama-cpp-python` and a local GGUF model. The HUD includes a reactive core, a draggable overlay, a fullscreen skill tree, theme packs, locally installed system voices, and opt-in app permissions.

> This is a practical local assistant, not movie-grade general AI. It can launch only apps you explicitly allow-list and only after you enable that permission; it does not use a shell or execute generated code. Routine use makes no network requests.

## Automatic setup

Use the Python installer from the project folder:

**Windows:**

```text
python installer.py --launch
```

**macOS/Linux:**

```text
python3 installer.py --launch
```

The installer automatically:

1. Uses the Python interpreter running the installer. If it cannot, it checks PATH, common install folders, Windows' Python launcher/registry, and then searches accessible app/user folders for Python 3.10+.
2. Creates a project-local `.venv` with the selected interpreter, so the runtime does not depend on which Python is first on PATH afterward.
3. Installs Python packages and downloads the ~40 MB speech model plus the ~1.93 GB local conversation model by default.
4. Creates app configuration, enables local chat and built-in skills, then launches the desktop interface when `--launch` is supplied.

The first setup requires internet access and roughly 2.5 GB of free disk space for Python packages and models; normal app use works offline. The large chat-model download may take a while depending on your connection. If interrupted, rerun setup and the `.part` download resumes when supported by the host. If it must scan folders, that fallback search is bounded to 45 seconds by default; adjust with `--search-seconds 120`. If no Python 3.10+ installation can be found, install Python 3.10 or newer first—the installer cannot create an interpreter from nothing.

For an easier handoff, use the separate **JARVIS-One-File-Setup.py**: it embeds the project and extracts it automatically, so you only need that single `.py` file. Run `python JARVIS-One-File-Setup.py` on Windows or `python3 JARVIS-One-File-Setup.py` on macOS/Linux. It downloads the chat model by default; add `--without-chat` on a metered connection or a low-storage computer, or `--no-launch` to install without opening the app.

Useful options:

- `python installer.py` — install and print the run command without opening the GUI
- `python installer.py --launch` — install the local chat model automatically and open JARVIS
- `python installer.py --without-chat --launch` — skip the ~1.93 GB chat model download
- `python installer.py --refresh` — rebuild the project virtual environment
- `python installer.py --skip-speech-model` — install dependencies without downloading the speech model

Run the command using any Python 3 interpreter available on the computer. Once setup has completed, `.venv` is used for JARVIS itself. Run the installer again to resume/retry interrupted package or model downloads.

## Local conversational AI

The installer downloads the GGUF model and enables chat by default. It runs directly through `llama-cpp-python`; it does not require Ollama, a model server, or an API. For a smaller installation, pass `--without-chat`. You can add the local model later:

**Windows:**

```text
.venv\Scripts\python.exe bootstrap.py --with-chat
```

**macOS/Linux:**

```text
.venv/bin/python bootstrap.py --with-chat
```

Allow about 2 GB of disk space for the model, plus RAM while it runs. If no compatible wheel is available, installing `llama-cpp-python` may require a compiler. The model is from [bartowski/Qwen2.5-3B-Instruct-GGUF](https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF); review its license/terms before use.

## Skills and add-ons

Open **Skills** to enable/disable dynamically discovered capabilities. Built-in offline add-ons include:

- Date/time, safe arithmetic, and common distance/weight/volume/temperature conversions.
- Searchable conversation recall and a local knowledge vault: say **“Learn that my project uses Python”**; later say **“What have you learned?”** or ask about that subject.
- Local coding help using the bundled on-device LLM. JARVIS does not train or fine-tune itself: it stores only facts/files you explicitly teach it and retrieves them as local prompt context. To save a response, first enable workspace writes and choose a folder in Settings, then say **“Save the last code as parser.py.”** Saves are restricted to that folder and never overwrite existing files; JARVIS does not run the code.
- Voice-controlled theme and voice changes, an in-process timer with spoken completion alerts, and a permission-gated app launcher.

To ingest a local text/source document, first enable **Learn from files I explicitly select**, then say **“Learn from a file.”** Choose one text file in the picker. It stays on the device, is bounded to 200 KB, is stored in local SQLite chunks, and may be retrieved by the local LLM. JARVIS does **not** crawl other folders or silently read files.

To extend JARVIS, add a trusted `*_skill.py` module to the project's `skills/` folder. Define `register(manager)` and register a handler that returns a response string or `None`:

```python
def handle(text, context):
    if text.strip().lower() == "hello skill":
        return "Hello from my local add-on."
    return None

def register(manager):
    manager.register("example", "A short example add-on.", handle, ("Hello skill",))
```

Choose **Rescan plugins** in the Skills panel, then switch on the new add-on. In the source project, put developer-authored plugins in `skills/`; personal plugins belong in `user_skills/` (or `%LOCALAPPDATA%\JARVIS-Local\user_skills` in a packaged Windows build). Set **Allow user-installed Python skill plugins** first. A trusted integration may be named `*_integration.py`; it is separately gated by **Allow third-party/local app integrations** and must declare a permission matcher. Custom appearance packs are validated, non-executable JSON files stored under the local app-data `data/themes/` folder.

These permission switches are **policy gates, not a sandbox**. An enabled Python plugin runs in-process with the same OS-user privileges as JARVIS, so only add code you trust. External integrations are not automatically populated with credentials or cloud APIs; each future integration must be installed/configured by you. Nothing is downloaded from an add-on marketplace.

## Desktop modes and voice control

The everyday desktop remains the separate chat/history window. Use **Display modes** or the default shortcuts to switch surfaces:

- **Everyday desktop** — normal resizable chat window with saved conversations and voice controls.
- **Floating HUD overlay** — a draggable, resizable, always-on-top window with the reactive core and Voice, Chat, Command Center, and Settings controls. Overlay opacity is adjustable. Click-through is available on Windows only; use a shortcut to restore pointer control.
- **Fullscreen command center** — an animated JARVIS core with an interactive skill tree around it. Click a plugin node to enable or disable it. Nodes come from registered skills, not a hard-coded list.

From **Settings**, adjust UI scale, overlay opacity, animation detail (**low**, **medium**, or **high**), animations on/off, always-on-top, Windows click-through, sign-in startup, and keyboard shortcuts. Default shortcuts are `Ctrl+Alt+O` (overlay), `Ctrl+Alt+K` (command center), `Ctrl+Alt+J` (everyday), and `Ctrl+Alt+V` (Voice Chat). Global shortcuts require the OS hook to initialize; shortcuts also work while JARVIS has focus. Settings live at `data/desktop_settings.json` in a source install and in the OS per-user app-data folder in the packaged EXE.

Voice is the main control surface in the everyday window, overlay, and command center. The prominent **Start Voice Chat** button listens continuously for turns; **Start mic** uses the wake word. Settings provide multiple local color themes, local OS-installed TTS voices (where the OS and TTS backend expose them), and Calm/Balanced/Energetic/Concise speaking-rate profiles. Say **“Switch theme to Emerald”** or **“Change voice to Calm.”** No voice is fetched from the network. The core reacts to listening, thinking, and speaking. Model repair controls in Settings can recover missing Vosk or chat models; explicit model setup needs internet.

## Launch and use

The installer opens the GUI with `--launch`. Later, start it from the project folder:

**Windows:**

```text
.venv\Scripts\python.exe run.py
```

**macOS/Linux:**

```text
.venv/bin/python run.py
```

Click **Start Voice Chat** for a continuous spoken conversation without repeating the wake word, or use **Start mic** to say **“Jarvis, what time is it?”** Try **“Convert 12 miles to km,” “Set a timer for 5 minutes,” “Learn that my project uses Python,”** or **“What did I tell you about Iceland?”** Typed chat and the separate conversation sidebar remain available; long code is shown in the local chat instead of being read aloud in full. Voice Chat listens for a turn, replies aloud, then listens again until you tap **End Voice Chat**. The microphone stays active in that mode; press the button to stop it.

Under **Settings → Security & permissions**, app launching, workspace writes, selected-file learning, personal Python plugins, and third-party app integrations are separate **off-by-default** switches. To enable an app: turn on app launching, add an executable/launcher by file picker with a voice alias, then say **“Open app Calculator.”** JARVIS launches only that allow-listed path (no arbitrary shell commands). Scripts/documents are refused; remove the app or switch off the permission to revoke access.

## Conversation memory

- Each completed exchange is saved to a local SQLite database at `data/jarvis_memory.sqlite3`.
- Conversation sessions can be reopened from the left sidebar; the search field searches all saved transcripts.
- JARVIS can retrieve relevant prior exchanges when asked about previous discussions. The local model also receives retrieved excerpts as context for follow-up questions.
- Explicitly taught notes and selected source/text files share the local SQLite memory vault and are retrieved as relevant context. This is **retrieval memory**, not self-training or automatic learning from your whole PC; no background file crawling occurs.
- Data stays on the device. The database is not encrypted; protect it with your OS account if chats are sensitive. Delete `data/jarvis_memory.sqlite3` to erase history.
- Older conversations from before local memory was added are not recoverable. New interactions are saved automatically.

## Privacy

Microphone audio is processed locally; raw recordings are not saved. Text transcripts, learned knowledge, permissions, allow-listed app paths, and preferences are stored locally. Speech recognition, TTS, memory, skills, and model inference run on-device. Setup and explicit model-repair actions use the network to install packages or download model files; ordinary assistant use makes no network requests. App launches, user plugins, integration code, and workspace file writes are separately permission-gated. App path names may be stored in the unencrypted local settings file; the memory database is not encrypted.

## Troubleshooting

- **No Python found:** Install Python 3.10 or newer, then run the installer again. If Python is installed outside PATH/common folders, increase the recursive fallback with `--search-seconds 120`.
- **Tkinter missing:** On minimal Linux installations Tk is a separate OS package (Debian/Ubuntu: `python3-tk`) matching the Python used by the virtual environment. Windows/macOS desktop Python installers usually include Tkinter.
- **Microphone unavailable:** Allow microphone access in OS settings and connect an input device. Linux may need the PortAudio runtime library.
- **No spoken response on Linux:** Check whether the native TTS backend (e.g. eSpeak NG) is installed; text output still works.
- **No voice/profile available:** The selectable TTS voices come from the OS. Install a local system voice and a compatible native speech backend; JARVIS will not download a voice.
- **App launch blocked:** Enable the app-launch permission, add the exact executable/launcher to the approved-app list, and use the same saved app alias in your voice command.
- **Code is not saved:** Choose a workspace folder and enable workspace writes. JARVIS only saves a fenced source block as a new file inside that folder and does not execute it.
- **Local chat unavailable:** Rerun `installer.py`, verify the GGUF download completed, and check available RAM. Use `--without-chat` only if you want a smaller setup.
- **Interrupted setup:** Rerun `installer.py`; the setup steps can be repeated.

## Build a Windows executable

On a Windows build PC, first run the normal setup so the project environment has the dependencies and local models, then run `build_windows.bat`. It produces `dist/JARVIS/JARVIS.exe` and its supporting runtime files. Copy the **whole `dist/JARVIS` folder** to the target Windows PC; Python does not need to be installed or on PATH. The application can still start if a model is absent and offers repair controls in Settings.

PyInstaller builds are OS-specific. This project is being edited in a Linux sandbox, so a native Windows `.exe` cannot be compiled or verified here. Run the supplied `.bat` on Windows to create it. `python build_windows.py --dry-run` lists the resources that would be packaged on any OS.

## Project files

- `installer.py` — interpreter discovery, virtual-environment creation, one-command install
- `make_single_file_installer.py` — builds a standalone self-extracting Python setup file from the project ZIP
- `jarvis_ui.py` — Tkinter desktop chat, history navigation/search, microphone control
- `hud.py` — reactive core, draggable overlay, fullscreen command center, dynamic plugin tree
- `permissions.py` — exact-path approved app launching without shell execution
- `desktop_settings.py`, `hotkeys.py` — persisted preferences, login startup, and keyboard shortcuts
- `themes.py`, `theme_manager.py`, `voices.py` — local appearance packs and installed speech voice profiles
- `app_paths.py` — bundled-asset and writable per-user paths for frozen builds
- `build_windows.py`, `build_windows.bat`, `requirements-build.txt` — Windows executable build workflow
- `jarvis.py` — voice/terminal interface, built-in commands, local model and memory integration
- `skill_manager.py`, `skills/` — local permission-aware plugin registry and built-in add-ons
- `memory.py` — SQLite transcript storage, search, recall, and explicitly taught knowledge
- `run.py` — Python desktop/terminal launcher
- `bootstrap.py`, `setup_model.py`, `download_local_model.py` — Python setup and model downloaders
- `requirements*.txt` — Python dependencies
- `tests/` — assistant, setup discovery, memory, model transfers, desktop settings, and plugins


## One-file setup download

A self-extracting Python setup script is available at [`downloads/JARVIS-One-File-Setup.py`](downloads/JARVIS-One-File-Setup.py). Run it with Python 3.10+; it unpacks this project and starts the automatic installer. Setup fetches the offline Vosk speech model and the approximately 1.93 GB local chat model by default. Use `--without-chat` to skip the large model or `--no-launch` to install without opening the app.
