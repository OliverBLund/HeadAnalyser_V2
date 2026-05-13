"""
HeadAnalyser V2 - Welcome Widget
Animated welcome screen with glowing contours, particles, and glass UI cards.
Uses QWebEngineView to render the animated HTML background.
"""

import html
import json
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl

from styles.colors import Colors


class WelcomeBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel."""
    open_file = pyqtSignal()
    load_recent = pyqtSignal()
    open_recent_file = pyqtSignal(str)
    help_requested = pyqtSignal()
    contact_requested = pyqtSignal()

    @pyqtSlot()
    def requestHelp(self):
        self.help_requested.emit()

    @pyqtSlot()
    def requestContact(self):
        self.contact_requested.emit()

    @pyqtSlot()
    def openFile(self):
        self.open_file.emit()

    @pyqtSlot()
    def loadRecent(self):
        self.load_recent.emit()

    @pyqtSlot(str)
    def openRecentFile(self, file_path):
        self.open_recent_file.emit(file_path or "")


class WelcomeWidget(QWidget):
    """Animated welcome screen shown when no datasets are loaded."""

    open_file_requested = pyqtSignal()
    load_recent_requested = pyqtSignal()
    open_recent_file_requested = pyqtSignal(str)
    help_requested = pyqtSignal()
    contact_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent_sessions = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()

        # Setup bridge for button clicks
        self._bridge = WelcomeBridge()
        self._bridge.open_file.connect(self.open_file_requested)
        self._bridge.load_recent.connect(self.load_recent_requested)
        self._bridge.open_recent_file.connect(self.open_recent_file_requested)
        self._bridge.help_requested.connect(self.help_requested)
        self._bridge.contact_requested.connect(self.contact_requested)

        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.web_view.page().setWebChannel(self._channel)

        layout.addWidget(self.web_view)

        # Load the welcome page
        self._load_welcome_html()

    def shutdown(self):
        """Stop/unload WebEngine content before widget destruction."""
        try:
            self.web_view.stop()
        except Exception:
            pass
        try:
            self.web_view.page().setWebChannel(None)
        except Exception:
            pass
        try:
            self.web_view.setHtml("<!doctype html><html><body></body></html>", QUrl("about:blank"))
        except Exception:
            pass

    def _load_welcome_html(self):
        """Build and load the welcome HTML with inlined JS."""
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        
        # Read particles.min.js
        particles_js = ""
        particles_path = os.path.join(assets_dir, "particles.min.js")
        if os.path.exists(particles_path):
            with open(particles_path, "r", encoding="utf-8") as f:
                particles_js = f.read()

        # Build DTU logo data URL (small PNG is safe to inline)
        import base64
        dtu_logo_data_url = ""
        dtu_logo_path = os.path.join(assets_dir, "DTU_logo.png")
        if os.path.exists(dtu_logo_path):
            with open(dtu_logo_path, "rb") as f:
                dtu_logo_b64 = base64.b64encode(f.read()).decode("utf-8")
                dtu_logo_data_url = f"data:image/png;base64,{dtu_logo_b64}"

        # App logo: keep as file URL via baseUrl to avoid huge inline SVG payload.
        app_logo_html = ""
        preferred_app_logo_png_path = os.path.join(assets_dir, "logo_newest.png")
        preferred_app_logo_path = os.path.join(assets_dir, "headanalyser_logo.svg")
        clean_app_logo_path = os.path.join(assets_dir, "logo_newest_clean.svg")
        raw_app_logo_path = os.path.join(assets_dir, "logo_newest.svg")
        if os.path.exists(preferred_app_logo_png_path):
            app_logo_html = '<img src="logo_newest.png" class="app-logo" alt="HeadAnalyser logo" loading="eager" decoding="async" />'
        elif os.path.exists(preferred_app_logo_path):
            app_logo_html = '<img src="headanalyser_logo.svg" class="app-logo" alt="HeadAnalyser logo" loading="eager" decoding="async" />'
        elif os.path.exists(clean_app_logo_path):
            app_logo_html = '<img src="logo_newest_clean.svg" class="app-logo" alt="HeadAnalyser logo" loading="eager" decoding="async" />'
        elif os.path.exists(raw_app_logo_path):
            app_logo_html = '<img src="logo_newest.svg" class="app-logo" alt="HeadAnalyser logo" loading="eager" decoding="async" />'

        dtu_logo_html = f'<img src="{dtu_logo_data_url}" class="dtu-logo" alt="DTU logo" />' if dtu_logo_data_url else ""
        recent_sessions_html = self._build_recent_sessions_html(self._recent_sessions)
        html_doc = self._build_html(particles_js, app_logo_html, dtu_logo_html, recent_sessions_html)
        self.web_view.setHtml(html_doc, QUrl.fromLocalFile(assets_dir + os.sep))

    def update_recent_sessions(self, recent_sessions):
        """Replace and rerender recent sessions on welcome screen."""
        self._recent_sessions = recent_sessions if isinstance(recent_sessions, list) else []
        self._load_welcome_html()

    def apply_theme(self):
        self._load_welcome_html()

    def _build_recent_sessions_html(self, sessions):
        """Render recent sessions list HTML from persisted settings data."""
        items = []
        for session in sessions[:6]:
            if not isinstance(session, dict):
                continue
            files = session.get("files") if isinstance(session.get("files"), list) else []
            if not files:
                continue
            file_path = str(files[0] or "")
            if not file_path:
                continue
            name = str(session.get("name") or os.path.basename(file_path))
            opened_at = str(session.get("opened_at") or "")
            escaped_name = html.escape(name)
            escaped_time = html.escape(opened_at)
            js_path = html.escape(json.dumps(file_path))
            meta = f"<span>{escaped_time}</span>" if escaped_time else "<span>recent file</span>"
            items.append(
                f"""
                <li class="recent-item" onclick="if(window.bridge) bridge.openRecentFile({js_path});">
                  <div class="recent-dot"></div>
                  <div class="recent-info">
                    <div class="recent-name">{escaped_name}</div>
                    <div class="recent-meta">{meta}</div>
                  </div>
                </li>
                """
            )
        if not items:
            return '<div class="empty-recent">No recent sessions yet</div>'
        return '<ul class="recent-list">' + "".join(items) + "</ul>"

    def _build_html(self, particles_js: str, app_logo_html: str, dtu_logo_html: str, recent_sessions_html: str) -> str:
        """Build the complete welcome HTML string."""
        is_dark = Colors.is_dark()
        grid_line = Colors.rgba(Colors.ACCENT_PRIMARY, 0.03 if is_dark else 0.045)
        vignette_mid = Colors.rgba(Colors.BG_APP, 0.30 if is_dark else 0.18)
        vignette_outer = Colors.rgba(Colors.BG_APP, 0.75 if is_dark else 0.80)
        glass_bg = Colors.rgba(Colors.BG_DARK if is_dark else Colors.BG_ELEVATED, 0.78 if is_dark else 0.84)
        glass_border = Colors.BORDER_DEFAULT
        glass_shadow = (
            f"0 4px 20px {Colors.rgba('#000000', 0.40)}, inset 0 1px 0 {Colors.rgba('#ffffff', 0.03)}"
            if is_dark
            else f"0 10px 30px {Colors.SHADOW_MEDIUM}, inset 0 1px 0 {Colors.rgba('#ffffff', 0.55)}"
        )
        secondary_bg = Colors.BG_WELL
        secondary_border = Colors.BORDER_DEFAULT
        kbd_bg = Colors.BG_WELL
        kbd_border = Colors.BORDER_MEDIUM
        particle_colors = json.dumps([
            Colors.ACCENT_PRIMARY,
            Colors.ACCENT_BRIGHT,
            Colors.INFO,
            Colors.ACCENT_PRESSED,
        ])
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {Colors.BG_APP};
    overflow: hidden;
    width: 100vw; height: 100vh;
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  }}
  .grid-bg {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 0;
    background-image:
      linear-gradient({grid_line} 1px, transparent 1px),
      linear-gradient(90deg, {grid_line} 1px, transparent 1px);
    background-size: 40px 40px;
  }}
  #particles-js {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 1;
  }}
  #glow-canvas {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 2;
    pointer-events: none;
    filter: blur(8px); opacity: 0.6;
  }}
  #gis-canvas {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 3;
    pointer-events: none;
  }}
  .vignette {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 4;
    pointer-events: none;
    background: radial-gradient(ellipse at 50% 50%,
      transparent 20%, {vignette_mid} 55%, {vignette_outer} 100%);
  }}
  .welcome-overlay {{
    position: fixed; top: 0; left: 0;
    width: 100%; height: 100%; z-index: 10;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    pointer-events: none; padding: 40px;
  }}
  .title-section {{ text-align: center; margin-bottom: 28px; }}
  .app-logo {{
    display: block;
    width: auto;
    height: clamp(225px, 32.5vh, 400px);
    max-width: min(980px, 95vw);
    margin: 0 auto -42px auto;
    object-fit: contain;
    object-position: center 76%;
    opacity: 0;
    transform: translateY(6px);
    transition: opacity 360ms ease, transform 360ms ease;
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.25));
    will-change: opacity, transform;
  }}
  .app-logo.is-visible {{
    opacity: 0.98;
    transform: translateY(0);
  }}
  .title-section h1 {{
    font-size: 42px; font-weight: 800; color: {Colors.TEXT_PRIMARY};
    letter-spacing: -1px; margin: 0 0 2px 0; line-height: 1.1;
  }}
  .title-section h1 span {{ color: {Colors.ACCENT_PRIMARY}; }}
  .title-section .tagline {{
    font-size: 13px; font-weight: 400; color: {Colors.TEXT_TERTIARY};
    letter-spacing: 0.3px; margin-top: 6px;
  }}
  .version-badge {{
    display: inline-block; margin-top: 10px;
    font-size: 10px; font-weight: 700; color: {Colors.ACCENT_PRIMARY};
    background: {Colors.ACCENT_GHOST};
    border: 1px solid {Colors.BORDER_ACCENT};
    border-radius: 9px; padding: 3px 12px;
    letter-spacing: 0.8px; text-transform: uppercase;
  }}
  .card-grid {{
    display: grid;
    grid-template-columns: 280px 340px;
    grid-template-rows: auto auto;
    gap: 10px; max-width: 640px;
  }}
  .glass-card {{
    background: {glass_bg};
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid {glass_border};
    border-radius: 10px; padding: 16px 18px;
    box-shadow: {glass_shadow};
  }}
  .card-header {{
    display: flex; align-items: center;
    gap: 8px; margin-bottom: 12px;
  }}
  .card-icon {{
    width: 28px; height: 28px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }}
  .card-icon svg {{ width: 14px; height: 14px; }}
  .card-icon.accent {{ background: {Colors.ACCENT_GHOST}; }}
  .card-icon.accent svg {{ stroke: {Colors.ACCENT_PRIMARY}; fill: none; }}
  .card-icon.blue {{ background: {Colors.INFO_BG}; }}
  .card-icon.blue svg {{ stroke: {Colors.INFO}; fill: none; }}
  .card-icon.green {{ background: {Colors.SUCCESS_BG}; }}
  .card-icon.green svg {{ stroke: {Colors.SUCCESS}; fill: none; }}
  .card-icon.amber {{ background: {Colors.WARNING_BG}; }}
  .card-icon.amber svg {{ stroke: {Colors.WARNING}; fill: none; }}
  .card-title {{
    font-size: 11px; font-weight: 700; color: {Colors.TEXT_PRIMARY};
    letter-spacing: 0.4px; text-transform: uppercase;
  }}
  .actions-card {{ grid-column: 1; grid-row: 1; }}
  .btn-primary {{
    display: block; width: 100%; padding: 10px 16px;
    font-family: inherit; font-size: 12px; font-weight: 600;
    color: {Colors.TEXT_INVERSE};
    background: linear-gradient(135deg, {Colors.ACCENT_PRESSED}, {Colors.ACCENT_PRIMARY});
    border: none; border-radius: 7px; cursor: pointer;
    pointer-events: auto; text-align: left;
    transition: transform 0.12s, box-shadow 0.12s;
    box-shadow: 0 2px 8px {Colors.ACCENT_SHADOW};
  }}
  .btn-primary:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 16px {Colors.ACCENT_SHADOW};
  }}
  .btn-secondary {{
    display: block; width: 100%; padding: 9px 16px;
    font-family: inherit; font-size: 12px; font-weight: 500;
    color: {Colors.TEXT_SECONDARY};
    background: {secondary_bg};
    border: 1px solid {secondary_border};
    border-radius: 7px; cursor: pointer;
    pointer-events: auto; text-align: left;
    margin-top: 6px;
    transition: background 0.12s, color 0.12s;
  }}
  .btn-secondary:hover {{
    background: {Colors.ACCENT_GHOST}; color: {Colors.ACCENT_BRIGHT};
  }}
  .btn-icon {{
    display: inline-block; width: 14px;
    margin-right: 8px; vertical-align: -1px; opacity: 0.7;
  }}
  .recent-card {{ grid-column: 2; grid-row: 1 / 3; }}
  .recent-list {{ list-style: none; }}
  .recent-item {{
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 10px; border-radius: 6px;
    cursor: pointer; pointer-events: auto;
    transition: background 0.12s; margin-bottom: 2px;
  }}
  .recent-item:hover {{ background: {Colors.ACCENT_GHOST}; }}
  .recent-dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: {Colors.ACCENT_PRIMARY}; margin-top: 5px;
    flex-shrink: 0; opacity: 0.5;
  }}
  .recent-item:hover .recent-dot {{ opacity: 1; }}
  .recent-info {{ flex: 1; min-width: 0; }}
  .recent-name {{
    font-size: 12px; font-weight: 600; color: {Colors.TEXT_PRIMARY};
    white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; line-height: 1.3;
  }}
  .recent-meta {{ font-size: 10px; color: {Colors.TEXT_MUTED}; margin-top: 1px; }}
  .recent-meta span {{ color: {Colors.TEXT_TERTIARY}; }}
  .empty-recent {{
    text-align: center; padding: 24px 0;
    color: {Colors.TEXT_MUTED}; font-size: 11px;
  }}
  .tips-card {{ grid-column: 1; grid-row: 2; }}
  .shortcut-list {{ list-style: none; }}
  .shortcut-item {{
    display: flex; align-items: center;
    justify-content: space-between; padding: 4px 0;
  }}
  .shortcut-label {{ font-size: 11px; color: {Colors.TEXT_SECONDARY}; }}
  .shortcut-keys {{ display: flex; gap: 3px; }}
  .kbd {{
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 9px; font-weight: 600; color: {Colors.TEXT_SECONDARY};
    background: {kbd_bg};
    border: 1px solid {kbd_border};
    border-radius: 3px; padding: 2px 5px; line-height: 1.3;
  }}
  .changelog-card {{ grid-column: 1 / 3; grid-row: 3; }}
  .changelog-list {{
    list-style: none; display: grid;
    grid-template-columns: 1fr 1fr; gap: 4px 20px;
  }}
  .changelog-item {{
    display: flex; align-items: flex-start;
    gap: 8px; padding: 3px 0;
  }}
  .changelog-tag {{
    flex-shrink: 0; font-size: 8px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
    padding: 2px 5px; border-radius: 3px;
    margin-top: 1px; line-height: 1.3;
  }}
  .tag-new {{ background: {Colors.SUCCESS_BG}; color: {Colors.SUCCESS}; }}
  .tag-improved {{ background: {Colors.INFO_BG}; color: {Colors.INFO}; }}
  .tag-fixed {{ background: {Colors.WARNING_BG}; color: {Colors.WARNING}; }}
  .changelog-text {{ font-size: 11px; color: {Colors.TEXT_SECONDARY}; line-height: 1.4; }}
  .dtu-logo {{
    position: fixed;
    bottom: 25px;
    left: 30px;
    max-width: 65px;
    max-height: 65px;
    object-fit: contain;
    opacity: 0.9;
    z-index: 100;
    pointer-events: none;
  }}
  .author-credit {{
    position: fixed;
    bottom: 25px;
    right: 30px;
    text-align: right;
    z-index: 100;
    pointer-events: none;
  }}
  .author-name {{
    font-size: 13px; font-weight: 600; color: {Colors.TEXT_PRIMARY};
    letter-spacing: 0.5px;
    text-shadow: none;
  }}
  .author-sub {{
    font-size: 10px; color: {Colors.ACCENT_PRIMARY}; margin-top: 1px;
    font-weight: 500;
  }}
</style>
</head>
<body>
<div class="grid-bg"></div>
<div id="particles-js"></div>
<canvas id="glow-canvas"></canvas>
<canvas id="gis-canvas"></canvas>
<div class="vignette"></div>

<div class="welcome-overlay">
  <div class="title-section">
    {app_logo_html}
    <h1>Head<span>Analyser</span></h1>
    <div class="tagline">Hydraulic Head Analysis &amp; Gradient Computation</div>
    <div class="version-badge">v2.0 beta</div>
  </div>
  <div class="card-grid">
    <div class="glass-card actions-card">
      <div class="card-header">
        <div class="card-icon accent">
          <svg viewBox="0 0 16 16" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 14 L8 2 L14 14 Z" fill="none"/>
          </svg>
        </div>
        <span class="card-title">Get Started</span>
      </div>
      <button class="btn-primary" onclick="if(window.bridge) bridge.openFile();">
        <svg class="btn-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
          <rect x="2" y="3" width="12" height="10" rx="1"/>
          <path d="M2 5.5 L6.5 5.5 L7.5 3 L8.5 5.5"/>
        </svg>
        Open File
      </button>
      <button class="btn-secondary" onclick="if(window.bridge) bridge.loadRecent();">
        <svg class="btn-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
          <circle cx="8" cy="8" r="5.5"/>
          <path d="M8 5 L8 8 L10.5 9.5"/>
        </svg>
        Load Recent
      </button>
      <div style="display: flex; gap: 10px; margin-top: 6px;">
        <button class="btn-secondary" onclick="if(window.bridge) bridge.requestContact();" style="margin-top: 0;">
          Contact
        </button>
        <button class="btn-secondary" onclick="if(window.bridge) bridge.requestHelp();" style="margin-top: 0;">
          Help
        </button>
      </div>
    </div>

    <div class="glass-card recent-card">
      <div class="card-header">
        <div class="card-icon blue">
          <svg viewBox="0 0 16 16" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 4 L3 13 L13 13 L13 4"/>
            <path d="M1 2 L15 2 L15 4 L1 4 Z"/>
          </svg>
        </div>
        <span class="card-title">Recent Sessions</span>
      </div>
      {recent_sessions_html}
    </div>

    <div class="glass-card tips-card">
      <div class="card-header">
        <div class="card-icon amber">
          <svg viewBox="0 0 16 16" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="1" y="5" width="14" height="9" rx="1.5"/>
            <path d="M4 8 L4 8.01"/><path d="M8 8 L8 8.01"/><path d="M12 8 L12 8.01"/>
            <path d="M5 11 L11 11"/>
          </svg>
        </div>
        <span class="card-title">Shortcuts</span>
      </div>
      <ul class="shortcut-list">
        <li class="shortcut-item"><span class="shortcut-label">Open file</span><div class="shortcut-keys"><span class="kbd">Ctrl</span><span class="kbd">O</span></div></li>
        <li class="shortcut-item"><span class="shortcut-label">Save session</span><div class="shortcut-keys"><span class="kbd">Ctrl</span><span class="kbd">S</span></div></li>
        <li class="shortcut-item"><span class="shortcut-label">Data table</span><div class="shortcut-keys"><span class="kbd">Ctrl</span><span class="kbd">T</span></div></li>
        <li class="shortcut-item"><span class="shortcut-label">Export plot</span><div class="shortcut-keys"><span class="kbd">Ctrl</span><span class="kbd">E</span></div></li>
      </ul>
    </div>

    <div class="glass-card changelog-card">
      <div class="card-header">
        <div class="card-icon green">
          <svg viewBox="0 0 16 16" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 2 L4 14"/>
            <path d="M4 4 Q8 4 8 7 Q8 10 12 10"/>
            <circle cx="4" cy="2" r="1.2" fill="{Colors.SUCCESS}" stroke="none"/>
            <circle cx="4" cy="14" r="1.2" fill="{Colors.SUCCESS}" stroke="none"/>
            <circle cx="12" cy="10" r="1.2" fill="{Colors.SUCCESS}" stroke="none"/>
          </svg>
        </div>
        <span class="card-title">Changelog</span>
      </div>
      <ul class="changelog-list">
        <li class="changelog-item"><span class="changelog-tag tag-new">new</span><span class="changelog-text">Triangle inspection dialog with geometry plots</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-new">new</span><span class="changelog-text">Selection inspector for point-level analysis</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-improved">upd</span><span class="changelog-text">Filled contours and contour line overlay on 2D plots</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-new">new</span><span class="changelog-text">Calculation settings dialog with filter controls</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-improved">upd</span><span class="changelog-text">Statistics panel with rejection breakdown bars</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-fixed">fix</span><span class="changelog-text">Gradient stacking epsilon for thin triangles</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-improved">upd</span><span class="changelog-text">Per-plot-type HintBar with contextual tips</span></li>
        <li class="changelog-item"><span class="changelog-tag tag-new">new</span><span class="changelog-text">Point selection dialog for interactive exclusion</span></li>
      </ul>
    </div>
  </div>
  </div>
  
  {dtu_logo_html}
  
  <div class="author-credit">
    <div class="author-name">Created by Oliver Brincks Lund</div>
    <div class="author-sub">DTU Sustain</div>
  </div>
</div>

<!-- Particles.js (inlined) -->
<script>{particles_js}</script>
<script>
  particlesJS('particles-js', {{
    particles: {{
      number: {{ value: 30, density: {{ enable: true, value_area: 1200 }} }},
      color: {{ value: {particle_colors} }},
      shape: {{ type: "circle" }},
      opacity: {{
        value: 0.6, random: true,
        anim: {{ enable: true, speed: 0.5, opacity_min: 0.1, sync: false }}
      }},
      size: {{
        value: 1.8, random: true,
        anim: {{ enable: false }}
      }},
      line_linked: {{ enable: false }},
      move: {{
        enable: true, speed: 0.3, direction: "none",
        random: true, straight: false, out_mode: "out", bounce: false
      }}
    }},
    interactivity: {{
      detect_on: "canvas",
      events: {{ onhover: {{ enable: false }}, onclick: {{ enable: false }}, resize: true }}
    }},
    retina_detect: true
  }});
</script>

<!-- Perlin Noise -->
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
    noise(x, y = 0, z = 0) {{
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
  window.noise = (x, y, z = 0) => (_pn.noise(x, y, z) + 1) / 2;
</script>

<!-- Contour Animation with glow -->
<script>
(function() {{
  const sharpCanvas = document.getElementById('gis-canvas');
  const glowCanvas = document.getElementById('glow-canvas');
  const sharpCtx = sharpCanvas.getContext('2d');
  const glowCtx = glowCanvas.getContext('2d');

  const thresholdIncrement = 3;
  const thickLineThresholdMultiple = 4;
  const res = 4.5;
  const baseZOffset = 0.0004;

  let currentThreshold = 0;
  let cols = 0, rows = 0, zOffset = 0;
  let inputValues = [];
  let noiseMin = 100, noiseMax = 0;

  function resizeCanvas() {{
    sharpCanvas.width = glowCanvas.width = window.innerWidth;
    sharpCanvas.height = glowCanvas.height = window.innerHeight;
    cols = Math.floor(sharpCanvas.width / res) + 1;
    rows = Math.floor(sharpCanvas.height / res) + 1;
  }}

  function generateNoise() {{
    inputValues = [];
    for (let y = 0; y < rows; y++) {{
      inputValues[y] = [];
      for (let x = 0; x <= cols; x++) {{
        const n1 = window.noise(x * 0.018, y * 0.018, zOffset) * 100;
        const n2 = window.noise(x * 0.04, y * 0.04, zOffset * 1.3 + 100) * 30;
        inputValues[y][x] = n1 + n2;
        if (inputValues[y][x] < noiseMin) noiseMin = inputValues[y][x];
        if (inputValues[y][x] > noiseMax) noiseMax = inputValues[y][x];
      }}
    }}
  }}

  function linInterpolate(x0, x1) {{
    return x0 === x1 ? 0 : (currentThreshold - x0) / (x1 - x0);
  }}

  function binaryToType(nw, ne, se, sw) {{ return (nw << 3) | (ne << 2) | (se << 1) | sw; }}

  function line(ctx, from, to) {{ ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); }}

  function placeLines(ctx, gv, x, y) {{
    const nw = inputValues[y][x], ne = inputValues[y][x+1];
    const se = inputValues[y+1][x+1], sw = inputValues[y+1][x];
    const r = res, px = x * r, py = y * r;
    const a = [px + r * linInterpolate(nw, ne), py];
    const b = [px + r, py + r * linInterpolate(ne, se)];
    const c = [px + r * linInterpolate(sw, se), py + r];
    const d = [px, py + r * linInterpolate(nw, sw)];
    switch (gv) {{
      case 1: case 14: line(ctx, d, c); break;
      case 2: case 13: line(ctx, b, c); break;
      case 3: case 12: line(ctx, d, b); break;
      case 4: case 11: line(ctx, a, b); break;
      case 5: line(ctx, d, a); line(ctx, c, b); break;
      case 6: case 9: line(ctx, c, a); break;
      case 7: case 8: line(ctx, d, a); break;
      case 10: line(ctx, a, b); line(ctx, c, d); break;
    }}
  }}

  function renderAtThreshold() {{
    const isMajor = currentThreshold % (thresholdIncrement * thickLineThresholdMultiple) === 0;
    const mid = (noiseMin + noiseMax) / 2;
    const distFromMid = Math.abs(currentThreshold - mid) / ((noiseMax - noiseMin) / 2 + 0.1);
    const brightnessFactor = Math.max(0.15, 1.0 - distFromMid * 0.7);

    sharpCtx.beginPath();
    glowCtx.beginPath();

    for (let y = 0; y < inputValues.length - 1; y++) {{
      for (let x = 0; x < inputValues[y].length - 1; x++) {{
        const nw = inputValues[y][x] > currentThreshold ? 1 : 0;
        const ne = inputValues[y][x+1] > currentThreshold ? 1 : 0;
        const se = inputValues[y+1][x+1] > currentThreshold ? 1 : 0;
        const sw = inputValues[y+1][x] > currentThreshold ? 1 : 0;
        if (nw && ne && se && sw) continue;
        if (!nw && !ne && !se && !sw) continue;
        const gv = binaryToType(nw, ne, se, sw);
        placeLines(sharpCtx, gv, x, y);
        if (isMajor) placeLines(glowCtx, gv, x, y);
      }}
    }}

    if (isMajor) {{
      const a = Math.min(0.55, 0.35 * brightnessFactor + 0.1);
      sharpCtx.strokeStyle = `rgba(165,180,252,${{a}})`;
      sharpCtx.lineWidth = 1.8;
    }} else {{
      const a = Math.min(0.25, 0.12 * brightnessFactor + 0.03);
      sharpCtx.strokeStyle = `rgba(129,140,248,${{a}})`;
      sharpCtx.lineWidth = 0.7;
    }}
    sharpCtx.stroke();

    if (isMajor) {{
      const ga = Math.min(0.7, 0.5 * brightnessFactor + 0.1);
      glowCtx.strokeStyle = `rgba(165,180,252,${{ga}})`;
      glowCtx.lineWidth = 3.5;
      glowCtx.stroke();
    }}
  }}

  function animate() {{
    sharpCtx.clearRect(0, 0, sharpCanvas.width, sharpCanvas.height);
    glowCtx.clearRect(0, 0, glowCanvas.width, glowCanvas.height);
    zOffset += baseZOffset;
    generateNoise();
    const roundMin = Math.floor(noiseMin / thresholdIncrement) * thresholdIncrement;
    const roundMax = Math.ceil(noiseMax / thresholdIncrement) * thresholdIncrement;
    for (let t = roundMin; t < roundMax; t += thresholdIncrement) {{
      currentThreshold = t;
      renderAtThreshold();
    }}
    noiseMin = 100; noiseMax = 0;
    requestAnimationFrame(animate);
  }}

  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  setTimeout(animate, 200);
}})();
</script>

<!-- QWebChannel bridge -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.bridge = channel.objects.bridge;
  }});

  // Reveal logo only after it is ready to reduce visible pop-in.
  const appLogo = document.querySelector('.app-logo');
  if (appLogo) {{
    const revealLogo = () => window.requestAnimationFrame(() => appLogo.classList.add('is-visible'));
    if (appLogo.complete) {{
      revealLogo();
    }} else {{
      appLogo.addEventListener('load', revealLogo, {{ once: true }});
    }}
  }}
</script>
</body>
</html>'''
