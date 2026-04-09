"""
Metro Package Review 1.0 — UI
==============================
PySide6 GUI with Sydney Metro branding.  The train image fills the entire
window and shows through a frosted-glass log panel.  A single accent orb
floats gently up and down.
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap,
    QRadialGradient, QImage, QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from modules import APP_ROOT, ModuleResult
from modules import asset_register_checker, ifc_checker, nwc_checker
from modules.eir_config import discover_versions, load_bim_schema, EIRVersion
from orchestrator import run as orchestrate

# ---------------------------------------------------------------------------
# Paths — APP_ROOT is where bundled assets live (may be a temp dir when frozen).
# USER_ROOT is where the exe actually sits (for inputs/outputs beside the exe).
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    USER_ROOT = Path(sys.executable).parent.resolve()
else:
    USER_ROOT = APP_ROOT

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

# Modern font stack — prefer Inter / Segoe UI Variable
FONT_FAMILY    = "Segoe UI Variable, Segoe UI, Inter, Helvetica Neue, sans-serif"
MONO_FAMILY    = "Cascadia Mono, Cascadia Code, Consolas, monospace"

TAG_COLORS = {
    "pass": PASS_GREEN, "fail": FAIL_RED, "warn": WARN_AMBER,
    "heading": ACCENT_BRIGHT, "dim": TEXT_DIM, "": TEXT_LIGHT,
}

INPUT_DEFAULT  = USER_ROOT / "inputs"
OUTPUT_DEFAULT = USER_ROOT / "outputs"
TRAIN_IMAGE    = APP_ROOT / "metro_train_image.png"


def _lerp(c1: str, c2: str, t: float) -> QColor:
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return QColor(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class WorkerSignals(QObject):
    log = Signal(str, str)
    indicator = Signal(str, str)
    finished = Signal(bool)


class ReviewWorker(QThread):
    def __init__(self, inp: Path, out: Path, sig: WorkerSignals,
                 eir_version: EIRVersion | None = None):
        super().__init__()
        self.inp, self.out, self.sig = inp, out, sig
        self.eir_version = eir_version

    def _log(self, msg, tag=""):
        self.sig.log.emit(msg, tag)

    def _ind(self, mod, st):
        self.sig.indicator.emit(mod, st)

    def run(self):
        self._log("=" * 50, "heading")
        self._log("  METRO PACKAGE REVIEW 1.0", "heading")
        self._log("=" * 50, "heading")
        self._log(f"Input:  {self.inp}")
        self._log(f"Output: {self.out}")

        # ── Load EIR schema if a version was selected ──
        bim_schema = None
        if self.eir_version:
            self._log(f"EIR:    {self.eir_version.display_name}")
            if self.eir_version.has_schemas:
                self._log(f"Loading BIM schema from {self.eir_version.bim_schema_path.name}…")
                try:
                    bim_schema = load_bim_schema(self.eir_version)
                    if bim_schema:
                        self._log(
                            f"  Loaded {len(bim_schema.fields)} fields, "
                            f"{len(bim_schema.ifc_property_sets)} property sets",
                            "pass",
                        )
                    else:
                        self._log("  Could not parse BIM schema — using built-in rules", "warn")
                except Exception as exc:
                    self._log(f"  Schema load error: {exc} — using built-in rules", "warn")
            else:
                self._log("  No schema files in this EIR version — using built-in rules", "warn")
        else:
            self._log("EIR:    None selected — using built-in rules")
        self._log("")

        results: list[ModuleResult] = []

        for name, checker in [
            ("Asset Register", asset_register_checker),
            ("IFC Model", ifc_checker),
            ("NWC Model", nwc_checker),
        ]:
            self._log(f"─── {name} Check ───", "heading")
            self._ind(name, "running")
            try:
                if name == "IFC Model":
                    r = checker.run(self.inp, self.out, self._log,
                                    bim_schema=bim_schema)
                elif name == "NWC Model":
                    r = checker.run(self.inp, self.out, self._log,
                                    bim_schema=bim_schema)
                else:
                    r = checker.run(self.inp, self.out, self._log)
                results.append(r)
                self._ind(name, "pass" if r.overall_passed else "fail")
            except Exception as exc:
                self._log(f"[{name}] ERROR: {exc}", "fail")
                self._ind(name, "fail")
            self._log("")

        eir_label = self.eir_version.display_name if self.eir_version else None
        try:
            orchestrate(results, self.out, self._log, eir_version=eir_label)
        except Exception as exc:
            self._log(f"[Orchestrator] ERROR: {exc}", "fail")

        ok = all(r.overall_passed for r in results)
        self._log("")
        self._log("=" * 50, "heading")
        self._log(
            f"  REVIEW COMPLETE — {'ALL PASSED' if ok else 'ISSUES FOUND'}",
            "pass" if ok else "fail",
        )
        self._log("=" * 50, "heading")
        self.sig.finished.emit(ok)


# ---------------------------------------------------------------------------
# Full-window background  (train image + orb)
# ---------------------------------------------------------------------------

class BackgroundWidget(QWidget):
    """Fills the entire window with the train image.  Draws a gentle
    floating orb that moves slowly up and down near the title area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._px: QPixmap | None = None
        self._tick = 0
        self._orb_base_y = 30.0
        self._load_bg()

    def _load_bg(self):
        if not TRAIN_IMAGE.exists():
            return
        try:
            from PIL import Image, ImageEnhance
            img = Image.open(str(TRAIN_IMAGE)).convert("RGBA")
            img = ImageEnhance.Brightness(img).enhance(0.38)
            img = ImageEnhance.Contrast(img).enhance(1.15)
            tint = Image.new("RGBA", img.size, (6, 16, 32, 70))
            img = Image.alpha_composite(img, tint)
            data = img.tobytes("raw", "RGBA")
            qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            self._px = QPixmap.fromImage(qi.copy())
        except ImportError:
            pm = QPixmap(str(TRAIN_IMAGE))
            if not pm.isNull():
                self._px = pm

    def tick(self):
        self._tick += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Full-bleed train image ──
        if self._px:
            sc = self._px.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            xo = (sc.width() - w) // 2
            yo = (sc.height() - h) // 2
            p.drawPixmap(0, 0, sc, xo, yo, w, h)
        else:
            p.fillRect(0, 0, w, h, QColor("#060C14"))

        # ── Subtle top gradient for title legibility ──
        grad = QLinearGradient(0, 0, 0, 90)
        grad.setColorAt(0, QColor(6, 12, 20, 200))
        grad.setColorAt(1, QColor(6, 12, 20, 0))
        p.fillRect(0, 0, w, 90, grad)

        # ── Floating orb — slow up/down hover ──
        t = self._tick
        glow_t = (math.sin(t * 0.04) + 1) / 2           # brightness pulse
        hover_y = self._orb_base_y + math.sin(t * 0.025) * 10  # gentle float
        ox = w - 22.0   # right of the status label
        oy = hover_y
        oc = _lerp(ACCENT_DIM, ACCENT_BRIGHT, glow_t)

        for radius, alpha in [(28, 35), (14, 80), (6, 160)]:
            rg = QRadialGradient(ox, oy, radius)
            c = QColor(oc)
            c.setAlpha(alpha)
            rg.setColorAt(0, c)
            rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(rg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(ox, oy), radius, radius)

        # Core dot
        core = QColor(oc)
        core.setAlpha(220)
        p.setBrush(core)
        p.drawEllipse(QPointF(ox, oy), 3, 3)

        p.end()


