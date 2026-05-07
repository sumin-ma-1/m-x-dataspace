from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
from pyshacl import validate


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
    # CSV example: "2013-01-02 01:44:17 347:000:000"
    # We keep only the leading "%Y-%m-%d %H:%M:%S".
    s = s.strip()
    if len(s) < 19:
        raise ValueError(f"TIME too short: {s!r}")
    base = s[:19]
    dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
    return dt.isoformat()


def _decimal(s: str) -> Literal:
    return Literal(s.strip(), datatype=XSD.decimal)


def _read_rows(path: Path, max_rows: int) -> Iterable[Row]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        required = [
            "TIME",
            "id",
            "CNC cutting conditions-S",
            "CNC cutting conditions-F",
            "X tool position",
            "Y tool position",
            "Z tool position",
            "spindle motor-U CT",
            "spindle motor-V CT",
            "label",
        ]
        if not r.fieldnames or any(c not in r.fieldnames for c in required):
            raise ValueError(f"Unexpected headers. Expected at least: {required}. Got: {r.fieldnames}")

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


def rows_to_rdf(rows: Iterable[Row]) -> Graph:
    g = Graph()
    g.bind("ex", EX)

    for idx, r in enumerate(rows, start=1):
        subj = URIRef(f"{EX}record/{idx}")
        g.add((subj, RDF.type, EX.OperationRecord))

        g.add((subj, EX.time, Literal(_parse_time_to_xsd_datetime(r.time), datatype=XSD.dateTime)))
        g.add((subj, EX.operationId, Literal(r.operation_id.strip(), datatype=XSD.string)))

        g.add((subj, EX.controlS, _decimal(r.control_s)))
        g.add((subj, EX.controlF, _decimal(r.control_f)))
        g.add((subj, EX.toolPosX, _decimal(r.x)))
        g.add((subj, EX.toolPosY, _decimal(r.y)))
        g.add((subj, EX.toolPosZ, _decimal(r.z)))
        g.add((subj, EX.spindleCurrentU, _decimal(r.current_u)))
        g.add((subj, EX.spindleCurrentV, _decimal(r.current_v)))
        g.add((subj, EX.statusLabel, Literal(r.label.strip(), datatype=XSD.string)))

    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--shapes", required=True)
    ap.add_argument("--max-rows", type=int, default=20000)
    args = ap.parse_args()

    csv_path = Path(args.csv)
    shapes_path = Path(args.shapes)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not shapes_path.exists():
        raise SystemExit(f"Shapes not found: {shapes_path}")

    rows = list(_read_rows(csv_path, args.max_rows))
    data_graph = rows_to_rdf(rows)
    shapes_graph = Graph().parse(shapes_path, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        meta_shacl=False,
        advanced=False,
        debug=False,
    )

    print(f"rows={len(rows)} conforms={conforms}")
    print(report_text)
    return 0 if conforms else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)

