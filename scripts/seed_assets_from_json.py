#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Mapping

EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"
DATASPACE_PROTOCOL_HTTP_V_2025_1 = "dataspace-protocol-http:2025-1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to read JSON file {path}: {e}") from e


def _request_json(url: str, method: str, body: Mapping[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {raw[:3000]}") from e

    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _extract_id(obj: Any) -> str:
    if not isinstance(obj, dict):
        raise RuntimeError(f"Expected object response with id, got: {type(obj)}")
    for k in ("@id", "id"):
        if obj.get(k):
            return str(obj[k])
    raise RuntimeError(f"Response has no id field: {obj!r}")


def _policy_body() -> dict[str, Any]:
    return {
        "@context": {"@vocab": EDC_NAMESPACE},
        "@type": "PolicyDefinition",
        "policy": {"@context": "http://www.w3.org/ns/odrl.jsonld", "@type": "Set", "permission": []},
    }


def _contract_body(contract_id: str, policy_id: str, asset_id: str) -> dict[str, Any]:
    return {
        "@context": {"@vocab": EDC_NAMESPACE},
        "@type": EDC_NAMESPACE + "ContractDefinition",
        "@id": contract_id,
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


def _catalog_request(provider_dsp: str, counter_party_id: str) -> dict[str, Any]:
    return {
        "@context": {"edc": EDC_NAMESPACE},
        "@type": "CatalogRequest",
        "counterPartyId": counter_party_id,
        "counterPartyAddress": provider_dsp,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
    }


def _catalog_item_by_asset_id(catalog: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    items = catalog.get("dataset")
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("@id", "")) == asset_id or str(item.get("id", "")) == asset_id:
            return item
    return None


def _extract_aas_fields(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "aasShellId": obj.get("aasShellId") or obj.get("edc:aasShellId"),
        "aasSubmodelId": obj.get("aasSubmodelId") or obj.get("edc:aasSubmodelId"),
        "aasSemanticId": obj.get("aasSemanticId") or obj.get("edc:aasSemanticId"),
        "aasSubmodelEndpoint": obj.get("aasSubmodelEndpoint") or obj.get("edc:aasSubmodelEndpoint"),
    }


def _basyx_shell_exists(registry_base: str, shell_id: str) -> bool:
    shells = _request_json(f"{registry_base.rstrip('/')}/shells", "GET")
    items: list[dict[str, Any]] = []
    if isinstance(shells, list):
        items = [x for x in shells if isinstance(x, dict)]
    elif isinstance(shells, dict):
        result = shells.get("result")
        if isinstance(result, list):
            items = [x for x in result if isinstance(x, dict)]
    return any(str(it.get("id", "")) == shell_id for it in items)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed provider assets from JSON files and verify consumer metadata + optional BaSyx details."
    )
    parser.add_argument(
        "--asset-with-aas",
        default="templates/assets/provider_asset_with_aas.json",
        help="Path to provider asset JSON that contains aas* properties.",
    )
    parser.add_argument(
        "--asset-without-aas",
        default="templates/assets/provider_asset_without_aas.json",
        help="Path to provider asset JSON that does not contain aas* properties.",
    )
    parser.add_argument(
        "--shell-json",
        default="templates/aas/sample_shell.json",
        help="Optional BaSyx shell JSON path. Pass empty string to skip shell registration.",
    )
    parser.add_argument("--provider-mgmt", default="http://127.0.0.1:28181/api/management")
    parser.add_argument("--consumer-mgmt", default="http://127.0.0.1:18181/api/management")
    parser.add_argument("--provider-dsp", default="http://provider-cp:8282/api/protocol/2025-1")
    parser.add_argument("--counter-party-id", default="counter-party-id")
    parser.add_argument("--aas-registry-base", default="http://127.0.0.1:38081")
    parser.add_argument(
        "--run-suffix",
        default=uuid.uuid4().hex[:8],
        help="Suffix appended to asset ids (and linked shell ids) to avoid collisions on repeated runs.",
    )
    args = parser.parse_args()

    pm = args.provider_mgmt.rstrip("/")
    cm = args.consumer_mgmt.rstrip("/")
    registry_base = args.aas_registry_base.rstrip("/")

    with_aas = _read_json(Path(args.asset_with_aas))
    without_aas = _read_json(Path(args.asset_without_aas))
    shell_json: dict[str, Any] | None = None
    if args.shell_json.strip():
        shell_json = _read_json(Path(args.shell_json))

    # Make demo re-runnable without duplicate-id conflicts.
    with_aas_id = f"{str(with_aas.get('@id') or 'asset-with-aas')}-{args.run_suffix}"
    without_aas_id = f"{str(without_aas.get('@id') or 'asset-without-aas')}-{args.run_suffix}"
    with_aas["@id"] = with_aas_id
    without_aas["@id"] = without_aas_id

    if shell_json is not None and isinstance(shell_json.get("id"), str):
        shell_json["id"] = f"{shell_json['id']}-{args.run_suffix}"
    props_with_aas = with_aas.get("properties")
    if isinstance(props_with_aas, dict) and isinstance(shell_json, dict) and isinstance(shell_json.get("id"), str):
        props_with_aas["aasShellId"] = shell_json["id"]

    print("==> Creating one provider policy (reused for both assets)")
    policy_resp = _request_json(f"{pm}/v3/policydefinitions", "POST", _policy_body())
    policy_id = _extract_id(policy_resp)
    print(f"    policyId={policy_id}")

    if shell_json is not None:
        print("==> Registering shell in BaSyx")
        _request_json(f"{registry_base}/shells", "POST", shell_json)
        print(f"    shellId={shell_json.get('id')}")

    for idx, asset in enumerate([with_aas, without_aas], start=1):
        asset_id = str(asset.get("@id") or f"asset-json-{idx}-{uuid.uuid4().hex[:8]}")
        print(f"==> Creating provider asset ({idx}/2): {asset_id}")
        asset_resp = _request_json(f"{pm}/v3/assets", "POST", asset)
        print(f"    createdAssetId={_extract_id(asset_resp)}")

        contract_id = f"contract-json-{uuid.uuid4().hex[:8]}"
        _request_json(f"{pm}/v3/contractdefinitions", "POST", _contract_body(contract_id, policy_id, asset_id))
        print(f"    contractDefinitionId={contract_id}")

    print("==> Requesting consumer catalog once")
    catalog = _request_json(
        f"{cm}/v3/catalog/request",
        "POST",
        _catalog_request(args.provider_dsp, args.counter_party_id),
    )
    if not isinstance(catalog, dict):
        raise RuntimeError(f"Unexpected catalog response type: {type(catalog)}")

    result: dict[str, Any] = {"assets": []}
    for asset in [with_aas, without_aas]:
        aid = str(asset["@id"])
        catalog_item = _catalog_item_by_asset_id(catalog, aid) or {}
        cat_fields = _extract_aas_fields(catalog_item) if isinstance(catalog_item, dict) else {}
        dataset = _request_json(
            f"{cm}/v3/catalog/dataset/request",
            "POST",
            _dataset_request(aid, args.provider_dsp, args.counter_party_id),
        )
        if not isinstance(dataset, dict):
            raise RuntimeError(f"Unexpected dataset response for {aid}: {type(dataset)}")
        ds_fields = _extract_aas_fields(dataset)
        props = dataset.get("properties") if isinstance(dataset.get("properties"), dict) else {}
        if isinstance(props, dict):
            # Some EDC variants carry custom metadata under properties for dataset responses.
            ds_fields = {k: (ds_fields.get(k) or props.get(k)) for k in ds_fields.keys()}
        entry = {
            "assetId": aid,
            "consumerCatalogHasAasMetadata": bool(cat_fields.get("aasShellId") or cat_fields.get("aasSubmodelId") or cat_fields.get("aasSemanticId")),
            "consumerDatasetHasAasMetadata": bool(ds_fields.get("aasShellId") or ds_fields.get("aasSubmodelId") or ds_fields.get("aasSemanticId")),
            "catalogAasFields": cat_fields,
            "datasetAasFields": ds_fields,
        }
        result["assets"].append(entry)

    if shell_json is not None and isinstance(shell_json.get("id"), str):
        sid = str(shell_json["id"])
        result["basyxShellResolvable"] = _basyx_shell_exists(registry_base, sid)
        result["basyxShellId"] = sid

    print("==> Verification result")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
