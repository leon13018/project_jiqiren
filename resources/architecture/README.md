# 系統架構文件（architecture/）

Project_01 — Raspberry Pi 4 上的互動式銷售輔助機器人（規則匹配點餐 / 收款模擬）。本資料夾是**整體系統架構的單一事實來源**，以 `myProgram/` 實際程式碼為準（非願景、非計畫）。

> **重寫日期：2026-06-21。** 舊版（2026-05-24 敲定的三層願景 + 後端模組契約）描述的是「未來式」（FastAPI :8000、REST+WebSocket、Repository Pattern 等多未落地或已換實作），與現況脫節，已封存進 [`_archive/`](_archive/)，不再維護、不作參考依據。

---

## 閱讀順序

| 檔 | 內容 | 一句話 |
|---|---|---|
| [`00-system-overview.md`](00-system-overview.md) | 全系統鳥瞰 | 進入點、process / thread 模型、模組地圖、啟動模式、端到端資料流、env 旋鈕家族 |
| [`10-runtime-and-workers.md`](10-runtime-and-workers.md) | 執行期與 worker 層 | `main.py` 編排 + `QueueWorker` 骨架 + tts / stt / action / input_reader 四 worker 並行模型 + 預熱 / cleanup |
| [`20-sales-state-machine.md`](20-sales-state-machine.md) | 核心對話狀態機 | L0–L5：`SalesMachine`、狀態轉移表、各層語義、跨層流程、NLU / cart / product_parser、callback 注入清單 |
| [`30-web-mirror-and-frontend.md`](30-web-mirror-and-frontend.md) | web 顯示鏡像 | 「web 交互狀態機」：transport（EventBus / DTO / 路由 / 上行命令）+ 前端 phase→UI 映射、兩段式資料、`syncCart`、serve.py vs FastAPI、Glaze tokens、Pi 渲染限制 |

新手建議從 `00` 讀起；只想懂「對話怎麼跑」直接看 `20`；只想懂「螢幕怎麼跟著動」看 `30`。

---

## 與其他資料夾的分工

| 來源 | 內容 | 與本資料夾的關係 |
|---|---|---|
| `resources/plans/` | 單一任務的規格書 / 計畫 / 終審報告（含 L0–L5 業務規格 `業務程式邏輯規劃/`）| 規格是「該怎樣」，本資料夾是「實際長怎樣」 |
| `resources/specs/` | SDD 規格（單一改動）| 同上，顆粒更細 |
| `.claude/code_map.md`（巢狀）| 檔案路徑單一事實來源 | 「檔在哪」查 code_map；「為什麼這樣設計 / 怎麼串」查本資料夾 |
| `.claude/skills/project-01-workflow/reference/` | workflow 協議 + 領域設計（`sales-dialog-design.md` / `sales-tts-ux.md` 等）| 領域決策細節與本資料夾互補，本資料夾偏整體結構 |

---

## 維護原則

- 架構**實作變動**時 → 更新對應檔 + 在該檔「變動紀錄」補一行（日期 + 變動）。
- 本資料夾描述**現況**，不寫願景 / TODO（那些進 `plans/` 或 skill）。
- 與 `myProgram/` code 對不上時，**以 code 為準**，回頭修本文件。
- 新增 / 移動本資料夾的檔 → 同步更新 `resources/.claude/code_map.md`。
