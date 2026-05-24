# 前後端契約規劃

**敲定日期：** 2026-05-24
**狀態：** 願景已敲定；接口框架延後到「真正要做 HTML 前端」時再選

---

## 三層願景

| 層 | 技術選擇（暫定） | 目前進度 |
|---|---|---|
| **前端** | HTML + CSS + TypeScript（複雜時可加 React） | 待規劃；包含商品顯示 / QR Code 掃碼 / 金額顯示 / 廣告影片背景循環 |
| **後端** | Python（規則匹配業務邏輯） | S1 v2 進行中（`myProgram/sales/`）|
| **資料庫** | 暫不需要（商品只兩個）；商品多再上 SQLite / Postgres | 延後 |

---

## 推薦框架組合（待 HTML 前端開工時敲定）

### 後端：FastAPI + Pydantic

- FastAPI 自動產生 OpenAPI 文件 + Swagger UI（免手寫 API 文件）
- Pydantic 用 Python type hints 定義 DTO，請求 / 回應自動驗證
- 內建 WebSocket 支援（之後機器人事件推播直接接）

**為何 FastAPI 而非 Flask：** FastAPI = Flask + 強型別 + 自動文件 + async + WebSocket。本身就強迫寫好契約，無痛符合大公司分層解耦規範。Flask 要自己外掛一堆東西才達到同等水準。

### 前端：HTML + TypeScript（暫不上 React）

- 用 `openapi-typescript` 工具，從後端 OpenAPI 文件**自動產生 TS 型別**
- 前後端型別 100% 同步，後端改了前端編譯就會報錯

### 資料層：Repository Pattern

- 現在 `ProductRepository` 內部用 dict（in-memory）
- 未來換 SQLite / Postgres 時，**只改 repo 內部，service layer 一行不動**

---

## 標準化接口的核心（不論用哪個傳輸協定）

大公司一定做的三件事：

1. **DTO (Data Transfer Object)** — 跨層 / 跨語言傳的「資料形狀」必須先定死
2. **Schema / Contract** — 用 Pydantic（Python）/ Zod（TS）/ JSON Schema 描述 DTO，前後端共用同一份契約
3. **分層解耦** — Service Layer（業務邏輯）跟 Transport Layer（HTTP / WS）分開；業務碼不知道自己被誰呼叫

---

## 常見三種傳輸架構比較

| 模式 | 用途 | 適不適合本專案 |
|---|---|---|
| **REST + JSON** | 前端發 HTTP 請求、後端回 JSON | ✅ 最通用，本專案剛好 |
| **WebSocket** | 後端主動推訊息給前端（事件流） | ✅ 適合「機器人動作完成 → 通知 UI 換頁」 |
| **gRPC / Protobuf** | 強型別、高效能、跨語言 | ❌ 對本專案太重，主要給 microservice 間用 |

---

## 接口框架延後決策（2026-05-24 紀錄）

**決策：** 這輪只敲定後端目錄結構（`myProgram/sales/`），FastAPI / Pydantic 等真正要做 HTML 前端時才選定。

**理由：**
1. 現在加 FastAPI 是空殼，沒對應的前端調用
2. Pi 上 FastAPI 套件要不要走 source build 還不確定（memory `pi-glibc-piwheels-trap`），要做時實機驗證
3. 目前優先級是 S1 v2 純單線程 5 層狀態機，不被 web framework 打擾

**何時觸發決策：** 主框架（S1 v2 → S7）跑通 → 開始做 HTML 前端 → 此時敲定 FastAPI / 替代方案。

---

## 相關文件

- 後端模組結構細節：`backend-module-structure.md`
- 業務邏輯規格書：`resources/plans/業務程式邏輯規劃/L0_共通.md` + L1-L5
- 廠商 SDK 不可改背景：`.claude/CLAUDE.md` ⛔ 絕對禁止 #1
- Pi 套件相容性陷阱：memory `pi-glibc-piwheels-trap`

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-05-24 | 初版敲定三層願景；接口框架延後決策（HTML 前端開工時再選 FastAPI / 替代方案）|
