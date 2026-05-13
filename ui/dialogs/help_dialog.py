"""
Help dialog with QWebEngineView — light/dark mode, Perlin contours, glass cards.
"""

import os
import re
import sys
import json

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl, QSettings, Qt
from PyQt5.QtGui import QDesktopServices
from qt_chrome import FramelessDialogMixin
from styles.colors import Colors


# ---------------------------------------------------------------------------
# Bridge  (Python ↔ JS)
# ---------------------------------------------------------------------------

class HelpBridge(QObject):
    """Exposed to JavaScript via QWebChannel as ``bridge``."""

    close_requested = pyqtSignal()

    def __init__(self, dialog: "HelpDialog"):
        super().__init__()
        self._dialog = dialog

    # -- Slots called from JS --------------------------------------------------

    @pyqtSlot(str)
    def loadPage(self, page_name: str):
        body = self._dialog._extract_body(page_name)
        safe = json.dumps(body)
        page_id = json.dumps(page_name)
        self._dialog.web_view.page().runJavaScript(
            f"receivePageContent({safe}, {page_id});"
        )

    @pyqtSlot(str)
    def searchContent(self, query: str):
        results = self._dialog._search_files(query)
        payload = json.dumps(results)
        self._dialog.web_view.page().runJavaScript(
            f"receiveSearchResults({payload});"
        )

    @pyqtSlot(str)
    def saveTheme(self, theme: str):
        settings = QSettings("DTU", "HeadAnalyser")
        settings.setValue("help_theme", theme)

    @pyqtSlot(str)
    def openExternal(self, url: str):
        QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot()
    def requestClose(self):
        self.close_requested.emit()


# ---------------------------------------------------------------------------
# Custom page — intercept external link clicks
# ---------------------------------------------------------------------------

