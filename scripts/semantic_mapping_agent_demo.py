from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "catena-x-sw-sample"))

from app.semantic_mapping import (
    build_aas_submodel_draft,
    infer_mappings,
    read_csv_header,
    required_fields_coverage,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--submodel-id", default="urn:uuid:etri-aiot-submodel-draft")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    cols = read_csv_header(str(csv_path))
    mappings = infer_mappings(cols)
    coverage = required_fields_coverage(mappings)
    aas = build_aas_submodel_draft(mappings, submodel_id=args.submodel_id)

    print(
        json.dumps(
            {
                "columns": cols,
                "coverage": coverage,
                "mappings": mappings,
                "aas_submodel_draft": aas,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

