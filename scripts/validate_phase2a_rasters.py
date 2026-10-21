"""Validate Phase 2A georeferenced derived rasters without modifying files."""

from __future__ import annotations

import json
from pathlib import Path

if __package__:
    from .prepare_georeferenced_rasters import validate_outputs
else:
    from prepare_georeferenced_rasters import validate_outputs


def main() -> int:
    output_dir = Path(__file__).resolve().parents[1] / "data" / "processed_phase2a"
    report = validate_outputs(output_dir=output_dir)
    print(json.dumps(report, indent=2, default=list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
