#!/usr/bin/env python3
"""QuickView — macOS-like Quick Look for KDE Plasma / Dolphin"""

import sys
import os
import mimetypes
import subprocess
import tempfile
import glob
import zipfile
import tarfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTextBrowser, QTextEdit,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QSlider,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QPoint, QRect, QByteArray, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPixmap, QImage, QKeyEvent, QMouseEvent, QRegion

try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget as _QOGLWidget
    from PyQt6.QtGui import QOpenGLContext as _QOGLCtx
    import mpv as _mpv
    HAS_MPV = True
except ImportError:
    HAS_MPV = False
    _QOGLWidget = QWidget  # dummy base so the class block is skipped

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtCore import QUrl
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


# ── Draggable title bar ───────────────────────────────────────────────────────

class TitleBar(QWidget):
    """Title bar that drags the parent QMainWindow via compositor (Wayland-safe)."""

    def __init__(self, parent_win: QMainWindow):
        super().__init__(objectName="titlebar")
        self._win = parent_win
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._win.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)


# ── Image label that stays scaled to its container ───────────────────────────

class ScaledImageLabel(QLabel):
    """QLabel that rescales its pixmap whenever the widget is resized."""

    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self._src = pixmap
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self):
        if self._src.isNull():
            return
        scaled = self._src.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        super().setPixmap(scaled)


# ── Blur effect via KWindowEffects ────────────────────────────────────────────

def _enable_blur(window: QMainWindow) -> None:
    """Enable KDE compositor blur-behind for the given window."""
    try:
        import ctypes
        from PyQt6 import sip

        lib = ctypes.CDLL("libKF6WindowSystem.so.6")
        fn = lib["_ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion"]
        fn.restype = None
        fn.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p]

        qwindow = window.windowHandle()
        if qwindow is None:
            return

        region = QRegion()  # empty = entire window surface
        fn(
            sip.unwrapinstance(qwindow),
            True,
            sip.unwrapinstance(region),
        )
    except Exception:
        pass  # blur is cosmetic — fail silently


# ── Archive listing ───────────────────────────────────────────────────────────

_ARCHIVE_MIME = {
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-xz",
    "application/x-7z-compressed",
    "application/x-rar",
    "application/x-rar-compressed",
    "application/zstd",
    "application/x-lz4",
}
_ARCHIVE_SUFFIX = {
    ".zip", ".tar", ".gz", ".bz2", ".tgz", ".tbz2",
    ".7z", ".rar", ".xz", ".zst", ".lz4", ".iso",
}


