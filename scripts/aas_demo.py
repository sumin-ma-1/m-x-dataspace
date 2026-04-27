#!/usr/bin/env python3
"""
AAS + EDC integration demo (separate script).

What this script demonstrates:
  1) Create a provider-side EDC asset that carries AAS metadata
     (AAS shell ID, submodel ID, semantic ID, submodel endpoint URL).
  2) Create policy + contract definition for that asset.
  3) Request catalog/dataset from consumer and verify AAS metadata is discoverable.

Why this shape:
  - IDTA AAS spec defines standardized digital twin semantics/APIs (IDTA-01001/01002).
  - Catena-X CX-0002/CX-0003 emphasizes discovery + semantics via Digital Twin patterns.
  - This script keeps runtime dependencies minimal (stdlib only) and plugs into the
    current local EDC stack immediately.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
import urllib.error
import urllib.request
from typing import Any, Mapping

EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"
DATASPACE_PROTOCOL_HTTP_V_2025_1 = "dataspace-protocol-http:2025-1"


def _post_json(url: str, body: Mapping[str, Any], method: str = "POST") -> Any:
    req = urllib.request.Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {raw[:3000]}") from e

    if not raw.strip():
        return None
    return json.loads(raw)


def _extract_id(obj: Any) -> str:
    if not isinstance(obj, dict):
        raise RuntimeError(f"Expected JSON object, got: {type(obj)}")
    for key in ("@id", "id"):
        if obj.get(key):
            return str(obj[key])
    raise RuntimeError(f"No id field in response: {obj!r}")


def _policy_body() -> dict[str, Any]:
    return {
        "@context": {"@vocab": EDC_NAMESPACE},
        "@type": "PolicyDefinition",
        "policy": {"@context": "http://www.w3.org/ns/odrl.jsonld", "@type": "Set", "permission": []},
    }


def _asset_body(
    asset_id: str,
    *,
    shell_id: str,
    submodel_id: str,
    semantic_id: str,
    submodel_endpoint: str,
) -> dict[str, Any]:
    return {
        "@context": {"edc": EDC_NAMESPACE},
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "name": "aas-linked-asset",
            "description": "EDC asset carrying AAS shell/submodel metadata",
            "contenttype": "application/json",
            "version": "0.1.0",
            "aasShellId": shell_id,
            "aasSubmodelId": submodel_id,
            "aasSemanticId": semantic_id,
            "aasSubmodelEndpoint": submodel_endpoint,
        },
        "dataAddress": {
            "@type": "DataAddress",
            "type": "HttpData",
            "baseUrl": submodel_endpoint,
        },
    }


def _contract_body(definition_id: str, policy_id: str, asset_id: str) -> dict[str, Any]:
    return {
        "@context": {"@vocab": EDC_NAMESPACE},
        "@type": EDC_NAMESPACE + "ContractDefinition",
        "@id": definition_id,
        "accessPolicyId": policy_id,
        "contractPolicyId": policy_id,
        "assetsSelector": [
            {
                "@type": "Criterion",
                "operandLeft": EDC_NAMESPACE + "id",
                "operator": "=",
                "operandRight": asset_id,
            }
        ],
    }


def _dataset_request(asset_id: str, provider_dsp: str, counter_party_id: str) -> dict[str, Any]:
    return {
        "@context": {"edc": EDC_NAMESPACE},
        "@type": "DatasetRequest",
        "@id": asset_id,
        "counterPartyId": counter_party_id,
        "counterPartyAddress": provider_dsp,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AAS + EDC metadata integration demo.")
    parser.add_argument("--provider-mgmt", default="http://127.0.0.1:28181/api/management")
    parser.add_argument("--consumer-mgmt", default="http://127.0.0.1:18181/api/management")
    parser.add_argument("--provider-dsp", default="http://provider-cp:8282/api/protocol/2025-1")
    parser.add_argument("--counter-party-id", default="counter-party-id")
    parser.add_argument(
        "--aas-shell-id",
        default="urn:uuid:" + str(uuid.uuid4()),
        help="AAS Shell identifier (IRI/URN recommended by AAS conventions).",
    )
    parser.add_argument(
        "--aas-submodel-id",
        default="urn:uuid:" + str(uuid.uuid4()),
        help="AAS Submodel identifier.",
    )
    parser.add_argument(
        "--aas-semantic-id",
        default="urn:samm:com.example:DemandForecast:1.0.0",
        help="Semantic ID (e.g. SAMM/IDTA aligned semantic reference).",
    )
    parser.add_argument(
        "--aas-submodel-endpoint",
        default="https://httpbin.org/get",
        help="HTTP endpoint exposed by submodel service/repository.",
    )
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:10]
    asset_id = f"aas-asset-{run_id}"
    contract_id = f"aas-contract-{run_id}"
    pm = args.provider_mgmt.rstrip("/")
    cm = args.consumer_mgmt.rstrip("/")

    print("==> Creating provider policy")
    policy_resp = _post_json(f"{pm}/v3/policydefinitions", _policy_body())
    policy_id = _extract_id(policy_resp)
    print(f"    policyId={policy_id}")

    print("==> Creating provider asset with AAS metadata")
    asset_resp = _post_json(
        f"{pm}/v3/assets",
        _asset_body(
            asset_id,
            shell_id=args.aas_shell_id,
            submodel_id=args.aas_submodel_id,
            semantic_id=args.aas_semantic_id,
            submodel_endpoint=args.aas_submodel_endpoint,
        ),
    )
    print(f"    assetId={_extract_id(asset_resp)}")

    print("==> Creating provider contract definition")
    contract_resp = _post_json(
        f"{pm}/v3/contractdefinitions",
        _contract_body(contract_id, policy_id, asset_id),
    )
    print(f"    contractDefinitionId={_extract_id(contract_resp)}")

    print("==> Requesting consumer dataset for AAS-linked asset")
    dataset = _post_json(
        f"{cm}/v3/catalog/dataset/request",
        _dataset_request(asset_id, args.provider_dsp, args.counter_party_id),
    )
    if not isinstance(dataset, dict):
        raise RuntimeError(f"Unexpected dataset response type: {type(dataset)}")

    props = dataset.get("properties", {})
    result = {
        "assetId": asset_id,
        "datasetType": dataset.get("@type") or dataset.get("type"),
        "aasShellId": props.get("aasShellId"),
        "aasSubmodelId": props.get("aasSubmodelId"),
        "aasSemanticId": props.get("aasSemanticId"),
        "aasSubmodelEndpoint": props.get("aasSubmodelEndpoint"),
    }
    print("==> AAS metadata visibility check")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
