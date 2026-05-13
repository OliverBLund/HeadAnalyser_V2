"""
Sensitivity Analysis Dialog - Parameter Sweep with Actionable Insights.

Three-column layout:
  Left   (280px) : mode tabs, scenario setup, progress, baseline info
  Center (stretch): tornado chart + parameter response scatter + distribution histogram
  Right  (300px) : envelope KPIs, fragile points, export
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from styles.colors import Colors
from ui.icons import icon, Icons
from ui.workers import FunctionWorker
from qt_chrome import FramelessDialogMixin
from core.sensitivity_analysis import (
    SensitivityConfig,
    SensitivityResult,
    sensitivity_runs_to_dataframe,
    sensitivity_result_to_json_dict,
)


# ---------------------------------------------------------------------------
#  Grid sweep generator
# ---------------------------------------------------------------------------

# The 3 parameters we sweep, with their dataset attribute names
_SWEEP_PARAMS = [
    ("gradient_base_height_low",  "BH Low"),
    ("gradient_base_height_high", "BH High"),
    ("gradient_head_uncertainty", "Head Unc"),
]

# Sweep range: each param is varied from baseline*(1-spread) to baseline*(1+spread)
_DEFAULT_SPREAD = 0.50  # ±50%


def _build_grid_scenarios(baseline: dict[str, float], steps: int, spread: float = _DEFAULT_SPREAD) -> list[dict]:
    """Build a cartesian-product grid of parameter scenarios."""
    from itertools import product as cartesian_product

    axes = []
    axis_labels = []
    for param, short in _SWEEP_PARAMS:
        val = float(baseline.get(param, 0.0))
        lo = max(1e-6, val * (1.0 - spread))
        hi = max(lo + 1e-6, val * (1.0 + spread))
        axis = np.linspace(lo, hi, steps).tolist()
        axes.append(axis)
        axis_labels.append((param, short))

    scenarios = []
    for idx, combo in enumerate(cartesian_product(*axes), start=1):
        scen = {"label": f"grid-{idx:04d}"}
        parts = []
        for (param, short), val in zip(axis_labels, combo):
            scen[param] = float(val)
            parts.append(f"{short}={val:.4f}")
        scen["label"] = " | ".join(parts)
        scenarios.append(scen)
    return scenarios


# ---------------------------------------------------------------------------
#  Small helpers
# ---------------------------------------------------------------------------

def _fmt(v, decimals=4, fallback="-"):
    if v is None:
        return fallback
    return f"{float(v):.{decimals}f}"


def _pct(v, fallback="-"):
    if v is None:
        return fallback
    return f"{float(v) * 100:.1f}%"


def _make_separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setFrameShadow(QFrame.Plain)
    sep.setStyleSheet(f"background-color: {Colors.BORDER_DEFAULT}; border: none; max-height: 1px;")
    sep.setFixedHeight(1)
    return sep


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color: {Colors.TEXT_TERTIARY};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        background: transparent;
        border: none;
    """)
    return lbl