def _list_archive(path: Path) -> list[tuple[str, int]]:
    """Return [(name, size_bytes)] for every entry in the archive."""
    suffix = path.suffix.lower()

    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                return [(i.filename, i.file_size) for i in zf.infolist()]
    except Exception:
        pass

    try:
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as tf:
                return [(m.name + ("/" if m.isdir() else ""), m.size)
                        for m in tf.getmembers()]
    except Exception:
        pass

    # Fallback: 7z handles 7z, rar, iso, cab, etc.
    try:
        r = subprocess.run(
            ["7z", "l", "-slt", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        entries: list[tuple[str, int]] = []
        name = size = None
        for line in r.stdout.splitlines():
            if line.startswith("Path = ") and name is None:
                name = line[7:]
            elif line.startswith("Size = "):
                try:
                    size = int(line[7:])
                except ValueError:
                    size = 0
            elif line.startswith("----------"):
                if name is not None:
                    entries.append((name, size or 0))
                name = size = None
        if name:
            entries.append((name, size or 0))
        if entries:
            # 7z includes the archive itself as the first entry; drop it
            return entries[1:] if entries[0][0] == str(path) else entries
    except Exception:
        pass

    return []


def _list_directory(path: Path) -> list[tuple[str, int]]:
    """Return [(name, size)] for directory entries (dirs first, then files)."""
    try:
        entries = list(path.iterdir())
    except PermissionError:
        return []
    dirs  = sorted((e for e in entries if e.is_dir()),  key=lambda e: e.name.lower())
    files = sorted((e for e in entries if e.is_file()), key=lambda e: e.name.lower())
    result = []
    for e in dirs:
        result.append((e.name + "/", -1))        # -1 = directory marker
    for e in files:
        try:
            result.append((e.name, e.stat().st_size))
        except OSError:
            result.append((e.name, 0))
    return result


def _fmt_directory(path: Path, entries: list[tuple[str, int]]) -> str:
    dirs  = sum(1 for _, s in entries if s == -1)
    files = sum(1 for _, s in entries if s >= 0)
    parts = []
    if dirs:  parts.append(f"{dirs} {'папка' if dirs == 1 else 'папки' if 2 <= dirs <= 4 else 'папок'}")
    if files: parts.append(f"{files} {'файл' if files == 1 else 'файла' if 2 <= files <= 4 else 'файлов'}")
    lines = ["  " + "  ·  ".join(parts) + "\n", "─" * 52]
    for name, size in entries:
        if size == -1:
            lines.append(f"  📁 {name}")
        else:
            lines.append(f"  📄 {name:<42}{_fmt_size(size).rjust(9)}")
    return "\n".join(lines)


def _fmt_archive(path: Path, entries: list[tuple[str, int]]) -> str:
    """Format archive listing as readable text."""
    total = sum(s for _, s in entries)
    lines = [
        f"  {len(entries)} files  ·  {_fmt_size(total)} uncompressed\n",
        "─" * 52,
    ]
    for name, size in entries:
        size_str = _fmt_size(size).rjust(10) if size else "          "
        lines.append(f"  {name:<40}  {size_str}")
    return "\n".join(lines)


# ── Async loader ──────────────────────────────────────────────────────────────

class LoaderThread(QThread):
    # emits QPixmap | str | list[tuple[str,int]]
    ready = pyqtSignal(object)

    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self._tmp_files: list[str] = []

    def run(self):
        if self.file_path.is_dir():
            entries = _list_directory(self.file_path)
            self.ready.emit(entries if entries is not None else "")
            return

        mime, _ = mimetypes.guess_type(str(self.file_path))
        mime = mime or ""
        suffix = self.file_path.suffix.lower()

        if mime.startswith("image/"):
            # QImage is thread-safe; QPixmap must be created in the GUI thread
            img = QImage(str(self.file_path))
            self.ready.emit(img if not img.isNull() else "")

        elif mime == "application/pdf":
            img = self._pdf_to_image()
            self.ready.emit(img if img and not img.isNull() else "")

        elif mime.startswith("video/") or mime.startswith("audio/"):
            if HAS_MPV:
                kind = "video" if mime.startswith("video/") else "audio"
                self.ready.emit((kind, str(self.file_path)))
            else:
                img = self._video_thumbnail_image()
                self.ready.emit(img if img and not img.isNull() else "")

        elif mime in _ARCHIVE_MIME or suffix in _ARCHIVE_SUFFIX:
            entries = _list_archive(self.file_path)
            self.ready.emit(entries if entries else "")

        elif mime == "text/html" and HAS_WEBENGINE:
            self.ready.emit(("html", str(self.file_path)))

        elif mime.startswith("text/") or self._is_text():
            try:
                text = self.file_path.read_text(errors="replace")
                if len(text) > 30_000:
                    text = text[:30_000] + "\n\n… [truncated]"
                self.ready.emit(text)
            except Exception as e:
                self.ready.emit(f"[Error reading file: {e}]")

        else:
            self.ready.emit("")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _pdf_to_image(self) -> QImage | None:
        tmp = tempfile.mktemp(suffix=".png")
        self._tmp_files.append(tmp)
        r = subprocess.run(
            ["pdftoppm", "-r", "180", "-l", "1", "-png",
             str(self.file_path), tmp[:-4]],
            capture_output=True,
        )
        candidates = glob.glob(tmp[:-4] + "*.png")
        if r.returncode == 0 and candidates:
            return QImage(candidates[0])
        return None

    def _video_thumbnail_image(self) -> QImage | None:
        tmp = tempfile.mktemp(suffix=".png")
        self._tmp_files.append(tmp)
        r = subprocess.run(
            ["ffmpegthumbnailer", "-i", str(self.file_path),
             "-o", tmp, "-s", "0", "-q", "8"],
            capture_output=True,
        )
        if r.returncode == 0 and os.path.exists(tmp):
            return QImage(tmp)
        return None

    def _is_text(self) -> bool:
        try:
            with open(self.file_path, "rb") as f:
                return b"\x00" not in f.read(1024)
        except Exception:
            return False

    def cleanup(self):
        for f in self._tmp_files:
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass


# ── Styles ────────────────────────────────────────────────────────────────────

# Slightly lower alpha so the blur is visible through the window
_BG = "rgba(20, 20, 26, 185)"

STYLE = f"""
QMainWindow {{ background: transparent; }}

#shell {{
    background-color: {_BG};
    border-radius: 14px;
    border: none;
}}
#titlebar {{ background: transparent; }}
#filename  {{ color: rgba(255,255,255,215); font-size: 14px; font-weight: 600; }}
#fileinfo  {{ color: rgba(255,255,255,90);  font-size: 11px; }}

#closeBtn {{
    background: rgba(255,255,255,22); color: rgba(255,255,255,180);
    border: none; border-radius: 11px; font-size: 12px;
    min-width: 22px; min-height: 22px; max-width: 22px; max-height: 22px;
}}
#closeBtn:hover {{ background: rgba(230,60,60,200); color: white; }}

QScrollArea  {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent; width: 6px; border: none;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,55); border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QTextBrowser, #textView {{
    background: transparent;
    color: rgba(255,255,255,210);
    font-family: "Hack","JetBrains Mono","Fira Code","Cascadia Code",monospace;
    font-size: 13px; border: none;
    selection-background-color: rgba(80,140,255,160);
}}

#infoWidget {{ background: transparent; }}
#infoIcon   {{ font-size: 52px; }}
#infoName   {{ color: rgba(255,255,255,210); font-size: 16px; font-weight: 600; }}
#infoMeta   {{ color: rgba(255,255,255,110); font-size: 13px; }}
#spinner    {{ color: rgba(255,255,255,130); font-size: 15px; }}
"""


# ── Main window ───────────────────────────────────────────────────────────────

class QuickViewWindow(QMainWindow):
    def __init__(self, file_path: str):
        super().__init__()
        self.path = Path(file_path).resolve()
        self._loader: LoaderThread | None = None

        self.setWindowTitle("QuickView")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)

        self._build_ui()
        # Probe the content size synchronously (fast header reads only),
        # so the window is shown at the correct size from the start.
        # KWin then centers it correctly via the window rule.
        self._set_geometry(*_probe_size(self.path))
        self._start_load()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        shell = QWidget(objectName="shell")
        self.setCentralWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Draggable title bar
        titlebar = TitleBar(self)
        tb = QHBoxLayout(titlebar)
        tb.setContentsMargins(14, 0, 10, 0)
        tb.setSpacing(8)

        btn = QPushButton("✕", objectName="closeBtn")
        btn.clicked.connect(self.close)
        btn.setCursor(Qt.CursorShape.ArrowCursor)

        self.lbl_name = QLabel(self.path.name, objectName="filename")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_info = QLabel(self._meta_line(), objectName="fileinfo")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        # [btn-width spacer] [stretch] [name centered] [stretch] [size] [btn]
        left = QWidget()
        left.setFixedWidth(btn.sizeHint().width())
        tb.addWidget(left)
        tb.addStretch(1)
        tb.addWidget(self.lbl_name)
        tb.addStretch(1)
        tb.addWidget(self.lbl_info)
        tb.addSpacing(10)
        tb.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,15);")
        sep.setFixedHeight(1)

        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 0, 0, 0)

        self.spinner = QLabel("Loading…", objectName="spinner")
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_lay.addWidget(self.spinner)

        root.addWidget(titlebar)
        root.addWidget(sep)
        root.addWidget(self.content, 1)

    def _set_geometry(self, w: int, h: int):
        self.resize(w, h)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: _enable_blur(self))

    # ── Loading ───────────────────────────────────────────────────────────────

    def _start_load(self):
        self._loader = LoaderThread(self.path)
        self._loader.ready.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, result):
        self._clear_content()
        if isinstance(result, QImage) and not result.isNull():
            result = QPixmap.fromImage(result)

        if isinstance(result, tuple) and result[0] in ("video", "audio"):
            self._media_view = MediaView(Path(result[1]), result[0] == "video")
            self.content_lay.addWidget(self._media_view)
        elif isinstance(result, tuple) and result[0] == "html":
            self._show_html(result[1])
        elif isinstance(result, QPixmap) and not result.isNull():
            self._show_pixmap(result)
        elif isinstance(result, list):
            if self.path.is_dir():
                self._show_text(_fmt_directory(self.path, result), plain=True)
            else:
                self._show_text(_fmt_archive(self.path, result), plain=True)
        elif isinstance(result, str) and result:
            self._show_text(result)
        else:
            self._show_info()
        if self._loader:
            self._loader.cleanup()

    def _clear_content(self):
        for i in reversed(range(self.content_lay.count())):
            w = self.content_lay.itemAt(i).widget()
            if w:
                w.setParent(None)

    # ── Views ─────────────────────────────────────────────────────────────────

    def _show_pixmap(self, pixmap: QPixmap):
        label = ScaledImageLabel(pixmap)
        self.content_lay.addWidget(label)

    def _show_html(self, file_path: str):
        view = QWebEngineView()
        view.setUrl(QUrl.fromLocalFile(file_path))
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_lay.addWidget(view)

    def _show_text(self, text: str, plain: bool = False):
        browser = QTextBrowser()
        browser.setOpenLinks(False)
        browser.setFrameShape(QFrame.Shape.NoFrame)

        if not plain:
            html = _pygments_html(text, self.path)
            if html:
                browser.setHtml(html)
                browser.setStyleSheet(
                    "QTextBrowser { background: #272822; border: none; }"
                )
                self.content_lay.addWidget(browser)
                return

        # Plain text fallback (archives or pygments unavailable)
        browser.setPlainText(text)
        browser.setStyleSheet(
            "QTextBrowser { background: transparent; color: rgba(255,255,255,200);"
            " border: none; font-family: monospace; font-size: 13px; }"
        )
        self.content_lay.addWidget(browser)

    def _show_info(self):
        w = QWidget(objectName="infoWidget")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        mime, _ = mimetypes.guess_type(str(self.path))
        for text, name in [
            (_mime_icon(mime or ""), "infoIcon"),
            (self.path.name, "infoName"),
            (self._meta_line(verbose=True), "infoMeta"),
        ]:
            lbl = QLabel(text, objectName=name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)

        self.content_lay.addWidget(w)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _meta_line(self, verbose=False) -> str:
        try:
            size_str = _fmt_size(self.path.stat().st_size)
        except OSError:
            size_str = "?"
        if verbose:
            mime, _ = mimetypes.guess_type(str(self.path))
            return f"{mime or 'unknown type'}  ·  {size_str}"
        return size_str

    # ── Events ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            if hasattr(self, "_media_view"):
                self._media_view.toggle_play()  # Space = play/pause for media
            else:
                self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "_media_view"):
            self._media_view.terminate()
        super().closeEvent(event)


