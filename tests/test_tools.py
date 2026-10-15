"""十工具接线测试：薄转发+写显式+上游权威语义透传。"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP

import wire_ops_mcp.tools_console as tc
from wire_ops_mcp.client import WireError


class FakeClient:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    async def request(self, method, path, *, bearer, params=None, json_body=None):
        self.calls.append({"method": method, "path": path, "bearer": bearer,
                           "params": params, "json_body": json_body})
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def bearer(monkeypatch):
    monkeypatch.setattr(tc, "_current_bearer", lambda: "tok-abc")
    return "tok-abc"


async def _mk(fake):
    mcp = FastMCP("t-wire")
    tc.register(mcp, fake)
    return mcp


async def test_demand_submit_thin_forward_with_compliance(bearer):
    fake = FakeClient(result={"id": 1, "status": "submitted"})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        out = await c.call_tool("wire_demand_submit", {
            "description": "需要全国城市面板数据",
            "contact_email": "a@b.c",
            "source_urls": ["https://stats.gov.cn/x"],
            "public_data_asserted": True,
            "company": "测试公司",
        })
    call = fake.calls[0]
    assert call["method"] == "POST" and call["path"] == "/api/v1/demands"
    assert call["json_body"]["public_data_asserted"] is True
    assert len(call["json_body"]["source_urls"]) == 1


async def test_demands_list_status_filter(bearer):
    fake = FakeClient(result=[])
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("wire_demands_list", {"status": "submitted"})
    assert fake.calls[0]["params"] == {"status": "submitted"}


async def test_dataset_query_readonly_shape(bearer):
    fake = FakeClient(result={"rows": []})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("wire_dataset_query", {
            "dataset_id": "ds1", "filters": {"city": "北京"}, "limit": 10,
        })
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/api/v1/datasets/ds1/query"
    assert call["json_body"] == {"limit": 10, "offset": 0, "count_only": False,
                                 "filters": {"city": "北京"}}


async def test_market_subscribe_approval_semantics_pass_through(bearer):
    fake = FakeClient(result={"subscribed": False, "access_request": {"id": 9}, "created": True})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        out = await c.call_tool("wire_market_subscribe", {"dataset_id": "mkt1"})
    assert fake.calls[0]["path"] == "/api/v1/market/datasets/mkt1/subscribe"
    data = out.data if hasattr(out, "data") else out
    assert data["result"]["subscribed"] is False  # 不冒充订阅成功


async def test_unsubscribe_delete(bearer):
    fake = FakeClient(result={"ok": True})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("wire_market_unsubscribe", {"dataset_id": "mkt1"})
    assert fake.calls[0]["method"] == "DELETE"


async def test_viewer_403_propagates(bearer):
    fake = FakeClient(error=WireError("forbidden", 403, "团队成员权限不足（viewer 只读）"))
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        with pytest.raises(Exception) as ei:
            await c.call_tool("wire_demand_submit", {
                "description": "x", "contact_email": "a@b.c",
                "source_urls": ["https://x"], "public_data_asserted": True,
            })
    assert "viewer 只读" in str(ei.value)


async def test_missing_credential_hints_dual_track(monkeypatch):
    monkeypatch.setattr(tc, "_current_bearer", lambda: None)
    fake = FakeClient()
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        with pytest.raises(Exception) as ei:
            await c.call_tool("wire_datasets_list", {})
    assert "wdk_" in str(ei.value)
    assert fake.calls == []
