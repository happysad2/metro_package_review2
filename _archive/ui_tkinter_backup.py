"""
Metro Package Review 1.0 — UI
==============================
Tkinter-based GUI with Sydney Metro branding and a train-image background.
"""

from __future__ import annotations

import math
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from modules import ModuleResult
from modules import asset_register_checker, ifc_checker, nwc_checker
from orchestrator import run as orchestrate

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
ACCENT        = "#00D4AA"
ACCENT_BRIGHT = "#33FFD0"
ACCENT_DIM    = "#00806A"
TEXT_WHITE     = "#F0F4F8"
TEXT_LIGHT     = "#C0D0DD"
TEXT_DIM       = "#6A8090"
BTN_FG         = "#0A1018"
PASS_GREEN     = "#2EE06C"
FAIL_RED       = "#FF3355"
WARN_AMBER     = "#FFAA00"
GLASS_BG       = "#0C1420"
LOG_BG         = "#0A111A"  # very dark blue-black, not pure black

APP_ROOT = Path(__file__).parent.resolve()
INPUT_DEFAULT  = APP_ROOT / "inputs"
OUTPUT_DEFAULT = APP_ROOT / "outputs"
TRAIN_IMAGE    = APP_ROOT / "metro_train_image.png"


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class MetroApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Metro Package Review")
        self.geometry("820x560")
        self.minsize(680, 460)
        self.configure(bg="#080E14")
        self.resizable(True, True)
        self.iconphoto(False, tk.PhotoImage(width=1, height=1))

        self.input_var  = tk.StringVar(value=str(INPUT_DEFAULT))
        self.output_var = tk.StringVar(value=str(OUTPUT_DEFAULT))
        self._running   = False
        self._anim_tick = 0
        self._log_lines: list[tuple[str, str]] = []
        self._log_scroll = 0
        self._log_line_h = 16
        self._orb_x = 400.0
        self._orb_y = 28.0
        self._orb_dx = 1.6
        self._orb_dy = 0.9

        # Background image
        self._bg_image_id = None
        self._bg_photo = None
        self._resized_pil = None
        self._load_background()
        self._build()
        self._start_animations()

    # ------------------------------------------------------------------
    # Background image  (bright enough to actually see the train)
    # ------------------------------------------------------------------
    def _load_background(self):
        self._pil_image = None
        if not TRAIN_IMAGE.exists():
            return
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            img = Image.open(str(TRAIN_IMAGE)).convert("RGBA")
            # Keep it visible — moderate darken only
            img = ImageEnhance.Brightness(img).enhance(0.45)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            # Gentle blue tint to unify with palette
            tint = Image.new("RGBA", img.size, (8, 20, 40, 80))
            img = Image.alpha_composite(img, tint)
            self._pil_image = img
        except ImportError:
            pass

    def _set_bg(self, event=None):
        if not hasattr(self, "_canvas"):
            return
        w, h = self._canvas.winfo_width(), self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        if self._pil_image is not None:
            from PIL import Image, ImageTk
            resized = self._pil_image.resize((w, h), Image.LANCZOS)
            self._resized_pil = resized
            self._bg_photo = ImageTk.PhotoImage(resized)
        else:
            return
        if self._bg_image_id:
            self._canvas.delete(self._bg_image_id)
        self._bg_image_id = self._canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
        self._canvas.tag_lower(self._bg_image_id)

    # ------------------------------------------------------------------
    # UI construction — everything on Canvas for transparency
    # ------------------------------------------------------------------
    def _build(self):
        self._canvas = tk.Canvas(self, highlightthickness=0, bg="#080E14")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", self._on_resize)

        # We draw semi-transparent glass panels as canvas rectangles,
        # then place lightweight widget windows on top.

        # ── Glass overlay for top controls ──
        self._glass_top = self._canvas.create_rectangle(
            0, 0, 0, 0, fill="#0A1420", stipple="gray25", outline=""
        )

        # ── Glass overlay for log area ──
        self._glass_log = self._canvas.create_rectangle(
            0, 0, 0, 0, fill="#080E18", stipple="gray50", outline=""
        )

        # ── Accent line (animated glow) ──
        self._accent_line = self._canvas.create_line(
            0, 0, 0, 0, fill=ACCENT, width=2
        )

        # ── Title (canvas text — no opaque bg) ──
        self._title_id = self._canvas.create_text(
            20, 14, anchor="nw",
            text="Metro Package Review",
            font=("Segoe UI Semibold", 16), fill=TEXT_WHITE,
        )
        self._subtitle_id = self._canvas.create_text(
            20, 40, anchor="nw",
            text="Sydney Metro  ·  Automated Compliance  ·  v1.0",
            font=("Segoe UI", 8), fill=TEXT_DIM,
        )

        # ── Status text (right-aligned, set in _on_resize) ──
        self._status_id = self._canvas.create_text(
            0, 18, anchor="ne",
            text="● Ready", font=("Segoe UI", 9), fill=TEXT_DIM,
        )

        # ── Folder entries (placed as windows on canvas) ──
        ctrl = tk.Frame(self._canvas, bg="")
        ctrl.configure(bg=GLASS_BG)

        row_in = tk.Frame(ctrl, bg=GLASS_BG)
        row_in.pack(fill="x", pady=(2, 2))
        tk.Label(row_in, text="Input", font=("Segoe UI", 8), fg=ACCENT, bg=GLASS_BG, width=5, anchor="w").pack(side="left")
        e_in = tk.Entry(row_in, textvariable=self.input_var, font=("Segoe UI", 8),
                        bg="#101824", fg=TEXT_WHITE, insertbackground=ACCENT,
                        relief="flat", bd=2, highlightthickness=1,
                        highlightcolor=ACCENT, highlightbackground="#1A2838")
        e_in.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self._make_browse_btn(row_in, self.input_var)

        row_out = tk.Frame(ctrl, bg=GLASS_BG)
        row_out.pack(fill="x", pady=(0, 2))
        tk.Label(row_out, text="Output", font=("Segoe UI", 8), fg=ACCENT, bg=GLASS_BG, width=5, anchor="w").pack(side="left")
        e_out = tk.Entry(row_out, textvariable=self.output_var, font=("Segoe UI", 8),
                         bg="#101824", fg=TEXT_WHITE, insertbackground=ACCENT,
                         relief="flat", bd=2, highlightthickness=1,
                         highlightcolor=ACCENT, highlightbackground="#1A2838")
        e_out.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self._make_browse_btn(row_out, self.output_var)

        self._ctrl_win = self._canvas.create_window(20, 64, anchor="nw", window=ctrl, tags="ctrl")

        # ── Run button (canvas window for hover animation) ──
        btn_frame = tk.Frame(self._canvas, bg="")
        self._run_btn = tk.Label(
            btn_frame, text="▶  Run Review",
            font=("Segoe UI Semibold", 10),
            bg=ACCENT, fg=BTN_FG, padx=18, pady=5, cursor="hand2",
        )
        self._run_btn.pack()
        self._run_btn.bind("<Button-1>", lambda e: self._on_run())
        self._run_btn.bind("<Enter>", self._btn_hover_enter)
        self._run_btn.bind("<Leave>", self._btn_hover_leave)
        self._btn_win = self._canvas.create_window(20, 0, anchor="nw", window=btn_frame, tags="btn")

        # ── Module indicator dots (drawn on canvas) ──
        self._indicator_ids: dict[str, int] = {}
        self._indicator_label_ids: dict[str, int] = {}
        x_off = 180
        for name in ("Asset Register", "IFC Model", "NWC Model"):
            dot_id = self._canvas.create_text(
                x_off, 0, anchor="w", text="●",
                font=("Segoe UI", 10), fill=TEXT_DIM,
            )
            lbl_id = self._canvas.create_text(
                x_off + 14, 0, anchor="w", text=name,
                font=("Segoe UI", 8), fill=TEXT_DIM,
            )
            self._indicator_ids[name] = dot_id
            self._indicator_label_ids[name] = lbl_id
            x_off += 110

        # ── Log canvas (transparent — train image shows through) ──
        self._log_canvas = tk.Canvas(self._canvas, highlightthickness=0, bg=LOG_BG)
        self._log_canvas.bind("<MouseWheel>", self._on_log_scroll)
        self._log_bg_photo = None
        self._log_win = self._canvas.create_window(0, 0, anchor="nw",
                                                    window=self._log_canvas, tags="log")

        # ── Bouncing glow orb ──
        self._orb_glow3 = self._canvas.create_oval(
            0, 0, 0, 0, fill=ACCENT_DIM, outline="", stipple="gray25")
        self._orb_glow2 = self._canvas.create_oval(
            0, 0, 0, 0, fill=ACCENT, outline="", stipple="gray50")
        self._orb_core = self._canvas.create_oval(
            0, 0, 0, 0, fill=ACCENT_BRIGHT, outline="")
        self._orb_bounds = (0, 0, 820, 110)

    def _make_browse_btn(self, parent, var):
        btn = tk.Label(
            parent, text=" … ", font=("Segoe UI", 8, "bold"),
            bg="#182030", fg=ACCENT, cursor="hand2", padx=4,
        )
        btn.pack(side="left")
        btn.bind("<Button-1>", lambda e: self._browse(var))
        btn.bind("<Enter>", lambda e: btn.configure(bg="#203040", fg=ACCENT_BRIGHT))
        btn.bind("<Leave>", lambda e: btn.configure(bg="#182030", fg=ACCENT))

    # ------------------------------------------------------------------
    # Layout on resize
    # ------------------------------------------------------------------
    def _on_resize(self, event=None):
        self._set_bg(event)
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        pad = 16
        ctrl_top = 64
        ctrl_h = 52
        btn_row_y = ctrl_top + ctrl_h + 6
        log_top = btn_row_y + 34
        log_h = h - log_top - pad

        # Glass panels
        self._canvas.coords(self._glass_top, 0, 0, w, log_top - 4)
        self._canvas.coords(self._glass_log, pad - 2, log_top - 2, w - pad + 2, h - pad + 2)

        # Accent line
        self._canvas.coords(self._accent_line, pad, ctrl_top - 4, w - pad, ctrl_top - 4)

        # Status label (right)
        self._canvas.coords(self._status_id, w - pad, 18)

        # Ctrl entry width
        self._canvas.itemconfigure("ctrl", width=w - pad * 2)

        # Run button + indicators
        self._canvas.coords(self._btn_win, pad, btn_row_y)
        for name in self._indicator_ids:
            dot_id = self._indicator_ids[name]
            lbl_id = self._indicator_label_ids[name]
            # vertical align with button row
            cx, _ = self._canvas.coords(dot_id)[:2]
            self._canvas.coords(dot_id, cx, btn_row_y + 12)
            self._canvas.coords(lbl_id, cx + 14, btn_row_y + 12)

        # Log area
        if log_h < 40:
            log_h = 40
        log_w = w - pad * 2
        self._canvas.coords(self._log_win, pad, log_top)
        self._canvas.itemconfigure("log", width=log_w, height=log_h)
        self._update_log_bg(pad, log_top, log_w, log_h)

        # Orb bounds = top area above the log
        self._orb_bounds = (20, 10, w - 20, log_top - 6)

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------
    def _start_animations(self):
        """~30fps animation loop for accent line, orb, and status pulse."""
        self._anim_tick += 1
        t = self._anim_tick

        # Pulsing accent line
        pulse = (math.sin(t * 0.08) + 1) / 2
        line_color = _lerp_color(ACCENT_DIM, ACCENT_BRIGHT, pulse)
        self._canvas.itemconfigure(self._accent_line, fill=line_color)

        # Pulsing status when running
        if self._running:
            dp = (math.sin(t * 0.15) + 1) / 2
            self._canvas.itemconfigure(self._status_id,
                                       fill=_lerp_color(WARN_AMBER, "#FFEE55", dp))

        # ── Bouncing orb ──
        bx1, by1, bx2, by2 = self._orb_bounds
        self._orb_x += self._orb_dx
        self._orb_y += self._orb_dy
        if self._orb_x <= bx1 + 22 or self._orb_x >= bx2 - 22:
            self._orb_dx = -self._orb_dx
        if self._orb_y <= by1 + 22 or self._orb_y >= by2 - 22:
            self._orb_dy = -self._orb_dy
        ox, oy = self._orb_x, self._orb_y
        gp = (math.sin(t * 0.06) + 1) / 2
        gr = 20 + int(gp * 10)
        mr = 11 + int(gp * 5)
        cr = 4
        self._canvas.coords(self._orb_glow3, ox - gr, oy - gr, ox + gr, oy + gr)
        self._canvas.coords(self._orb_glow2, ox - mr, oy - mr, ox + mr, oy + mr)
        self._canvas.coords(self._orb_core,  ox - cr, oy - cr, ox + cr, oy + cr)
        oc = _lerp_color(ACCENT, ACCENT_BRIGHT, gp)
        self._canvas.itemconfigure(self._orb_glow3, fill=_lerp_color("#081018", oc, 0.25))
        self._canvas.itemconfigure(self._orb_glow2, fill=_lerp_color("#081018", oc, 0.55))
        self._canvas.itemconfigure(self._orb_core, fill=oc)

        self.after(33, self._start_animations)

    def _btn_hover_enter(self, event):
        self._run_btn.configure(bg=ACCENT_BRIGHT, font=("Segoe UI Semibold", 10, "underline"))

    def _btn_hover_leave(self, event):
        self._run_btn.configure(bg=ACCENT, font=("Segoe UI Semibold", 10))

    # ------------------------------------------------------------------
    # Browse / Logging / Indicators
    # ------------------------------------------------------------------
    def _browse(self, var: tk.StringVar):
        folder = filedialog.askdirectory(initialdir=var.get() or str(APP_ROOT))
        if folder:
            var.set(folder)

    # ------------------------------------------------------------------
    # Transparent log — canvas-based with cropped train bg
    # ------------------------------------------------------------------
    def _update_log_bg(self, x, y, w, h):
        """Crop the train image for the log region so it looks transparent."""
        if self._resized_pil is None:
            return
        from PIL import ImageTk, ImageEnhance
        iw, ih = self._resized_pil.size
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(int(x + w), iw), min(int(y + h), ih)
        if x2 <= x1 or y2 <= y1:
            return
        crop = self._resized_pil.crop((x1, y1, x2, y2))
        crop = ImageEnhance.Brightness(crop).enhance(0.55)
        self._log_bg_photo = ImageTk.PhotoImage(crop)
        self._log_canvas.delete("logbg")
        self._log_canvas.create_image(0, 0, anchor="nw",
                                       image=self._log_bg_photo, tags="logbg")
        self._log_canvas.tag_lower("logbg")
        self._redraw_log()

    def _redraw_log(self):
        """Redraw visible log lines on the log canvas."""
        c = self._log_canvas
        c.delete("logtext")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1:
            return
        tag_colors = {
            "pass": PASS_GREEN, "fail": FAIL_RED, "warn": WARN_AMBER,
            "heading": ACCENT_BRIGHT, "dim": TEXT_DIM, "": TEXT_LIGHT,
        }
        y = 8 - self._log_scroll
        for msg, tag in self._log_lines:
            if y > h:
                break
            if y + self._log_line_h > 0:
                color = tag_colors.get(tag, TEXT_LIGHT)
                font = ("Cascadia Code", 9, "bold") if tag == "heading" else ("Cascadia Code", 9)
                c.create_text(10, y, anchor="nw", text=msg, fill=color,
                              font=font, width=w - 20, tags="logtext")
            y += self._log_line_h

    def _on_log_scroll(self, event):
        total_h = len(self._log_lines) * self._log_line_h + 16
        visible_h = self._log_canvas.winfo_height()
        max_scroll = max(0, total_h - visible_h)
        self._log_scroll += (-event.delta // 120) * self._log_line_h * 3
        self._log_scroll = max(0, min(self._log_scroll, max_scroll))
        self._redraw_log()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log_msg(self, msg: str, tag: str = ""):
        def _append():
            actual_tag = tag
            if not actual_tag:
                if "FAIL" in msg:
                    actual_tag = "fail"
                elif "PASS" in msg and "Done" in msg:
                    actual_tag = "pass"
                elif "WARNING" in msg:
                    actual_tag = "warn"
                elif msg.startswith("=") or msg.startswith("  ORCHESTRATOR") or msg.startswith("  METRO"):
                    actual_tag = "heading"
            self._log_lines.append((msg, actual_tag))
            total_h = len(self._log_lines) * self._log_line_h + 16
            visible_h = self._log_canvas.winfo_height()
            if total_h > visible_h:
                self._log_scroll = total_h - visible_h
            self._redraw_log()
        self.after(0, _append)

    def _set_indicator(self, module: str, status: str):
        colour = {
            "running": WARN_AMBER,
            "pass": PASS_GREEN,
            "fail": FAIL_RED,
            "skip": TEXT_DIM,
        }.get(status, TEXT_DIM)
        def _update():
            if module in self._indicator_ids:
                self._canvas.itemconfigure(self._indicator_ids[module], fill=colour)
        self.after(0, _update)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _on_run(self):
        if self._running:
            return

        input_path  = Path(self.input_var.get())
        output_path = Path(self.output_var.get())

        if not input_path.exists():
            self._log_msg(f"Input folder not found: {input_path}", "fail")
            return

        output_path.mkdir(parents=True, exist_ok=True)

        self._running = True
        self._run_btn.configure(bg=ACCENT_DIM, text="⏳ Running…")
        self._canvas.itemconfigure(self._status_id, text="● Scanning…", fill=WARN_AMBER)

        # Reset indicators
        for name in self._indicator_ids:
            self._set_indicator(name, "skip")

        # Clear log
        self._log_lines.clear()
        self._log_scroll = 0
        self._redraw_log()

        threading.Thread(
            target=self._run_checks,
            args=(input_path, output_path),
            daemon=True,
        ).start()

    def _run_checks(self, input_path: Path, output_path: Path):
        self._log_msg("=" * 50, "heading")
        self._log_msg("  METRO PACKAGE REVIEW 1.0", "heading")
        self._log_msg("=" * 50, "heading")
        self._log_msg(f"Input:  {input_path}")
        self._log_msg(f"Output: {output_path}")
        self._log_msg("")

        results: list[ModuleResult] = []

        # ── Asset Register ──
        self._log_msg("─── Asset Register Check ───", "heading")
        self._set_indicator("Asset Register", "running")
        try:
            ar_result = asset_register_checker.run(input_path, output_path, self._log_msg)
            results.append(ar_result)
            self._set_indicator(
                "Asset Register", "pass" if ar_result.overall_passed else "fail"
            )
        except Exception as exc:
            self._log_msg(f"[Asset Register] ERROR: {exc}", "fail")
            self._set_indicator("Asset Register", "fail")
        self._log_msg("")

        # ── IFC ──
        self._log_msg("─── IFC Model Check ───", "heading")
        self._set_indicator("IFC Model", "running")
        try:
            ifc_result = ifc_checker.run(input_path, output_path, self._log_msg)
            results.append(ifc_result)
            self._set_indicator(
                "IFC Model", "pass" if ifc_result.overall_passed else "fail"
            )
        except Exception as exc:
            self._log_msg(f"[IFC] ERROR: {exc}", "fail")
            self._set_indicator("IFC Model", "fail")
        self._log_msg("")

        # ── NWC ──
        self._log_msg("─── NWC Model Check ───", "heading")
        self._set_indicator("NWC Model", "running")
        try:
            nwc_result = nwc_checker.run(input_path, output_path, self._log_msg)
            results.append(nwc_result)
            self._set_indicator(
                "NWC Model", "pass" if nwc_result.overall_passed else "fail"
            )
        except Exception as exc:
            self._log_msg(f"[NWC] ERROR: {exc}", "fail")
            self._set_indicator("NWC Model", "fail")
        self._log_msg("")

        # ── Orchestrator ──
        try:
            orchestrate(results, output_path, self._log_msg)
        except Exception as exc:
            self._log_msg(f"[Orchestrator] ERROR: {exc}", "fail")

        # Done
        overall = all(r.overall_passed for r in results)
        self._log_msg("")
        self._log_msg("=" * 50, "heading")
        self._log_msg(
            f"  REVIEW COMPLETE — {'ALL PASSED' if overall else 'ISSUES FOUND'}",
            "pass" if overall else "fail",
        )
        self._log_msg("=" * 50, "heading")

        def _finish():
            self._running = False
            self._run_btn.configure(bg=ACCENT, text="▶  Run Review")
            status_text = "✓ Pass" if overall else "✗ Issues found"
            status_color = PASS_GREEN if overall else FAIL_RED
            self._canvas.itemconfigure(self._status_id, text=status_text, fill=status_color)
        self.after(0, _finish)


def launch():
    """Create and run the application."""
    app = MetroApp()
    app.mainloop()
