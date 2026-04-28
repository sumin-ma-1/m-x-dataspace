#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
import urllib.error
import urllib.request


def _request(url: str, method: str, body: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed one sample shell into BaSyx AAS Environment.")
    parser.add_argument("--registry-base", default="http://127.0.0.1:38081")
    args = parser.parse_args()

    uid = uuid.uuid4().hex[:8]
    shell_id = f"urn:uuid:{uuid.uuid4()}"
    body = {
        "id": shell_id,
        "idShort": f"SampleShell-{uid}",
        "assetInformation": {
            "assetKind": "INSTANCE",
            "globalAssetId": f"urn:uuid:{uuid.uuid4()}",
        },
        "submodels": [],
    }

    base = args.registry_base.rstrip("/")
    status, text = _request(f"{base}/shells", "POST", body)
    if status not in (200, 201, 204):
        print(f"ERROR: register shell failed (HTTP {status}) {text[:1500]}", file=sys.stderr)
        return 1

    status, text = _request(f"{base}/shells", "GET")
    if status != 200:
        print(f"ERROR: read shells failed (HTTP {status}) {text[:1500]}", file=sys.stderr)
        return 1

    try:
        data = json.loads(text) if text.strip() else []
        count = len(data) if isinstance(data, list) else 1
    except json.JSONDecodeError:
        count = -1
    print(json.dumps({"registeredShellId": shell_id, "shellCount": count}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
