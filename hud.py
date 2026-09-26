"""Futuristic Tk HUD views kept separate from chat, voice, and skill internals."""
from __future__ import annotations

import math
import platform
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

BG = "#07111b"
PANEL = "#102536"
PANEL_ALT = "#132b3b"
TEXT = "#dff8ff"
CYAN = "#53ddff"
BLUE = "#278cff"
GREEN = "#52f1c2"
MUTED = "#69879a"


class ReactiveCore(tk.Canvas):
    """Procedurally drawn, performance-configurable HUD core and plugin nodes."""
    INTERVALS = {"low": 240, "medium": 90, "high": 32}

    def __init__(self, parent: tk.Widget, settings: dict[str, Any], skill_manager: Any,
                 on_skill: Callable[[str], None] | None = None, skill_tree: bool = False,
                 state_getter: Callable[[], str] | None = None, **kwargs: Any) -> None:
        super().__init__(parent, bg=BG, highlightthickness=0, **kwargs)
        self.settings = settings
        self.skill_manager = skill_manager
        self.on_skill = on_skill
        self.skill_tree = skill_tree
        self.state_getter = state_getter or (lambda: "standby")
        self.phase = 0.0
        self._last_state: str | None = None
        self._animation_id: str | None = None
        self.bind("<Configure>", lambda _event: self.draw_frame())
        self._animate()

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.draw_frame()

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        self.phase += 0.075 if self.settings.get("animation_performance") == "high" else 0.035
        current_state = self.state_getter()
        if self.settings.get("animations_enabled", True) or current_state != self._last_state:
            self.draw_frame()
        interval = 700 if not self.settings.get("animations_enabled", True) else self.INTERVALS.get(
            self.settings.get("animation_performance", "medium"), 90
        )
        self._animation_id = self.after(interval, self._animate)

    def destroy(self) -> None:
        if self._animation_id:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        super().destroy()

    def draw_frame(self) -> None:
        if not self.winfo_exists():
            return
        self.delete("frame")
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        scale = float(self.settings.get("scale", 1.0))
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.10 * scale
        state = self.state_getter()
        self._last_state = state
        accent = GREEN if state == "speaking" else ("#ffc46b" if state == "thinking" else CYAN)
        pulse = (math.sin(self.phase * (2.7 if state == "speaking" else 1.0)) + 1) / 2
        performance = self.settings.get("animation_performance", "medium")
        rings = {"low": 2, "medium": 4, "high": 7}.get(performance, 4)

        # Orbital mesh and concentric energy rings.
        for index in range(rings):
            distance = radius * (1.65 + index * 0.53 + (pulse * 0.09 if index % 2 == 0 else 0))
            color = accent if index == 0 or index == rings - 1 else PANEL_ALT
            self.create_oval(cx-distance, cy-distance, cx+distance, cy+distance,
                             outline=color, width=1 if performance != "high" else 2,
                             dash=(5, 7) if index % 2 else (), tags="frame")
        self.create_oval(cx-radius*1.35, cy-radius*1.35, cx+radius*1.35, cy+radius*1.35,
                         outline="#2d89b4", width=2, tags="frame")
        for index in range(12):
            angle = self.phase * (0.45 if index % 2 else -0.32) + index * math.tau / 12
            r1, r2 = radius * 1.25, radius * (1.5 + pulse * 0.1)
            self.create_line(cx+math.cos(angle)*r1, cy+math.sin(angle)*r1,
                             cx+math.cos(angle)*r2, cy+math.sin(angle)*r2,
                             fill=accent if index % 3 == 0 else "#246b8e", width=2, tags="frame")
        glow = radius * (0.9 + pulse * (0.08 if state == "standby" else 0.22))
        self.create_oval(cx-glow, cy-glow, cx+glow, cy+glow,
                         fill=PANEL, outline=accent, width=3, tags="frame")
        self.create_oval(cx-radius*0.66, cy-radius*0.66, cx+radius*0.66, cy+radius*0.66,
                         fill=BG, outline=accent, width=2, tags="frame")
        self.create_text(cx, cy-7*scale, text="J.A.R.V.I.S.", fill=TEXT,
                         font=("Segoe UI", max(7, int(11*scale)), "bold"), tags="frame")
        self.create_text(cx, cy+11*scale, text=state.replace("_", " ").upper(), fill=accent,
                         font=("Segoe UI", max(6, int(7*scale)), "bold"), tags="frame")

        particles = {"low": 5, "medium": 12, "high": 28}.get(performance, 12)
        for index in range(particles):
            angle = self.phase * (0.18 + (index % 4) * .025) + math.tau * index / particles
            orbit = radius * (2.0 + (index % 5) * .52)
            px, py = cx + math.cos(angle)*orbit, cy + math.sin(angle)*orbit
            size = 1.4 + (index % 3) * .65
            self.create_oval(px-size, py-size, px+size, py+size,
                             fill=accent if index % 4 == 0 else PANEL_ALT, outline="", tags="frame")

        if self.skill_tree:
            skills = self.skill_manager.list_skills()
            node_radius = max(23, min(41, 32 * scale))
            for index, skill in enumerate(skills):
                per_orbit = 14
                orbit_index = index // per_orbit
                orbit_items = min(per_orbit, len(skills) - orbit_index * per_orbit)
                angle = -math.pi/2 + math.tau * (index % per_orbit) / max(1, orbit_items)
                orbit = min(width, height) * max(.18, .43 - orbit_index * .12)
                nx, ny = cx + math.cos(angle)*orbit, cy + math.sin(angle)*orbit
                tag = f"skill:{skill['name']}"
                color = CYAN if skill["enabled"] else "#4c6474"
                self.create_line(cx, cy, nx, ny, fill=PANEL_ALT, width=1, tags=("frame", tag))
                self.create_oval(nx-node_radius, ny-node_radius, nx+node_radius, ny+node_radius,
                                 fill=PANEL, outline=color, width=2, tags=("frame", tag))
                self.create_text(nx, ny-4, text=skill["name"].replace("_", " ")[:15], fill=TEXT,
                                 font=("Segoe UI", max(7, int(8*scale)), "bold"), tags=("frame", tag))
                self.create_text(nx, ny+9, text="ON" if skill["enabled"] else "OFF",
                                 fill=color, font=("Segoe UI", 7), tags=("frame", tag))
                if self.on_skill:
                    self.tag_bind(tag, "<Button-1>", lambda _event, name=skill["name"]: self.on_skill(name))


