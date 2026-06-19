# StaticFiles no-cache + arecord stderr 收斂 — Mini SDD spec

**日期：** 2026-06-19
**類型：** Pi 實測暴露的兩個 Pi-only 小修（斷線-reset 驗收時發現）

---

## 修 1：`app.py` StaticFiles 加 `Cache-Control: no-cache`

- **檔**：`myProgram/web/app.py`
- **症狀（Pi 實測）**：前端 `app.js` 已更新（commit `6026288` 加 `resetToWelcome`）並 push/pull 到 Pi，但筆電瀏覽器仍跑**舊版** app.js（斷線時 `showReconnecting` 有跑但 `resetToWelcome` 沒跑 → 卡點餐頁）。
- **Root cause**：`app.mount("/", StaticFiles(...))` 的 Starlette StaticFiles **不送 `Cache-Control: no-cache`** → 瀏覽器快取住 app.js、重連時不重抓 → 跑舊碼。（Phase 0 `serve.py` 本為 no-cache，Phase 1 換 FastAPI StaticFiles 後掉了。）
- **改**：新增 `StaticFiles` 子類別 `_NoCacheStaticFiles`，覆寫 `get_response` 在回應加 `Cache-Control: no-cache, no-store, must-revalidate`；mount 改用它。
```python
class _NoCacheStaticFiles(StaticFiles):
    """靜態檔一律 no-cache —— 前端 app.js 更新後瀏覽器一般重整即拿新版（避免 demo 開發快取舊碼）。"""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
```
mount：`app.mount("/", _NoCacheStaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")`
- **驗證**：Windows `ast.parse`（app.py 是 Pi-only，import fastapi）；Pi：更新前端後瀏覽器**一般重整**（非硬重整）即拿到新版（斷線回歡迎畫面生效）。

## 修 2：`stt.py` arecord 子程序 stderr 收掉

- **檔**：`myProgram/stt.py`（`_default_audio_factory`）
- **症狀（Pi 實測）**：`q` 退出時印 `arecord: pcm_read:2145: read error: 中斷的系統呼叫`。
- **Root cause（非裝置問題——裝置已修好）**：本次無 `Channels count non available`，代表 `STT_ARECORD_DEVICE` 已生效、arecord 正常開麥。新訊息是 `_ArecordSource.close()` 對卡在 `pcm_read` 的 arecord `terminate()`（SIGTERM）→ read syscall 被中斷（EINTR）→ arecord 自印臨終訊息到 stderr。`Popen` 未導 stderr（`stdout=PIPE, stdin=DEVNULL`）→ 雜訊上終端。**無害**（arecord 被關閉時的正常反應）。
- **改**：`Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)` —— 加 `stderr=subprocess.DEVNULL`。
- **取捨**：一併隱藏 arecord 真實裝置錯誤（如 channel 不符）的 stderr。可接受：裝置已設定進 `~/.bashrc`；未來裝置不通會以「STT 聽不懂 / 收不到音」的行為層面顯現，非靠這行 stderr 才看得出。
- **驗證**：`python -m pytest tests/`（stt.py Windows 可 import；現有 tests/stt/ 用 fake audio_factory，`_default_audio_factory` 不被單測——改不影響測試路徑，應仍 649 綠）；Pi：`q` 退出 / 每輪 disarm 不再印 arecord EINTR。

## Out of scope
- 不改前端 / 不動 `resetToWelcome`（那個修正本身是對的，問題在快取）。
- 不改 STT 對話 / 裝置邏輯（裝置由使用者 `~/.bashrc` 設定）。