class _HelpPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            scheme = url.scheme()
            if scheme in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class HelpDialog(FramelessDialogMixin, QDialog):
    """Full QWebEngineView help dialog — ``HelpDialog(parent).exec_()``."""

    # Nav items: (id, label, svg_icon, filename)
    NAV_ITEMS = [
        ("getting_started", "Getting Started",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10 L10 3 L17 10"/><path d="M5 9 L5 16 A1 1 0 0 0 6 17 L14 17 A1 1 0 0 0 15 16 L15 9"/></svg>',
         "getting_started.html"),
        ("user_interface", "User Interface",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="16" height="14" rx="2"/><path d="M2 7 L18 7"/><path d="M7 7 L7 17"/></svg>',
         "user_interface.html"),
        ("file_formats", "File Formats",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 2 L5 18 L15 18 L15 6 L11 2 Z"/><path d="M11 2 L11 6 L15 6"/><path d="M7 10 L13 10"/><path d="M7 13 L11 13"/></svg>',
         "file_formats.html"),
        ("plots", "Plots & Visualisation",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17 L3 3"/><path d="M3 17 L17 17"/><path d="M5 13 L8 8 L11 11 L15 5"/></svg>',
         "plots.html"),
        ("exporting", "Exporting",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 L10 13"/><path d="M6 9 L10 13 L14 9"/><path d="M3 15 L3 17 L17 17 L17 15"/></svg>',
         "exporting.html"),
        ("statistics", "Statistics & Analysis",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="3" height="7"/><rect x="8.5" y="6" width="3" height="11"/><rect x="14" y="3" width="3" height="14"/></svg>',
         "statistics.html"),
        ("sensitivity_analysis", "Sensitivity Analysis",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 14 L7 6 L11 12 L15 4 L17 8"/><circle cx="7" cy="6" r="1.5"/><circle cx="11" cy="12" r="1.5"/><circle cx="15" cy="4" r="1.5"/></svg>',
         "sensitivity_analysis.html"),
        ("map_view", "Map View",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 17 C10 17 4 11.5 4 7.5 A6 6 0 0 1 16 7.5 C16 11.5 10 17 10 17Z"/><circle cx="10" cy="7.5" r="2"/></svg>',
         "map_view.html"),
        ("data_filtration", "Filtration & Settings",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4 L18 4 L12 10.5 L12 15 L8 17 L8 10.5 Z"/></svg>',
         "data_filtration.html"),
        ("shortcuts", "Shortcuts & Tips",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="16" height="10" rx="2"/><path d="M5 10 L7 10"/><path d="M9 10 L11 10"/><path d="M13 10 L15 10"/><path d="M6 13 L14 13"/></svg>',
         "shortcuts.html"),
        ("about", "About & References",
         '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7.5"/><path d="M10 9 L10 14"/><circle cx="10" cy="6.5" r="0.5" fill="currentColor" stroke="none"/></svg>',
         "about.html"),
    ]

    def __init__(self, parent=None, initial_page: str | None = None):
        super().__init__(parent)
        self._initial_page = initial_page  # e.g. "sensitivity_analysis"
        self.setWindowTitle("HeadAnalyser Help & Documentation")
        self.resize(1060, 720)
        self.setMinimumSize(700, 450)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        if parent:
            pg = parent.geometry()
            self.move(pg.x() + (pg.width() - 1060) // 2,
                      pg.y() + (pg.height() - 720) // 2)

        # Resolve help_content directory
        try:
            base = sys._MEIPASS
            self.help_dir = os.path.join(base, "help_content")
        except AttributeError:
            root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.help_dir = os.path.join(root, "help_content")

        self._setup_ui()
        self.bind_frameless_drag_widget(self._chrome_header)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("helpChromeHeader")
        header.setFixedHeight(42)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        title = QLabel("Help & Documentation")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("helpChromeClose")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.accept)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        self._chrome_header = header

        self.web_view = QWebEngineView()
        custom_page = _HelpPage(self.web_view)
        self.web_view.setPage(custom_page)

        self._bridge = HelpBridge(self)
        self._bridge.close_requested.connect(self.accept)

        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.web_view.page().setWebChannel(self._channel)

        layout.addWidget(self.web_view)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Colors.BG_MODAL};
            }}
            QWidget#helpChromeHeader {{
                background-color: {Colors.BG_SURFACE};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
            QPushButton#helpChromeClose {{
                background: transparent;
                border: none;
                border-radius: 6px;
                color: {Colors.TEXT_TERTIARY};
                font-size: 14px;
            }}
            QPushButton#helpChromeClose:hover {{
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
            """
        )

        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.setHtml(self._build_html(), QUrl("about:blank"))

    def on_dialog_chrome_state_changed(self, is_frameless: bool, is_maximized: bool):
        if hasattr(self, "_chrome_header"):
            self._chrome_header.setVisible(bool(is_frameless))

    # ------------------------------------------------------------------
    # After page loads — push saved theme + first page
    # ------------------------------------------------------------------

    def _on_load_finished(self, ok: bool):
        if not ok:
            return
        settings = QSettings("DTU", "HeadAnalyser")
        theme = settings.value("help_theme", "light")
        self.web_view.page().runJavaScript(f'setTheme("{theme}");')

        # Determine which page to show first
        nav_id = "getting_started"
        filename = "getting_started.html"
        if self._initial_page:
            for nid, _, _, fname in self.NAV_ITEMS:
                if nid == self._initial_page:
                    nav_id = nid
                    filename = fname
                    break

        # Push initial page directly — bridge may not be wired yet
        body = self._extract_body(filename)
        safe = json.dumps(body)
        self.web_view.page().runJavaScript(
            f'_currentNavId = "{nav_id}";'
            f'document.querySelector(\'.nav-item[data-id="{nav_id}"]\').classList.add("active");'
            f'receivePageContent({safe}, "{filename}");'
        )

    # ------------------------------------------------------------------
    # Help-file helpers
    # ------------------------------------------------------------------

    def _extract_body(self, filename: str) -> str:
        path = os.path.join(self.help_dir, filename)
        if not os.path.isfile(path):
            return (
                '<h1>Coming Soon</h1>'
                f'<p>The page <code>{filename}</code> is being written.</p>'
                '<p>Check back in a future update!</p>'
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as exc:
            return f"<h1>Error</h1><p>{exc}</p>"

        m = re.search(r"<body[^>]*>(.*)</body>", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else raw

    def _search_files(self, query: str):
        query_lower = query.lower()
        results = []
        for nav_id, label, _, fname in self.NAV_ITEMS:
            path = os.path.join(self.help_dir, fname)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
            except Exception:
                continue
            text = re.sub(r"<[^>]+>", " ", raw)
            idx = text.lower().find(query_lower)
            if idx == -1:
                continue
            start = max(0, idx - 60)
            end = min(len(text), idx + len(query) + 60)
            context = text[start:end].strip()
            results.append({
                "title": label,
                "filename": fname,
                "navId": nav_id,
                "context": context,
            })
        return results

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------

    def _build_html(self) -> str:
        nav_html = ""
        for nav_id, label, icon, fname in self.NAV_ITEMS:
            nav_html += (
                f'<button class="nav-item" data-id="{nav_id}" data-file="{fname}" '
                f'onclick="navigateTo(\'{nav_id}\',\'{fname}\')">'
                f'<span class="nav-icon">{icon}</span>'
                f'<span class="nav-label">{label}</span>'
                f'</button>\n'
            )

        return f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<style>
/* ===== CSS Custom Properties ===== */
:root {{
  --page-bg: #f8f9fc;
  --sidebar-bg: #f1f3f8;
  --sidebar-hover: #e8ebf4;
  --sidebar-active: #e0e4f0;
  --sidebar-border: #e2e5ee;
  --card-bg: rgba(255,255,255,0.82);
  --card-border: rgba(0,0,0,0.06);
  --card-shadow: 0 2px 16px rgba(0,0,0,0.06);
  --text-primary: #1a1c2b;
  --text-secondary: #4a4d5e;
  --text-muted: #6b6e80;
  --accent: #6366f1;
  --accent-light: #818cf8;
  --accent-bg: rgba(99,102,241,0.08);
  --accent-border: rgba(99,102,241,0.22);
  --contour-color: rgba(99,102,241,0.08);
  --contour-major: rgba(99,102,241,0.14);
  --input-bg: #ffffff;
  --input-border: #d1d5e0;
  --scroll-thumb: #c4c8d4;
  --scroll-track: transparent;
  --code-bg: #f0f2f7;
  --code-border: #e2e5ee;
  --table-header-bg: #6366f1;
  --table-header-color: #ffffff;
  --table-row-alt: #f8f9fc;
  --table-border: #e2e5ee;
  --note-bg: #fffbeb;
  --note-border: #f59e0b;
  --note-text: #92400e;
  --tip-bg: #ecfdf5;
  --tip-border: #10b981;
  --tip-text: #065f46;
  --warning-bg: #fef2f2;
  --warning-border: #ef4444;
  --warning-text: #991b1b;
  --hr-color: #e5e7eb;
  --link-color: #6366f1;
  --search-highlight: rgba(99,102,241,0.15);
}}

[data-theme="dark"] {{
  --page-bg: #0f0f12;
  --sidebar-bg: #141418;
  --sidebar-hover: #1e1e24;
  --sidebar-active: #212127;
  --sidebar-border: #28282f;
  --card-bg: rgba(26,26,31,0.82);
  --card-border: rgba(255,255,255,0.06);
  --card-shadow: 0 2px 20px rgba(0,0,0,0.35);
  --text-primary: #ececf0;
  --text-secondary: #a8a8b3;
  --text-muted: #6e6e7a;
  --accent: #818cf8;
  --accent-light: #a5b4fc;
  --accent-bg: rgba(129,140,248,0.1);
  --accent-border: rgba(129,140,248,0.25);
  --contour-color: rgba(129,140,248,0.06);
  --contour-major: rgba(165,180,252,0.12);
  --input-bg: #1a1a1f;
  --input-border: #2f2f37;
  --scroll-thumb: #3a3a44;
  --scroll-track: transparent;
  --code-bg: #1a1a1f;
  --code-border: #28282f;
  --table-header-bg: #818cf8;
  --table-header-color: #ffffff;
  --table-row-alt: #17171c;
  --table-border: #28282f;
  --note-bg: rgba(245,158,11,0.08);
  --note-border: #f59e0b;
  --note-text: #fbbf24;
  --tip-bg: rgba(16,185,129,0.08);
  --tip-border: #10b981;
  --tip-text: #34d399;
  --warning-bg: rgba(239,68,68,0.08);
  --warning-border: #ef4444;
  --warning-text: #f87171;
  --hr-color: #28282f;
  --link-color: #a5b4fc;
  --search-highlight: rgba(129,140,248,0.2);
}}

/* ===== Reset & Base ===== */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
  width: 100%; height: 100%; overflow: hidden;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--page-bg);
  color: var(--text-primary);
  transition: background 0.3s, color 0.3s;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: var(--scroll-track); }}
::-webkit-scrollbar-thumb {{ background: var(--scroll-thumb); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

/* ===== Canvas ===== */
#contour-canvas {{
  position: fixed; top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 0; pointer-events: none;
}}

/* ===== App Shell ===== */
.app-shell {{
  position: relative; z-index: 1;
  display: flex; width: 100%; height: 100%;
}}

/* ===== Sidebar ===== */
.sidebar {{
  width: 240px; min-width: 240px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  display: flex; flex-direction: column;
  z-index: 20;
  transition: background 0.3s, border-color 0.3s;
}}

.sidebar-header {{
  padding: 20px 18px 14px;
  border-bottom: 1px solid var(--sidebar-border);
}}
.sidebar-header h2 {{
  font-size: 14px; font-weight: 700;
  color: var(--text-primary); margin-bottom: 12px;
  letter-spacing: 0.2px;
}}

/* Search */
.search-wrap {{
  position: relative;
}}
.search-wrap svg {{
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  width: 14px; height: 14px; color: var(--text-muted);
  pointer-events: none;
}}
.search-input {{
  width: 100%; padding: 8px 10px 8px 32px;
  font-family: inherit; font-size: 12px;
  color: var(--text-primary);
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 7px; outline: none;
  transition: border-color 0.2s, background 0.2s;
}}
.search-input:focus {{
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-bg);
}}
.search-input::placeholder {{ color: var(--text-muted); }}

/* Nav */
.sidebar-nav {{
  flex: 1; overflow-y: auto; padding: 8px 10px;
}}
.nav-item {{
  display: flex; align-items: center; gap: 10px;
  width: 100%; padding: 9px 12px;
  font-family: inherit; font-size: 12.5px; font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none; border-left: 3px solid transparent;
  border-radius: 6px; cursor: pointer;
  text-align: left; transition: all 0.15s;
}}
.nav-item:hover {{
  background: var(--sidebar-hover);
  color: var(--text-primary);
}}
.nav-item.active {{
  background: var(--sidebar-active);
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 600;
}}
.nav-icon {{
  width: 18px; height: 18px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}}
.nav-icon svg {{ width: 16px; height: 16px; }}

/* Search results in sidebar */
.search-results {{
  display: none; flex: 1; overflow-y: auto; padding: 8px 10px;
}}
.search-results.visible {{
  display: block;
}}
.search-results.visible ~ .sidebar-nav {{
  display: none;
}}
.search-result-item {{
  padding: 10px 12px; border-radius: 6px;
  cursor: pointer; margin-bottom: 2px;
  transition: background 0.15s;
}}
.search-result-item:hover {{
  background: var(--sidebar-hover);
}}
.search-result-title {{
  font-size: 12px; font-weight: 600;
  color: var(--text-primary); margin-bottom: 3px;
}}
.search-result-context {{
  font-size: 11px; color: var(--text-muted);
  line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}}
.search-result-context mark {{
  background: var(--search-highlight);
  color: var(--accent); border-radius: 2px;
  padding: 0 1px;
}}
.search-no-results {{
  padding: 16px 12px; text-align: center;
  font-size: 12px; color: var(--text-muted);
}}

/* Sidebar footer */
.sidebar-footer {{
  padding: 12px 18px;
  border-top: 1px solid var(--sidebar-border);
  display: flex; align-items: center;
  justify-content: space-between;
}}
.theme-toggle {{
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; font-weight: 500;
  color: var(--text-muted); cursor: pointer;
  background: none; border: none; padding: 6px 10px;
  border-radius: 6px; font-family: inherit;
  transition: background 0.15s, color 0.15s;
}}
.theme-toggle:hover {{
  background: var(--sidebar-hover);
  color: var(--text-primary);
}}
.theme-toggle svg {{ width: 16px; height: 16px; }}

.close-btn {{
  font-size: 11px; font-weight: 500;
  color: var(--text-muted); cursor: pointer;
  background: none; border: 1px solid var(--sidebar-border);
  padding: 5px 14px; border-radius: 6px;
  font-family: inherit; transition: all 0.15s;
}}
.close-btn:hover {{
  background: var(--sidebar-hover);
  color: var(--text-primary); border-color: var(--text-muted);
}}

/* ===== Main Content ===== */
.main-content {{
  flex: 1; overflow-y: auto; padding: 28px 36px;
  z-index: 10;
}}
.content-card {{
  max-width: 780px; margin: 0 auto;
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 36px 40px;
  box-shadow: var(--card-shadow);
  transition: background 0.3s, border-color 0.3s, box-shadow 0.3s;
}}

/* ===== Content Typography ===== */
.content-card h1 {{
  font-size: 24px; font-weight: 700;
  color: var(--text-primary);
  border-bottom: 2px solid var(--accent);
  padding-bottom: 10px; margin: 0 0 20px;
}}
.content-card h2 {{
  font-size: 17px; font-weight: 700;
  color: var(--accent);
  margin: 28px 0 12px;
  padding-left: 12px;
  border-left: 3px solid var(--accent);
}}
.content-card h3 {{
  font-size: 14px; font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 8px;
}}
.content-card p {{
  font-size: 13px; line-height: 1.7;
  color: var(--text-secondary);
  margin: 0 0 12px;
}}
.content-card ul, .content-card ol {{
  font-size: 13px; line-height: 1.8;
  color: var(--text-secondary);
  padding-left: 22px; margin: 0 0 12px;
}}
.content-card li {{ margin-bottom: 4px; }}
.content-card strong {{ color: var(--text-primary); font-weight: 600; }}
.content-card a {{
  color: var(--link-color); text-decoration: none;
  font-weight: 500;
}}
.content-card a:hover {{ text-decoration: underline; }}
.content-card hr {{
  border: none; height: 1px;
  background: var(--hr-color);
  margin: 20px 0;
}}
.content-card code {{
  font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 0.88em;
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  padding: 1px 5px; border-radius: 4px;
}}
.content-card pre {{
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  border-radius: 8px; padding: 14px 16px;
  overflow-x: auto; margin: 14px 0;
}}
.content-card pre code {{
  background: transparent; border: none;
  padding: 0; font-size: 12px;
}}
.content-card table {{
  width: 100%; border-collapse: collapse;
  margin: 16px 0; font-size: 12.5px;
}}
.content-card th {{
  background: var(--table-header-bg);
  color: var(--table-header-color);
  padding: 9px 12px; text-align: left;
  font-weight: 600;
}}
.content-card td {{
  padding: 8px 12px;
  border: 1px solid var(--table-border);
}}
.content-card tr:nth-child(even) {{ background: var(--table-row-alt); }}

/* Callouts */
.content-card .note,
.content-card .tip,
.content-card .warning {{
  padding: 12px 16px; margin: 16px 0;
  border-radius: 8px; font-size: 12.5px;
  line-height: 1.6;
}}
.content-card .note {{
  background: var(--note-bg);
  border-left: 4px solid var(--note-border);
  color: var(--note-text);
}}
.content-card .tip {{
  background: var(--tip-bg);
  border-left: 4px solid var(--tip-border);
  color: var(--tip-text);
}}
.content-card .warning {{
  background: var(--warning-bg);
  border-left: 4px solid var(--warning-border);
  color: var(--warning-text);
}}
.content-card .formula {{
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  padding: 14px; margin: 14px 0;
  font-family: 'Consolas', monospace;
  text-align: center; font-size: 13px;
  border-radius: 8px;
}}

/* ===== Loading placeholder ===== */
.loading-placeholder {{
  text-align: center; padding: 60px 0;
  color: var(--text-muted); font-size: 13px;
}}
.loading-dot {{ display: inline-block; animation: pulse 1.2s ease-in-out infinite; }}
.loading-dot:nth-child(2) {{ animation-delay: 0.15s; }}
.loading-dot:nth-child(3) {{ animation-delay: 0.3s; }}
@keyframes pulse {{ 0%,80%,100% {{ opacity: 0.3; }} 40% {{ opacity: 1; }} }}
</style>
</head>
<body>
<canvas id="contour-canvas"></canvas>

<div class="app-shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>Help &amp; Documentation</h2>
      <div class="search-wrap">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="8.5" cy="8.5" r="5.5"/><path d="M13 13 L17 17"/>
        </svg>
        <input type="text" class="search-input" placeholder="Search help..."
               oninput="onSearchInput(this.value)" />
      </div>
    </div>

    <div class="search-results" id="search-results"></div>

    <div class="sidebar-nav" id="sidebar-nav">
      {nav_html}
    </div>

    <div class="sidebar-footer">
      <button class="theme-toggle" onclick="toggleTheme()">
        <svg id="theme-icon-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor"
             stroke-width="1.6" stroke-linecap="round">
          <circle cx="10" cy="10" r="4"/>
          <path d="M10 2 L10 4 M10 16 L10 18 M2 10 L4 10 M16 10 L18 10
                   M4.93 4.93 L6.34 6.34 M13.66 13.66 L15.07 15.07
                   M4.93 15.07 L6.34 13.66 M13.66 6.34 L15.07 4.93"/>
        </svg>
        <svg id="theme-icon-moon" viewBox="0 0 20 20" fill="none" stroke="currentColor"
             stroke-width="1.6" stroke-linecap="round" style="display:none">
          <path d="M17 11.5 A7.5 7.5 0 1 1 8.5 3 A5.5 5.5 0 0 0 17 11.5Z"/>
        </svg>
        <span id="theme-label">Dark mode</span>
      </button>
      <button class="close-btn" onclick="if(window.bridge) bridge.requestClose();">Close</button>
    </div>
  </aside>

  <!-- Main -->
  <main class="main-content">
    <div class="content-card" id="content-area">
      <div class="loading-placeholder">
        <span class="loading-dot">&#9679;</span>
        <span class="loading-dot">&#9679;</span>
        <span class="loading-dot">&#9679;</span>
      </div>
    </div>
  </main>
</div>

<!-- ===== Perlin Noise ===== -->
<script>
class PerlinNoise {{
  constructor() {{
    this.p = [];
    const perm = [];
    for (let i = 0; i < 256; i++) perm[i] = Math.floor(Math.random() * 256);
    for (let i = 0; i < 512; i++) this.p[i] = perm[i & 255];
  }}
  fade(t) {{ return t * t * t * (t * (t * 6 - 15) + 10); }}
  lerp(t, a, b) {{ return a + t * (b - a); }}
  grad(hash, x, y, z) {{
    const h = hash & 15;
    const u = h < 8 ? x : y;
    const v = h < 4 ? y : (h === 12 || h === 14 ? x : z);
    return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
  }}
  noise(x, y, z) {{
    const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
    x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
    const u = this.fade(x), v = this.fade(y), w = this.fade(z);
    const A = this.p[X] + Y, AA = this.p[A] + Z, AB = this.p[A + 1] + Z;
    const B = this.p[X + 1] + Y, BA = this.p[B] + Z, BB = this.p[B + 1] + Z;
    return this.lerp(w,
      this.lerp(v,
        this.lerp(u, this.grad(this.p[AA], x, y, z), this.grad(this.p[BA], x - 1, y, z)),
        this.lerp(u, this.grad(this.p[AB], x, y - 1, z), this.grad(this.p[BB], x - 1, y - 1, z))),
      this.lerp(v,
        this.lerp(u, this.grad(this.p[AA + 1], x, y, z - 1), this.grad(this.p[BA + 1], x - 1, y, z - 1)),
        this.lerp(u, this.grad(this.p[AB + 1], x, y - 1, z - 1), this.grad(this.p[BB + 1], x - 1, y - 1, z - 1))
      )
    );
  }}
}}
const _pn = new PerlinNoise();
function pnoise(x, y, z) {{ return (_pn.noise(x, y, z || 0) + 1) / 2; }}
</script>

<!-- ===== Static Contour Renderer ===== -->
<script>
(function() {{
  const canvas = document.getElementById('contour-canvas');
  const ctx = canvas.getContext('2d');
  const res = 5;
  const thresholdInc = 3;
  const thickMul = 4;
  const zOffset = 0;   /* fixed — no animation */

  let cols, rows, inputValues, noiseMin, noiseMax, currentThreshold;

  function resize() {{
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    cols = Math.floor(canvas.width / res) + 1;
    rows = Math.floor(canvas.height / res) + 1;
  }}

  function generate() {{
    inputValues = []; noiseMin = 100; noiseMax = 0;
    for (let y = 0; y < rows; y++) {{
      inputValues[y] = [];
      for (let x = 0; x <= cols; x++) {{
        const n1 = pnoise(x * 0.018, y * 0.018, zOffset) * 100;
        const n2 = pnoise(x * 0.04, y * 0.04, zOffset + 100) * 30;
        const v = n1 + n2;
        inputValues[y][x] = v;
        if (v < noiseMin) noiseMin = v;
        if (v > noiseMax) noiseMax = v;
      }}
    }}
  }}

  function linInterp(x0, x1) {{ return x0 === x1 ? 0 : (currentThreshold - x0) / (x1 - x0); }}

  function drawLine(from, to) {{ ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); }}

  function march(x, y) {{
    const nw = inputValues[y][x], ne = inputValues[y][x+1];
    const se = inputValues[y+1][x+1], sw = inputValues[y+1][x];
    const r = res, px = x * r, py = y * r;
    const a = [px + r * linInterp(nw, ne), py];
    const b = [px + r, py + r * linInterp(ne, se)];
    const c = [px + r * linInterp(sw, se), py + r];
    const d = [px, py + r * linInterp(nw, sw)];
    const gv = ((nw > currentThreshold ? 1 : 0) << 3) |
               ((ne > currentThreshold ? 1 : 0) << 2) |
               ((se > currentThreshold ? 1 : 0) << 1) |
                (sw > currentThreshold ? 1 : 0);
    switch (gv) {{
      case 1: case 14: drawLine(d, c); break;
      case 2: case 13: drawLine(b, c); break;
      case 3: case 12: drawLine(d, b); break;
      case 4: case 11: drawLine(a, b); break;
      case 5: drawLine(d, a); drawLine(c, b); break;
      case 6: case 9: drawLine(c, a); break;
      case 7: case 8: drawLine(d, a); break;
      case 10: drawLine(a, b); drawLine(c, d); break;
    }}
  }}

  function render() {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    generate();
    const contourColor = getComputedStyle(document.documentElement)
                         .getPropertyValue('--contour-color').trim();
    const majorColor   = getComputedStyle(document.documentElement)
                         .getPropertyValue('--contour-major').trim();
    const roundMin = Math.floor(noiseMin / thresholdInc) * thresholdInc;
    const roundMax = Math.ceil(noiseMax / thresholdInc) * thresholdInc;
    for (let t = roundMin; t < roundMax; t += thresholdInc) {{
      currentThreshold = t;
      const isMajor = t % (thresholdInc * thickMul) === 0;
      ctx.beginPath();
      for (let y = 0; y < inputValues.length - 1; y++) {{
        for (let x = 0; x < inputValues[y].length - 1; x++) {{
          const nw = inputValues[y][x] > t ? 1 : 0;
          const ne = inputValues[y][x+1] > t ? 1 : 0;
          const se = inputValues[y+1][x+1] > t ? 1 : 0;
          const sw = inputValues[y+1][x] > t ? 1 : 0;
          if ((nw + ne + se + sw) === 0 || (nw + ne + se + sw) === 4) continue;
          march(x, y);
        }}
      }}
      ctx.strokeStyle = isMajor ? majorColor : contourColor;
      ctx.lineWidth = isMajor ? 1.4 : 0.6;
      ctx.stroke();
    }}
  }}

  resize();
  window.addEventListener('resize', function() {{ resize(); render(); }});
  window.renderContours = render;
  setTimeout(render, 80);
}})();
</script>

<!-- ===== App Logic ===== -->
<script>
  let _searchTimer = null;
  let _currentNavId = null;

  /* ---------- Navigation ---------- */
  function navigateTo(navId, filename) {{
    _currentNavId = navId;
    /* Update active state */
    document.querySelectorAll('.nav-item').forEach(function(el) {{
      el.classList.toggle('active', el.dataset.id === navId);
    }});
    /* Clear search */
    var input = document.querySelector('.search-input');
    if (input) input.value = '';
    document.getElementById('search-results').classList.remove('visible');
    /* Request content from Python */
    if (window.bridge) {{
      bridge.loadPage(filename);
    }}
  }}

  /* ---------- Receive content from Python ---------- */
  function receivePageContent(html, pageId) {{
    document.getElementById('content-area').innerHTML = html;
    /* Scroll to top */
    document.querySelector('.main-content').scrollTop = 0;
  }}

  /* ---------- Search ---------- */
  function onSearchInput(value) {{
    clearTimeout(_searchTimer);
    var q = value.trim();
    if (q.length < 2) {{
      document.getElementById('search-results').classList.remove('visible');
      return;
    }}
    _searchTimer = setTimeout(function() {{
      if (window.bridge) bridge.searchContent(q);
    }}, 250);
  }}

  function receiveSearchResults(results) {{
    var container = document.getElementById('search-results');
    container.innerHTML = '';
    if (!results || results.length === 0) {{
      container.innerHTML = '<div class="search-no-results">No results found.</div>';
      container.classList.add('visible');
      return;
    }}
    var q = document.querySelector('.search-input').value.trim();
    results.forEach(function(r) {{
      var item = document.createElement('div');
      item.className = 'search-result-item';
      item.onclick = function() {{ navigateTo(r.navId, r.filename); }};
      /* Highlight query in context */
      var ctx = r.context;
      if (q) {{
        var re = new RegExp('(' + q.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
        ctx = ctx.replace(re, '<mark>$1</mark>');
      }}
      item.innerHTML =
        '<div class="search-result-title">' + r.title + '</div>' +
        '<div class="search-result-context">...' + ctx + '...</div>';
      container.appendChild(item);
    }});
    container.classList.add('visible');
  }}

  /* ---------- Theming ---------- */
  function setTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    var isSun = (theme === 'light');
    document.getElementById('theme-icon-sun').style.display  = isSun ? 'block' : 'none';
    document.getElementById('theme-icon-moon').style.display = isSun ? 'none'  : 'block';
    document.getElementById('theme-label').textContent = isSun ? 'Dark mode' : 'Light mode';
    /* Re-render contours with updated CSS vars */
    if (window.renderContours) setTimeout(window.renderContours, 30);
  }}

  function toggleTheme() {{
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    var next = current === 'light' ? 'dark' : 'light';
    setTheme(next);
    if (window.bridge) bridge.saveTheme(next);
  }}
</script>

<!-- ===== QWebChannel ===== -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.bridge = channel.objects.bridge;
  }});
</script>
</body>
</html>'''
