from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.validation

from tests.support.paths import service_import

with service_import("b2c"):
    from contract_api.envelope import err, ok


def test_ok_envelope_shape() -> None:
    response = ok({"items": []})
    body = json.loads(response.body)
    assert set(body.keys()) == {"data", "error"}
    assert body["error"] is None
    assert body["data"] == {"items": []}


def test_err_envelope_shape() -> None:
    response = err(code="NOT_FOUND", message="missing", status_code=404)
    body = json.loads(response.body)
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "missing"
    assert isinstance(body["error"]["details"], dict)
