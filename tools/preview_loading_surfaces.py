"""Looping preview for the HeadAnalyser splash and loading dialog.

Run from the repository root:
    python tools/preview_loading_surfaces.py

Close the loading dialog or press Ctrl+C in the terminal to exit.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from Splash.simple_splash import SimpleSplash
from styles.colors import Colors
from styles.stylesheet import StyleSheet
from styles.theme import build_qpalette
from ui.loading_dialog import LoadingDialog


LOOP_STEPS = (
    (0, "Reading source file", "Parsing CSV/XLSX data and checking delimiters."),
    (16, "Resolving column mapping", "Preparing hydraulic head, coordinate, and ID columns."),
    (32, "Validating measurements", "Converting decimal separators and checking required values."),
    (48, "Transforming coordinates", "Projecting dataset coordinates for the map workspace."),
    (64, "Computing gradients", "Building triangle candidates and hydraulic-gradient vectors."),
    (82, "Rendering surfaces", "Refreshing plots, statistics, and report-ready outputs."),
    (95, "Finalizing workspace", "Synchronizing tabs, status counters, and preview surfaces."),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview HeadAnalyser loading surfaces in a loop.")
    parser.add_argument(
        "--theme",
        default="dark",
        choices=Colors.available_themes(),
        help="Theme used by the reusable loading dialog. The startup splash is intentionally always dark.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=90,
        help="Milliseconds between loop updates.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=2,
        help="Progress percentage increment per update.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _stage_for(percent: int) -> tuple[str, str]:
    stage = LOOP_STEPS[0]
    for candidate in LOOP_STEPS:
        if percent >= candidate[0]:
            stage = candidate
        else:
            break
    return stage[1], stage[2]


def _position_windows(splash: SimpleSplash, loading: LoadingDialog) -> None:
    screen = QApplication.primaryScreen()
    if screen is None:
        return

    geo = screen.availableGeometry()
    gap = 28
    loading.adjustSize()
    loading_width = max(520, min(620, loading.width() or loading.sizeHint().width()))
    loading_height = max(300, loading.sizeHint().height())
    loading.resize(loading_width, loading_height)

    total_width = splash.width() + gap + loading.width()
    if total_width <= geo.width() - 80:
        left = geo.center().x() - total_width // 2
        y = geo.center().y() - max(splash.height(), loading.height()) // 2
        splash.move(left, y)
        loading.move(left + splash.width() + gap, y + (splash.height() - loading.height()) // 2)
        return

    total_height = splash.height() + gap + loading.height()
    x = geo.center().x() - max(splash.width(), loading.width()) // 2
    y = geo.center().y() - total_height // 2
    splash.move(x, max(geo.top() + 20, y))
    loading.move(x + (splash.width() - loading.width()) // 2, splash.y() + splash.height() + gap)


def _reset_splash_progress(splash: SimpleSplash) -> None:
    # Startup progress is monotonic in production; reset internals only for this visual preview loop.
    splash._progress_animation.stop()  # type: ignore[attr-defined]
    splash._target_progress = 0  # type: ignore[attr-defined]
    splash._display_progress = 0.0  # type: ignore[attr-defined]


def _reset_loading_progress(dialog: LoadingDialog) -> None:
    progress = getattr(dialog, "_progress", None)
    if progress is None:
        return
    progress._current = 0  # type: ignore[attr-defined]
    progress._total = 100  # type: ignore[attr-defined]
    progress._ratio = 0.0  # type: ignore[attr-defined]
    progress.update()


def main() -> int:
    args = _parse_args()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("HeadAnalyser Loading Preview")
    app.setFont(QFont("Segoe UI", 10))
    Colors.apply_theme(args.theme)
    app.setPalette(build_qpalette())
    app.setStyleSheet(StyleSheet.get_main_stylesheet())

    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    splash = SimpleSplash()
    loading = LoadingDialog(
        "Loading Dialog Preview",
        "Reusable progress surface for imports, calculations, and report generation",
        None,
        cancellable=True,
    )
    loading.setModal(False)
    loading.setWindowModality(Qt.NonModal)
    loading.cancellation_requested.connect(app.quit)
    loading.destroyed.connect(app.quit)

    splash.set_progress(0, "Preview loop starting", "The splash and loading dialog will cycle indefinitely.")
    loading.update_progress(
        0,
        100,
        "Preview loop starting",
        "The reusable loading dialog will cycle indefinitely.",
        count_label="0%",
        activity_label="Close this dialog to stop the preview.",
    )
    loading.set_activity("This is a preview harness only; it does not run real data processing.")

    splash.show()
    loading.show()
    _position_windows(splash, loading)
    splash.raise_()
    loading.raise_()

    state = {"percent": 0, "loop": 1}

    def tick() -> None:
        previous = int(state["percent"])
        percent = previous + max(1, int(args.step))
        if percent > 100:
            percent = 0
            state["loop"] += 1
            _reset_splash_progress(splash)
            _reset_loading_progress(loading)

        state["percent"] = percent
        stage, detail = _stage_for(percent)
        activity = f"Loop {state['loop']} - {stage.lower()}."
        splash.set_progress(percent, stage, detail)
        loading.update_progress(
            percent,
            100,
            stage,
            detail,
            count_label=f"{percent}%",
            activity_label=activity,
        )

    timer = QTimer()
    timer.setInterval(max(16, int(args.interval)))
    timer.timeout.connect(tick)
    timer.start()

    keep_signal_timer_alive = QTimer()
    keep_signal_timer_alive.setInterval(250)
    keep_signal_timer_alive.timeout.connect(lambda: None)
    keep_signal_timer_alive.start()

    if args.smoke_test:
        QTimer.singleShot(250, app.quit)

    exit_code = app.exec_()
    return 0 if args.smoke_test else int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