def _kpi_card(title: str, value: str = "-", color: str = Colors.TEXT_PRIMARY) -> tuple:
    """Small KPI card widget returning (container, value_label)."""
    card = QWidget()
    card.setStyleSheet(f"""
        QWidget {{
            background: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: 6px;
        }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 9px; font-weight: 600; border: none; background: transparent;")
    lay.addWidget(t)
    v_lbl = QLabel(value)
    v_lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700; border: none; background: transparent;")
    lay.addWidget(v_lbl)
    return card, v_lbl


# ---------------------------------------------------------------------------
#  Dark matplotlib canvas helper
# ---------------------------------------------------------------------------

def _plot_bg() -> str:
    return Colors.PLOT_DARK_BG if Colors.is_dark() else Colors.PLOT_BG


def _plot_face() -> str:
    return Colors.PLOT_DARK_FACE if Colors.is_dark() else Colors.PLOT_FACE


def _plot_border() -> str:
    return Colors.PLOT_DARK_BORDER if Colors.is_dark() else Colors.PLOT_BORDER


def _plot_text() -> str:
    return Colors.PLOT_DARK_TEXT if Colors.is_dark() else Colors.PLOT_TEXT


def _plot_spine() -> str:
    return Colors.PLOT_DARK_SPINE if Colors.is_dark() else Colors.PLOT_SPINE


def _make_dark_figure(width=4, height=3, dpi=100) -> tuple:
    fig = Figure(figsize=(width, height), dpi=dpi, facecolor=_plot_bg())
    canvas = FigureCanvas(fig)
    canvas.setStyleSheet(f"background: {_plot_bg()}; border: 1px solid {_plot_border()}; border-radius: 6px;")
    return fig, canvas


# ---------------------------------------------------------------------------
#  Fragile point row widget
# ---------------------------------------------------------------------------

class _FragileRow(QWidget):
    """Single fragile-point row: ID + fill bar + score label."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.id_label = QLabel("")
        self.id_label.setFixedWidth(60)
        self.id_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; background: transparent;")
        layout.addWidget(self.id_label)

        self._bar = QWidget()
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bar.setFixedHeight(12)
        self._bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bar.setStyleSheet(f"background-color: {Colors.BG_SURFACE}; border-radius: 3px;")
        layout.addWidget(self._bar)

        self.score_label = QLabel("")
        self.score_label.setFixedWidth(50)
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.score_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; background: transparent;")
        layout.addWidget(self.score_label)

        # Inner fill
        self._fill = QWidget(self._bar)
        self._fill.setAttribute(Qt.WA_StyledBackground, True)
        self._fill.setFixedHeight(12)

    def set_data(self, point_id: str, score: float):
        self.id_label.setText(str(point_id))
        pct = max(0.0, min(1.0, score))
        self.score_label.setText(f"{pct * 100:.0f}%")

        # Color: amber for < 0.5, red for >= 0.5
        if pct >= 0.5:
            color = Colors.ERROR
        else:
            color = Colors.WARNING

        self._fill.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        # Defer geometry to resizeEvent
        self._score = pct

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bar_w = self._bar.width()
        pct = getattr(self, "_score", 0.0)
        fill_w = max(2, int(bar_w * pct))
        self._fill.setGeometry(0, 0, fill_w, 12)


# ---------------------------------------------------------------------------
#  Tornado data computation
# ---------------------------------------------------------------------------

def _compute_tornado_data(result: SensitivityResult, metric: str) -> list[dict]:
    """Compute tornado chart data for each sweep parameter.

    Groups runs by each parameter's value (5 groups of N/5 runs),
    computes mean metric per group, returns range = max - min of group means.
    """
    runs = result.runs
    if not runs:
        return []

    # Extract metric values per run
    def _get_metric(r):
        if metric == "gradient":
            return r.avg_gradient
        elif metric == "direction":
            return r.avg_angle_weighted
        elif metric == "rejection":
            return r.rejected_ratio
        return None

    bars = []
    for param_key, param_short in _SWEEP_PARAMS:
        # Group by this parameter's value
        groups = defaultdict(list)
        for r in runs:
            val = r.calc_params.get(param_key)
            if val is not None:
                m = _get_metric(r)
                if m is not None:
                    groups[round(val, 8)].append(m)

        if not groups:
            continue

        group_means = [float(np.mean(vals)) for vals in groups.values()]
        if not group_means:
            continue

        lo = min(group_means)
        hi = max(group_means)
        sensitivity_range = hi - lo

        bars.append({
            "param": param_short,
            "param_key": param_key,
            "range": sensitivity_range,
            "lo": lo,
            "hi": hi,
            "group_keys": sorted(groups.keys()),
            "group_means": [float(np.mean(groups[k])) for k in sorted(groups.keys())],
        })

    bars.sort(key=lambda b: b["range"], reverse=True)
    return bars


# ---------------------------------------------------------------------------
#  Main dialog
# ---------------------------------------------------------------------------

class SensitivityDialog(FramelessDialogMixin, QDialog):
    """Sensitivity Analysis dialog - Parameter Sweep with actionable insights."""

    _progress_sig = pyqtSignal(int, int, str)  # current, total, label

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self._result: Optional[SensitivityResult] = None
        self._worker: Optional[FunctionWorker] = None
        self._thread: Optional[QThread] = None
        self._cancel_flag = False
        self._run_start_time: Optional[float] = None

        self.setWindowTitle("Sensitivity Analysis")
        self.resize(1400, 820)
        self.setMinimumSize(1000, 600)
        self.setModal(False)
        self.init_frameless_dialog_chrome(
            default_windows="frameless",
            default_other="native",
            resize_margin=10,
            top_resize_margin=10,
        )

        self._setup_ui()
        self._apply_styles()
        self.bind_frameless_drag_widget(self._chrome_header)
        self._progress_sig.connect(self._on_progress)

    # ==================================================================
    #  UI SETUP
    # ==================================================================

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_header(root)

        body = QHBoxLayout()
        body.setContentsMargins(12, 8, 12, 12)
        body.setSpacing(10)

        self._build_left_column(body)
        self._build_center_column(body)
        self._build_right_column(body)

        root.addLayout(body, 1)

    # ------------------------------------------------------------------
    #  Header
    # ------------------------------------------------------------------
    def _build_header(self, root_layout):
        header = QWidget()
        self._chrome_header = header
        header.setObjectName("dialog_header")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 14, 20, 14)
        h_lay.setSpacing(12)

        icon_box = QLabel()
        icon_box.setFixedSize(36, 36)
        icon_box.setPixmap(icon(Icons.SENSITIVITY, color=Colors.ACCENT_PRIMARY).pixmap(QSize(18, 18)))
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f"""
            background: {Colors.ACCENT_GHOST};
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 8px;
        """)
        h_lay.addWidget(icon_box)

        title_block = QVBoxLayout()
        title_block.setSpacing(0)
        title = QLabel("Sensitivity Analysis")
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 16px; font-weight: 700; background: transparent; border: none;")
        title_block.addWidget(title)
        subtitle = QLabel("Parameter Sweep  \u00b7  Explore how calculation settings affect results")
        subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px; background: transparent; border: none;")
        title_block.addWidget(subtitle)
        h_lay.addLayout(title_block)

        h_lay.addStretch()

        diag_chip = QLabel("Diagnostic Mode")
        diag_chip.setStyleSheet(f"""
            background: {Colors.ACCENT_GHOST};
            color: {Colors.ACCENT_PRIMARY};
            font-size: 10px; font-weight: 600;
            padding: 3px 10px;
            border: 1px solid {Colors.BORDER_ACCENT};
            border-radius: 10px;
        """)
        h_lay.addWidget(diag_chip)

        self._seed_chip = QLabel("Seed: 18472")
        self._seed_chip.setStyleSheet(f"""
            background: {Colors.BG_SURFACE};
            color: {Colors.TEXT_TERTIARY};
            font-size: 10px; font-weight: 600;
            padding: 3px 10px;
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: 10px;
        """)
        h_lay.addWidget(self._seed_chip)

        help_btn = QPushButton("?")
        help_btn.setObjectName("help_btn")
        help_btn.setFixedSize(32, 32)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setToolTip("How to interpret these results")
        help_btn.clicked.connect(self._open_help)
        h_lay.addWidget(help_btn)

        close_btn = QPushButton("\u00d7")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("Close")
        h_lay.addWidget(close_btn)

        root_layout.addWidget(header)

    # ------------------------------------------------------------------
    #  Left column (280px)
    # ------------------------------------------------------------------
    def _build_left_column(self, parent_layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(280)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_SUBTLE}; border-radius: 8px; }}")

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # -- Mode tabs --
        lay.addWidget(_section_label("MODE"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._mode_btns = []
        for label, enabled in [("Sweep", True), ("Leave-out", False), ("Monte Carlo", False)]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setEnabled(enabled)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)
            if not enabled:
                btn.setToolTip("Coming soon")
            self._mode_btns.append(btn)
            mode_row.addWidget(btn)
        self._mode_btns[0].setChecked(True)
        lay.addLayout(mode_row)

        lay.addWidget(_make_separator())

        # -- Grid Setup --
        lay.addWidget(_section_label("GRID SWEEP SETUP"))
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._steps_spin = QSpinBox()
        self._steps_spin.setObjectName("styled_spinbox")
        self._steps_spin.setRange(3, 9)
        self._steps_spin.setValue(5)
        self._steps_spin.setToolTip("Steps per parameter. Total runs = steps^3")
        self._steps_spin.valueChanged.connect(self._update_scenario_count)
        form.addRow("Steps/param:", self._steps_spin)

        self._spread_spin = QSpinBox()
        self._spread_spin.setObjectName("styled_spinbox")
        self._spread_spin.setRange(10, 100)
        self._spread_spin.setValue(50)
        self._spread_spin.setSuffix("%")
        self._spread_spin.setToolTip("How far from baseline each param varies (e.g. 50% = \u00b150%)")
        form.addRow("Spread:", self._spread_spin)

        self._seed_spin = QSpinBox()
        self._seed_spin.setObjectName("styled_spinbox")
        self._seed_spin.setRange(0, 999999)
        self._seed_spin.setValue(18472)
        self._seed_spin.valueChanged.connect(lambda v: self._seed_chip.setText(f"Seed: {v}"))
        form.addRow("Seed:", self._seed_spin)

        self._scenario_count_label = QLabel("")
        self._scenario_count_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
        form.addRow("Total runs:", self._scenario_count_label)
        self._update_scenario_count()

        lay.addLayout(form)

        lay.addWidget(_make_separator())

        # -- Run / Cancel --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._run_btn = QPushButton("Run Analysis")
        self._run_btn.setObjectName("primary_btn")
        self._run_btn.setFixedHeight(34)
        self._run_btn.setCursor(Qt.PointingHandCursor)
        self._run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self._run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        lay.addLayout(btn_row)

        # -- Progress --
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        lay.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px; background: transparent; border: none;")
        lay.addWidget(self._status_label)

        self._eta_label = QLabel("")
        self._eta_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        lay.addWidget(self._eta_label)

        lay.addWidget(_make_separator())

        # -- Current Settings (baseline) --
        lay.addWidget(_section_label("CURRENT SETTINGS"))
        self._baseline_info = QLabel("Load a dataset to see baseline")
        self._baseline_info.setWordWrap(True)
        self._baseline_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(self._baseline_info)
        self._refresh_baseline_info()

        lay.addWidget(_make_separator())

        # -- Active Data Scope --
        lay.addWidget(_section_label("ACTIVE DATA SCOPE"))
        self._scope_label = QLabel("")
        self._scope_label.setWordWrap(True)
        self._scope_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(self._scope_label)
        self._refresh_scope_info()

        lay.addStretch()
        scroll.setWidget(panel)
        parent_layout.addWidget(scroll)

    # ------------------------------------------------------------------
    #  Center column (stretch) - Tornado + Response Scatter + Histogram
    # ------------------------------------------------------------------
    def _build_center_column(self, parent_layout):
        center = QWidget()
        center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        c_lay = QVBoxLayout(center)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(8)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("Metric:"))
        self._metric_combo = QComboBox()
        self._metric_combo.addItems(["Gradient", "Direction", "Rejection %"])
        self._metric_combo.setFixedHeight(26)
        self._metric_combo.currentIndexChanged.connect(self._redraw_plots)
        toolbar.addWidget(self._metric_combo)

        toolbar.addWidget(QLabel("Parameter:"))
        self._param_combo = QComboBox()
        self._param_combo.addItems([short for _, short in _SWEEP_PARAMS])
        self._param_combo.setFixedHeight(26)
        self._param_combo.currentIndexChanged.connect(self._redraw_plots)
        toolbar.addWidget(self._param_combo)

        toolbar.addStretch()

        self._baseline_check = QCheckBox("Show baseline")
        self._baseline_check.setChecked(True)
        self._baseline_check.stateChanged.connect(self._redraw_plots)
        toolbar.addWidget(self._baseline_check)

        c_lay.addLayout(toolbar)

        # Tornado chart (~35%)
        self._fig_tornado, self._canvas_tornado = _make_dark_figure(8, 3)
        c_lay.addWidget(self._canvas_tornado, 3)

        # Parameter response scatter (~35%)
        self._fig_response, self._canvas_response = _make_dark_figure(8, 3)
        c_lay.addWidget(self._canvas_response, 3)

        # Distribution histogram (~30%)
        self._fig_histogram, self._canvas_histogram = _make_dark_figure(8, 2.5)
        c_lay.addWidget(self._canvas_histogram, 2)

        parent_layout.addWidget(center, 1)

    # ------------------------------------------------------------------
    #  Right column (300px) - Envelope KPIs + Fragile Points + Export
    # ------------------------------------------------------------------
    def _build_right_column(self, parent_layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(300)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_SUBTLE}; border-radius: 8px; }}")

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # -- Result Envelope KPIs --
        lay.addWidget(_section_label("RESULT ENVELOPE"))

        kpi_grid = QVBoxLayout()
        kpi_grid.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        c1, self._kpi_grad_range = _kpi_card("Gradient Range", "-", Colors.ACCENT_PRIMARY)
        c2, self._kpi_dir_range = _kpi_card("Direction Range", "-", Colors.WARNING)
        row1.addWidget(c1)
        row1.addWidget(c2)
        kpi_grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        c3, self._kpi_within_10 = _kpi_card("Within \u00b110\u00b0", "-", Colors.INFO)
        c4, self._kpi_within_20 = _kpi_card("Within \u00b120%", "-", Colors.INFO)
        row2.addWidget(c3)
        row2.addWidget(c4)
        kpi_grid.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(6)
        c5, self._kpi_stability = _kpi_card("Stability Score", "-", Colors.SUCCESS)
        row3.addWidget(c5)
        row3.addStretch()
        kpi_grid.addLayout(row3)

        lay.addLayout(kpi_grid)

        lay.addWidget(_make_separator())

        # -- Fragile Points --
        lay.addWidget(_section_label("FRAGILE POINTS"))
        self._fragile_empty_label = QLabel("Run analysis to see fragile points")
        self._fragile_empty_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        self._fragile_empty_label.setWordWrap(True)
        lay.addWidget(self._fragile_empty_label)

        self._fragile_scroll = QScrollArea()
        self._fragile_scroll.setWidgetResizable(True)
        self._fragile_scroll.setMaximumHeight(260)
        self._fragile_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._fragile_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }}")
        self._fragile_scroll.setVisible(False)

        self._fragile_container = QWidget()
        self._fragile_layout = QVBoxLayout(self._fragile_container)
        self._fragile_layout.setContentsMargins(0, 0, 0, 0)
        self._fragile_layout.setSpacing(2)
        self._fragile_scroll.setWidget(self._fragile_container)
        lay.addWidget(self._fragile_scroll)

        lay.addWidget(_make_separator())

        # -- Export --
        lay.addWidget(_section_label("EXPORT"))
        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        self._export_csv_btn = QPushButton("Export CSV")
        self._export_csv_btn.setFixedHeight(30)
        self._export_csv_btn.setCursor(Qt.PointingHandCursor)
        self._export_csv_btn.setEnabled(False)
        self._export_csv_btn.clicked.connect(self._export_csv)
        export_row.addWidget(self._export_csv_btn)

        self._export_json_btn = QPushButton("Export JSON")
        self._export_json_btn.setFixedHeight(30)
        self._export_json_btn.setCursor(Qt.PointingHandCursor)
        self._export_json_btn.setEnabled(False)
        self._export_json_btn.clicked.connect(self._export_json)
        export_row.addWidget(self._export_json_btn)
        lay.addLayout(export_row)

        lay.addStretch()
        scroll.setWidget(panel)
        parent_layout.addWidget(scroll)

    # ==================================================================
    #  Styles
    # ==================================================================

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {Colors.BG_APP};
            }}
            #dialog_header {{
                background: {Colors.BG_PANEL};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
            #help_btn {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                font-size: 16px;
                font-weight: 700;
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
            }}
            #help_btn:hover {{
                background: {Colors.ACCENT_GHOST};
                color: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.BORDER_ACCENT};
            }}
            #close_btn {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                font-size: 20px;
                font-weight: 400;
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
            }}
            #close_btn:hover {{
                background: {Colors.ERROR_BG};
                color: {Colors.ERROR};
                border-color: {Colors.ERROR};
            }}
            #primary_btn {{
                background: {Colors.GRADIENT_ACCENT};
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
            }}
            #primary_btn:hover {{
                background: {Colors.ACCENT_BRIGHT};
            }}
            #primary_btn:disabled {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_DISABLED};
            }}
            #cancel_btn {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 600;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 0 12px;
            }}
            #cancel_btn:hover {{
                background: {Colors.ERROR_BG};
                color: {Colors.ERROR};
                border-color: {Colors.ERROR};
            }}
            #cancel_btn:disabled {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.BORDER_SUBTLE};
            }}
            QPushButton[checkable="true"] {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 2px 10px;
            }}
            QPushButton[checkable="true"]:checked {{
                background: {Colors.ACCENT_GHOST};
                color: {Colors.ACCENT_PRIMARY};
                border-color: {Colors.BORDER_ACCENT};
            }}
            QPushButton[checkable="true"]:disabled {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.BORDER_SUBTLE};
            }}
            QProgressBar {{
                background: {Colors.BG_SURFACE};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {Colors.GRADIENT_ACCENT};
                border-radius: 3px;
            }}
            QComboBox {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QSpinBox {{
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QCheckBox {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                spacing: 6px;
                background: transparent;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QScrollArea {{
                border: none;
            }}
        """)

    # ==================================================================
    #  Info helpers
    # ==================================================================

    def _refresh_baseline_info(self):
        ds = self.main_window.get_active_dataset() if self.main_window else None
        if ds is None:
            self._baseline_info.setText("No dataset loaded")
            return
        lines = [
            f"base_height_low: {_fmt(getattr(ds, 'gradient_base_height_low', None))}",
            f"base_height_high: {_fmt(getattr(ds, 'gradient_base_height_high', None))}",
            f"head_uncertainty: {_fmt(getattr(ds, 'gradient_head_uncertainty', None))}",
            f"confidence: {_fmt(getattr(ds, 'gradient_confidence_level', None))}",
        ]
        self._baseline_info.setText("\n".join(lines))

    def _refresh_scope_info(self):
        ds = self.main_window.get_active_dataset() if self.main_window else None
        if ds is None:
            self._scope_label.setText("No dataset loaded")
            return
        data = ds.filtered_data if ds.filtered_data is not None else ds.data
        n = len(data) if data is not None else 0
        self._scope_label.setText(f"Scope: all points\nPoints: {n}")

    def _update_scenario_count(self):
        steps = self._steps_spin.value()
        total = steps ** 3
        self._scenario_count_label.setText(f"{total} ({steps}\u00b3)")

    # ==================================================================
    #  Run / Cancel
    # ==================================================================

    def _on_run(self):
        ds = self.main_window.get_active_dataset() if self.main_window else None
        if ds is None:
            QMessageBox.warning(self, "Sensitivity Analysis", "No active dataset.")
            return

        self._cancel_flag = False
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Preparing...")
        self._eta_label.setText("")
        self._run_start_time = time.perf_counter()

        baseline = {
            "gradient_base_height_low": float(getattr(ds, "gradient_base_height_low", 0.2)),
            "gradient_base_height_high": float(getattr(ds, "gradient_base_height_high", 8.0)),
            "gradient_head_uncertainty": float(getattr(ds, "gradient_head_uncertainty", 0.01)),
        }
        steps = self._steps_spin.value()
        spread = self._spread_spin.value() / 100.0
        scenarios = _build_grid_scenarios(baseline, steps, spread)

        config_dict = {
            "mode": "parameter_sweep",
            "seed": self._seed_spin.value(),
            "parameter_scenarios": scenarios,
        }

        def _work():
            return self.main_window.run_sensitivity_analysis(
                config=config_dict,
                progress_callback=self._thread_progress,
                cancel_check=lambda: self._cancel_flag,
            )

        self._thread = QThread()
        self._worker = FunctionWorker(_work)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results_ready)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._on_error)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_cancel(self):
        self._cancel_flag = True
        self._status_label.setText("Cancelling...")
        self._cancel_btn.setEnabled(False)

    def _thread_progress(self, current: int, total: int, label: str):
        self._progress_sig.emit(current, total, label)

    def _on_progress(self, current: int, total: int, label: str):
        if total > 0:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)
            self._status_label.setText(f"Running {current}/{total}: {label}")
            if current > 0 and self._run_start_time is not None:
                elapsed = time.perf_counter() - self._run_start_time
                eta = (elapsed / current) * (total - current)
                self._eta_label.setText(f"ETA: {eta:.1f}s remaining")

    def _on_results_ready(self, result):
        self._result = result
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(100)
        elapsed = time.perf_counter() - self._run_start_time if self._run_start_time else 0
        self._status_label.setText(f"Done - {len(result.runs)} runs in {elapsed:.1f}s")
        self._eta_label.setText("")
        self._export_csv_btn.setEnabled(True)
        self._export_json_btn.setEnabled(True)
        self._populate_results(result)

    def _on_error(self, message: str, tb: str):
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText("Error")
        self._eta_label.setText("")
        QMessageBox.critical(self, "Sensitivity Analysis Error", f"{message}\n\n{tb}")

    def _cleanup_thread(self):
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ==================================================================
    #  Populate results
    # ==================================================================

    def _populate_results(self, result: SensitivityResult):
        self._update_kpis(result)
        self._populate_fragile_points(result)

        # Auto-select dominant parameter in the param combo
        bars = _compute_tornado_data(result, self._get_selected_metric())
        if bars:
            dominant_key = bars[0]["param_key"]
            for i, (key, _) in enumerate(_SWEEP_PARAMS):
                if key == dominant_key:
                    self._param_combo.blockSignals(True)
                    self._param_combo.setCurrentIndex(i)
                    self._param_combo.blockSignals(False)
                    break

        self._redraw_plots()

    def _update_kpis(self, result: SensitivityResult):
        bl = result.baseline
        dists = result.distributions

        # Gradient Range (min-max across runs)
        if dists.get("avg_gradient"):
            g_min = min(dists["avg_gradient"])
            g_max = max(dists["avg_gradient"])
            self._kpi_grad_range.setText(f"{g_min:.4f} \u2013 {g_max:.4f}")
        else:
            self._kpi_grad_range.setText("-")

        # Direction Range (min-max across runs)
        if dists.get("avg_angle_weighted") and len(dists["avg_angle_weighted"]) > 1:
            angles = np.array(dists["avg_angle_weighted"])
            # Use circular range: max angular distance between any two run results
            rad = np.deg2rad(angles)
            s = np.mean(np.sin(rad))
            c = np.mean(np.cos(rad))
            mean_angle = np.degrees(np.arctan2(s, c)) % 360
            deltas = np.abs((angles - mean_angle + 180) % 360 - 180)
            spread = float(np.max(deltas) - np.min(deltas)) if len(deltas) > 1 else 0.0
            d_min = float(np.min(angles))
            d_max = float(np.max(angles))
            self._kpi_dir_range.setText(f"{d_min:.1f}\u00b0 \u2013 {d_max:.1f}\u00b0")
        else:
            self._kpi_dir_range.setText("-")

        # Within ±10° of baseline direction
        within_10_ratio = 0.0
        if bl.avg_angle_weighted is not None and dists.get("avg_angle_weighted"):
            bl_angle = float(bl.avg_angle_weighted)
            angles = np.array(dists["avg_angle_weighted"])
            deltas = np.abs((angles - bl_angle + 180) % 360 - 180)
            n_within_10 = int(np.sum(deltas <= 10))
            within_10_ratio = n_within_10 / len(angles) if len(angles) > 0 else 0.0
            self._kpi_within_10.setText(f"{n_within_10}/{len(angles)}")
        else:
            self._kpi_within_10.setText("-")

        # Within ±20% of baseline gradient
        within_20_ratio = 0.0
        if bl.avg_gradient is not None and bl.avg_gradient > 0 and dists.get("avg_gradient"):
            grads = np.array(dists["avg_gradient"])
            within = np.abs(grads - bl.avg_gradient) <= 0.2 * bl.avg_gradient
            n_within_20 = int(np.sum(within))
            within_20_ratio = n_within_20 / len(grads) if len(grads) > 0 else 0.0
            self._kpi_within_20.setText(f"{n_within_20}/{len(grads)}")
        else:
            self._kpi_within_20.setText("-")

        # Stability Score = product of the two "within" ratios
        if within_10_ratio > 0 or within_20_ratio > 0:
            stability = within_10_ratio * within_20_ratio
            self._kpi_stability.setText(f"{stability:.1%}")
        else:
            self._kpi_stability.setText("-")

    def _populate_fragile_points(self, result: SensitivityResult):
        # Clear old rows
        while self._fragile_layout.count():
            item = self._fragile_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        fragile = result.fragile_points
        if not fragile:
            self._fragile_empty_label.setText("No fragile points \u2014 all triangles are stable across runs")
            self._fragile_empty_label.setVisible(True)
            self._fragile_scroll.setVisible(False)
            return

        self._fragile_empty_label.setVisible(False)
        self._fragile_scroll.setVisible(True)

        for fp in fragile[:50]:  # Cap at 50 rows
            row = _FragileRow()
            row.set_data(fp["point_id"], fp["fragility_score"])
            self._fragile_layout.addWidget(row)

        self._fragile_layout.addStretch()

    # ==================================================================
    #  Plot drawing
    # ==================================================================

    def _redraw_plots(self):
        result = self._result
        if result is None:
            return
        self._draw_tornado(result)
        self._draw_response(result)
        self._draw_histogram(result)

    def _get_selected_metric(self) -> str:
        idx = self._metric_combo.currentIndex()
        return ["gradient", "direction", "rejection"][idx]

    def _draw_tornado(self, result: SensitivityResult):
        fig = self._fig_tornado
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_dark_ax(ax)

        metric = self._get_selected_metric()
        metric_labels = {"gradient": "Mean Gradient", "direction": "Direction (\u00b0)", "rejection": "Rejection %"}
        ax.set_title(f"Parameter Sensitivity \u2014 {metric_labels.get(metric, metric)}", color=_plot_text(), fontsize=10, pad=8)

        bars = _compute_tornado_data(result, metric)
        if not bars:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_plot_text(), fontsize=12, transform=ax.transAxes)
            fig.tight_layout(pad=1.5)
            self._canvas_tornado.draw_idle()
            return

        # Horizontal bar chart - most important on top
        param_names = [b["param"] for b in bars]
        ranges = [b["range"] for b in bars]
        lo_vals = [b["lo"] for b in bars]
        hi_vals = [b["hi"] for b in bars]

        y_pos = np.arange(len(bars))
        bar_colors = [Colors.ACCENT_PRIMARY, Colors.INFO, Colors.WARNING][:len(bars)]

        # Draw bars from lo to hi (centered on the midpoint)
        for i, b in enumerate(bars):
            ax.barh(y_pos[i], b["hi"] - b["lo"], left=b["lo"], height=0.5,
                    color=bar_colors[i], alpha=0.85, edgecolor=_plot_border(), linewidth=0.5)
            # Value labels at ends
            ax.text(b["lo"] - (b["range"] * 0.02 + 0.001), y_pos[i], f"{b['lo']:.4f}",
                    ha="right", va="center", color=_plot_text(), fontsize=8)
            ax.text(b["hi"] + (b["range"] * 0.02 + 0.001), y_pos[i], f"{b['hi']:.4f}",
                    ha="left", va="center", color=_plot_text(), fontsize=8)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(param_names)
        ax.invert_yaxis()

        # Baseline vertical line
        if self._baseline_check.isChecked():
            bl = result.baseline
            bl_val = None
            if metric == "gradient":
                bl_val = bl.avg_gradient
            elif metric == "direction":
                bl_val = bl.avg_angle_weighted
            elif metric == "rejection":
                bl_val = bl.rejected_ratio
            if bl_val is not None:
                ax.axvline(bl_val, color="#4ade80", linewidth=1.5, linestyle="--", label="Baseline", zorder=5)
                ax.legend(fontsize=8, facecolor=_plot_bg(), edgecolor=_plot_border(), labelcolor=_plot_text(), loc="lower right")

        ax.set_xlabel(metric_labels.get(metric, metric), color=_plot_text(), fontsize=9)
        # Add some padding to x-axis
        if ranges:
            max_range = max(ranges)
            all_lo = min(lo_vals)
            all_hi = max(hi_vals)
            pad = max_range * 0.15
            ax.set_xlim(all_lo - pad, all_hi + pad)

        fig.tight_layout(pad=1.5)
        self._canvas_tornado.draw_idle()

    def _draw_response(self, result: SensitivityResult):
        """Parameter response scatter: selected param (x) vs selected metric (y)."""
        fig = self._fig_response
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_dark_ax(ax)

        runs = result.runs
        if not runs:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_plot_text(), fontsize=12, transform=ax.transAxes)
            fig.tight_layout(pad=1.5)
            self._canvas_response.draw_idle()
            return

        # Selected parameter
        param_idx = self._param_combo.currentIndex()
        param_key, param_short = _SWEEP_PARAMS[param_idx]

        # Selected metric
        metric = self._get_selected_metric()
        metric_labels = {"gradient": "Mean Gradient", "direction": "Direction (\u00b0)", "rejection": "Rejection %"}

        def _get_metric(r):
            if metric == "gradient":
                return r.avg_gradient
            elif metric == "direction":
                return r.avg_angle_weighted
            elif metric == "rejection":
                return r.rejected_ratio
            return None

        # Extract x, y from each run
        x_vals, y_vals = [], []
        for r in runs:
            xv = r.calc_params.get(param_key)
            yv = _get_metric(r)
            if xv is not None and yv is not None:
                x_vals.append(float(xv))
                y_vals.append(float(yv))

        if not x_vals:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_plot_text(), fontsize=12, transform=ax.transAxes)
            fig.tight_layout(pad=1.5)
            self._canvas_response.draw_idle()
            return

        ax.set_title(f"{param_short} vs {metric_labels.get(metric, metric)}", color=_plot_text(), fontsize=10, pad=8)

        # Scatter all points
        ax.scatter(x_vals, y_vals, s=14, color=Colors.ACCENT_PRIMARY, alpha=0.35, edgecolors="none", zorder=2)

        # Group means + trend line
        groups = defaultdict(list)
        for xv, yv in zip(x_vals, y_vals):
            groups[round(xv, 8)].append(yv)

        sorted_keys = sorted(groups.keys())
        group_x = [k for k in sorted_keys]
        group_y = [float(np.mean(groups[k])) for k in sorted_keys]
        ax.plot(group_x, group_y, color=Colors.ACCENT_BRIGHT, linewidth=1.8, marker="o", markersize=5, zorder=3, label="Group mean")

        # Baseline diamond
        if self._baseline_check.isChecked():
            bl = result.baseline
            bl_x = bl.calc_params.get(param_key) if bl.calc_params else None
            bl_y = _get_metric(bl)
            if bl_x is not None and bl_y is not None:
                ax.scatter([float(bl_x)], [float(bl_y)], s=80, color="#4ade80", marker="D", zorder=5, label="Baseline", edgecolors="#166534", linewidths=0.8)

        ax.set_xlabel(param_short, color=_plot_text(), fontsize=9)
        ax.set_ylabel(metric_labels.get(metric, metric), color=_plot_text(), fontsize=9)
        ax.legend(fontsize=7, facecolor=_plot_bg(), edgecolor=_plot_border(), labelcolor=_plot_text(), loc="best")

        fig.tight_layout(pad=1.5)
        self._canvas_response.draw_idle()

    def _draw_histogram(self, result: SensitivityResult):
        """Distribution histogram of selected metric across all runs."""
        fig = self._fig_histogram
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_dark_ax(ax)

        metric = self._get_selected_metric()
        metric_labels = {"gradient": "Mean Gradient", "direction": "Direction (\u00b0)", "rejection": "Rejection %"}
        dist_keys = {"gradient": "avg_gradient", "direction": "avg_angle_weighted", "rejection": "rejected_ratio"}

        values = result.distributions.get(dist_keys.get(metric, ""))
        if not values:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_plot_text(), fontsize=12, transform=ax.transAxes)
            fig.tight_layout(pad=1.5)
            self._canvas_histogram.draw_idle()
            return

        arr = np.array(values, dtype=float)
        n_bins = max(5, int(np.sqrt(len(arr))))

        ax.set_title(f"Distribution \u2014 {metric_labels.get(metric, metric)}", color=_plot_text(), fontsize=10, pad=8)
        ax.hist(arr, bins=n_bins, color=Colors.ACCENT_PRIMARY, alpha=0.65, edgecolor=_plot_border(), linewidth=0.5)

        # Baseline vertical line
        if self._baseline_check.isChecked():
            bl = result.baseline
            bl_val = None
            if metric == "gradient":
                bl_val = bl.avg_gradient
            elif metric == "direction":
                bl_val = bl.avg_angle_weighted
            elif metric == "rejection":
                bl_val = bl.rejected_ratio
            if bl_val is not None:
                ax.axvline(float(bl_val), color="#4ade80", linewidth=1.5, linestyle="--", label="Baseline", zorder=5)
                ax.legend(fontsize=7, facecolor=_plot_bg(), edgecolor=_plot_border(), labelcolor=_plot_text(), loc="best")

        ax.set_xlabel(metric_labels.get(metric, metric), color=_plot_text(), fontsize=9)
        ax.set_ylabel("Count", color=_plot_text(), fontsize=9)

        fig.tight_layout(pad=1.5)
        self._canvas_histogram.draw_idle()

    @staticmethod
    def _style_dark_ax(ax):
        ax.set_facecolor(_plot_face())
        ax.tick_params(colors=_plot_text(), labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(_plot_spine())

    # ==================================================================
    #  Export
    # ==================================================================

    def _export_csv(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "sensitivity_runs.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = sensitivity_runs_to_dataframe(self._result)
            df.to_csv(path, index=False)
            QMessageBox.information(self, "Export", f"CSV exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_json(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "sensitivity_result.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            data = sensitivity_result_to_json_dict(self._result)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            QMessageBox.information(self, "Export", f"JSON exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ==================================================================
    #  Cleanup
    # ==================================================================

    # ==================================================================
    #  Help
    # ==================================================================

    def _open_help(self):
        from .help_dialog import HelpDialog
        dlg = HelpDialog(parent=self, initial_page="sensitivity_analysis")
        try:
            dlg.exec_()
        finally:
            dlg.deleteLater()

    def closeEvent(self, event):
        self._cancel_flag = True
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)
