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

## 展示拓樸與網路通訊（2026-05-24 加入）

### 硬體拓樸

```
              同一個 Wi-Fi 路由器
              ┌────────┴────────────────────────────────┐
              │                                          │
          [Pi 4]                  [Windows]          [手機]
            │                        │                   │
            ├─ FastAPI server        ├─ RealVNC Viewer   ├─ 瀏覽器
            │  listen :8000          │  → Pi 桌面         │
            │  （0.0.0.0 全介面）     │                   │
            │                        │                   │
            └─ Pi 桌面瀏覽器          └─ Windows 瀏覽器    │
               http://localhost         http://raspberrypi   http://raspberrypi
               :8000                    .local:8000          .local:8000
                                        （走 wifi 內網）     （走 wifi 內網）
```

### 核心觀念

- Pi 跑 web server，**監聽**某個 port（FastAPI 慣例 8000、Flask 慣例 5000、HTTP 標準 80、HTTPS 標準 443）。
- 其他同 wifi 裝置都可以連 `http://<Pi位址>:<port>`。
- Pi 位址兩種寫法：
  - **`raspberrypi.local`** — mDNS 主機名（您的 RealVNC 已經在用）；macOS / iOS 內建支援，Windows 通常裝過 Bonjour / iTunes 也有，Android 通常**沒有**。
  - **IP 位址** — 例 `192.168.1.50`；任何系統都認得，但 Pi DHCP 換 IP 會失效。

### 三種「在哪看 UI」場景對比

| 場景 | URL | 用途 |
|---|---|---|
| **Pi 桌面內瀏覽器** | `http://localhost:8000` | 機器人展場時讓客人看 Pi 接的 HDMI 螢幕（主要展示場景）|
| **Windows VNC 看 Pi 桌面內瀏覽器** | 同上（在 VNC 視窗內）| 開發 / debug 用；雙重轉發（VNC + 瀏覽器渲染）效能差，少用 |
| **Windows 用自己瀏覽器直連** | `http://raspberrypi.local:8000` | **開發最順** — 不用 VNC、不用切視窗、F12 dev tools 在本機跑 |
| **手機連** | `http://raspberrypi.local:8000`（iOS）／ `http://192.168.x.x:8000`（Android）| 展示給客人 / 遠端遙控 / 行動裝置測試 |

### Android 無 mDNS 解法

- Pi 上跑 `hostname -I` 查 IP（例 `192.168.1.50`），手機改用該 IP 連。
- **長久解法：** 路由器設 **DHCP reservation** 把該 MAC 綁固定 IP；或 Pi 設靜態 IP。避免 DHCP 換 IP 導致連線失效。

---

## HTTP REST vs WebSocket

| 通訊方式 | 比喻 | 連線特性 | 場景 |
|---|---|---|---|
| **HTTP REST** | 打電話問一個問題、聽到答案就掛 | 短連線、一問一答、client 主動 | 加單、結帳、查商品 — 前端問、後端答 |
| **WebSocket** | 兩邊講對講機，一直連著、誰想說就說 | 長連線、雙向、server 可主動推 | 機器人動作完成 → 後端主動通知 UI 換頁 |

**URL scheme：**
- HTTP：`http://...` / `https://...`
- WebSocket：`ws://...` / `wss://...`（s 版本走 TLS 加密）

**重點：** REST 跟 WebSocket **不互斥**，通常同一個 server 兩種都開、走同一個 port。FastAPI 一個 app 內：

```python
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.get("/api/cart")              # REST endpoint
async def get_cart():
    return {"items": [...]}

@app.websocket("/ws/events")       # WebSocket endpoint
async def event_stream(ws: WebSocket):
    await ws.accept()
    while True:
        msg = await event_queue.get()
        await ws.send_json(msg)
```

前端載入時 `fetch('/api/cart')` 拿初始資料，同時 `new WebSocket('ws://raspberrypi.local:8000/ws/events')` 開長連線收事件，兩者並用。

---

## 您場景的功能對應表

