# myProgram/web/ — 本層導引

> **本層結構索引：`.claude/code_map.md`——任何「web 裡的檔在哪 / 結構」務必第一優先讀它。**

FastAPI 顯示鏡像 **transport 層**（與 `sales/` 業務邏輯分離）：把機器人狀態 / 購物車 / 結帳即時鏡像到同 wifi 瀏覽器。`sales/` 只多呼叫一個注入的 `display` 回呼，不知道 web 存在。

- **Windows 可 pytest（純 stdlib）**：`bus.py`（asyncio 廣播橋）、`display.py`（cart→dict 映射，只 import sales 常數）→ `tests/web/`。
- **Pi-only（import fastapi / uvicorn / pydantic，Windows 裝不了 → 不可 import / run，只能 `ast.parse`）**：`models.py`（Pydantic DTO）、`app.py`（路由 + StaticFiles）、`server.py`（uvicorn 背景執行緒）。真驗在 Pi。
- 完整安全紅線（不改 vendor / Windows 不裝依賴 / 不 import vendor SDK）+ 繁中規範見 root `CLAUDE.md`；workflow 協議見 `project-01-workflow` skill，本檔不重述。
