from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_ALLOWED_MODES = {"parameter_sweep", "leave_out", "monte_carlo"}
_ALLOWED_SCOPE_TYPES = {"all_points", "selected_points"}
_ALLOWED_LEAVE_OUT_STRATEGY = {"one", "k_random"}


@dataclass
class PointScope:
    type: str = "all_points"
    ids: List[str] = field(default_factory=list)

    def normalize(self) -> "PointScope":
        self.type = str(self.type or "all_points").strip().lower()
        if self.type not in _ALLOWED_SCOPE_TYPES:
            raise ValueError(f"Unsupported point scope type: {self.type}")
        self.ids = sorted({str(v).strip() for v in (self.ids or []) if str(v).strip()})
        return self


@dataclass
class LeaveOutConfig:
    strategy: str = "one"
    k: int = 2
    iterations: int = 100

    def normalize(self) -> "LeaveOutConfig":
        self.strategy = str(self.strategy or "one").strip().lower()
        if self.strategy not in _ALLOWED_LEAVE_OUT_STRATEGY:
            raise ValueError(f"Unsupported leave-out strategy: {self.strategy}")
        self.k = max(1, int(self.k))
        self.iterations = max(1, int(self.iterations))
        return self


@dataclass
class MonteCarloConfig:
    perturb_h_sigma: float = 0.01
    perturb_xy_sigma: float = 0.0
    apply_xy: bool = False

    def normalize(self) -> "MonteCarloConfig":
        self.perturb_h_sigma = max(0.0, float(self.perturb_h_sigma))
        self.perturb_xy_sigma = max(0.0, float(self.perturb_xy_sigma))
        self.apply_xy = bool(self.apply_xy)
        return self


@dataclass
class SensitivityConfig:
    mode: str = "parameter_sweep"
    seed: int = 18472
    iterations: int = 120
    parameter_scenarios: List[Dict[str, float]] = field(default_factory=list)
    point_scope: PointScope = field(default_factory=PointScope)
    leave_out: LeaveOutConfig = field(default_factory=LeaveOutConfig)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SensitivityConfig":
        src = dict(data or {})

        point_scope_data = src.get("point_scope") or {}
        leave_out_data = src.get("leave_out") or {}
        monte_carlo_data = src.get("monte_carlo") or {}

        cfg = cls(
            mode=src.get("mode", "parameter_sweep"),
            seed=int(src.get("seed", 18472)),
            iterations=max(1, int(src.get("iterations", 120))),
            parameter_scenarios=list(src.get("parameter_scenarios") or []),
            point_scope=PointScope(
                type=point_scope_data.get("type", "all_points"),
                ids=list(point_scope_data.get("ids") or []),
            ),
            leave_out=LeaveOutConfig(
                strategy=leave_out_data.get("strategy", "one"),
                k=leave_out_data.get("k", 2),
                iterations=leave_out_data.get("iterations", 100),
            ),
            monte_carlo=MonteCarloConfig(
                perturb_h_sigma=monte_carlo_data.get("perturb_h_sigma", 0.01),
                perturb_xy_sigma=monte_carlo_data.get("perturb_xy_sigma", 0.0),
                apply_xy=monte_carlo_data.get("apply_xy", False),
            ),
        )
        return cfg.normalize()

    def normalize(self) -> "SensitivityConfig":
        self.mode = str(self.mode or "parameter_sweep").strip().lower()
        if self.mode not in _ALLOWED_MODES:
            raise ValueError(f"Unsupported sensitivity mode: {self.mode}")
        self.seed = int(self.seed)
        self.iterations = max(1, int(self.iterations))
        self.parameter_scenarios = [dict(v) for v in (self.parameter_scenarios or []) if isinstance(v, dict)]
        self.point_scope.normalize()
        self.leave_out.normalize()
        self.monte_carlo.normalize()
        return self


@dataclass
class RunSummary:
    run_id: str
    mode: str
    scenario_label: str
    num_points: int
    total_triangles: int
    kept_triangles: int
    rejected_triangles: int
    rejected_ratio: Optional[float]
    avg_gradient: Optional[float]
    avg_angle_unweighted: Optional[float]
    avg_angle_weighted: Optional[float]
    direction_coherence_r: Optional[float]
    calc_params: Dict[str, float] = field(default_factory=dict)
    seed: Optional[int] = None
    delta_avg_gradient: Optional[float] = None
    delta_avg_angle_weighted: Optional[float] = None
    rejected_due_to_uncertainty: int = 0
    rejected_due_to_triangle_quality: int = 0
    rejected_due_to_calculation_failed: int = 0


@dataclass
class SensitivityResult:
    config: SensitivityConfig
    baseline: RunSummary
    runs: List[RunSummary]
    distributions: Dict[str, List[float]]
    influence: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    rejection_breakdown: Dict[str, List[int]] = field(default_factory=dict)
    fragile_points: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "mode": self.config.mode,
                "seed": self.config.seed,
                "iterations": self.config.iterations,
                "parameter_scenarios": self.config.parameter_scenarios,
                "point_scope": {
                    "type": self.config.point_scope.type,
                    "ids": list(self.config.point_scope.ids),
                },
                "leave_out": {
                    "strategy": self.config.leave_out.strategy,
                    "k": self.config.leave_out.k,
                    "iterations": self.config.leave_out.iterations,
                },
                "monte_carlo": {
                    "perturb_h_sigma": self.config.monte_carlo.perturb_h_sigma,
                    "perturb_xy_sigma": self.config.monte_carlo.perturb_xy_sigma,
                    "apply_xy": self.config.monte_carlo.apply_xy,
                },
            },
            "baseline": self.baseline.__dict__,
            "runs": [r.__dict__ for r in self.runs],
            "distributions": self.distributions,
            "influence": self.influence,
            "metadata": self.metadata,
            "rejection_breakdown": self.rejection_breakdown,
            "fragile_points": self.fragile_points,
        }
