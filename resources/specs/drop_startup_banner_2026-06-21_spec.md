# drop_startup_banner — Mini SDD spec

- **檔**：`myProgram/main.py:374-384`（`main()` 開頭的啟動橫幅 + 操作小抄 print 區塊）
- **改前**：
  ```python
  print("=" * 50)
  print("Project_01 互動式銷售輔助機器人 — 模擬模式")
  print("（單線程對話 + 背景 worker 處理語音 / 動作 / input）")
  print("=" * 50)
  print("操作小抄（chat-driven 模擬）：")
  print("  [L1 商家層] 1=叫賣 / 2=待機 / 3=客服 / q=退出")
  print("    └ 進叫賣後按 't' = 開始點餐（模擬觸控）→ 轉 L2 對話")
  print("    └ 進待機後按 'r' 回主選單（其他鍵無效）")
  print("    └ 進客服印電話後自動回主選單")
  print("  [L2-L5 顧客對話層] 打字=顧客語音回應 / 空 Enter=模擬 timeout")
  print("=" * 50)
  ```
- **改後**：整段刪除。`main()` docstring 後直接接背景預熱 worker thread；啟動終端直接進「請選擇模式」選單。
- **Why**：使用者要求終端不再印這段啟動橫幅 + 操作小抄。demo 經 web UI（client 筆電）/ 觸控操作，終端這段是雜訊；操作鍵說明已不需印在終端。Pi 實機證據：2026-06-21 `python3.11 -m myProgram --web` 啟動畫面，使用者標注此區塊「不在印」。
- **Out of scope**：不動「請選擇模式」選單（logic/states 印，仍需要）；不動其他 print；不加 env 旗標（直接刪，非條件抑制）。
- **驗證**：
  - `py -3.14 -m pytest tests/sales/ tests/stt/test_main_wireup.py`（無測試斷言橫幅 → 應全綠、數量不變）
  - Pi 端 `python3.11 -m myProgram --web`：啟動不再印橫幅 + 操作小抄，直接顯示模式選單。