# ── Media player ─────────────────────────────────────────────────────────────

def _fmt_time(secs: float) -> str:
    s = int(secs)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


if HAS_MPV:
    class MpvWidget(_QOGLWidget):
        """Qt widget that renders mpv output via OpenGL (Wayland-compatible)."""

        def __init__(self, audio_only: bool = False, parent=None):
            import locale
            locale.setlocale(locale.LC_NUMERIC, "C")  # required by libmpv
            super().__init__(parent)
            self._audio_only = audio_only
            self._ctx = None
            self._player = _mpv.MPV(
                ytdl=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
            )
            if audio_only:
                self._player["vid"] = "no"
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumSize(1, 1)

        def initializeGL(self):
            def get_proc_addr(_, name):
                ctx = _QOGLCtx.currentContext()
                if ctx is None:
                    return 0
                addr = ctx.getProcAddress(QByteArray(name))
                return int(addr) if addr else 0

            self._ctx = _mpv.MpvRenderContext(
                self._player, "opengl",
                opengl_init_params={"get_proc_address": get_proc_addr},
            )
            self._ctx.update_cb = self.update  # thread-safe Qt update request

        def paintGL(self):
            if self._ctx:
                self._ctx.render(
                    flip_y=True,
                    opengl_fbo={
                        "w": int(self.width()  * self.devicePixelRatioF()),
                        "h": int(self.height() * self.devicePixelRatioF()),
                        "fbo": self.defaultFramebufferObject(),
                        "pixel_format": 0,
                    },
                )

        def resizeGL(self, w, h):
            self.update()

        def play(self, path: str):
            self._player.play(path)

        def terminate(self):
            try:
                if self._ctx:
                    self._ctx.free()
                    self._ctx = None
                self._player.terminate()
            except Exception:
                pass

        @property
        def player(self):
            return self._player


    class MediaView(QWidget):
        """Video/audio player widget with playback controls."""

        STYLE = """
        #playBtn {
            background: rgba(255,255,255,28); color: white;
            border: none; border-radius: 14px; font-size: 14px;
            min-width: 28px; max-width: 28px;
            min-height: 28px; max-height: 28px;
        }
        #playBtn:hover { background: rgba(255,255,255,55); }
        QSlider::groove:horizontal {
            background: rgba(255,255,255,28); height: 4px; border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: rgba(255,255,255,150); border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: white; width: 12px; height: 12px;
            border-radius: 6px; margin: -4px 0;
        }
        #timeLabel { color: rgba(255,255,255,140); font-size: 11px; }
        """

        def __init__(self, path: Path, is_video: bool, parent=None):
            super().__init__(parent)
            self.setStyleSheet(self.STYLE)
            self._seeking = False

            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 10)
            lay.setSpacing(4)

            self._mpv = MpvWidget(audio_only=not is_video)

            if is_video:
                lay.addWidget(self._mpv, 1)
            else:
                # Audio: show big icon, mpv plays audio silently in background
                icon = QLabel("🎵")
                icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon.setStyleSheet("font-size: 72px; background: transparent;")
                lay.addWidget(icon, 1)

            # Controls bar
            ctrl = QWidget()
            cl = QHBoxLayout(ctrl)
            cl.setContentsMargins(12, 0, 12, 0)
            cl.setSpacing(8)

            self._btn = QPushButton("⏸", objectName="playBtn")
            self._btn.clicked.connect(self._toggle_play)

            self._slider = QSlider(Qt.Orientation.Horizontal)
            self._slider.setRange(0, 10000)
            self._slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
            self._slider.sliderReleased.connect(self._do_seek)

            self._lbl = QLabel("0:00 / 0:00", objectName="timeLabel")

            cl.addWidget(self._btn)
            cl.addWidget(self._slider, 1)
            cl.addWidget(self._lbl)
            lay.addWidget(ctrl)

            self._timer = QTimer(interval=300)
            self._timer.timeout.connect(self._update_ui)
            self._timer.start()

            self._mpv.play(str(path))

        def toggle_play(self):
            self._toggle_play()

        def _toggle_play(self):
            try:
                p = self._mpv.player
                p.pause = not p.pause
                self._btn.setText("▶" if p.pause else "⏸")
            except Exception:
                pass

        def _do_seek(self):
            self._seeking = False
            try:
                dur = self._mpv.player.duration
                if dur:
                    self._mpv.player.seek(
                        self._slider.value() / 10000 * dur, "absolute"
                    )
            except Exception:
                pass

        def _update_ui(self):
            if self._seeking:
                return
            try:
                pos = self._mpv.player.time_pos or 0.0
                dur = self._mpv.player.duration or 0.0
                if dur > 0:
                    self._slider.setValue(int(pos / dur * 10000))
                self._lbl.setText(f"{_fmt_time(pos)} / {_fmt_time(dur)}")
            except Exception:
                pass

        def terminate(self):
            self._timer.stop()
            self._mpv.terminate()


