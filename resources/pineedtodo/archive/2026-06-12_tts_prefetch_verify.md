# TTS prefetch 實機驗證（perf_w2）

- 建立日期：2026-06-12
- 對應提交：`75b960e` — perf(tts): reuse persistent event loop in worker thread；
  `104db16` — perf(tts): prefetch next utterance during playback via double buffer
- 簡介：TTS worker 改為「當前句播放期間預合成下一句」（雙 buffer），連發句之間的
  靜默等待應從「一次雲端合成時間（約 0.5–2 秒）」降到接近 0。純 Pi 端聽感驗證，
  **無新依賴、無系統設定變更**——只需跑 demo 實聽。

## 驗證步驟

1. Pi 端確認已同步到含上述兩 commit 的 main（Stop hook 會自動 sync；
   手動確認：`cd /home/pi/Desktop/project_jiqiren && git log --oneline -3`）。
2. `python3.11 -m myProgram` 啟動。
3. **場景 A（hawk→L2 連發）**：等叫賣 slogan 開始播 → 模擬顧客接近觸發 L2——
   聽「slogan 播完」到「您好，請問需要購買什麼東西嗎？」開始播之間的間隔。
4. **場景 B（L4 循環刷新連發）**：點餐進 L4 後等 12 秒循環——聽「明細重印提示」
   與「請掃碼」連發兩句之間的間隔。

## 驗證段（預期輸出／行為）

- **預期**：連發第二句幾乎緊接第一句播完（剩 ALSA drain 0.3s 級的自然停頓）；
  改動前是明顯 0.5–2 秒無聲等待。
- **不變行為抽查**：對話計時倒數照常從語音播完才開始；按 q 退出時播放中語音立刻停止
  （shutdown terminate 不變）；單句場景（一般對話一問一答）聽感應與改動前無差。
- **故障排除**：
  - 若句間間隔沒變短：SSH log 看兩句之間是否有 `[語音] ⚠️ TTS 失敗（階段=synth）`
    ——prefetch 失敗會回退為逐句合成（功能正常、只是沒加速），多半是網路抖動。
  - 若出現語音內容錯亂／互踩：立即回報（理論不可達的 buffer race），
    revert `104db16` 即恢復原行為。
- **回報**：兩場景間隔是否明顯縮短＋有無任何異常，回報後此單關閉。
