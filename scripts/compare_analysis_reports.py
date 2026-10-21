"""Create a non-equivalence comparison of synthetic/demo and real-data runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def create_comparison(synthetic_path: Path, real_path: Path) -> dict[str, Any]:
    synthetic = json.loads(synthetic_path.read_text(encoding="utf-8"))
    real = json.loads(real_path.read_text(encoding="utf-8"))
    if synthetic.get("analysis_mode") != "synthetic_demo":
        raise ValueError("Synthetic input must declare analysis_mode='synthetic_demo'.")
    if real.get("analysis_mode") != "real_data_geographic_access_diagnostics":
        raise ValueError("Real input must be a real-data geographic-access diagnostic report.")
    district_name = synthetic.get("district")
    real_district = next(
        (district for district in real.get("districts", []) if district.get("district") == district_name),
        None,
    )
    if real_district is None:
        raise ValueError(f"Real report does not contain synthetic district {district_name!r}.")
    return {
        "schema_version": "1.0.0",
        "comparison_type": "methodology_and_coverage_side_by_side",
        "numerical_metric_comparison_performed": False,
        "equivalent_measurements": False,
        "synthetic": {
            "district": district_name,
            "analysis_mode": synthetic["analysis_mode"],
            "result_type": synthetic.get("result_type"),
            "metrics": {
                "total_habitations": synthetic.get("total_habitations"),
                "total_population": synthetic.get("total_population"),
                "underserved_habitations_60min": synthetic.get("underserved_habitations_60min"),
                "underserved_population_60min": synthetic.get("underserved_population_60min"),
            },
            "interpretation": (
                "Synthetic/demo estimate from the existing synthetic terrain and simulated modifiers; "
                "its modeled-minute and population metrics are not measurements from the real datasets."
            ),
        },
        "real": {
            "district": district_name,
            "analysis_mode": real["analysis_mode"],
            "result_type": real.get("result_type"),
            "source_counts": real_district.get("counts"),
            "metric": real_district.get("accessibility_metric"),
            "interpretation": (
                "Nearest straight-line facility-point proximity in meters, without routed travel, "
                "population weighting, capacity, or service-availability claims."
            ),
        },
        "reason_not_comparable": (
            "The synthetic pipeline's modeled-minute/coverage estimates and real-data straight-line "
            "distances use different inputs, units, and algorithms. They are shown side by side only."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-json", type=Path, required=True)
    parser.add_argument("--real-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New JSON path; a sibling Markdown report is created.")
    args = parser.parse_args()
    output = args.output.resolve()
    markdown = output.with_suffix(".md")
    if output.exists() or markdown.exists():
        raise FileExistsError(f"Refusing to overwrite comparison output: {output} or {markdown}")
    result = create_comparison(args.synthetic_json, args.real_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(
        "# Synthetic and real-data side-by-side comparison\n\n"
        f"- District: {result['synthetic']['district']}\n"
        "- Numerical metric comparison: **not performed**.\n"
        "- Equivalent measurements: **no**.\n\n"
        f"## Synthetic/demo\n\n{result['synthetic']['interpretation']}\n\n"
        f"## Real data\n\n{result['real']['interpretation']}\n\n"
        f"## Why the results are not directly comparable\n\n{result['reason_not_comparable']}\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "markdown": str(markdown)}, indent=2))


if __name__ == "__main__":
    main()