class HudController:
    def __init__(self, root: tk.Tk, settings: dict[str, Any], skill_manager: Any,
                 on_voice: Callable[[], None], on_chat: Callable[[], None],
                 on_settings: Callable[[], None], on_mode: Callable[[str], None],
                 on_skill_toggle: Callable[[str], None], state_getter: Callable[[], str]) -> None:
        self.root, self.settings, self.skills = root, settings, skill_manager
        self.on_voice, self.on_chat, self.on_settings = on_voice, on_chat, on_settings
        self.on_mode, self.on_skill_toggle, self.state_getter = on_mode, on_skill_toggle, state_getter
        self.overlay: tk.Toplevel | None = None
        self.center: tk.Toplevel | None = None
        self.overlay_core: ReactiveCore | None = None
        self.center_core: ReactiveCore | None = None

    def show_everyday(self) -> None:
        self._close_center()
        self._close_overlay()
        self.root.attributes("-fullscreen", False)
        self.root.deiconify()
        self.root.state("normal")
        self.on_mode("everyday")

    def show_overlay(self) -> None:
        self._close_center()
        if self.overlay is None or not self.overlay.winfo_exists():
            self._create_overlay()
        self.root.iconify()
        self.overlay.deiconify()
        self.overlay.lift()
        self._apply_overlay_settings()
        self.on_mode("overlay")

    def _create_overlay(self) -> None:
        self.overlay = tk.Toplevel(self.root)
        self.overlay.title("JARVIS HUD")
        self.overlay.geometry(str(self.settings.get("overlay_geometry", "380x380+40+40")))
        self.overlay.minsize(300, 300)
        self.overlay.resizable(True, True)
        self.overlay.configure(bg=BG)
        head = tk.Frame(self.overlay, bg=PANEL, padx=10, pady=7)
        head.pack(fill="x")
        title = tk.Label(head, text="◈  JARVIS HUD  ·  DRAG TO MOVE", bg=PANEL, fg=CYAN,
                         font=("Segoe UI", 9, "bold"), cursor="fleur")
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self._drag_start)
        title.bind("<B1-Motion>", self._drag_move)
        tk.Button(head, text="×", command=self.show_everyday, bg=PANEL, fg=TEXT,
                  relief="flat", font=("Segoe UI", 13, "bold")).pack(side="right")
        self.overlay_core = ReactiveCore(self.overlay, self.settings, self.skills,
                                         state_getter=self.state_getter, height=250)
        self.overlay_core.pack(fill="both", expand=True, padx=8, pady=4)
        buttons = tk.Frame(self.overlay, bg=BG)
        buttons.pack(fill="x", padx=9, pady=(2, 10))
        self._small_button(buttons, "Voice", self.on_voice, primary=True).pack(side="left", expand=True, fill="x", padx=3)
        self._small_button(buttons, "Chat", self._show_chat).pack(side="left", expand=True, fill="x", padx=3)
        self._small_button(buttons, "Center", self.show_command_center).pack(side="left", expand=True, fill="x", padx=3)
        self._small_button(buttons, "Settings", self.on_settings).pack(side="left", expand=True, fill="x", padx=3)
        self.overlay.protocol("WM_DELETE_WINDOW", self.show_everyday)
        self.overlay.bind("<Escape>", lambda _event: self.show_everyday())
        self._apply_overlay_settings()

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x, self._drag_y = event.x_root, event.y_root
        self._drag_geometry = self.overlay.geometry() if self.overlay else ""

    def _drag_move(self, event: tk.Event) -> None:
        if not self.overlay or not hasattr(self, "_drag_x"):
            return
        dx, dy = event.x_root-self._drag_x, event.y_root-self._drag_y
        self._drag_x, self._drag_y = event.x_root, event.y_root
        self.overlay.geometry(f"+{self.overlay.winfo_x()+dx}+{self.overlay.winfo_y()+dy}")
        self.settings["overlay_geometry"] = self.overlay.geometry()

    def _show_chat(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.on_chat()

    @staticmethod
    def _small_button(parent: tk.Widget, label: str, command: Callable[[], None], primary: bool = False) -> tk.Button:
        return tk.Button(parent, text=label, command=command, bg=PANEL_ALT,
                         fg=CYAN if primary else TEXT, activebackground=PANEL, relief="flat",
                         cursor="hand2", font=("Segoe UI", 8, "bold"), padx=7, pady=7)

    def show_command_center(self) -> None:
        self._close_overlay()
        if self.center is not None and self.center.winfo_exists():
            self.center.deiconify()
            self.center.attributes("-fullscreen", True)
            self.center.lift()
            return
        self.center = tk.Toplevel(self.root)
        self.center.title("JARVIS Command Center")
        self.center.configure(bg=BG)
        self.center.attributes("-fullscreen", True)
        if self.settings.get("always_on_top", True):
            self.center.attributes("-topmost", True)
        header = tk.Frame(self.center, bg=BG, padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="J.A.R.V.I.S.  /  COMMAND CENTER", bg=BG, fg=CYAN,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="SELECT A SKILL NODE TO ENABLE / DISABLE", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=25)
        tk.Button(header, text="EVERYDAY MODE  ·  ESC", command=self.show_everyday,
                  bg=PANEL_ALT, fg=TEXT, relief="flat", padx=14, pady=7).pack(side="right")
        tk.Button(header, text="OVERLAY", command=self.show_overlay, bg=PANEL_ALT, fg=TEXT,
                  relief="flat", padx=14, pady=7).pack(side="right", padx=8)
        tk.Button(header, text="CHAT WINDOW", command=self._show_chat, bg=PANEL_ALT, fg=TEXT,
                  relief="flat", padx=14, pady=7).pack(side="right", padx=8)
        tk.Button(header, text="VOICE CONTROL", command=self.on_voice, bg=PANEL_ALT, fg=CYAN,
                  relief="flat", padx=14, pady=7, font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)
        tk.Button(header, text="SETTINGS", command=self.on_settings, bg=PANEL_ALT, fg=TEXT,
                  relief="flat", padx=14, pady=7).pack(side="right", padx=8)
        self.center_core = ReactiveCore(self.center, self.settings, self.skills,
                                       on_skill=self.on_skill_toggle, skill_tree=True,
                                       state_getter=self.state_getter)
        self.center_core.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        footer = tk.Label(self.center, text="VOICE CONTROL ACTIVE ON THE LOCAL DEVICE  ·  CLICK SKILL NODES TO CHANGE THEM",
                          bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold"))
        footer.pack(pady=(0, 15))
        self.center.bind("<Escape>", lambda _event: self.show_everyday())
        self.center.protocol("WM_DELETE_WINDOW", self.show_everyday)
        self.root.iconify()
        self.on_mode("command_center")

    def refresh_skills(self) -> None:
        if self.center_core:
            self.center_core.draw_frame()

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        for core in (self.overlay_core, self.center_core):
            if core and core.winfo_exists():
                core.apply_settings(settings)
        self._apply_overlay_settings()
        if self.center and self.center.winfo_exists():
            self.center.attributes("-topmost", bool(settings.get("always_on_top", True)))

    def _apply_overlay_settings(self) -> None:
        if not self.overlay or not self.overlay.winfo_exists():
            return
        self.overlay.attributes("-alpha", float(self.settings.get("opacity", .93)))
        self.overlay.attributes("-topmost", bool(self.settings.get("always_on_top", True)))
        self._set_click_through(bool(self.settings.get("click_through", False)))

    def _set_click_through(self, enabled: bool) -> None:
        if not self.overlay or platform.system() != "Windows":
            return
        try:
            import ctypes
            hwnd = self.overlay.winfo_id()
            hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            transparent = 0x20
            layered = 0x80000
            style |= layered
            style = style | transparent if enabled else style & ~transparent
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    def toggle_overlay(self) -> None:
        if self.overlay and self.overlay.winfo_exists() and self.overlay.state() != "withdrawn":
            self.show_everyday()
        else:
            self.show_overlay()

    def toggle_center(self) -> None:
        if self.center and self.center.winfo_exists():
            self.show_everyday()
        else:
            self.show_command_center()

    def _close_center(self) -> None:
        if self.center and self.center.winfo_exists():
            self.center.destroy()
        self.center = self.center_core = None

    def _close_overlay(self) -> None:
        if self.overlay and self.overlay.winfo_exists():
            try:
                self.settings["overlay_geometry"] = self.overlay.geometry()
            except tk.TclError:
                pass
            self.overlay.destroy()
        self.overlay = self.overlay_core = None

    def shutdown(self) -> None:
        self._close_center()
        self._close_overlay()


def apply_theme(colors: dict[str, str]) -> None:
    """Update shared HUD palette constants for newly drawn frames and windows."""
    global BG, PANEL, PANEL_ALT, TEXT, CYAN, BLUE, GREEN, MUTED
    BG = colors["background"]
    PANEL = colors["panel"]
    PANEL_ALT = colors["panel_alt"]
    TEXT = colors["text"]
    CYAN = colors["accent"]
    BLUE = colors["secondary"]
    GREEN = colors["success"]
    MUTED = colors["muted"]
