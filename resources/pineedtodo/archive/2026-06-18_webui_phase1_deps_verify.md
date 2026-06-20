# WebUI Phase 1 — Pi 依賴安裝 + 端到端整合驗收

建立日期：2026-06-18
對應提交：webui Phase 1（`worktree-webui-phase1` ff-merge 進 main，Tasks 1–7）
簡介：機器人主程式加了 `--web` 模式——`python3.11 -m myProgram --web` 會在背景多跑一條 FastAPI（uvicorn）伺服器（port 8137），把點餐 / 購物車 / 結帳 / 感謝即時狀態用 WebSocket 推給同 wifi 的 client 筆電瀏覽器，讓 Phase 0 的 Glaze UI **即時鏡像**機器人對話。**這是 Phase 1 的最終驗收**。

> **與 Phase 0 差異**：Phase 0 用 `serve.py`（純靜態）；Phase 1 改由 `--web` 的 FastAPI server 出靜態 + WS，**不再需要單獨跑 serve.py**。

## 前置
- code 已隨 `git push` 由 Stop hook 自動 sync 到 Pi（`/home/pi/Desktop/project_jiqiren`）。
- Pi 同 wifi 且**有網路**（前端字型 / 圖示走 CDN；FastAPI 裝依賴也要網路）。
- STT / TTS 已 Pi 定版可用（Phase 1 是在完整機器人上加 web 鏡像）。

## Step 1：裝 Python 依賴（純 uvicorn，**非** `uvicorn[standard]`）
```bash
cd /home/pi/Desktop/project_jiqiren && python3.11 -m pip install fastapi uvicorn
```
- **為何不要 `uvicorn[standard]`**：`[standard]` 會拉 `uvloop`/`httptools`（C 擴充），Pi 可能無 wheel 要 source build。純 `uvicorn` 是純 Python（asyncio + h11），夠用。
- **若裝失敗（piwheels / GLIBC / build 錯）→ 先回報，不要自行裝 `[standard]` 或其他變體**；我評估降級（websockets-only / SSE）。

## Step 2：驗 import
```bash
python3.11 -c "import fastapi, uvicorn, pydantic; print('deps ok')"
```
印 `deps ok` 即三套件就緒。

## Step 3：起機器人 web 模式
```bash
python3.11 -m myProgram --web
```
- 終端印 `[webui] FastAPI 已啟動 → http://0.0.0.0:8137/...` 即成功。
- **若印 `[webui] web 依賴缺失…退回無 web 模式`** → Step 1 沒裝成功（機器人仍會正常跑、只是沒 web），回 Step 1。

## Step 4：client 筆電端到端鏡像驗收（最關鍵）
1. **筆電瀏覽器**開 `http://raspberrypi.local:8137`（解析不到用 Pi `hostname -I` 的 IP）。初始應顯示**待機**（歡迎光臨）畫面。
2. **在 Pi 終端**用鍵盤驅動機器人（不必語音也能驗）：按 `1`（叫賣）→ `c`（模擬偵測顧客 → 進對話）→ 輸入 `冰紅茶兩瓶`。
   → **筆電畫面購物車應即時長出「冰紅茶 ×2」**（由左流星刷入）。
3. 再輸入 `刮刮樂一張` → 畫面再長出一列。輸入 `結帳` → 確認後 → **畫面切到結帳 QR**。完成付款流程 → **畫面切到感謝頁、顯示已付金額**。
4. （可選）用**語音**走一遍，確認語音點餐也即時鏡像。

## Step 5：斷線重連
- Pi 終端 `Ctrl+C` 關掉機器人 → 筆電畫面角落應出現「重新連線中…」→ 重新 `python3.11 -m myProgram --web` → 筆電自動恢復鏡像。

## 驗證 / 裁決
- **各階段即時鏡像正確 + 延遲可接受** → ✅ Phase 1 過關，可進 Phase 2（觸控雙向 / 真 QR 金流）。
- **某階段不對 / 延遲明顯 / 連不上** → 回報哪一步 + 終端有無錯誤訊息 → 我 debug。

## 回報
請回報：(1) fastapi/uvicorn 裝成功？(import ok？) (2) `--web` 起得來？(3) 待機→點餐→購物車增量→結帳 QR→感謝 各階段鏡像對不對？(4) 延遲體感？(5) 放行 Phase 2？
> 裝成功後我會把 `fastapi` / `uvicorn` 補進 `resources/requirements/raspberry_pi_setup.md`（該檔只記**已確認安裝**項）。
