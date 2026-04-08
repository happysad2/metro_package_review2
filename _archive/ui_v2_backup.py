"""
Metro Package Review 1.0 — UI
==============================
PySide6-based GUI with Sydney Metro branding and train-image background.
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread, QPointF
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient, QImage,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

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
BTN_FG        = "#0A1018"
PASS_GREEN    = "#2EE06C"
FAIL_RED      = "#FF3355"
WARN_AMBER    = "#FFAA00"
LOG_BG        = "#0A111A"

TAG_COLORS = {
    "pass": PASS_GREEN,
    "fail": FAIL_RED,
    "warn": WARN_AMBER,
    "heading": ACCENT_BRIGHT,
    "dim": TEXT_DIM,
    "": TEXT_LIGHT,
}

APP_ROOT = Path(__file__).parent.resolve()
INPUT_DEFAULT  = APP_ROOT / "inputs"
OUTPUT_DEFAULT = APP_ROOT / "outputs"
TRAIN_IMAGE    = APP_ROOT / "metro_train_image.png"


def _lerp_color(c1: str, c2: str, t: float) -> QColor:
    """Linearly interpolate between two hex colours."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return QColor(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


# ---------------------------------------------------------------------------
# Worker thread — signal-based thread-safe communication
# ---------------------------------------------------------------------------

class WorkerSignals(QObject):
    log = Signal(str, str)        # message, tag
    indicator = Signal(str, str)  # module, status
    finished = Signal(bool)       # overall pass


class ReviewWorker(QThread):
    """Runs the three checker modules + orchestrator off the main thread."""

    def __init__(self, input_path: Path, output_path: Path, signals: WorkerSignals):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.sig = signals

    def _log(self, msg: str, tag: str = ""):
        self.sig.log.emit(msg, tag)

    def _ind(self, module: str, status: str):
        self.sig.indicator.emit(module, status)

    def run(self):
        self._log("=" * 50, "heading")
        self._log("  METRO PACKAGE REVIEW 1.0", "heading")
        self._log("=" * 50, "heading")
        self._log(f"Input:  {self.input_path}")
        self._log(f"Output: {self.output_path}")
        self._log("")

        results: list[ModuleResult] = []

        # ── Asset Register ──
        self._log("─── Asset Register Check ───", "heading")
        self._ind("Asset Register", "running")
        try:
            ar = asset_register_checker.run(self.input_path, self.output_path, self._log)
            results.append(ar)
            self._ind("Asset Register", "pass" if ar.overall_passed else "fail")
        except Exception as exc:
            self._log(f"[Asset Register] ERROR: {exc}", "fail")
            self._ind("Asset Register", "fail")
        self._log("")

        # ── IFC ──
        self._log("─── IFC Model Check ───", "heading")
        self._ind("IFC Model", "running")
        try:
            ifc = ifc_checker.run(self.input_path, self.output_path, self._log)
            results.append(ifc)
            self._ind("IFC Model", "pass" if ifc.overall_passed else "fail")
        except Exception as exc:
            self._log(f"[IFC] ERROR: {exc}", "fail")
            self._ind("IFC Model", "fail")
        self._log("")

        # ── NWC ──
        self._log("─── NWC Model Check ───", "heading")
        self._ind("NWC Model", "running")
        try:
            nwc = nwc_checker.run(self.input_path, self.output_path, self._log)
            results.append(nwc)
            self._ind("NWC Model", "pass" if nwc.overall_passed else "fail")
        except Exception as exc:
            self._log(f"[NWC] ERROR: {exc}", "fail")
            self._ind("NWC Model", "fail")
        self._log("")

        # ── Orchestrator ──
        try:
            orchestrate(results, self.output_path, self._log)
        except Exception as exc:
            self._log(f"[Orchestrator] ERROR: {exc}", "fail")

        overall = all(r.overall_passed for r in results)
        self._log("")
        self._log("=" * 50, "heading")
        self._log(
            f"  REVIEW COMPLETE — {'ALL PASSED' if overall else 'ISSUES FOUND'}",
            "pass" if overall else "fail",
        )
        self._log("=" * 50, "heading")
        self.sig.finished.emit(overall)


# ---------------------------------------------------------------------------
# Animated background widget
# ---------------------------------------------------------------------------

