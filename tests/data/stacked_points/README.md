# Stacked Points Test Datasets

These CSV fixtures are for validating stacked-point behavior in 2D plots.

## Files

- `stacked_same_id_same_xy.csv`
  - Multiple rows share identical `ID`, `x`, and `y`.
  - Rows differ by `hydraulic head`, `top`, and `bottom`.
  - Use this to verify member-level selection (not ID-level collapse).

- `stacked_same_xy_diff_id.csv`
  - Multiple rows share identical `x` and `y`, but have different `ID` values.
  - Use this to verify normal stacked selection when IDs are unique.

- `stacked_precision_heads.csv`
  - Heads differ mainly at 3rd/4th decimal place.
  - Use this to verify display precision and avoid over-rounding.

## Expected Columns

Each file contains:

- `ID`
- `x`
- `y`
- `hydraulic head`
- `top`
- `bottom`

