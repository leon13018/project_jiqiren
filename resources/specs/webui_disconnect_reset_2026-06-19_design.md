# WebUI 斷線回歡迎畫面 設計（Design Spec）

**日期：** 2026-06-19
**狀態：** 設計已與使用者敲定 → 轉 writing-plans
**對應：** 前端 webui Phase 0+1+2 ✅（`roadmaps/html_ui_plan.md`）；本案是 Phase 2 後的 UX 修補，延伸 Phase 1 hardening「斷線不跳轉」修正。

---

## 目標（Goal）

client 瀏覽器**在任何階段（點餐 / 結帳 / 感謝）WS 斷線時，立即退回歡迎（待機）畫面**——而非凍結卡在當前頁。重連後機器人推來的狀態自動接手、恢復當前 phase。

**現況問題**：`connectLive` 的 `ws.onclose` 只 `showReconnecting()` + 重連，**不改 view** → 斷線當下在哪頁就凍在哪頁（點餐頁卡死、按鈕點了也沒反應卻看不出原因）。只有「斷線時剛好在待機」才正確顯示歡迎畫面。

---

## 範圍（Scope）

**In：**
- `myProgram/webui/app.js`：斷線（`ws.onclose`）與初次連不上（`connectLive` 的 `catch`）時，先把 view 重置為待機歡迎畫面，再 `showReconnecting()` + 重連。

**Out（不做）：**
- 後端 / 機器人 process 任何改動（純瀏覽器 view 行為；機器人保留自己的 cart / phase）。
- 不取消 / 不重置機器人的訂單（斷線只影響瀏覽器顯示）。
- 不灰階禁用歡迎頁「開始點餐」按鈕（斷線時點它仍 no-op，既有 Phase 1 行為；YAGNI）。
- 不加斷線寬限期（使用者敲定：**一斷線立即跳**）。

---

## 決策（已與使用者敲定）

| 決策 | 選擇 | 理由 |
|---|---|---|
| 重置時機 | **一斷線立即跳歡迎畫面** | 最簡、符合「任何階段斷線都回一開始畫面」字面；穩定同區網實際罕見瞬斷，立即跳的代價（瞬斷閃一下歡迎再跳回）可忽略。 |
| 重連後 | **恢復機器人當前 phase（既有鏡像）** | 架構決定：重連即 `fetch /api/state` → `applyState(機器人狀態)` 接手。「停在歡迎」不可行——機器人若仍在 L3，待機頁點「開始點餐」送 `wake`(`c`) 對 L3 無效。 |
| 範圍 | **純前端 app.js** | view 行為，無業務 / 後端牽連。 |

---

## 架構 / 元件 / 資料流

```
WS onclose（中途斷） ─┐
fetch catch（初次連不上）─┴─▶ App.resetToWelcome() ─▶ render() 顯示 Standby() 歡迎畫面
                                       + showReconnecting()（右上角指示器，#app 外固定定位）
                                       + setTimeout(connectLive, backoff)  ← 既有重連

重連成功 ─▶ fetch /api/state ─▶ applyState(機器人當前狀態) ─▶ render()（恢復 phase）─▶ hideReconnecting()
```

**新增 `App.resetToWelcome()`**：
```js
resetToWelcome() {
  this._awaitingConfirm = false;              // 清掉「確認金額」本地 affordance（若斷在結帳兩拍中途）
  this.setState({ standby: true, overlay: null });   // setState 內 render → Standby() 歡迎畫面
}
```

**接點**（`connectLive` 內，既有兩處各加一行 `App.resetToWelcome()`）：
- `ws.onclose`：`App._ws = null; App.resetToWelcome(); showReconnecting(); setTimeout(connectLive, nextBackoff());`
- `catch (_)`：`App.resetToWelcome(); showReconnecting(); setTimeout(connectLive, nextBackoff());`

---

## 錯誤處理 / 邊緣

- **重連時機器人狀態**：仍在點餐 → 歡迎跳回點餐頁（cart 完整、機器人保留）；已逾時回 hawk → 顯示待機。皆正確鏡像。
- **初次載入 server 未起**（catch，`_catalog` 仍 null）：`resetToWelcome` 顯示歡迎畫面（`Standby()` 不需 catalog）→ 不再卡空白頁。
- **「重新連線中」指示器**：固定定位、append 到 `body`（非 `#app`），`render()` 重畫 `#app` innerHTML 不沖掉它。
- **斷線期間歡迎頁觸控**：「開始點餐」→ `sendCommand({wake})` 在 `_ws` 非 OPEN 時 no-op（既有 Phase 1 修正，原樣保留）。
- **冪等**：長斷線每個 backoff 週期 connectLive 失敗 → 再次 `resetToWelcome`（重畫歡迎，無副作用）。

---

## 測試

- 無 JS 單元框架（buildless，對齊 Phase 0/1/2）→ **Pi 視覺驗收**：點餐 / 結帳任一階段停掉 server（Pi Ctrl+C）→ 筆電**立即**回歡迎畫面 + 「重新連線中」；重啟 server → 自動恢復機器人當前 phase（cart 不丟）。
- `?demo=1`（非 live）路徑不受影響（`connectLive` 只在 live 跑）。

---

## 範圍外 / 後續

- demo 若覺得瞬斷閃一下歡迎突兀 → 再議寬限期（目前 YAGNI）。
- 斷線時灰階「開始點餐」按鈕做更明確的視覺禁用 → 視 demo 體感再議。
