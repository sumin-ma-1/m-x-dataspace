from __future__ import annotations

import asyncio
import os
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .edc_flow import EdcFlowClient


app = FastAPI(title="m-x-dataspace API", version="v1")

_PROXY_TARGETS = {
    "consumer": {
        "management": os.getenv(
            "APP_CONSUMER_MGMT_URL", "http://127.0.0.1:18181/api/management"
        ),
        "default": os.getenv("APP_CONSUMER_DEFAULT_URL", "http://127.0.0.1:19191/api"),
        "protocol": os.getenv(
            "APP_CONSUMER_PROTOCOL_URL", "http://127.0.0.1:18282/api/protocol"
        ),
    },
    "provider": {
        "management": os.getenv(
            "APP_PROVIDER_MGMT_URL", "http://127.0.0.1:28181/api/management"
        ),
        "default": os.getenv("APP_PROVIDER_DEFAULT_URL", "http://127.0.0.1:29191/api"),
        "protocol": os.getenv(
            "APP_PROVIDER_PROTOCOL_URL", "http://127.0.0.1:28282/api/protocol"
        ),
    },
}


def _forward_proxy_request(
    url: str, method: str, body: bytes, headers: dict[str, str]
) -> tuple[bytes, str, int]:
    upstream_req = urllib.request.Request(
        url,
        data=body if body else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(upstream_req, timeout=180) as resp:
            return (
                resp.read(),
                resp.headers.get("Content-Type", "application/json"),
                resp.status,
            )
    except urllib.error.HTTPError as e:
        return (
            e.read(),
            e.headers.get("Content-Type", "application/json"),
            e.code,
        )


class FlowConfig(BaseModel):
    consumer_mgmt: str = Field(
        default=os.getenv("APP_CONSUMER_MGMT_URL", "http://127.0.0.1:18181/api/management"),
        description="Consumer Management API base URL",
    )
    provider_mgmt: str = Field(
        default=os.getenv("APP_PROVIDER_MGMT_URL", "http://127.0.0.1:28181/api/management"),
        description="Provider Management API base URL",
    )
    provider_dsp: str = Field(
        default=os.getenv(
            "APP_PROVIDER_DSP_URL",
            "http://provider-cp:8282/api/protocol/2025-1",
        ),
        description="Provider DSP URL reachable from consumer connector",
    )
    counter_party_id: str = os.getenv("APP_COUNTER_PARTY_ID", "counter-party-id")
    provider_participant_id: str = os.getenv("APP_PROVIDER_PARTICIPANT_ID", "anonymous")


def _client(cfg: FlowConfig) -> EdcFlowClient:
    return EdcFlowClient(
        consumer_mgmt=cfg.consumer_mgmt,
        provider_mgmt=cfg.provider_mgmt,
        provider_dsp=cfg.provider_dsp,
        counter_party_id=cfg.counter_party_id,
        provider_participant_id=cfg.provider_participant_id,
    )


class SeedAssetRequest(FlowConfig):
    asset_id: str | None = None
    contract_definition_id: str | None = None


class SeedAssetResponse(BaseModel):
    policy_id: str
    asset_id: str
    contract_definition_id: str


class CatalogRequest(FlowConfig):
    pass


class CatalogResponse(BaseModel):
    catalog: dict


class DatasetRequest(FlowConfig):
    asset_id: str


class DatasetResponse(BaseModel):
    dataset: dict


class ContractRequest(FlowConfig):
    negotiation_timeout_sec: int = 120
    asset_id: str | None = None
    contract_definition_id: str | None = None


class ContractResponse(BaseModel):
    policy_id: str
    asset_id: str
    contract_definition_id: str
    negotiation_id: str
    contract_agreement_id: str


class TransferRequest(BaseModel):
    contract_agreement_id: str
    consumer_mgmt: str = FlowConfig.model_fields["consumer_mgmt"].default
    provider_mgmt: str = FlowConfig.model_fields["provider_mgmt"].default
    provider_dsp: str = FlowConfig.model_fields["provider_dsp"].default
    counter_party_id: str = FlowConfig.model_fields["counter_party_id"].default
    provider_participant_id: str = FlowConfig.model_fields["provider_participant_id"].default
    transfer_timeout_sec: int = 180
    transfer_success_state: str = "COMPLETED"
    sink_base_url: str = "https://httpbin.org/post"
    transfer_type: str = "HttpData-PUSH"


class TransferResponse(BaseModel):
    transfer_process_id: str
    transfer_state: str


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route(
    "/proxy/{connector}/{api_kind}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_edc(
    connector: str,
    api_kind: str,
    path: str,
    request: Request,
) -> Response:
    conn = _PROXY_TARGETS.get(connector)
    if conn is None:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector}")
    base = conn.get(api_kind)
    if base is None:
        raise HTTPException(status_code=404, detail=f"Unknown api kind: {api_kind}")

    base = base.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = {
        "Accept": request.headers.get("accept", "application/json"),
    }
    if request.headers.get("content-type"):
        headers["Content-Type"] = request.headers["content-type"]
    if request.headers.get("authorization"):
        headers["Authorization"] = request.headers["authorization"]

    try:
        raw, content_type, status = await asyncio.to_thread(
            _forward_proxy_request,
            url,
            request.method,
            body,
            headers,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e

    return Response(content=raw, status_code=status, media_type=content_type)


@app.post("/api/v1/assets", response_model=SeedAssetResponse)
def seed_asset(req: SeedAssetRequest) -> SeedAssetResponse:
    try:
        result = _client(req).seed_asset_for_contract(
            asset_id=req.asset_id,
            contract_definition_id=req.contract_definition_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e
    return SeedAssetResponse(
        policy_id=result.policy_id,
        asset_id=result.asset_id,
        contract_definition_id=result.contract_definition_id,
    )


@app.post("/api/v1/catalog", response_model=CatalogResponse)
def request_catalog(req: CatalogRequest) -> CatalogResponse:
    try:
        catalog = _client(req).request_catalog()
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e
    return CatalogResponse(catalog=catalog)


@app.post("/api/v1/dataset", response_model=DatasetResponse)
def request_dataset(req: DatasetRequest) -> DatasetResponse:
    try:
        dataset = _client(req).request_dataset(asset_id=req.asset_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e
    return DatasetResponse(dataset=dataset)


@app.post("/api/v1/contract", response_model=ContractResponse)
def create_contract(req: ContractRequest) -> ContractResponse:
    try:
        result = _client(req).run_contract_workflow(
            negotiation_timeout_sec=req.negotiation_timeout_sec,
            asset_id=req.asset_id,
            contract_definition_id=req.contract_definition_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e

    return ContractResponse(
        policy_id=result.policy_id,
        asset_id=result.asset_id,
        contract_definition_id=result.contract_definition_id,
        negotiation_id=result.negotiation_id,
        contract_agreement_id=result.contract_agreement_id,
    )


@app.post("/api/v1/transfer", response_model=TransferResponse)
def create_transfer(req: TransferRequest) -> TransferResponse:
    cfg = FlowConfig(
        consumer_mgmt=req.consumer_mgmt,
        provider_mgmt=req.provider_mgmt,
        provider_dsp=req.provider_dsp,
        counter_party_id=req.counter_party_id,
        provider_participant_id=req.provider_participant_id,
    )
    try:
        result = _client(cfg).run_transfer_workflow(
            contract_agreement_id=req.contract_agreement_id,
            transfer_timeout_sec=req.transfer_timeout_sec,
            transfer_success_state=req.transfer_success_state,
            sink_base_url=req.sink_base_url,
            transfer_type=req.transfer_type,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=repr(e)) from e

    return TransferResponse(
        transfer_process_id=result.transfer_process_id,
        transfer_state=result.transfer_state,
    )
