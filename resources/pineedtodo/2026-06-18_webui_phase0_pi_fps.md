# WebUI Phase 0 — Pi fps 實機驗收

建立日期：2026-06-18
對應提交：webui Phase 0（`worktree-webui-phase0` ff-merge 進 main）
簡介：把 Glaze 玻璃點餐 UI（buildless 靜態）搬上 Pi，接 HDMI 用 Pi 桌面 Chromium 量 fps，
判定 Liquid Glass 玻璃 + 動畫在 Pi 4 GPU 上是否流暢——這是 Phase 0 的最終裁決。
**無新依賴**：字型/圖示走 CDN、伺服器用 Python stdlib，故不必 pip / apt 安裝。

## 前置
- code 已隨 `git push` 由 Stop hook 自動 sync 到 Pi（`/home/pi/Desktop/project_jiqiren`）。
- 確認 Pi 同 wifi 且**有網路**（Phase 0 字型/圖示走 CDN；離線在地化留待後續）。

## Step 1：在 Pi 啟動 webui 伺服器（單行）
```bash
cd /home/pi/Desktop/project_jiqiren && python3.11 myProgram/webui/serve.py 8137
```
（no-cache 靜態伺服器，監聽 0.0.0.0:8137；終端印 `WebUI no-cache server → http://0.0.0.0:8137/` 即成功。）

## Step 2：Pi 桌面 Chromium 開啟、全螢幕
- Pi 桌面瀏覽器開 `http://localhost:8137`，按 F11 全螢幕。
- （或同 wifi 別台裝置連 `http://raspberrypi.local:8137` 或 `http://<Pi IP>:8137`。）

## Step 3：量 fps
- Chromium F12 → ⋮ → More tools → Rendering → 勾「Frame Rendering Stats」（或 Performance 錄一段）。
- 逐一操作量 fps：① 待機↔點餐切換（漸層動畫）② 開/關結帳 sheet（玻璃 + backdrop-blur）
  ③ 加入購物車（morph + 流星刷入）④ 刪除（往上縮收合）⑤ 背景霓虹飄移。

## 驗證 / 裁決
- **≥ 50 fps 順暢** → ✅ Phase 0 過關，玻璃方向成立，可進 Phase 1（後端 FastAPI + WebSocket）。
- **< 30 fps / 明顯卡頓** → 回報哪個操作卡 → 走降規（全站 prefers-reduced-motion ／ 降 blur 層數 ／
  結帳遮罩去二次模糊 ／ 背景光暈減層）後重量。

## 回報
請回報：(1) 各操作的 fps (2) go ／ 需降規 ／ 降規後可接受 三選一 (3) 是否放行 Phase 1。
