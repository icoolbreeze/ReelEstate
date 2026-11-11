# CRM 数据：云端部署与本项目用法

租赁成片的房源事实来自云端部署的 crm_connector（BeikeMicroservice）。公网只能看归档进度，不能搜房；搜房、详情和实勘要先在本机建立 SSH 转发，访问服务器上的 127.0.0.1:8020。

## 1. 本项目用它做什么

`pipeline/common/crm_listing.py`（`python pipeline/common/crm_listing.py projects/listing/<ep>`，读 episode.yaml 的 `listing.ref`，写 `data/listing.json` 与 `data/listing_prospect.json`）只读租赁房源。旧 `pipeline/stages/listing.py` 与 `npm run make` 已于 2026-10-30 退役。二手房、新房成片目前没有接到这个连接器；连接器上另有买卖查询，本仓库流水线不调用。

`CC_BASE_URL` 默认 `http://127.0.0.1:8020`，实际请求前缀是 `{CC_BASE_URL}/api/v1`。本阶段只打三个接口：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/listings/rental/search` | 租赁房源搜索 |
| GET | `/api/v1/listings/rental/{listing_id}` | 单套房源详情 |
| GET | `/api/v1/listings/rental/{listing_id}/prospect` | 实勘照片 |

搜索 body：`scope`（brief 里 `filters.scope`，默认 `all`）、`page=1`、`page_size=12`，以及 `listing_id` 或 `community_keyword`；有则带上 `rooms`、`monthly_rent_yuan`、`area_sqm`、`orientations`。

错误处理：

- 错误文本含 `CRM_AUTH_REQUIRED` 或 `unreachable` 时，阶段改写虚构 fixture（`source=mock`，`live_status=untested`），**不得当真实房源发布**。
- `brief.listing.source=mock` 或命令 `--mock` 从一开始就不访问 CRM。
- 其他 HTTP 错误直接失败，不会改成假数据。

禁止调用 `GET /api/v1/listings/rental/{listing_id}/house-info` 和 MCP 工具 `rental_listing_get_house_info`（含跟进人姓名电话）。

## 2. 服务部署在哪里

连接器与门店媒体在同一台机器上：

| 项 | 值 |
|---|---|
| SSH 别名 | `beike-server` |
| 地址 | `119.29.187.184` |
| systemd 服务 | `crm-connector.service` |
| 监听端口 | 只绑服务器的 `127.0.0.1:8020` |
| 代码目录 | `/opt/crm-connector/current` |
| 持久化目录 | `/var/lib/crm-connector`（归档库 `rental_archive.sqlite3`，以及凭证） |
| 环境变量文件 | `/etc/crm-connector/crm-connector.env`（只记录路径，不得读取或提交） |

公网端口 8080（store-media）只转发两处，用来看归档进度，**不能搜房、不能下详情**：

- 看板：`http://119.29.187.184:8080/archive`
- 状态：`http://119.29.187.184:8080/api/v1/archive/rental/status`

房源搜索、详情、实勘、登录、`POST /api/v1/archive/rental/tick`、`GET /api/v1/archive/rental/listings` 和单条归档查询都只在服务器 `127.0.0.1:8020` 上，8080 没有这些路由。

服务器上的健康检查：`curl --fail http://127.0.0.1:8020/api/v1/health`。

## 3. 从本机连到云端再取数

代码默认访问本机 `127.0.0.1:8020`，而云端进程绑在服务器 loopback 上。保持下面的转发运行，再执行 `python pipeline/common/crm_listing.py projects/listing/<ep>`，不必改默认 `CC_BASE_URL`：

```
ssh -N -L 8020:127.0.0.1:8020 beike-server
```

- 本机若已有进程占用 8020：先停本机实例，或把转发映射到另一个本地端口并设置 `CC_BASE_URL`。
- 不要把 8020 对公网开放。
- `CRM_AUTH_REQUIRED` 表示云端会话失效，由用户在已连接云枢的那台服务器上扫码。Agent 不得代登录，不得读取凭证、cookie、token、`/var/lib/crm-connector` 里的凭证、BeikeMicroservice 的 `services/crm_connector/run/*`。
- SSH 使用本机已有的 `beike-server` 别名，文档不记录私钥路径。

## 4. 成都租赁归档

默认开启（`CC_RENTAL_ARCHIVE_ENABLED=1`，设为 `0` 关闭），覆盖成都 CRM「全部房源」的 24 个 `districtId`，每轮重扫列表。

- 详情在未采过、超过 TTL、上次失败或列表指纹变化时才重采。TTL 默认 14 天（`CC_RENTAL_ARCHIVE_DETAIL_TTL_DAYS`）。指纹是月租、状态、封面、户型、小区。
- 作业窗口默认 Asia/Shanghai 09:00–21:00（`CC_RENTAL_ARCHIVE_WINDOW_START` / `CC_RENTAL_ARCHIVE_WINDOW_END`），21:00 至次日 09:00 暂停。列表翻页间隔约 8–25 秒，每套详情之后停 2 秒。日请求上限默认 0，表示不另设封顶。
- 某一租金档超过上游 1000 条深分页上限时，先把租金档对半切；切到 1 元档仍超过，再按委托类型切（普租 `del_type` 2，托管 `del_type` 5）。完整扫完且未中断、未触顶的档，本轮未见的房源只把 `is_active` 置 0，不删除；中断或超限的不完整档不做这批下架。
- 入库前去掉具体楼层、详细地址、电话、业主底价，保留高/中/低楼层。普租跟进文本可能仍留在归档 payload 里；本项目白名单不取跟进，口播、字幕、画面不得使用跟进、人名或电话。
- `GET /api/v1/archive/rental/listings` 的查询参数只有 `district_id`、`active`（默认 true）、`page`、`page_size`（最大 50），不能按小区名或租金过滤。按小区取数用实时搜索。此接口不在 8080 上。

