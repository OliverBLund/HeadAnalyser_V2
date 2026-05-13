"""
HeadAnalyser V2 - Runtime cProfile hooks

Opt-in method-level profiling for interactive GUI flows.
Enable with:
    HEADANALYSER_CPROFILE=1
"""

from __future__ import annotations

import atexit
import cProfile
import io
import os
import pstats
import threading
import time
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Tuple


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if raw == "":
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


class RuntimeCProfiler:
    """Attach cProfile wrappers to selected class methods."""

    def __init__(self):
        self.enabled = _env_flag("HEADANALYSER_CPROFILE", default=False)
        self.deep = _env_flag("HEADANALYSER_CPROFILE_DEEP", default=False)
        self.include_callers = _env_flag("HEADANALYSER_CPROFILE_INCLUDE_CALLERS", default=False)
        self.min_ms = max(0.0, _env_float("HEADANALYSER_CPROFILE_MIN_MS", 10.0))
        self.top_n = max(5, _env_int("HEADANALYSER_CPROFILE_TOP_N", 40))
        self.max_events_per_method = max(1, _env_int("HEADANALYSER_CPROFILE_MAX_EVENTS_PER_METHOD", 20))
        self.sort_key = str(os.getenv("HEADANALYSER_CPROFILE_SORT", "cumulative") or "cumulative")
        self.log_path = str(
            os.getenv("HEADANALYSER_CPROFILE_LOG", "runtime_cprofile.log") or "runtime_cprofile.log"
        )
        self._installed = False
        self._lock = threading.Lock()
        self._method_counts: Dict[str, int] = {}
        self._summary: Dict[str, Dict[str, float]] = {}
        self._install_started = time.perf_counter()
        self._thread_state = threading.local()
        self._warned_external_profiler = False

    def _append_log(self, text: str):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def _record_summary(self, label: str, elapsed_ms: float):
        stats = self._summary.get(label)
        if stats is None:
            stats = {"count": 0.0, "total_ms": 0.0, "max_ms": 0.0}
            self._summary[label] = stats
        stats["count"] += 1.0
        stats["total_ms"] += float(elapsed_ms)
        if elapsed_ms > stats["max_ms"]:
            stats["max_ms"] = float(elapsed_ms)

    def _emit_event_stats(self, label: str, elapsed_ms: float, profiler: cProfile.Profile):
        with self._lock:
            self._record_summary(label, elapsed_ms)
            emitted = int(self._method_counts.get(label, 0))
            if elapsed_ms < self.min_ms:
                return
            if emitted >= self.max_events_per_method:
                return
            self._method_counts[label] = emitted + 1

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sio = io.StringIO()
        try:
            st = pstats.Stats(profiler, stream=sio).strip_dirs().sort_stats(self.sort_key)
            st.print_stats(self.top_n)
            if self.include_callers:
                st.print_callers(self.top_n)
        except Exception as exc:
            sio.write(f"[runtime-cprofile] failed to render stats: {exc}\n")

        header = (
            f"[runtime-cprofile {ts}] {label} elapsed={elapsed_ms:.2f}ms "
            f"(event {self._method_counts[label]}/{self.max_events_per_method})"
        )
        self._append_log(header)
        self._append_log(sio.getvalue().rstrip())
        self._append_log("")

    def _wrap_method(self, cls, method_name: str, label: Optional[str] = None):
        if cls is None:
            return
        original = getattr(cls, method_name, None)
        if original is None or not callable(original):
            return
        if getattr(original, "_ha_runtime_cprofile_wrapped", False):
            return

        use_label = label or f"{cls.__name__}.{method_name}"
        profiler_owner = self

        @wraps(original)
        def wrapped(*args, **kwargs):
            if not profiler_owner.enabled:
                return original(*args, **kwargs)
            # cProfile cannot be nested in the same thread; skip inner wrapped calls.
            state = profiler_owner._thread_state
            depth = int(getattr(state, "active_depth", 0))
            if depth > 0:
                return original(*args, **kwargs)

            setattr(state, "active_depth", depth + 1)
            p = cProfile.Profile()
            t0 = time.perf_counter()
            prof_active = False
            try:
                try:
                    p.enable()
                    prof_active = True
                except ValueError:
                    # Another profiler tool is active (or external profiler installed).
                    # Fall back gracefully instead of crashing the app.
                    if not profiler_owner._warned_external_profiler:
                        profiler_owner._warned_external_profiler = True
                        profiler_owner._append_log(
                            "[runtime-cprofile] skipped: another profiler is already active."
                        )
                    return original(*args, **kwargs)
                return original(*args, **kwargs)
            finally:
                setattr(state, "active_depth", depth)
                if prof_active:
                    p.disable()
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    profiler_owner._emit_event_stats(use_label, elapsed_ms, p)

        wrapped._ha_runtime_cprofile_wrapped = True  # type: ignore[attr-defined]
        setattr(cls, method_name, wrapped)

    def _resolve_targets(self) -> List[Tuple[object, str, str]]:
        from ui.main_window import MainWindow
        from ui.plot_page import PlotPage
        from ui.plot_widget import PlotWidget, PlotCanvas
        from ui.plot_quick_stats_b import PlotQuickStatsPanel
        from ui.data_table import DataTableWidget
        from ui.statistics_panel import StatisticsPanel
        from core.file_handler import FileHandler
        from core.gradient_calculation import GradientCalculation

        targets = [
            (MainWindow, "update_plot", "MainWindow.update_plot"),
            (MainWindow, "update_data_views", "MainWindow.update_data_views"),
            (PlotPage, "update_plot", "PlotPage.update_plot"),
            (PlotPage, "_toggle_table", "PlotPage._toggle_table"),
            (PlotPage, "_toggle_quick_stats", "PlotPage._toggle_quick_stats"),
            (PlotWidget, "update_plot", "PlotWidget.update_plot"),
            (PlotQuickStatsPanel, "update_from_app", "PlotQuickStatsPanel.update_from_app"),
            (DataTableWidget, "set_data", "DataTableWidget.set_data"),
            (DataTableWidget, "_on_selection_changed", "DataTableWidget._on_selection_changed"),
            (DataTableWidget, "highlight_rows_by_ids", "DataTableWidget.highlight_rows_by_ids"),
            (PlotWidget, "highlight_points_by_ids", "PlotWidget.highlight_points_by_ids"),
            (StatisticsPanel, "update_statistics", "StatisticsPanel.update_statistics"),
            (FileHandler, "filter_data", "FileHandler.filter_data"),
            (GradientCalculation, "create_gradient_dataframe", "GradientCalculation.create_gradient_dataframe"),
            (GradientCalculation, "calculate_average_gradient", "GradientCalculation.calculate_average_gradient"),
        ]

        if self.deep:
            targets.extend(
                [
                    (PlotWidget, "_draw_2d_plot", "PlotWidget._draw_2d_plot"),
                    (PlotWidget, "_draw_3d_plot", "PlotWidget._draw_3d_plot"),
                    (PlotWidget, "_draw_gradient_vectors", "PlotWidget._draw_gradient_vectors"),
                    (PlotWidget, "_draw_histogram", "PlotWidget._draw_histogram"),
                    (PlotWidget, "_draw_rose_diagram", "PlotWidget._draw_rose_diagram"),
                    (PlotCanvas, "draw", "PlotCanvas.draw"),
                    (PlotCanvas, "paintEvent", "PlotCanvas.paintEvent"),
                ]
            )
        return targets

    def _dump_summary(self):
        if not self.enabled:
            return
        elapsed_s = time.perf_counter() - self._install_started
        lines = [f"[runtime-cprofile summary +{elapsed_s:.1f}s]"]
        items = sorted(self._summary.items(), key=lambda kv: kv[1]["total_ms"], reverse=True)
        for name, s in items:
            count = int(s["count"])
            total = float(s["total_ms"])
            max_ms = float(s["max_ms"])
            avg = total / max(1, count)
            lines.append(f"{name}: n={count} total={total:.1f}ms avg={avg:.2f}ms max={max_ms:.2f}ms")
        if len(lines) == 1:
            lines.append("No profiled calls recorded.")
        self._append_log("\n".join(lines))
        self._append_log("")

    def install(self):
        if not self.enabled or self._installed:
            return False
        targets = self._resolve_targets()
        for cls, method_name, label in targets:
            self._wrap_method(cls, method_name, label)
        header = (
            f"[runtime-cprofile] enabled | log={self.log_path} | min_ms={self.min_ms:.1f} "
            f"| top_n={self.top_n} | deep={self.deep} | include_callers={self.include_callers}"
        )
        self._append_log(header)
        atexit.register(self._dump_summary)
        self._installed = True
        return True


_GLOBAL_PROFILER = RuntimeCProfiler()


def install_runtime_cprofile() -> bool:
    """Install runtime cProfile hooks if enabled by env vars."""
    return bool(_GLOBAL_PROFILER.install())