# ── Quick size probe (runs before window is shown) ────────────────────────────

def _probe_size(path: Path) -> tuple[int, int]:
    """Return (w, h) for the window without fully loading the file."""
    screen = QApplication.primaryScreen().availableGeometry()
    max_w = int(screen.width()  * 0.88)
    max_h = int(screen.height() * 0.88)
    PAD_W, PAD_H = 24, 80

    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or ""
    suffix = path.suffix.lower()

    # Directory
    if path.is_dir():
        try:
            n = sum(1 for _ in path.iterdir())
        except Exception:
            n = 20
        return min(640, max_w), min(max(320, n * 22 + 120), max_h)

    # Images: read only the header via PIL (< 2 ms even for large files)
    if mime.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(path) as img:
                iw, ih = img.size
            scale = min((max_w - PAD_W) / iw, (max_h - PAD_H) / ih, 1.0)
            return (max(400, int(iw * scale) + PAD_W),
                    max(300, int(ih * scale) + PAD_H))
        except Exception:
            pass

    # Archives: quick listing for zip/tar, default for others
    if mime in _ARCHIVE_MIME or suffix in _ARCHIVE_SUFFIX:
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zf:
                    n = len(zf.namelist())
                return min(680, max_w), min(max(320, n * 21 + 140), max_h)
        except Exception:
            pass
        try:
            if tarfile.is_tarfile(path):
                with tarfile.open(path) as tf:
                    n = sum(1 for _ in tf)
                return min(680, max_w), min(max(320, n * 21 + 140), max_h)
        except Exception:
            pass
        return min(680, max_w), 480

    # Text: estimate from file size
    if mime.startswith("text/") or (
        not mime and path.suffix.lower() not in _ARCHIVE_SUFFIX
    ):
        try:
            size = path.stat().st_size
            # rough: ~60 chars/line, 13px line height
            lines = min(size // 60, 800)
            return min(840, max_w), min(max(320, int(lines * 19) + PAD_H), max_h)
        except Exception:
            pass

    # PDF: read page dimensions via pdfinfo
    if mime == "application/pdf":
        try:
            r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if line.startswith("Page size:"):
                    # "Page size:      595.28 x 841.89 pts (A4)"
                    parts = line.split(":")[1].split("x")
                    pw = float(parts[0].strip().split()[0])
                    ph = float(parts[1].strip().split()[0])
                    # pts → approx pixels at 96 dpi (1 pt = 1.333 px)
                    pw, ph = pw * 1.333, ph * 1.333
                    scale = min((max_w - PAD_W) / pw, (max_h - PAD_H) / ph, 1.5)
                    return (max(400, int(pw * scale) + PAD_W),
                            max(300, int(ph * scale) + PAD_H))
        except Exception:
            pass
        return 680, 880

    # Video: read dimensions via ffprobe
    if mime.startswith("video/"):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height",
                 "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=5,
            )
            vw, vh = (int(x) for x in r.stdout.strip().split(","))
            scale = min((max_w - PAD_W) / vw, (max_h - PAD_H) / vh, 1.0)
            return (max(400, int(vw * scale) + PAD_W),
                    max(300, int(vh * scale) + PAD_H))
        except Exception:
            pass
        return 820, 500

    # Audio player
    if mime.startswith("audio/"):
        return 480, 220

    return 480, 360


