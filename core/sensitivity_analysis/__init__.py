"""Sensitivity analysis backend package.

This package is intentionally isolated so it can be enabled/disabled without
impacting the core gradient workflow.
"""

from .models import SensitivityConfig, SensitivityResult, RunSummary
from .engine import SensitivityAnalysisEngine
from .exports import sensitivity_result_to_json_dict, sensitivity_runs_to_dataframe

__all__ = [
    "SensitivityConfig",
    "SensitivityResult",
    "RunSummary",
    "SensitivityAnalysisEngine",
    "sensitivity_result_to_json_dict",
    "sensitivity_runs_to_dataframe",
]
