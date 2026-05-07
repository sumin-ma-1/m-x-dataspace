from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    return set(_norm(s).split())


@dataclass(frozen=True)
class TargetDef:
    target_path: str
    aliases: tuple[str, ...]
    required: bool = True


TARGETS: dict[str, TargetDef] = {
    "time": TargetDef("record.time", ("time", "timestamp", "datetime")),
    "operationId": TargetDef("record.operationId", ("id", "operation id", "record id")),
    "controlS": TargetDef("cuttingCondition.S", ("cnc cutting conditions s", "control s", "s")),
    "controlF": TargetDef("cuttingCondition.F", ("cnc cutting conditions f", "control f", "f")),
    "toolPosX": TargetDef("toolPosition.X", ("x tool position", "tool x", "x position")),
    "toolPosY": TargetDef("toolPosition.Y", ("y tool position", "tool y", "y position")),
    "toolPosZ": TargetDef("toolPosition.Z", ("z tool position", "tool z", "z position")),
    "spindleCurrentU": TargetDef(
        "spindleMotor.currentU",
        ("spindle motor u ct", "spindle current u", "motor current u"),
    ),
    "spindleCurrentV": TargetDef(
        "spindleMotor.currentV",
        ("spindle motor v ct", "spindle current v", "motor current v"),
    ),
    "statusLabel": TargetDef(
        "operationStatus.label",
        ("label", "operation status classification", "status"),
    ),
}


def _score(col: str, target: TargetDef) -> tuple[float, str]:
    c = _norm(col)
    # Exact normalized alias match
    for a in target.aliases:
        if c == _norm(a):
            return 1.0, "exact alias match"

    c_tokens = _tokens(c)
    best = 0.0
    best_alias = ""
    for a in target.aliases:
        a_tokens = _tokens(a)
        if not a_tokens:
            continue
        jacc = len(c_tokens & a_tokens) / len(c_tokens | a_tokens)
        if jacc > best:
            best = jacc
            best_alias = a
    if best > 0:
        return round(best, 4), f"token overlap with alias '{best_alias}'"
    return 0.0, "no overlap"


def infer_mappings(columns: list[str]) -> list[dict[str, Any]]:
    used_targets: set[str] = set()
    results: list[dict[str, Any]] = []

    for col in columns:
        best_key = None
        best_score = -1.0
        best_rationale = ""
        for key, t in TARGETS.items():
            if key in used_targets:
                continue
            s, why = _score(col, t)
            if s > best_score:
                best_score = s
                best_key = key
                best_rationale = why

        if best_key is None:
            continue

        target = TARGETS[best_key]
        used_targets.add(best_key)
        results.append(
            {
                "sourceColumn": col,
                "canonicalField": best_key,
                "targetPath": target.target_path,
                "confidence": max(best_score, 0.0),
                "required": target.required,
                "rationale": best_rationale,
            }
        )

    # Sort high-confidence first for UI readability
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


def required_fields_coverage(mappings: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = {m["canonicalField"] for m in mappings}
    required = {k for k, v in TARGETS.items() if v.required}
    missing = sorted(required - mapped)
    return {
        "requiredTotal": len(required),
        "requiredMapped": len(required) - len(missing),
        "missingRequired": missing,
        "isReadyForDraft": len(missing) == 0,
    }


def build_aas_submodel_draft(
    mappings: list[dict[str, Any]],
    *,
    submodel_id: str,
    id_short: str = "MachiningConditionMonitoring",
    semantic_id: str = "urn:samm:mx:MachiningConditionMonitoring:1.0.0",
) -> dict[str, Any]:
    # Lightweight AAS-like draft (sufficient for UI preview / next-step conversion).
    elems: list[dict[str, Any]] = []
    for m in mappings:
        elems.append(
            {
                "idShort": m["canonicalField"],
                "modelType": "Property",
                "valueType": "string",
                "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": m["targetPath"]}]},
                "qualifiers": [
                    {"type": "sourceColumn", "valueType": "string", "value": m["sourceColumn"]},
                    {"type": "mappingConfidence", "valueType": "string", "value": str(m["confidence"])},
                ],
            }
        )

    return {
        "id": submodel_id,
        "idShort": id_short,
        "kind": "Instance",
        "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": semantic_id}]},
        "submodelElements": elems,
    }


def read_csv_header(csv_path: str) -> list[str]:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        try:
            header = next(r)
        except StopIteration:
            return []
    return [h.strip() for h in header]

