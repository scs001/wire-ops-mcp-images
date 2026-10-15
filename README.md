# wire-ops-mcp — 柏讯客户面操作 MCP

柏讯（wire 线）的动作 MCP（五线 AI 操作面 C3 切片，v1 子集）：**需求单**提交/列表/详情、
**数据面读**（列表/查询/聚合/行读）、**市场**目录/订阅/退订——十工具薄包 fd-wire-api
客户面 REST。

- 契约：`openspec/changes/wire-ops-mcp/specs/wire-ops-mcp/spec.md`（finddata 工作区）
- 接入规约：`LINES-MCP-CONFORMANCE.md`

## 双轨鉴权透传（wire 既有语义，上游权威）

进站 Bearer **原样转发**，wire 侧自行判轨：
- **console 轨**：Logto ID token（壹座同租户；sub→Customer 首登开户后生效；viewer 只读上游 403）
- **数据面轨**：`wdk_` 数据面 key（key 允许清单约束数据集访问）

需求单合规门（≥1 个公开 http(s) 数据源 URL + 公开数据声明必勾）422 逐字段透传——
**AI 绝不代勾声明**；市场订阅 approval 档上游自动转访问申请（不冒充订阅成功）。

## 工具面（十工具全 commercial）

| 组 | 工具 | 写 |
|---|---|---|
| 需求单 | `wire_demand_submit` / `wire_demands_list` / `wire_demand_read` | submit ✅ |
| 数据面 | `wire_datasets_list` / `wire_dataset_query` / `wire_dataset_aggregate` / `wire_dataset_rows` | 全读 |
| 市场 | `wire_market_browse` / `wire_market_subscribe` / `wire_market_unsubscribe` | 订/退 ✅ |

## 环境

| 变量 | 默认 |
|---|---|
| `WIRE_OPS_BASE_URL` | `https://wire.finddatatech.cloud` |
| `WIRE_OPS_TIMEOUT_SECONDS` | `20` |
| `WIRE_OPS_AUTH_CACHE_TTL` | `60` |

## 本地

```bash
pip install -e ".[dev]"
pytest && python3 scripts/selfcheck_surface.py
wire-ops-mcp serve --port 8000   # /health 无门；/mcp 无 Bearer 401
```
