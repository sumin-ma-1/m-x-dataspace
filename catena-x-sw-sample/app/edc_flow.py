"""
EDC Management API workflow client for catalog/contract/transfer.

Reference implementations:
- Connector management-api test fixtures `Participant`
- `CatalogApiEndToEndTest`, `ContractNegotiationApiEndToEndTest`,
  `TransferProcessApiEndToEndTest`
"""

from __future__ import annotations

import copy
import json
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"
EDC_PREFIX = "edc"
DATASPACE_PROTOCOL_HTTP_V_2025_1 = "dataspace-protocol-http:2025-1"
ODRL_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"


@dataclass(frozen=True)
class ContractWorkflowResult:
    policy_id: str
    asset_id: str
    contract_definition_id: str
    negotiation_id: str
    contract_agreement_id: str


@dataclass(frozen=True)
class TransferWorkflowResult:
    transfer_process_id: str
    transfer_state: str


@dataclass(frozen=True)
class SeedAssetResult:
    policy_id: str
    asset_id: str
    contract_definition_id: str


class EdcFlowClient:
    def __init__(
        self,
        *,
        consumer_mgmt: str,
        provider_mgmt: str,
        provider_dsp: str,
        counter_party_id: str = "counter-party-id",
        provider_participant_id: str = "anonymous",
    ) -> None:
        self.consumer_mgmt = consumer_mgmt.rstrip("/")
        self.provider_mgmt = provider_mgmt.rstrip("/")
        self.provider_dsp = provider_dsp
        self.counter_party_id = counter_party_id
        self.provider_participant_id = provider_participant_id

    def create_policy_definition(self) -> str:
        _, policy_resp = _post_json(
            f"{self.provider_mgmt}/v3/policydefinitions", _policy_body_v3()
        )
        return _extract_id(policy_resp)

    def create_asset(self, *, asset_id: str | None = None) -> str:
        actual_asset_id = asset_id or f"trade-demo-{uuid.uuid4().hex[:10]}"
        _post_json(
            f"{self.provider_mgmt}/v3/assets",
            _negotiation_asset_body_v3(actual_asset_id),
        )
        return actual_asset_id

    def create_contract_definition(
        self, *, policy_id: str, asset_id: str, contract_definition_id: str | None = None
    ) -> str:
        actual_contract_id = (
            contract_definition_id or f"trade-contract-{uuid.uuid4().hex[:10]}"
        )
        _post_json(
            f"{self.provider_mgmt}/v3/contractdefinitions",
            _contract_body_v3(actual_contract_id, policy_id, asset_id),
        )
        return actual_contract_id

    def seed_asset_for_contract(
        self,
        *,
        asset_id: str | None = None,
        contract_definition_id: str | None = None,
    ) -> SeedAssetResult:
        policy_id = self.create_policy_definition()
        actual_asset_id = self.create_asset(asset_id=asset_id)
        actual_contract_id = self.create_contract_definition(
            policy_id=policy_id,
            asset_id=actual_asset_id,
            contract_definition_id=contract_definition_id,
        )
        return SeedAssetResult(
            policy_id=policy_id,
            asset_id=actual_asset_id,
            contract_definition_id=actual_contract_id,
        )

    def request_catalog(self) -> dict[str, Any]:
        _, catalog = _post_json(
            f"{self.consumer_mgmt}/v3/catalog/request",
            _catalog_request_body_v3(self.provider_dsp, self.counter_party_id),
        )
        if not isinstance(catalog, dict):
            raise RuntimeError(f"unexpected catalog response: {catalog!r}")
        return catalog

    def request_dataset(self, *, asset_id: str) -> dict[str, Any]:
        _, dataset = _post_json(
            f"{self.consumer_mgmt}/v3/catalog/dataset/request",
            _dataset_request_body_v3(asset_id, self.provider_dsp, self.counter_party_id),
        )
        if not isinstance(dataset, dict):
            raise RuntimeError(f"unexpected dataset response: {dataset!r}")
        return dataset

    def run_contract_workflow(
        self,
        *,
        negotiation_timeout_sec: int = 120,
        asset_id: str | None = None,
        contract_definition_id: str | None = None,
    ) -> ContractWorkflowResult:
        seeded = self.seed_asset_for_contract(
            asset_id=asset_id,
            contract_definition_id=contract_definition_id,
        )

        dataset = self.request_dataset(asset_id=seeded.asset_id)

        offer = _first_has_policy(dataset)
        policy = _offer_policy_for_contract_request(
            offer,
            asset_id=seeded.asset_id,
            provider_participant_id=self.provider_participant_id,
        )
        _, nego_resp = _post_json(
            f"{self.consumer_mgmt}/v3/contractnegotiations",
            _contract_request_body(self.provider_dsp, policy),
        )
        negotiation_id = _extract_id(nego_resp)

        final = _wait_negotiation_finalized(
            self.consumer_mgmt, negotiation_id, negotiation_timeout_sec
        )
        contract_agreement_id = str(final.get("contractAgreementId") or "")
        if not contract_agreement_id:
            raise RuntimeError(
                "contract negotiation finalized but contractAgreementId is missing"
            )

        return ContractWorkflowResult(
            policy_id=seeded.policy_id,
            asset_id=seeded.asset_id,
            contract_definition_id=seeded.contract_definition_id,
            negotiation_id=negotiation_id,
            contract_agreement_id=contract_agreement_id,
        )

    def run_transfer_workflow(
        self,
        *,
        contract_agreement_id: str,
        transfer_timeout_sec: int = 180,
        transfer_success_state: str = "COMPLETED",
        sink_base_url: str = "https://httpbin.org/post",
        transfer_type: str = "HttpData-PUSH",
    ) -> TransferWorkflowResult:
        _, transfer_init = _post_json(
            f"{self.consumer_mgmt}/v3/transferprocesses",
            _transfer_request_body_v3(
                contract_agreement_id=contract_agreement_id,
                provider_dsp=self.provider_dsp,
                transfer_type=transfer_type,
                sink_base_url=sink_base_url,
            ),
        )
        transfer_id = _extract_id(transfer_init)
        state = _wait_transfer_state(
            self.consumer_mgmt,
            transfer_id,
            transfer_success_state,
            transfer_timeout_sec,
        )
        return TransferWorkflowResult(
            transfer_process_id=transfer_id,
            transfer_state=str(state.get("state") or ""),
        )


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

    return code, json.loads(raw) if raw.strip() else None


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
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "name": "trade-demo-asset",
            "description": "Seeded for contract workflow",
            "contenttype": "application/json",
            "version": "0.1.0",
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
    hp = dataset.get("hasPolicy") or dataset.get("http://www.w3.org/ns/odrl/2/hasPolicy")
    if hp is None:
        raise RuntimeError("Dataset has no hasPolicy.")
    first = hp[0] if isinstance(hp, list) else hp
    if not isinstance(first, dict):
        raise RuntimeError(f"Unexpected hasPolicy entry type: {type(first)}")
    return first


