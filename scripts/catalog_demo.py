#!/usr/bin/env python3
"""
Local EDC demo: seed provider, catalog peek, contract negotiation, then **data transfer**
via Management API v3 (0.14.x).

References (Eclipse EDC Connector):
  - Participant.initContractNegotiation / initiateTransfer / awaitTransferToBeInState
    — management-api-test-fixtures
  - CatalogApiEndToEndTest — DatasetRequest
  - ContractNegotiationApiV3 — ContractRequest
  - TransferProcessApiV3 / TransferProcessApiEndToEndTest — TransferRequest + POST .../transferprocesses
  - TransferRequestValidator — protocol, contractId, counterPartyAddress, transferType, dataDestination

Requires: docker compose up (consumer + provider). Uses stdlib only.

Notes:
  - Negotiation assets must not set isCatalog (see dataset/hasPolicy note in repo README).
  - TransferRequest `dataDestination` for HttpData uses nested `properties.baseUrl` (see TransferProcessApiEndToEndTest).
  - Default transfer type is taken from the dataset distribution (e.g. HttpData-PULL).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from typing import Any, Mapping

EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"
EDC_PREFIX = "edc"
DATASPACE_PROTOCOL_HTTP_V_2025_1 = "dataspace-protocol-http:2025-1"
ODRL_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"


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


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else None


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
    return {
        "@context": _ctx_vocab(),
        "@type": "PolicyDefinition",
        "policy": {
            "@context": ODRL_CONTEXT,
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


def _negotiation_asset_body_v3(asset_id: str) -> dict[str, Any]:
    """Asset + contract path for negotiation (no isCatalog — required for hasPolicy on dataset)."""
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "name": "trade-demo-asset",
            "description": "Seeded for catalog_demo negotiation",
            "contenttype": "application/json",
            "version": "0.1.0",
        },
        "dataAddress": {
            "@type": "DataAddress",
            "type": "HttpData",
            "baseUrl": "https://httpbin.org/get",
        },
    }


def _catalog_only_asset_body_v3(asset_id: str) -> dict[str, Any]:
    """Optional second asset that appears as a nested Catalog entry (catalog UX only)."""
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "name": "catalog-demo-asset",
            "description": "Catalog-only row (isCatalog)",
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


def _catalog_request_body_v3(counter_party_address: str, counter_party_id: str) -> dict[str, Any]:
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "CatalogRequest",
        "counterPartyId": counter_party_id,
        "counterPartyAddress": counter_party_address,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
    }


def _dataset_request_body_v3(
    asset_id: str, counter_party_address: str, counter_party_id: str
) -> dict[str, Any]:
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "DatasetRequest",
        "@id": asset_id,
        "counterPartyId": counter_party_id,
        "counterPartyAddress": counter_party_address,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
    }


def _first_has_policy(dataset: dict[str, Any]) -> dict[str, Any]:
    hp = dataset.get("hasPolicy") or dataset.get(
        "http://www.w3.org/ns/odrl/2/hasPolicy"
    )
    if hp is None:
        raise RuntimeError(
            "Dataset has no hasPolicy; use a non-catalog asset with a contract definition."
        )
    if isinstance(hp, list):
        if not hp:
            raise RuntimeError("Dataset hasPolicy is empty")
        first = hp[0]
    else:
        first = hp
    if not isinstance(first, dict):
        raise RuntimeError(f"Unexpected hasPolicy entry type: {type(first)}")
    return first


def _offer_policy_for_contract_request(
    offer: dict[str, Any], asset_id: str, provider_participant_id: str
) -> dict[str, Any]:
    """Mirror Participant.getOfferForAsset: ODRL Offer + assigner + target (@id objects)."""
    pol = copy.deepcopy(offer)
    if "@context" not in pol:
        pol["@context"] = ODRL_CONTEXT
    pol["assigner"] = {"@id": provider_participant_id}
    pol["target"] = {"@id": asset_id}
    return pol


def _contract_request_body(
    provider_dsp: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    # ContractNegotiationApiV3 example + working compact form (edc context, not @vocab-only).
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "ContractRequest",
        "counterPartyAddress": provider_dsp,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
        "policy": policy,
    }


def _default_transfer_type(dataset: dict[str, Any]) -> str:
    """
    Pick a transfer type from dataset distributions.
    Prefer **PUSH** for local Docker demos (consumer supplies sink URL; provider DP pushes),
    then PULL; default HttpData-PUSH (TransferProcessApiEndToEndTest style).
    """
    dists = dataset.get("distribution") or []
    push: str | None = None
    pull: str | None = None
    for d in dists:
        if not isinstance(d, dict):
            continue
        fmt = d.get("format")
        if not fmt:
            continue
        fs = str(fmt).upper()
        if "PUSH" in fs:
            push = str(fmt)
        if "PULL" in fs:
            pull = str(fmt)
    if push:
        return push
    if pull:
        return pull
    return "HttpData-PUSH"


def _transfer_request_body_v3(
    *,
    contract_agreement_id: str,
    provider_dsp: str,
    transfer_type: str,
    sink_base_url: str,
) -> dict[str, Any]:
    # TransferProcessApiEndToEndTest#create — dataDestination uses properties.baseUrl.
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "TransferRequest",
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
        "counterPartyAddress": provider_dsp,
        "contractId": contract_agreement_id,
        "transferType": transfer_type,
        "dataDestination": {
            "@type": "DataAddress",
            "type": "HttpData",
            "properties": {
                "baseUrl": sink_base_url,
            },
        },
    }


def _wait_transfer_state(
    consumer_mgmt: str,
    transfer_id: str,
    wanted: str,
    timeout_sec: int,
) -> dict[str, Any]:
    base = consumer_mgmt.rstrip("/") + "/v3/transferprocesses/" + transfer_id + "/state"
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _get_json(base)  # type: ignore[assignment]
        if not isinstance(last, dict):
            raise RuntimeError(f"unexpected transfer state payload: {last!r}")
        state = last.get("state")
        if state == wanted:
            return last
        if state in ("TERMINATED", "ERROR"):
            raise RuntimeError(
                f"transfer ended in state {state}: {json.dumps(last)[:2000]}"
            )
        time.sleep(0.5)
    raise RuntimeError(
        f"transfer {transfer_id} not {wanted} within {timeout_sec}s; last={json.dumps(last)[:1500]}"
    )


def _wait_negotiation_finalized(
    consumer_mgmt: str, negotiation_id: str, timeout_sec: int
) -> dict[str, Any]:
    base = consumer_mgmt.rstrip("/") + "/v3/contractnegotiations/" + negotiation_id
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _get_json(base)  # type: ignore[assignment]
        if not isinstance(last, dict):
            raise RuntimeError(f"unexpected negotiation payload: {last!r}")
        state = last.get("state")
        if state == "FINALIZED":
            return last
        if state in ("TERMINATED", "ERROR"):
            raise RuntimeError(f"negotiation ended in state {state}: {json.dumps(last)[:2000]}")
        time.sleep(0.5)
    raise RuntimeError(
        f"negotiation {negotiation_id} not FINALIZED within {timeout_sec}s; last={json.dumps(last)[:1500]}"
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="EDC catalog + contract negotiation + transfer demo (consumer -> provider)."
    )
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
        help="Provider DSP URL (from consumer CP network namespace).",
    )
    p.add_argument(
        "--counter-party-id",
        default="counter-party-id",
        help="counterPartyId for Catalog/Dataset requests (see CatalogApiEndToEndTest).",
    )
    p.add_argument(
        "--provider-participant-id",
        default="anonymous",
        help="odrl:assigner @id for ContractRequest.policy (matches catalog participantId).",
    )
    p.add_argument(
        "--negotiation-timeout",
        type=int,
        default=120,
        help="Seconds to wait for negotiation FINALIZED.",
    )
    p.add_argument(
        "--asset-id",
        default=None,
        help="Negotiation asset @id (default: random trade-demo-<suffix>).",
    )
    p.add_argument(
        "--contract-id",
        default=None,
        help="ContractDefinition @id (default: random trade-contract-<suffix>).",
    )
    p.add_argument(
        "--skip-catalog-entry",
        action="store_true",
        help="Do not create an extra isCatalog asset for nested catalog rows.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full catalog JSON (can be large).",
    )
    p.add_argument(
        "--skip-transfer",
        action="store_true",
        help="Stop after contract negotiation (no TransferRequest).",
    )
    p.add_argument(
        "--sink-base-url",
        default="https://httpbin.org/post",
        help="HttpData dataDestination.properties.baseUrl (consumer sink for PULL).",
    )
    p.add_argument(
        "--transfer-type",
        default=None,
        help="Override transferType (default: prefer PUSH from dataset, else HttpData-PUSH).",
    )
    p.add_argument(
        "--transfer-success-state",
        default="COMPLETED",
        help="Poll transfer /state until this state (e.g. COMPLETED or STARTED).",
    )
    p.add_argument(
        "--transfer-timeout",
        type=int,
        default=180,
        help="Seconds to wait for transfer state.",
    )
    args = p.parse_args()

    run_uid = uuid.uuid4().hex[:10]
    trade_asset_id = args.asset_id or f"trade-demo-{run_uid}"
    contract_def_id = args.contract_id or f"trade-contract-{run_uid}"
    catalog_row_id = f"catalog-row-{run_uid}"

    pm = args.provider_mgmt.rstrip("/")
    cm = args.consumer_mgmt.rstrip("/")
    ver = "v3"

    print("==> Creating policy definition on provider …")
    _, policy_resp = _post_json(f"{pm}/{ver}/policydefinitions", _policy_body_v3())
    policy_id = _extract_id(policy_resp)
    print(f"    policy id: {policy_id}")

    print("==> Creating negotiation asset on provider …")
    _, asset_resp = _post_json(
        f"{pm}/{ver}/assets", _negotiation_asset_body_v3(trade_asset_id)
    )
    print(f"    asset id: {_extract_id(asset_resp)}")

    if not args.skip_catalog_entry:
        print("==> Creating optional catalog-only asset (isCatalog) …")
        try:
            _post_json(f"{pm}/{ver}/assets", _catalog_only_asset_body_v3(catalog_row_id))
            print(f"    catalog row asset id: {catalog_row_id}")
        except RuntimeError as e:
            print(f"    (skipped catalog row due to error: {e})")

    print("==> Creating contract definition on provider …")
    _, cd_resp = _post_json(
        f"{pm}/{ver}/contractdefinitions",
        _contract_body_v3(contract_def_id, policy_id, trade_asset_id),
    )
    print(f"    contract definition id: {_extract_id(cd_resp)}")

    print("==> Requesting catalog from consumer (summary) …")
    cat_body = _catalog_request_body_v3(args.provider_dsp, args.counter_party_id)
    _, cat = _post_json(f"{cm}/{ver}/catalog/request", cat_body)
    if args.verbose:
        print(json.dumps(cat, indent=2, ensure_ascii=False))
    else:
        catalog = cat.get("catalog", []) if isinstance(cat, dict) else []
        ids = [
            (e.get("@id") or e.get("id") or "?")
            for e in catalog
            if isinstance(e, dict)
        ]
        print(f"    catalog entries: {len(ids)} (ids: {', '.join(ids[:8])}{'…' if len(ids) > 8 else ''})")

    print("==> Fetching dataset (offer) for negotiation asset …")
    ds_body = _dataset_request_body_v3(
        trade_asset_id, args.provider_dsp, args.counter_party_id
    )
    _, dataset = _post_json(f"{cm}/{ver}/catalog/dataset/request", ds_body)
    if not isinstance(dataset, dict):
        raise RuntimeError(f"unexpected dataset response: {dataset!r}")
    dtype = dataset.get("@type") or dataset.get("type")
    print(f"    dataset @type: {dtype}")
    offer = _first_has_policy(dataset)
    policy = _offer_policy_for_contract_request(
        offer, trade_asset_id, args.provider_participant_id
    )

    print("==> Initiating contract negotiation on consumer …")
    cr_body = _contract_request_body(args.provider_dsp, policy)
    _, neg_init = _post_json(f"{cm}/{ver}/contractnegotiations", cr_body)
    neg_id = _extract_id(neg_init)
    print(f"    negotiation id: {neg_id}")

    print("==> Waiting for FINALIZED …")
    final = _wait_negotiation_finalized(cm, neg_id, args.negotiation_timeout)
    agreement_id = final.get("contractAgreementId")
    if not agreement_id:
        raise RuntimeError("negotiation FINALIZED but contractAgreementId is missing")

    result: dict[str, Any] = {
        "negotiationId": neg_id,
        "negotiationState": final.get("state"),
        "contractAgreementId": agreement_id,
        "assetId": trade_asset_id,
    }

    if not args.skip_transfer:
        xfer_type = args.transfer_type or _default_transfer_type(dataset)
        print(f"==> Initiating transfer (type={xfer_type}) …")
        tr_body = _transfer_request_body_v3(
            contract_agreement_id=str(agreement_id),
            provider_dsp=args.provider_dsp,
            transfer_type=xfer_type,
            sink_base_url=args.sink_base_url,
        )
        _, tp_init = _post_json(f"{cm}/{ver}/transferprocesses", tr_body)
        tp_id = _extract_id(tp_init)
        print(f"    transfer process id: {tp_id}")

        print(
            f"==> Waiting for transfer state {args.transfer_success_state!r} (max {args.transfer_timeout}s) …"
        )
        tp_state = _wait_transfer_state(
            cm,
            tp_id,
            args.transfer_success_state,
            args.transfer_timeout,
        )
        result["transferProcessId"] = tp_id
        result["transferState"] = tp_state.get("state")

    print("==> Result")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
