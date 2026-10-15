"""FastMCP 组装 + ASGI 布线（鉴权门 + /health）。"""

from __future__ import annotations

from . import SERVER_NAME, tools_console
from .auth_gate import AuthGate, AuthGateMiddleware
from .client import WireClient
from .config import Settings

INSTRUCTIONS = (
    "柏讯客户面操作助手：提交/查询需求单、查本企业数据集并做只读查询/聚合/行读、"
    "浏览数据市场并订阅/退订。每个调用以你的柏讯凭据执行（Logto ID token 或 wdk_ "
    "数据面 key，上游双轨判定）；viewer 角色只读（写操作上游会 403 并如实转述）。"
    "需求单合规门（公开数据源 URL+公开数据声明）必须由用户真实意图驱动——绝不代勾。"
    "错误如实透传（401=未登录/未映射客户、403=无权限、404=无此条目、422=校验逐字段）；"
    "空结果如实为空，绝不编造数据集或数据行。"
)

_HEALTH_OK = b'{"status":"ok"}'


def create_server(settings: Settings | None = None) -> "FastMCP":
    from fastmcp import FastMCP

    settings = settings or Settings.from_env()
    mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    client = WireClient(settings.base_url, timeout_seconds=settings.timeout_seconds)
    tools_console.register(mcp, client)
    mcp._wire_ops_client = client
    mcp._wire_ops_settings = settings
    return mcp


def build_app(settings: Settings | None = None):
    """完整 ASGI 应用：/health 无门；其余（/mcp）走鉴权门（无 Bearer 拒）。"""
    mcp = create_server(settings)
    settings_: Settings = mcp._wire_ops_settings
    mcp_app = mcp.http_app(path="/mcp")
    gate = AuthGateMiddleware(mcp_app, AuthGate(settings_.auth_cache_ttl_seconds))

    async def app(scope, receive, send):
        if scope.get("type") == "http":
            path = (scope.get("path") or "").rstrip("/")
            if path == "/health":
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": _HEALTH_OK})
                return
        await gate(scope, receive, send)

    return app
