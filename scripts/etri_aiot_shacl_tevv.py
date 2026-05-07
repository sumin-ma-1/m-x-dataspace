from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

EX = Namespace("urn:mx:etri-aiot:")


@dataclass(frozen=True)
class Row:
    time: str
    operation_id: str
    control_s: str
    control_f: str
    x: str
    y: str
    z: str
    current_u: str
    current_v: str
    label: str


def _parse_time_to_xsd_datetime(s: str) -> str:
    s = s.strip()
    if len(s) < 19:
        raise ValueError(f"TIME too short: {s!r}")
    base = s[:19]
    dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
    return dt.isoformat()


def _read_rows(path: Path, max_rows: int) -> Iterable[Row]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=1):
            if max_rows > 0 and i > max_rows:
                break
            yield Row(
                time=row["TIME"],
                operation_id=row["id"],
                control_s=row["CNC cutting conditions-S"],
                control_f=row["CNC cutting conditions-F"],
                x=row["X tool position"],
                y=row["Y tool position"],
                z=row["Z tool position"],
                current_u=row["spindle motor-U CT"],
                current_v=row["spindle motor-V CT"],
                label=row["label"],
            )


def _single_row_graph(row: Row, idx: int, mode: str) -> Graph:
    g = Graph()
    subj = URIRef(f"{EX}case/{idx}")
    g.add((subj, RDF.type, EX.OperationRecord))

    # time
    if mode == "bad_time_type":
        g.add((subj, EX.time, Literal(row.time, datatype=XSD.string)))
    else:
        g.add((subj, EX.time, Literal(_parse_time_to_xsd_datetime(row.time), datatype=XSD.dateTime)))

    g.add((subj, EX.operationId, Literal(row.operation_id.strip(), datatype=XSD.string)))

    # numeric fields
    control_s = row.control_s
    tool_x = row.x
    status = row.label

    if mode == "controlS_out_of_range":
        control_s = "999999.0"
    if mode == "toolX_out_of_range":
        tool_x = "-9999.0"
    if mode == "status_unknown":
        status = "999"

    g.add((subj, EX.controlS, Literal(control_s, datatype=XSD.decimal)))
    g.add((subj, EX.controlF, Literal(row.control_f, datatype=XSD.decimal)))
    g.add((subj, EX.toolPosX, Literal(tool_x, datatype=XSD.decimal)))
    g.add((subj, EX.toolPosY, Literal(row.y, datatype=XSD.decimal)))
    g.add((subj, EX.toolPosZ, Literal(row.z, datatype=XSD.decimal)))
    g.add((subj, EX.spindleCurrentU, Literal(row.current_u, datatype=XSD.decimal)))
    if mode != "missing_spindle_v":
        g.add((subj, EX.spindleCurrentV, Literal(row.current_v, datatype=XSD.decimal)))
    g.add((subj, EX.statusLabel, Literal(status, datatype=XSD.string)))
    return g


def _validate_case(data_graph: Graph, shapes_graph: Graph) -> bool:
    conforms, _, _ = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        meta_shacl=False,
        advanced=False,
        debug=False,
    )
    return bool(conforms)


def _calc_metrics(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    total = tp + fp + fn + tn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="TEVV for SHACL conformance classifier on ETRI AIoT rows")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--shapes", required=True)
    ap.add_argument("--base-rows", type=int, default=400, help="number of clean rows to sample")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    csv_path = Path(args.csv)
    shapes_path = Path(args.shapes)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not shapes_path.exists():
        raise SystemExit(f"Shapes not found: {shapes_path}")

    rows = list(_read_rows(csv_path, max_rows=max(args.base_rows * 3, 1000)))
    rnd = random.Random(args.seed)
    rnd.shuffle(rows)
    rows = rows[: args.base_rows]
    shapes_graph = Graph().parse(shapes_path, format="turtle")

    tp = fp = fn = tn = 0
    # Positive class = "non-conformant" (violation detected)
    idx = 0
    for row in rows:
        idx += 1
        pred_conforms = _validate_case(_single_row_graph(row, idx, mode="clean"), shapes_graph)
        pred_violation = not pred_conforms
        actual_violation = False
        if pred_violation and actual_violation:
            tp += 1
        elif pred_violation and not actual_violation:
            fp += 1
        elif (not pred_violation) and actual_violation:
            fn += 1
        else:
            tn += 1

    bad_modes = [
        "status_unknown",
        "controlS_out_of_range",
        "toolX_out_of_range",
        "bad_time_type",
        "missing_spindle_v",
    ]
    for row in rows:
        for mode in bad_modes:
            idx += 1
            pred_conforms = _validate_case(_single_row_graph(row, idx, mode=mode), shapes_graph)
            pred_violation = not pred_conforms
            actual_violation = True
            if pred_violation and actual_violation:
                tp += 1
            elif pred_violation and not actual_violation:
                fp += 1
            elif (not pred_violation) and actual_violation:
                fn += 1
            else:
                tn += 1

    metrics = _calc_metrics(tp, fp, fn, tn)
    total = tp + fp + fn + tn
    print(f"cases={total} positives(non-conformant)={tp+fn} negatives(conformant)={tn+fp}")
    print(f"confusion_matrix: TP={tp} FP={fp} FN={fn} TN={tn}")
    print(
        "metrics: "
        + ", ".join([f"{k}={v:.4f}" for k, v in metrics.items()])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

