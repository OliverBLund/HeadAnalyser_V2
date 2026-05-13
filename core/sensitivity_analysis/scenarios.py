from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List

import numpy as np
import pandas as pd

from .models import SensitivityConfig


@dataclass
class RunPlan:
    run_id: str
    scenario_label: str
    data: pd.DataFrame
    calc_params: Dict[str, float]
    seed: int | None = None
    metadata: Dict[str, object] = field(default_factory=dict)


def _default_parameter_scenarios(base_settings: Dict[str, float]) -> List[Dict[str, float]]:
    low = float(base_settings["gradient_base_height_low"])
    high = float(base_settings["gradient_base_height_high"])
    h_unc = float(base_settings["gradient_head_uncertainty"])
    return [
        {
            "label": "strict",
            "gradient_base_height_low": max(0.0, low * 1.2),
            "gradient_base_height_high": max(0.001, high * 0.75),
            "gradient_head_uncertainty": max(0.0, h_unc * 0.8),
        },
        {
            "label": "default",
            "gradient_base_height_low": low,
            "gradient_base_height_high": high,
            "gradient_head_uncertainty": h_unc,
        },
        {
            "label": "permissive",
            "gradient_base_height_low": max(0.0, low * 0.8),
            "gradient_base_height_high": max(0.001, high * 1.25),
            "gradient_head_uncertainty": max(0.0, h_unc * 1.25),
        },
    ]


def build_run_plans(
    cfg: SensitivityConfig,
    data: pd.DataFrame,
    col_mapping: Dict[str, str],
    base_settings: Dict[str, float],
) -> List[RunPlan]:
    plans: List[RunPlan] = []
    rng = np.random.default_rng(int(cfg.seed))

    id_col = col_mapping["ID"]
    x_col = col_mapping["x"]
    y_col = col_mapping["y"]
    h_col = col_mapping["hydraulic head"]

    if cfg.mode == "parameter_sweep":
        scenarios = list(cfg.parameter_scenarios or _default_parameter_scenarios(base_settings))
        for i, scen in enumerate(scenarios, start=1):
            overrides = {k: float(v) for k, v in scen.items() if k.startswith("gradient_")}
            merged = dict(base_settings)
            merged.update(overrides)
            label = str(scen.get("label") or f"scenario-{i:02d}")
            plans.append(
                RunPlan(
                    run_id=f"S{i:03d}",
                    scenario_label=label,
                    data=data.copy(),
                    calc_params=merged,
                    seed=int(cfg.seed),
                )
            )
        return plans

    if cfg.mode == "leave_out":
        all_ids = sorted(set(data[id_col].astype(str).tolist()))
        strategy = cfg.leave_out.strategy
        if strategy == "one":
            for i, pid in enumerate(all_ids, start=1):
                d = data[data[id_col].astype(str) != str(pid)].copy()
                plans.append(
                    RunPlan(
                        run_id=f"L{i:03d}",
                        scenario_label=f"omit-{pid}",
                        data=d,
                        calc_params=dict(base_settings),
                        seed=int(cfg.seed),
                        metadata={"left_out_ids": [str(pid)]},
                    )
                )
            return plans

        # k-random
        k = min(max(1, int(cfg.leave_out.k)), max(1, len(all_ids) - 1))
        iterations = max(1, int(cfg.leave_out.iterations))
        seen = set()
        max_unique = 1
        if len(all_ids) > k:
            # bound by combinations for small sets to avoid duplicates dominating.
            try:
                max_unique = int(len(list(combinations(all_ids, k))))
            except Exception:
                max_unique = iterations
        target = min(iterations, max_unique)
        i = 0
        while len(plans) < target and i < iterations * 10:
            i += 1
            take = tuple(sorted(rng.choice(all_ids, size=k, replace=False).tolist()))
            if take in seen:
                continue
            seen.add(take)
            d = data[~data[id_col].astype(str).isin(set(take))].copy()
            plans.append(
                RunPlan(
                    run_id=f"L{len(plans)+1:03d}",
                    scenario_label=f"omit-{'-'.join(take)}",
                    data=d,
                    calc_params=dict(base_settings),
                    seed=int(cfg.seed + len(plans)),
                    metadata={"left_out_ids": list(take)},
                )
            )
        return plans

    # monte_carlo
    sigma_h = float(cfg.monte_carlo.perturb_h_sigma)
    sigma_xy = float(cfg.monte_carlo.perturb_xy_sigma)
    apply_xy = bool(cfg.monte_carlo.apply_xy)

    for i in range(int(cfg.iterations)):
        run_rng = np.random.default_rng(int(cfg.seed + i))
        d = data.copy()
        if sigma_h > 0.0:
            d[h_col] = d[h_col].astype(float).to_numpy() + run_rng.normal(0.0, sigma_h, size=len(d))
        if apply_xy and sigma_xy > 0.0:
            d[x_col] = d[x_col].astype(float).to_numpy() + run_rng.normal(0.0, sigma_xy, size=len(d))
            d[y_col] = d[y_col].astype(float).to_numpy() + run_rng.normal(0.0, sigma_xy, size=len(d))
        plans.append(
            RunPlan(
                run_id=f"M{i+1:03d}",
                scenario_label=f"mc-{i+1:03d}",
                data=d,
                calc_params=dict(base_settings),
                seed=int(cfg.seed + i),
                metadata={
                    "perturb_h_sigma": sigma_h,
                    "perturb_xy_sigma": sigma_xy,
                    "apply_xy": apply_xy,
                },
            )
        )
    return plans
