#!/usr/bin/env python3
"""
Seed a minimal asset + policy + contract on the provider, then request a catalog
from the consumer Management API.

EDC 0.14.x minimal CP exposes Management API **v3** (v4 may be absent). Shapes follow:
  - CatalogApiEndToEndTest (v3 catalog)
  - PolicyDefinitionApiEndToEndTest / AssetApiEndToEndTest / ContractDefinitionApiEndToEndTest

DSP address: ManagementEndToEndTestContext.providerDsp2025url() -> <protocolBase>/2025-1

Requires: docker compose up. Uses stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
import urllib.error
import urllib.request
from typing import Any, Mapping

# CoreConstants / Dsp2025Constants (Connector SPI)
EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"
EDC_PREFIX = "edc"
DATASPACE_PROTOCOL_HTTP_V_2025_1 = "dataspace-protocol-http:2025-1"


def _post_json(url: str, body: Mapping[str, Any], method: str = "POST") -> tuple[int, Any]:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {raw[:4000]}") from e

    if not raw.strip():
        return code, None
    try:
        return code, json.loads(raw)
    except json.JSONDecodeError:
        return code, raw


def _extract_id(obj: Any) -> str:
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object, got {type(obj)}")
    for key in ("@id", "id"):
        if key in obj and obj[key]:
            return str(obj[key])
    raise ValueError(f"no @id/id in response: {obj!r}")


def _ctx_edc_prefix() -> dict[str, str]:
    return {EDC_PREFIX: EDC_NAMESPACE}


def _ctx_vocab() -> dict[str, str]:
    return {"@vocab": EDC_NAMESPACE}


def _policy_body_v3() -> dict[str, Any]:
    # PolicyDefinitionApiEndToEndTest.sampleOdrlPolicy()
    return {
        "@context": _ctx_vocab(),
        "@type": "PolicyDefinition",
        "policy": {
            "@context": "http://www.w3.org/ns/odrl.jsonld",
            "@type": "Set",
            "permission": [
                {
                    "target": "http://example.com/asset:9898.movie",
                    "action": "use",
                    "constraint": {
                        "leftOperand": "left",
                        "operator": "eq",
                        "rightOperand": "value",
                    },
                }
            ],
            "prohibition": [
                {
                    "target": "http://example.com/data:77",
                    "action": "index",
                    "remedy": {"action": "anonymize"},
                }
            ],
            "obligation": [
                {
                    "target": "http://example.com/data:77",
                    "action": "use",
                    "consequence": [{"action": "use"}, {"action": "anonymize"}],
                }
            ],
        },
    }


def _asset_body_v3(asset_id: str) -> dict[str, Any]:
    # AssetApiEndToEndTest — use HttpData for a realistic pull address
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "name": "catalog-demo-asset",
            "description": "Seeded for local catalog demo",
            "contenttype": "application/json",
            "version": "0.1.0",
            "isCatalog": "true",
        },
        "dataAddress": {
            "@type": "DataAddress",
            "type": "HttpData",
            "baseUrl": "https://httpbin.org/get",
        },
    }


def _contract_body_v3(
    definition_id: str, policy_id: str, asset_id: str
) -> dict[str, Any]:
    # ContractDefinitionApiEndToEndTest.createDefinitionBuilder + asset id criterion
    return {
        "@context": _ctx_vocab(),
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


def _catalog_request_body_v3(counter_party_address: str) -> dict[str, Any]:
    # CatalogApiEndToEndTest.requestCatalog_shouldReturnCatalog_withoutQuerySpec
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "CatalogRequest",
        "counterPartyId": "counter-party-id",
        "counterPartyAddress": counter_party_address,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="EDC catalog demo (consumer -> provider).")
    p.add_argument(
        "--consumer-mgmt",
        default="http://127.0.0.1:18181/api/management",
        help="Consumer Management API base URL (no /v3 suffix)",
    )
    p.add_argument(
        "--provider-mgmt",
        default="http://127.0.0.1:28181/api/management",
        help="Provider Management API base URL",
    )
    p.add_argument(
        "--provider-dsp",
        default="http://provider-cp:8282/api/protocol/2025-1",
        help=(
            "Provider DSP counterPartyAddress (protocol base + /2025-1). "
            "Must be reachable from the *consumer* connector process (Compose: use provider-cp:8282)."
        ),
    )
    p.add_argument(
        "--asset-id",
        default=None,
        help="Asset @id (default: random catalog-demo-<suffix>)",
    )
    p.add_argument(
        "--contract-id",
        default=None,
        help="ContractDefinition @id (default: random catalog-contract-<suffix>)",
    )
    args = p.parse_args()

    run_uid = uuid.uuid4().hex[:10]
    asset_id = args.asset_id or f"catalog-demo-{run_uid}"
    contract_id = args.contract_id or f"catalog-contract-{run_uid}"

    pm = args.provider_mgmt.rstrip("/")
    cm = args.consumer_mgmt.rstrip("/")
    ver = "v3"

    print("==> Creating policy definition on provider …")
    _, policy_resp = _post_json(f"{pm}/{ver}/policydefinitions", _policy_body_v3())
    policy_id = _extract_id(policy_resp)
    print(f"    policy id: {policy_id}")

    print("==> Creating asset on provider …")
    _, asset_resp = _post_json(f"{pm}/{ver}/assets", _asset_body_v3(asset_id))
    print(f"    asset id: {_extract_id(asset_resp)}")

    print("==> Creating contract definition on provider …")
    _, cd_resp = _post_json(
        f"{pm}/{ver}/contractdefinitions",
        _contract_body_v3(contract_id, policy_id, asset_id),
    )
    print(f"    contract definition id: {_extract_id(cd_resp)}")

    print("==> Requesting catalog from consumer …")
    cat_body = _catalog_request_body_v3(args.provider_dsp)
    _, cat = _post_json(f"{cm}/{ver}/catalog/request", cat_body)
    print(json.dumps(cat, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