class BackgroundWidget(QWidget):
    """Paints train background, glass panels, accent line, and bouncing orb."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pixmap: QPixmap | None = None
        self._tick = 0
        self._orb = QPointF(400, 28)
        self._orb_d = QPointF(1.6, 0.9)
        self._load_background()

    def _load_background(self):
        if not TRAIN_IMAGE.exists():
            return
        try:
            from PIL import Image, ImageEnhance
            img = Image.open(str(TRAIN_IMAGE)).convert("RGBA")
            img = ImageEnhance.Brightness(img).enhance(0.45)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            tint = Image.new("RGBA", img.size, (8, 20, 40, 80))
            img = Image.alpha_composite(img, tint)
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            self._bg_pixmap = QPixmap.fromImage(qimg.copy())
        except ImportError:
            pm = QPixmap(str(TRAIN_IMAGE))
            if not pm.isNull():
                self._bg_pixmap = pm

    def tick(self):
        self._tick += 1
        w, h = self.width(), self.height()
        bx1, by1 = 20, 10
        bx2, by2 = max(w - 20, 40), max(min(h, 180) - 6, 40)
        self._orb += self._orb_d
        if self._orb.x() <= bx1 + 22 or self._orb.x() >= bx2 - 22:
            self._orb_d.setX(-self._orb_d.x())
        if self._orb.y() <= by1 + 22 or self._orb.y() >= by2 - 22:
            self._orb_d.setY(-self._orb_d.y())
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background image or solid fill
        if self._bg_pixmap:
            scaled = self._bg_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(0, 0, scaled)
        else:
            p.fillRect(0, 0, w, h, QColor("#080E14"))

        # Glass top panel
        log_top = 180
        p.setOpacity(0.75)
        p.fillRect(0, 0, w, log_top - 4, QColor(10, 20, 32))

        # Glass log panel
        pad = 16
        p.setOpacity(0.80)
        p.fillRect(pad - 2, log_top - 2, w - pad * 2 + 4, h - log_top - pad + 4,
                   QColor(8, 14, 24))
        p.setOpacity(1.0)

        # Accent line
        t = self._tick
        pulse = (math.sin(t * 0.08) + 1) / 2
        line_col = _lerp_color(ACCENT_DIM, ACCENT_BRIGHT, pulse)
        p.setPen(QPen(line_col, 2))
        p.drawLine(pad, 60, w - pad, 60)

        # Bouncing orb
        gp = (math.sin(t * 0.06) + 1) / 2
        ox, oy = self._orb.x(), self._orb.y()
        oc = _lerp_color(ACCENT, ACCENT_BRIGHT, gp)

        # Outer glow
        gr = 20 + int(gp * 10)
        grad = QRadialGradient(ox, oy, gr)
        gc = QColor(oc)
        gc.setAlpha(60)
        grad.setColorAt(0, gc)
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(ox, oy), gr, gr)

        # Mid glow
        mr = 11 + int(gp * 5)
        gc2 = QColor(oc)
        gc2.setAlpha(120)
        grad2 = QRadialGradient(ox, oy, mr)
        grad2.setColorAt(0, gc2)
        grad2.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad2)
        p.drawEllipse(QPointF(ox, oy), mr, mr)

        # Core
        p.setBrush(oc)
        p.drawEllipse(QPointF(ox, oy), 4, 4)

        p.end()


# ---------------------------------------------------------------------------
# Status indicator dot
# ---------------------------------------------------------------------------

class StatusDot(QWidget):
    """Module status indicator: dot + label."""

    STATUS_COLORS = {
        "running": WARN_AMBER,
        "pass": PASS_GREEN,
        "fail": FAIL_RED,
        "skip": TEXT_DIM,
    }

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._color = QColor(TEXT_DIM)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 10))
        self._dot.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        self._label = QLabel(label)
        self._label.setFont(QFont("Segoe UI", 8))
        self._label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    def set_status(self, status: str):
        color = self.STATUS_COLORS.get(status, TEXT_DIM)
        self._dot.setStyleSheet(f"color: {color}; background: transparent;")


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class MetroApp(QMainWindow):
    """Main application window — PySide6."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metro Package Review")
        self.resize(430, 600)
        self.setMinimumSize(350, 480)

        self._running = False
        self._worker: ReviewWorker | None = None
        self._signals = WorkerSignals()
        self._signals.log.connect(self._log_msg)
        self._signals.indicator.connect(self._set_indicator)
        self._signals.finished.connect(self._on_finish)

        self._build()
        self._start_animations()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        self._bg = BackgroundWidget(self)
        self.setCentralWidget(self._bg)

        root = QVBoxLayout(self._bg)
        root.setContentsMargins(20, 14, 20, 16)
        root.setSpacing(0)

        # ── Title row ──
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        lbl_title = QLabel("Metro Package Review")
        lbl_title.setFont(QFont("Segoe UI Semibold", 16))
        lbl_title.setStyleSheet(f"color: {TEXT_WHITE}; background: transparent;")
        title_col.addWidget(lbl_title)
        lbl_sub = QLabel("Sydney Metro  ·  Automated Compliance  ·  v1.0")
        lbl_sub.setFont(QFont("Segoe UI", 8))
        lbl_sub.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        title_col.addWidget(lbl_sub)
        title_row.addLayout(title_col)
        title_row.addStretch()

        self._status_label = QLabel("● Ready")
        self._status_label.setFont(QFont("Segoe UI", 9))
        self._status_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        title_row.addWidget(self._status_label)
        root.addLayout(title_row)
        root.addSpacing(10)

        # ── Input / Output folder rows ──
        entry_ss = (
            f"QLineEdit {{ background: #101824; color: {TEXT_WHITE}; border: 1px solid #1A2838;"
            f"  border-radius: 3px; padding: 3px 6px; font-size: 9pt; font-family: 'Segoe UI'; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT}; }}"
        )
        browse_ss = (
            f"QPushButton {{ background: #182030; color: {ACCENT}; border: none;"
            f"  border-radius: 3px; padding: 4px 10px; font-weight: bold; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: #203040; color: {ACCENT_BRIGHT}; }}"
        )
        lbl_ss = f"color: {ACCENT}; background: transparent; font-size: 9pt;"

        def _make_folder_row(label_text: str, default: Path):
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setFixedWidth(48)
            lbl.setStyleSheet(lbl_ss)
            entry = QLineEdit(str(default))
            entry.setStyleSheet(entry_ss)
            btn = QPushButton("…")
            btn.setFixedWidth(32)
            btn.setStyleSheet(browse_ss)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self._browse(entry))
            row.addWidget(lbl)
            row.addWidget(entry, 1)
            row.addWidget(btn)
            return row, entry

        row_in, self._input_entry = _make_folder_row("Input", INPUT_DEFAULT)
        row_out, self._output_entry = _make_folder_row("Output", OUTPUT_DEFAULT)
        root.addLayout(row_in)
        root.addSpacing(4)
        root.addLayout(row_out)
        root.addSpacing(8)

        # ── Run button + indicator dots ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._run_btn = QPushButton("▶  Run Review")
        self._run_btn.setFont(QFont("Segoe UI Semibold", 10))
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setFixedHeight(32)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {BTN_FG}; border: none;"
            f"  border-radius: 4px; padding: 0 20px; }}"
            f"QPushButton:hover {{ background: {ACCENT_BRIGHT}; }}"
            f"QPushButton:disabled {{ background: {ACCENT_DIM}; color: #333; }}"
        )
        self._run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self._run_btn)
        btn_row.addSpacing(16)

        self._dots: dict[str, StatusDot] = {}
        for name in ("Asset Register", "IFC Model", "NWC Model"):
            dot = StatusDot(name, self)
            self._dots[name] = dot
            btn_row.addWidget(dot)

        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addSpacing(10)

        # ── Log area ──
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Cascadia Code", 9))
        self._log_view.setStyleSheet(
            f"QTextEdit {{ background: rgba(10,17,26,200); color: {TEXT_LIGHT};"
            f"  border: 1px solid #1A2838; border-radius: 4px; padding: 8px; }}"
            f"QScrollBar:vertical {{ background: #0E1620; width: 10px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {ACCENT_DIM}; border-radius: 4px;"
            f"  min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._log_view, 1)

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------

    def _start_animations(self):
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start(33)
        self._anim_tick = 0

    def _on_tick(self):
        self._anim_tick += 1
        self._bg.tick()

        if self._running:
            t = self._anim_tick
            dp = (math.sin(t * 0.15) + 1) / 2
            col = _lerp_color(WARN_AMBER, "#FFEE55", dp)
            self._status_label.setStyleSheet(
                f"color: {col.name()}; background: transparent;"
            )

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    def _browse(self, entry: QLineEdit):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", entry.text() or str(APP_ROOT)
        )
        if folder:
            entry.setText(folder)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_msg(self, msg: str, tag: str = ""):
        if not tag:
            if "FAIL" in msg:
                tag = "fail"
            elif "PASS" in msg and "Done" in msg:
                tag = "pass"
            elif "WARNING" in msg:
                tag = "warn"
            elif (msg.startswith("=")
                  or msg.startswith("  ORCHESTRATOR")
                  or msg.startswith("  METRO")):
                tag = "heading"

        color = TAG_COLORS.get(tag, TEXT_LIGHT)
        weight = "bold" if tag == "heading" else "normal"
        escaped = html.escape(msg)
        self._log_view.append(
            f'<pre style="margin:0; color:{color}; font-weight:{weight};">{escaped}</pre>'
        )
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_indicator(self, module: str, status: str):
        if module in self._dots:
            self._dots[module].set_status(status)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self):
        if self._running:
            return

        input_path = Path(self._input_entry.text())
        output_path = Path(self._output_entry.text())

        if not input_path.exists():
            self._log_msg(f"Input folder not found: {input_path}", "fail")
            return

        output_path.mkdir(parents=True, exist_ok=True)

        self._running = True
        self._run_btn.setEnabled(False)
        self._run_btn.setText("⏳ Running…")
        self._status_label.setText("● Scanning…")
        self._status_label.setStyleSheet(
            f"color: {WARN_AMBER}; background: transparent;"
        )

        for dot in self._dots.values():
            dot.set_status("skip")

        self._log_view.clear()

        self._worker = ReviewWorker(input_path, output_path, self._signals)
        self._worker.start()

    def _on_finish(self, overall: bool):
        self._running = False
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run Review")

        if overall:
            self._status_label.setText("✓ Pass")
            self._status_label.setStyleSheet(
                f"color: {PASS_GREEN}; background: transparent;"
            )
        else:
            self._status_label.setText("✗ Issues found")
            self._status_label.setStyleSheet(
                f"color: {FAIL_RED}; background: transparent;"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def launch():
    """Create and run the application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MetroApp()
    window.show()
    sys.exit(app.exec())