def _offer_policy_for_contract_request(
    offer: dict[str, Any], asset_id: str, provider_participant_id: str
) -> dict[str, Any]:
    pol = copy.deepcopy(offer)
    if "@context" not in pol:
        pol["@context"] = ODRL_CONTEXT
    pol["assigner"] = {"@id": provider_participant_id}
    pol["target"] = {"@id": asset_id}
    return pol


def _contract_request_body(provider_dsp: str, policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "@context": _ctx_edc_prefix(),
        "@type": "ContractRequest",
        "counterPartyAddress": provider_dsp,
        "protocol": DATASPACE_PROTOCOL_HTTP_V_2025_1,
        "policy": policy,
    }


def _transfer_request_body_v3(
    *,
    contract_agreement_id: str,
    provider_dsp: str,
    transfer_type: str,
    sink_base_url: str,
) -> dict[str, Any]:
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
            "properties": {"baseUrl": sink_base_url},
        },
    }


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
            raise RuntimeError(
                f"negotiation ended in state {state}: {json.dumps(last)[:2000]}"
            )
        time.sleep(0.5)
    raise RuntimeError(
        f"negotiation {negotiation_id} not FINALIZED within {timeout_sec}s; "
        f"last={json.dumps(last)[:1000]}"
    )


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
        f"transfer {transfer_id} not {wanted} within {timeout_sec}s; "
        f"last={json.dumps(last)[:1000]}"
    )