单条归档字段：

| 字段 | 含义 |
|---|---|
| `listing_id` | 房源编号 |
| `district_id` | 成都区域编号 |
| `price_band` | 租金档 |
| `del_type` | 委托类型（2 普租，5 托管） |
| `community` | 小区名 |
| `detail_status` | 详情采集状态 |
| `detail_captured_at` | 详情采集时间 |
| `first_seen_at` | 首次出现时间 |
| `last_seen_at` | 最近出现时间 |
| `is_active` | 在架标记。只有完整扫完、且未中断、未触顶的租金档，才会把本轮未见的房源置为 0/false；行不删除。 |
| `payload` | 已去掉具体楼层、详细地址、电话和业主底价的归档内容。普租跟进文本可能仍在里面，成片不得使用。 |

## 5. 下架之后图片还在哪里

`is_active=0` 不删除 `payload`：列表封面、户型图 URL，以及详情里的实勘、户型图、VR 封面 URL 仍在。

下架后实时接口不一定能补图：托管详情可能返回 `CRM_UPSTREAM_INVALID_INPUT`，实勘接口可能 200 且照片数为 0。要取这些仍留在归档里的 URL，由管理员在服务器上只读处理。Agent 不得拷贝整库，不得读取凭证。

`crm_listing.py` 给图片 URL 追加 `.1500x.jpg`：

- URL 已以 `.450x.jpg`、`.750x.jpg`、`.800x.jpg`、`.1500x.jpg` 结尾的，不再追加。
- `img.ljcdn.com` 上的租赁图不加后缀通常仍能打开。
- `hdic-frame` 户型图不加 `.1500x.jpg` 会 403。
- 不要附带去水印参数。

## 6. 可以写入成片的字段

可以离开 CRM、写入 `listing.json` 的字段：

| 字段 | 字段 | 字段 |
|---|---|---|
| `listing_id` | `community` | `layout` |
| `area_sqm` | `monthly_rent_yuan` | `orientation` |
| `del_type` | `rent_mode_label` | `floor_desc` |
| `total_floors` | `listed_days` | `bedroom_amount` |
| `hall_amount` | `bathroom_amount` | `biz_circle` |
| `resblock_name` | `title_image_url` | `floor_plan_image_url` |
| `maintain_org` |  |  |

配套规则：

- `community`、`layout`、`area_sqm`、`monthly_rent_yuan`、`orientation`、`floor_desc` 缺失时写成 `待填`，合规检查失败。
- `floor_desc` 若包含「室」「单元」「号楼」或 `#`，改成 `待填`；画面只说低/中/高楼层。
- `listing_id` 只留在 `listing.json` 和 `wall_candidates.json`。`wall.json`、口播、字幕、画面不得出现 CRM 编号；编号与墙卡片的对应在 `raw/wall_map.json`，不进 Remotion。
- 实勘只下载 `image_type` 为 `REAL` 的照片到本期 `sources/crm/`。manifest 里 CRM 图的 `watermarked` 默认 `null`，人工确认没有平台水印后才改为 `false`；有平台水印的不能用，也不能去水印。
- MCP 业务工具默认每分钟 30 次（`CC_MCP_RATE_LIMIT_PER_MIN`）。成片取数以上述三个 HTTP 接口为准。

## 7. Agent 不得做的事

- 不代登录：`CRM_AUTH_REQUIRED` 时由用户本人在服务器上扫码。
- 不读取凭证、cookie、token，不读 `/etc/crm-connector/crm-connector.env`、`/var/lib/crm-connector` 里的凭证、BeikeMicroservice 的 `services/crm_connector/run/*`。
- 不调用 house-info 接口或同名 MCP 工具。
- 不把 mock fixture 当真实房源发布；不用 `--mock` 产物冒充正式片。
- 不把 8020 对公网开放；不尝试通过 8080 搜房或下详情。
- 不拷贝归档整库；下架房源的图片 URL 由管理员在服务器上只读处理。
- 不使用归档 payload 里的跟进文本、人名、电话；不去水印，不使用带平台水印的图片。
- 不让 CRM 编号进入 `wall.json`、口播、字幕或画面。

## 8. 依据

- `BeikeMicroservice/docs/deployment-servers.md`
- `BeikeMicroservice/services/crm_connector/deploy/README.md`
- `BeikeMicroservice/services/crm_connector/README.md`
- `BeikeMicroservice/services/store_media/app/main.py`（8080 只代理 `/archive` 与 `/api/v1/archive/rental/status`）
- `ReelEstate/pipeline/common/crm_listing.py`
