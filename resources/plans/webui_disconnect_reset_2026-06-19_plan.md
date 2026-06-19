# WebUI 斷線回歡迎畫面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WS 斷線時瀏覽器在任何階段立即退回待機歡迎畫面，不凍結卡在當前頁；重連後機器人狀態自動接手。

**Architecture:** 純前端 `myProgram/webui/app.js` 改動——新增 `App.resetToWelcome()`（清 `_awaitingConfirm` + `setState({standby:true, overlay:null})`），在 `connectLive` 的 `ws.onclose`（中途斷）與 `catch`（初次連不上）各呼叫一次；重連走既有 `applyState(機器人狀態)` 路徑接手。機器人 process 不動。

**Tech Stack:** buildless JS（無打包 / 無測試框架，對齊 Phase 0/1/2）；Pi 視覺驗收。

## Global Constraints

- **繁體中文**：所有新增註解 / commit message 繁中。
- **純前端**：只動 `myProgram/webui/app.js`；不改後端 / 機器人 / 不取消訂單。
- **一斷線立即跳**（無寬限期）；重連恢復機器人當前 phase（既有鏡像，不另寫）。
- **無 JS 單元框架** → 驗證 = `node --check` 語法 + Pi 視覺驗收；`?demo=1` 路徑不受影響（`connectLive` 只 live 跑）。
- **不灰階禁用「開始點餐」**（斷線時點它仍 no-op，既有 Phase 1 行為；YAGNI）。
- **worktree**：`app.js` 在 `myProgram/` 下 → 走 worktree（純 git worktree add + `git -C` 收尾）。
- **不用 `git add -A`**：明列檔名。

---

## Task 1: 斷線回歡迎畫面（app.js 三處改）

**Files:**
- Modify: `myProgram/webui/app.js`（`App` 物件加 `resetToWelcome`；`connectLive` 的 `ws.onclose` + `catch` 各加一行）

**Interfaces:**
- Produces: `App.resetToWelcome()` —— 重置 view 為待機歡迎畫面（`_awaitingConfirm=false` + `setState({standby:true, overlay:null})`）。
- Consumes（既有）：`App.setState`、`App._awaitingConfirm`、`connectLive`、`showReconnecting`、`nextBackoff`。

- [ ] **Step 1: `App` 物件新增 `resetToWelcome()`**

在 `app.js` 的 `sendCommand(cmd) { … },` 方法（現 ~196-200 行）**之後、`pendingQty(id)` 之前**插入：
```js
  // 斷線 → 立即回待機歡迎畫面（不凍結卡當前頁）；重連後 applyState(機器人狀態) 自動接手恢復 phase。
  resetToWelcome() {
    this._awaitingConfirm = false;                      // 清掉「確認金額」本地 affordance（若斷在結帳兩拍中途）
    this.setState({ standby: true, overlay: null });    // setState 內 render() → 顯示 Standby() 歡迎畫面
  },
```

- [ ] **Step 2: `ws.onclose` 加 `resetToWelcome()`**

把 `connectLive` 內（現 ~678 行）：
```js
    ws.onclose = () => { App._ws = null; showReconnecting(); setTimeout(connectLive, nextBackoff()); };
```
改為：
```js
    ws.onclose = () => { App._ws = null; App.resetToWelcome(); showReconnecting(); setTimeout(connectLive, nextBackoff()); };
```

- [ ] **Step 3: `catch` 加 `resetToWelcome()`**

把 `connectLive` 的 catch 區塊（現 ~680-683 行）：
```js
  } catch (_) {
    showReconnecting();
    setTimeout(connectLive, nextBackoff());   // /api/state 失敗（server 還沒起）→ 退避重試
  }
```
改為：
```js
  } catch (_) {
    App.resetToWelcome();                     // 初次連不上也先顯示歡迎畫面，不卡空白頁
    showReconnecting();
    setTimeout(connectLive, nextBackoff());   // /api/state 失敗（server 還沒起）→ 退避重試
  }
```

- [ ] **Step 4: 語法驗證**

Run（在 worktree）：`node --check myProgram/webui/app.js`
Expected: 無輸出（語法 OK）。

- [ ] **Step 5: 程式碼自檢（無 JS 測試框架）**

人工核對：
1. `resetToWelcome` 只改 view（`_awaitingConfirm` + `setState standby/overlay`），不碰 cart / 不送 WS / 不動機器人。
2. `ws.onclose` 與 `catch` 各只加一行 `App.resetToWelcome();`，其餘原樣（`App._ws=null`、`showReconnecting`、重連 setTimeout 都在）。
3. 重連路徑（`fetch` 成功 → `applyState` → `render` → `hideReconnecting`）未動 → 重連自動恢復機器人 phase。
4. `?demo=1` 不受影響（`connectLive` 只在 `App._live` 跑）。

- [ ] **Step 6: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "fix(webui): 斷線立即回待機歡迎畫面（任何階段不凍結卡當前頁）"
```

---

## Pi 視覺驗收（收尾，非 code）

worktree 收尾 merge/push 後，Pi 端 `python3.11 -m myProgram --web` + 筆電連線：
- 點餐 / 結帳任一階段 → Pi `Ctrl+C` 停 server → 筆電**立即**回歡迎畫面 + 右上「重新連線中」（不卡點餐頁）。
- 重啟 server → 筆電自動恢復機器人當前 phase（cart 不丟）。
- 初次：先停 server 再開筆電頁 → 顯示歡迎畫面（非空白）+ 重新連線中；起 server → 自動連上。

> 這項列入 worktree 收尾後的 pineedtodo / 口頭請使用者驗（無 JS 自動測試可代替）。

---

## Self-Review

**1. Spec coverage：** spec「In：onclose + catch 重置 view」→ Task 1 Step 1-3 ✓；「resetToWelcome 定義」→ Step 1 ✓；「重連鏡像接手」→ 既有路徑未動（Step 5.3 核對）✓；「立即跳 / 無寬限期」→ 直接呼叫無 timer ✓；「純前端 / 不動後端」→ Global Constraints + Files 只列 app.js ✓；「Pi 視覺驗收」→ 收尾段 ✓。範圍外（灰階按鈕 / 寬限期 / 後端）皆未納入 ✓。
**2. Placeholder scan：** 無 TBD / 模糊步驟；每步給確切 code + 確切指令。
**3. Type consistency：** `resetToWelcome()`（Step 1 定義）↔ `App.resetToWelcome()`（Step 2/3 呼叫）一致；`setState` / `_awaitingConfirm` / `standby` / `overlay` 皆既有欄位（Phase 0/2 已存在）。
