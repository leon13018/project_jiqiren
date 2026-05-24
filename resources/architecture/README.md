# 架構規劃資料夾

本資料夾收納專案「跨檔 / 跨層」的架構決策與未來方向，與 `plans/` 區別：

| 資料夾 | 內容 | 時效 |
|---|---|---|
| `plans/` | 單一任務的執行計劃（規格書、終審報告、BDD 規範等）| 短中期 |
| `architecture/` | 整體架構決策、模組拆分、前後端契約、擴展觸發條件 | 長期 |

---

## 目前檔案

| 檔名 | 內容 |
|---|---|
| `backend-module-structure.md` | `myProgram/sales/` 後端模組拆分方案 + 每檔職責 + 擴展觸發條件 |
| `frontend-backend-contract.md` | 三層願景（前端 / 後端 / 未來資料庫）+ 推薦框架（FastAPI + Pydantic + REST + Repository Pattern）+ 接口框架延後決策紀錄 |

---

## 維護原則

- 架構決策變動時 → 更新對應檔案 + 補一行「決策日期 + 變動原因」
- 與 `.claude/CLAUDE.md` / memory 同步：高階方向寫進 memory `project-architecture-vision`，細節留在本資料夾
- 與 `resources/projectStructure/projectStructure.md` 區別：那邊是「實際結構快照」，這邊是「決策與方向」