| 功能 | 用什麼 | 備註 |
|---|---|---|
| 點商品 / 加單 / 結帳 | REST | `POST /api/cart/items` / `POST /api/checkout` |
| 算金額 / 取訂單明細 | REST | `GET /api/cart` |
| 顯示 QR Code（金額編碼） | **純前端** | JS lib（如 `qrcode.js`）拿後端回的金額 render，無 WS |
| 廣告影片背景循環 | **純前端** | HTML5 `<video autoplay loop muted>`，後端完全不參與 |
| 機器人 `say` 完話 → UI 顯示完成圖 | **WebSocket** | 後端 push `{event: "speak_done"}` → UI 切畫面 |
| 機器人動作做完 → UI 切下一頁 | **WebSocket** | 後端 push `{event: "action_done", name: "bow"}` |
| 顧客「想一下」中倒數計時 | 純前端 `setTimeout` 或 WS 推進度 | 簡單就純前端，要與後端 timer 同步才用 WS |
| 模式切換（叫賣 / 待機 / 客服）通知 UI | **WebSocket** | 後端狀態機切層 → push `{event: "state_change", layer: "L3"}` |

---

## 後端啟動關鍵：`host="0.0.0.0"`

**Pi 的 web server 預設只 listen `127.0.0.1`（本機自己），其他裝置連不到。**

要讓 wifi 內其他裝置連得到，啟動時必須指定 `host="0.0.0.0"`（監聽所有網路介面）：

```python
# 程式內啟動
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

```bash
# 或命令列啟動
uvicorn myProgram.sales.api:app --host 0.0.0.0 --port 8000
```

- `127.0.0.1` / `localhost` → 只本機自己連得到
- `0.0.0.0` → 所有網路介面（wifi / 乙太網 / VPN）都接受
- 想限制只 wifi → 指定 wifi 介面的 IP（少用，麻煩）

---

## 連不上時的 debug 步驟

| 症狀 | 檢查 | 修復 |
|---|---|---|
| Windows / 手機完全連不到 | Pi 上 `curl http://localhost:8000` 看 server 自己回不回 | Server 沒起 / 沒監聽 0.0.0.0 |
| Pi 自己連 OK，外部連超時 | Pi 上 `sudo netstat -tlnp \| grep 8000` 看綁哪個介面 | 顯示 `127.0.0.1:8000` → 改 `host="0.0.0.0"` |
| 外部連被拒絕 | Pi 上 `sudo ufw status` 看防火牆 | `sudo ufw allow 8000/tcp` |
| 同 wifi 但 ping 不到 Pi | 路由器設定 | 部分路由器有 **AP isolation**（同 wifi 裝置互相隔離），要關掉 |
| `raspberrypi.local` 解析失敗 | Windows 上 `ping raspberrypi.local` | 改用 IP；或在 Windows 裝 Bonjour Print Services |
| WebSocket 連不上但 REST OK | 瀏覽器 F12 → Network → WS 分頁看握手錯誤 | 通常是 path 寫錯，或反向代理（nginx）沒設 upgrade header |

---

## Pi IP 穩定性建議

| 方法 | 做法 | 何時用 |
|---|---|---|
| **DHCP reservation** | 路由器後台把 Pi 的 MAC 綁固定 IP | 路由器有此功能（多數家用都有），最簡單 |
| **Pi 靜態 IP** | 編 `/etc/dhcpcd.conf` 設 static IP | 路由器不支援 reservation；要懂網段 / gateway |
| **依賴 mDNS** | 只用 `raspberrypi.local`，不碰 IP | Android 不支援，僅 iOS / macOS / Windows 有 Bonjour 時可行 |

---

## 安全性註記（內網限定）

目前架構僅在**家用 / 展場內網**運作，無需考慮：
- HTTPS 憑證（內網 `http://` 即可）
- 使用者驗證（無公開 endpoint）
- CSRF / CORS 等公網安全議題

**若未來要對外（demo 給遠端老師看 / 公開展示），需要補：**
- HTTPS（Let's Encrypt + DDNS）/ 或走 cloudflare tunnel
- API token / OAuth
- CORS 白名單

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
| 2026-05-24 | 加入「展示拓樸與網路通訊」整段：硬體拓樸圖（Pi + Windows + 手機同 wifi）／ 3 種展示場景 ／ Android 無 mDNS 解法 ／ HTTP REST vs WebSocket 概念 ／ 功能對應表（哪些用 REST / WS / 純前端）／ FastAPI 同 app 雙協定範例 ／ `host=0.0.0.0` 啟動關鍵 ／ 連不上 6 種症狀的 debug 步驟 ／ Pi IP 穩定性 3 種方法 ／ 內網安全性註記 |
