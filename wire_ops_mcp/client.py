"""wire 客户面 HTTP 客户端：Bearer 原样转发 + 诚实错误映射。

家族同款；wire 特有（spec：上游权威鉴权）——401（未映射客户/缺 token）、
403（viewer 只读/owner-only）、422（需求单合规门逐字段）全原样透传。
凭据只经手不落盘；连接失败/5xx=unreachable。
"""

from __future__ import annotations

from typing import Any

import httpx


class WireError(Exception):
    """结构化错误：kind + status + 上游 detail 原文。"""

    def __init__(self, kind: str, status: int | None, detail: str):
        super().__init__(f"[{kind}] {detail}" + (f" (HTTP {status})" if status else ""))
        self.kind = kind
        self.status = status
        self.detail = detail


MISSING_CREDENTIAL_HINT = (
    "缺少凭据：柏讯客户面需要 Bearer（Logto ID token——壹座同租户登录后获取；"
    "数据面工具也接受 wdk_ 数据面 key）"
)


class WireClient:
    def __init__(self, base_url: str, timeout_seconds: float = 20.0, transport=None):
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def aclose(self):
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        bearer: str | None,
        params: dict | None = None,
        json_body: Any | None = None,
    ) -> Any:
        if not bearer:
            raise WireError("missing_credential", 401, MISSING_CREDENTIAL_HINT)
        try:
            res = await self._client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {bearer}"},
                params=params,
                json=json_body,
            )
        except httpx.HTTPError as e:
            raise WireError(
                "unreachable", None, f"柏讯服务不可达：{type(e).__name__}: {e}"
            ) from e
        if res.status_code == 401:
            raise WireError("unauthorized", 401, _detail(res))
        if res.status_code == 402:
            raise WireError("billing", 402, _detail(res))
        if res.status_code == 403:
            raise WireError("forbidden", 403, _detail(res))
        if res.status_code == 404:
            raise WireError("not_found", 404, _detail(res))
        if res.status_code == 409:
            raise WireError("conflict", 409, _detail(res))
        if res.status_code == 422:
            raise WireError("invalid", 422, _detail(res))
        if res.status_code == 429:
            raise WireError("rate_limited", 429, _detail(res))
        if res.status_code >= 500:
            raise WireError("unreachable", res.status_code, f"柏讯服务错误：{_detail(res)}")
        if res.status_code >= 400:
            raise WireError("invalid", res.status_code, _detail(res))
        if not res.content:
            return None
        try:
            return res.json()
        except ValueError:
            return {"_raw": res.text}


def _detail(res: httpx.Response) -> str:
    try:
        body = res.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])[:800]
        if isinstance(body, dict) and "error" in body:
            return str(body["error"])[:800]
        return str(body)[:800]
    except Exception:
        return (res.text or "")[:800] or f"HTTP {res.status_code}（无 body）"