# ── Pygments helper ───────────────────────────────────────────────────────────

def _pygments_html(text: str, path: Path) -> str | None:
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_for_filename, TextLexer
        from pygments.formatters import HtmlFormatter
        from pygments.util import ClassNotFound

        try:
            lexer = get_lexer_for_filename(str(path), stripall=True)
        except ClassNotFound:
            lexer = TextLexer()

        formatter = HtmlFormatter(
            style="monokai",
            noclasses=True,
            prestyles="background:#272822; padding:14px 16px; margin:0; "
                      "font-family:'Hack','JetBrains Mono','Fira Code',monospace; "
                      "font-size:13px; line-height:1.55;",
            nobackground=False,
        )
        code = highlight(text, lexer, formatter)
        return (
            "<html><body style='background:#272822; margin:0; padding:0;'>"
            f"{code}</body></html>"
        )
    except ImportError:
        return None


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _mime_icon(mime: str) -> str:
    if mime.startswith("image/"):    return "🖼"
    if mime.startswith("video/"):    return "🎬"
    if mime.startswith("audio/"):    return "🎵"
    if mime == "application/pdf":    return "📄"
    if mime.startswith("text/"):     return "📝"
    if mime in _ARCHIVE_MIME:        return "📦"
    return "📁"


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: quickview <file>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"quickview: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("QuickView")
    app.setDesktopFileName("quickview")   # sets Wayland app_id → KWin matches by this

    win = QuickViewWindow(file_path)
    win.show()
    win.raise_()
    win.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