# ---------------------------------------------------------------------------
# Status dot
# ---------------------------------------------------------------------------

class StatusDot(QWidget):
    _COLORS = {
        "running": WARN_AMBER, "pass": PASS_GREEN,
        "fail": FAIL_RED, "skip": TEXT_DIM,
    }

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{TEXT_DIM}; background:transparent; font-size:9pt;")
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color:{TEXT_DIM}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:8pt;"
        )
        lay.addWidget(self._dot)
        lay.addWidget(self._lbl)

    def set_status(self, st):
        c = self._COLORS.get(st, TEXT_DIM)
        self._dot.setStyleSheet(f"color:{c}; background:transparent; font-size:9pt;")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MetroApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metro Package Review")
        logo = APP_ROOT / "logo_top_left.png"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))
        self.resize(430, 600)
        self.setMinimumSize(350, 480)
        self._running = False
        self._worker: ReviewWorker | None = None
        self._sig = WorkerSignals()
        self._sig.log.connect(self._log_msg)
        self._sig.indicator.connect(self._set_ind)
        self._sig.finished.connect(self._on_finish)
        self._build()
        self._start_anim()

    # ------------------------------------------------------------------
    def _build(self):
        self._bg = BackgroundWidget(self)
        self.setCentralWidget(self._bg)

        root = QVBoxLayout(self._bg)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(0)

        # ── Title ──
        tr = QHBoxLayout()
        tr.setSpacing(8)

        tc = QVBoxLayout()
        tc.setSpacing(1)
        t1 = QLabel("Metro Package Review")
        t1.setStyleSheet(
            f"color:{TEXT_WHITE}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:15pt; font-weight:600;"
        )
        tc.addWidget(t1)
        t2 = QLabel("Sydney Metro  ·  Automated Compliance  ·  v1.0")
        t2.setStyleSheet(
            f"color:{TEXT_DIM}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:7.5pt; letter-spacing:0.5px;"
        )
        tc.addWidget(t2)
        tr.addLayout(tc)
        tr.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet(
            f"color:{TEXT_DIM}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:8.5pt;"
            f" margin-right:32px;"
        )
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tr.addWidget(self._status)
        root.addLayout(tr)
        root.addSpacing(14)

        # ── Thin accent divider ──
        div = QWidget()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{ACCENT_DIM};")
        root.addWidget(div)
        root.addSpacing(10)

        # ── Folder rows ──
        entry_ss = (
            f"QLineEdit {{ background:rgba(16,24,36,180); color:{TEXT_WHITE};"
            f"  border:1px solid rgba(255,255,255,0.06); border-radius:4px;"
            f"  padding:4px 8px; font-family:{FONT_FAMILY}; font-size:8.5pt; }}"
            f"QLineEdit:focus {{ border:1px solid {ACCENT}; }}"
        )
        browse_ss = (
            f"QPushButton {{ background:rgba(24,32,48,180); color:{ACCENT}; border:none;"
            f"  border-radius:4px; padding:4px 10px; font-weight:600; font-size:8.5pt;"
            f"  font-family:{FONT_FAMILY}; }}"
            f"QPushButton:hover {{ background:rgba(32,48,64,200); color:{ACCENT_BRIGHT}; }}"
        )
        lbl_ss = (
            f"color:{ACCENT}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:8.5pt; font-weight:500;"
        )

        def _row(label_text, default):
            r = QHBoxLayout()
            r.setSpacing(6)
            lb = QLabel(label_text)
            lb.setFixedWidth(46)
            lb.setStyleSheet(lbl_ss)
            e = QLineEdit(str(default))
            e.setStyleSheet(entry_ss)
            b = QPushButton("…")
            b.setFixedWidth(30)
            b.setStyleSheet(browse_ss)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda: self._browse(e))
            r.addWidget(lb)
            r.addWidget(e, 1)
            r.addWidget(b)
            return r, e

        ri, self._in = _row("Input", INPUT_DEFAULT)
        ro, self._out = _row("Output", OUTPUT_DEFAULT)
        root.addLayout(ri)
        root.addSpacing(4)
        root.addLayout(ro)
        root.addSpacing(4)

        # ── EIR version selector ──
        eir_row = QHBoxLayout()
        eir_row.setSpacing(6)
        eir_lb = QLabel("EIR")
        eir_lb.setFixedWidth(46)
        eir_lb.setStyleSheet(lbl_ss)
        self._eir_combo = QComboBox()
        self._eir_combo.setStyleSheet(
            f"QComboBox {{ background:rgba(16,24,36,180); color:{TEXT_WHITE};"
            f"  border:1px solid rgba(255,255,255,0.06); border-radius:4px;"
            f"  padding:4px 8px; padding-right:4px;"
            f"  font-family:{FONT_FAMILY}; font-size:8.5pt; }}"
            f"QComboBox:focus {{ border:1px solid {ACCENT}; }}"
            f"QComboBox::drop-down {{ width:0px; border:none; }}"
            f"QComboBox::down-arrow {{ image:none; width:0px; height:0px; }}"
            f"QComboBox QAbstractItemView {{ background:rgba(16,24,36,240); color:{TEXT_WHITE};"
            f"  border:1px solid {ACCENT_DIM}; selection-background-color:{ACCENT_DIM};"
            f"  font-family:{FONT_FAMILY}; font-size:8.5pt; }}"
        )
        self._eir_versions: list[EIRVersion | None] = [None]
        self._eir_combo.addItem("(none — built-in rules)")
        for v in discover_versions():
            suffix = "" if v.has_schemas else "  (no schemas)"
            self._eir_combo.addItem(f"{v.display_name}{suffix}")
            self._eir_versions.append(v)
        # Default to newest version with schemas
        for i, v in enumerate(self._eir_versions):
            if v is not None and v.has_schemas:
                self._eir_combo.setCurrentIndex(i)
                break
        eir_row.addWidget(eir_lb)
        eir_row.addWidget(self._eir_combo, 1)
        root.addLayout(eir_row)
        root.addSpacing(10)

        # ── Run button + dots ──
        br = QHBoxLayout()
        br.setSpacing(10)
        self._run = QPushButton("▶  Run Review")
        self._run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run.setFixedHeight(30)
        self._run.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:{BTN_FG}; border:none;"
            f"  border-radius:5px; padding:0 18px;"
            f"  font-family:{FONT_FAMILY}; font-size:9.5pt; font-weight:600; }}"
            f"QPushButton:hover {{ background:{ACCENT_BRIGHT}; }}"
            f"QPushButton:disabled {{ background:{ACCENT_DIM}; color:#444; }}"
        )
        self._run.clicked.connect(self._on_run)
        br.addWidget(self._run)
        br.addSpacing(12)

        self._dots: dict[str, StatusDot] = {}
        for n in ("Asset Register", "IFC Model", "NWC Model"):
            d = StatusDot(n, self)
            self._dots[n] = d
            br.addWidget(d)
        br.addStretch()
        root.addLayout(br)
        root.addSpacing(10)

        # ── Log area — frosted glass over train image ──
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"QTextEdit {{"
            f"  background: rgba(8,14,22,140);"
            f"  color: {TEXT_LIGHT};"
            f"  border: 1px solid rgba(255,255,255,0.05);"
            f"  border-radius: 6px;"
            f"  padding: 10px;"
            f"  font-family: {MONO_FAMILY};"
            f"  font-size: 8.5pt;"
            f"  selection-background-color: {ACCENT_DIM};"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 8px; border: none;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: rgba(0,212,170,0.35); border-radius: 4px; min-height: 30px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}"
        )
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Subtle drop-shadow for depth
        shadow = QGraphicsDropShadowEffect(self._log)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self._log.setGraphicsEffect(shadow)

        root.addWidget(self._log, 1)

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _start_anim(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self._t = 0

    def _tick(self):
        self._t += 1
        self._bg.tick()
        if self._running:
            dp = (math.sin(self._t * 0.12) + 1) / 2
            c = _lerp(WARN_AMBER, "#FFEE55", dp)
            self._status.setStyleSheet(
                f"color:{c.name()}; background:transparent;"
                f" font-family:{FONT_FAMILY}; font-size:8.5pt;"
            )

    # ------------------------------------------------------------------
    def _browse(self, entry):
        f = QFileDialog.getExistingDirectory(self, "Select Folder", entry.text() or str(APP_ROOT))
        if f:
            entry.setText(f)

    # ------------------------------------------------------------------
    def _log_msg(self, msg, tag=""):
        if not tag:
            if "FAIL" in msg:
                tag = "fail"
            elif "PASS" in msg and "Done" in msg:
                tag = "pass"
            elif "WARNING" in msg:
                tag = "warn"
            elif msg.startswith("=") or msg.startswith("  ORCHESTRATOR") or msg.startswith("  METRO"):
                tag = "heading"
        color = TAG_COLORS.get(tag, TEXT_LIGHT)
        wt = "600" if tag == "heading" else "normal"
        esc = html.escape(msg)
        self._log.append(
            f'<pre style="margin:0; color:{color}; font-weight:{wt};'
            f' font-family:{MONO_FAMILY}; font-size:8.5pt;">{esc}</pre>'
        )
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_ind(self, mod, st):
        if mod in self._dots:
            self._dots[mod].set_status(st)

    # ------------------------------------------------------------------
    def _on_run(self):
        if self._running:
            return
        ip = Path(self._in.text())
        op = Path(self._out.text())
        if not ip.exists():
            self._log_msg(f"Input folder not found: {ip}", "fail")
            return
        op.mkdir(parents=True, exist_ok=True)

        self._running = True
        self._run.setEnabled(False)
        self._run.setText("⏳ Running…")
        self._status.setText("Scanning…")
        self._status.setStyleSheet(
            f"color:{WARN_AMBER}; background:transparent;"
            f" font-family:{FONT_FAMILY}; font-size:8.5pt;"
        )
        for d in self._dots.values():
            d.set_status("skip")
        self._log.clear()

        eir = self._eir_versions[self._eir_combo.currentIndex()]
        self._worker = ReviewWorker(ip, op, self._sig, eir_version=eir)
        self._worker.start()

    def _on_finish(self, ok):
        self._running = False
        self._run.setEnabled(True)
        self._run.setText("▶  Run Review")
        if ok:
            self._status.setText("Pass")
            self._status.setStyleSheet(
                f"color:{PASS_GREEN}; background:transparent;"
                f" font-family:{FONT_FAMILY}; font-size:8.5pt;"
            )
        else:
            self._status.setText("Issues found")
            self._status.setStyleSheet(
                f"color:{FAIL_RED}; background:transparent;"
                f" font-family:{FONT_FAMILY}; font-size:8.5pt;"
            )


# ---------------------------------------------------------------------------
def launch():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MetroApp()
    w.show()
    sys.exit(app.exec())
