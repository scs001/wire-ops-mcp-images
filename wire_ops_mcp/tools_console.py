"""十工具面（design D3）：需求单 3 + 数据面 4 + 市场 3，写显式，Bearer 原样转发。

Bearer 从进站 MCP 请求取（get_http_request 原始头——fastmcp 4.1.0 的
get_http_headers 过滤 Authorization，家族坑）。上游权威鉴权：双轨（Logto ID
token / wdk_ key）由 wire 判定，本层不解析凭据。
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .client import MISSING_CREDENTIAL_HINT, WireClient, WireError


def _current_bearer() -> str | None:
    try:
        from fastmcp.server.dependencies import get_http_request
    except ImportError:
        return None
    req = get_http_request()
    if req is None:
        return None
    auth = (req.headers.get("Authorization") or req.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _bearer_or_raise() -> str:
    bearer = _current_bearer()
    if not bearer:
        raise WireError("missing_credential", 401, MISSING_CREDENTIAL_HINT)
    return bearer


def register(mcp: FastMCP, client: WireClient) -> None:
    # ── 需求单（3）────────────────────────────────────────────────────────────

    @mcp.tool
    async def wire_demand_submit(
        description: str,
        contact_email: str,
        source_urls: list[str],
        public_data_asserted: bool,
        company: str | None = None,
        indicator_code: str | None = None,
    ) -> dict[str, Any]:
        """提交柏讯意向单（POST /api/v1/demands）——显式写操作。

        必填：需求描述（自由文本）、联系邮箱、≥1 个公开数据源 URL（http/https）、
        公开数据声明（所求数据为公开可获取——false 会被合规门拒绝）。选填：公司名、
        目录锚点 indicator code。初始状态 submitted，运营异步跟进；422 逐字段错误
        如实转述（绝不代勾声明或放宽校验）。
        """
        body: dict[str, Any] = {
            "description": description,
            "contact_email": contact_email,
            "source_urls": source_urls,
            "public_data_asserted": public_data_asserted,
        }
        if company is not None:
            body["company"] = company
        if indicator_code is not None:
            body["indicator_code"] = indicator_code
        result = await client.request(
            "POST", "/api/v1/demands", bearer=_bearer_or_raise(), json_body=body
        )
        return {"submitted": True, "demand": result}

    @mcp.tool
    async def wire_demands_list(status: str | None = None) -> Any:
        """本企业需求单列表（GET /api/v1/demands）——含当前状态与完整时间线。

        status 可选过滤（submitted/scoping/quoting/…以柏讯控制台口径为准）；
        他企需求单不可见（上游映射客户隔离）。
        """
        params = {"status": status} if status else None
        return await client.request(
            "GET", "/api/v1/demands", bearer=_bearer_or_raise(), params=params
        )

    @mcp.tool
    async def wire_demand_read(demand_id: int) -> Any:
        """需求单详情（GET /api/v1/demands/{id}）——他企或不存在一律 404（上游语义）。"""
        return await client.request(
            "GET", f"/api/v1/demands/{demand_id}", bearer=_bearer_or_raise()
        )

    # ── 数据面读（4）──────────────────────────────────────────────────────────

    @mcp.tool
    async def wire_datasets_list() -> Any:
        """本企业数据集列表（GET /api/v1/datasets）。双轨凭据（ID token 或 wdk_ key）。"""
        return await client.request(
            "GET", "/api/v1/datasets", bearer=_bearer_or_raise()
        )

    @mcp.tool
    async def wire_dataset_query(
        dataset_id: str,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 50,
        offset: int = 0,
        count_only: bool = False,
    ) -> Any:
        """数据集查询（POST /api/v1/datasets/{id}/query）——只读。

        filters/sort 形状按柏讯数据面契约；limit 默认 50（大量数据用分页，
        别一次拉全量）；count_only=true 只回计数。
        """
        body: dict[str, Any] = {"limit": limit, "offset": offset, "count_only": count_only}
        if filters:
            body["filters"] = filters
        if sort:
            body["sort"] = sort
        return await client.request(
            "POST", f"/api/v1/datasets/{dataset_id}/query",
            bearer=_bearer_or_raise(), json_body=body,
        )

    @mcp.tool
    async def wire_dataset_aggregate(dataset_id: str, body: dict[str, Any]) -> Any:
        """数据集聚合（POST /api/v1/datasets/{id}/aggregate）——只读。

        body 按柏讯数据面 AggregateIn 契约（group/aggregates 等）薄转发。
        """
        return await client.request(
            "POST", f"/api/v1/datasets/{dataset_id}/aggregate",
            bearer=_bearer_or_raise(), json_body=body,
        )

    @mcp.tool
    async def wire_dataset_rows(
        dataset_id: str, limit: int = 50, offset: int = 0
    ) -> Any:
        """数据集行读（GET /api/v1/datasets/{id}/rows）——只读分页。"""
        return await client.request(
            "GET", f"/api/v1/datasets/{dataset_id}/rows",
            bearer=_bearer_or_raise(), params={"limit": limit, "offset": offset},
        )

    # ── 市场（3）──────────────────────────────────────────────────────────────

    @mcp.tool
    async def wire_market_browse() -> Any:
        """浏览柏讯数据市场目录（GET /api/v1/market/datasets）——公开/客户可见集。"""
        return await client.request(
            "GET", "/api/v1/market/datasets", bearer=_bearer_or_raise()
        )

    @mcp.tool
    async def wire_market_subscribe(dataset_id: str) -> dict[str, Any]:
        """订阅市场数据集（POST /api/v1/market/datasets/{id}/subscribe）——显式写操作。

        approval 档不会直接订阅：上游自动转为访问申请（返回
        {subscribed: false, access_request: …}——如实转述，不冒充订阅成功）。
        """
        result = await client.request(
            "POST", f"/api/v1/market/datasets/{dataset_id}/subscribe",
            bearer=_bearer_or_raise(), json_body={},
        )
        return {"result": result}

    @mcp.tool
    async def wire_market_unsubscribe(dataset_id: str) -> dict[str, Any]:
        """退订市场数据集（DELETE /api/v1/market/datasets/{id}/unsubscribe）——显式写操作。"""
        result = await client.request(
            "DELETE", f"/api/v1/market/datasets/{dataset_id}/unsubscribe",
            bearer=_bearer_or_raise(),
        )
        return {"result": result}
