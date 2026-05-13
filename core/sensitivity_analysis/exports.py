from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from .models import SensitivityResult


def sensitivity_runs_to_dataframe(result: SensitivityResult) -> pd.DataFrame:
    rows = []
    for r in result.runs:
        row = asdict(r)
        row["calc_params"] = json.dumps(row.get("calc_params") or {}, sort_keys=True)
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity_result_to_json_dict(result: SensitivityResult) -> dict:
    return result.to_dict()
