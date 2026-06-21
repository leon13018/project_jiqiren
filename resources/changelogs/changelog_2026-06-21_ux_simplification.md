# Changelog — demo 終端淨化 + 控制模式重構（鍵盤 → web/語音/flag）（2026-06-21）

> 詳細設計在各 spec（`resources/specs/`）；本檔記結論 + commit + 驗證狀態。
> 起點：STT + 觸控/啟動弧（見 `changelog_2026-06-20_touch_ux_startup.md`）收尾後，使用者逐項 Pi 實測 → 下一步，把 demo 終端「淨化到只剩必要啟動提示」、控制權從鍵盤移交給 **web/語音 + `--模式` flag**。
> **驗證**：全程 `py -3.14 -m pytest` 綠（收尾 main **710 passed**）；多數行為類改動**使用者已 Pi by-ear 驗收 ✅**（逐項實測後才提下一步），最後的 `[模式]` 啟動行 Pi 待驗。

## 淨落地（留在 main）

| 成果 | commit | 驗證 |
|---|---|---|
| **移除啟動橫幅 + 操作小抄**：`main()` 開頭 `=`*50 橫幅 + 「操作小抄」chat-driven 鍵位說明整段刪除；啟動直接進選單/模式 | `e2e4c9f`（spec `2cb02ac`）| pytest ✅ / Pi ✅ |
| **移除 L1 待機/客服模式**：商家層只保留「叫賣」；`run_l1` 移 key 2/3 分派、刪 `_run_l1_standby`/`_run_l1_service`/`L1_STANDBY_ENTRY_PROMPT` + 對應測試；選單只剩「1 叫賣 + q」。**保留** `SERVICE_PHONE` 與 L2-L4 顧客客服 confirm（不同功能） | `4fe2d94`（spec `a111947` / stale scrub `b52a6ea`）| pytest ✅ / Pi ✅ |
| **`SALES_QUIET` → `SALES_VOICE`（反轉預設）**：機器人 echo（`[語音]`/`[動作]`/`[模擬提示]`）改**預設隱藏**，`SALES_VOICE=1` 才顯示（推翻 06-20 `SALES_QUIET` 的預設全顯示 `f529690`）；導航 + 錯誤 ⚠️ 恆顯示 | `4d85227`（spec `9c863f5` / doc `ce67f28`）| pytest ✅ / Pi ✅ |
| **`--hawk` 進場 flag + `SALES_KEYBOARD` gate + 啟動防呆**：模式入口改 CLI flag（`--hawk` 跳選單直進叫賣，複用 `enter_hawk_immediately`、一字之改）；鍵盤預設關（`SALES_KEYBOARD=1` 才啟 stdin reader thread，`inject()` web/語音不受影響）；退出 Ctrl+C；**防呆**：無 mode flag 且鍵盤關 → 印訊息 early return 防卡死 | `27d1971`+`6acdea7`（spec `ac550b6` / doc `6a346da`）| pytest ✅ / Pi ✅ |
| **移除 hawk entry「進入叫賣模式」print**：`_run_l1_hawk` 每次進場印的導航行刪除（連帶孤兒 `L1_HAWK_ENTRY_PROMPT` 常數 + stale 參照）；SALES_VOICE 關時進 hawk 終端全靜 | `1bcc20c`（spec `9131276` / doc `9697a37`）| pytest ✅ / Pi ✅ |
| **加 `[模式] 叫賣模式` 一次性啟動提示**：`_run_wiring` 啟動防呆通過後，`--hawk` 時印一次模式標示（對齊 `[webui]` 啟動提示風格；非 `_run_l1_hawk` 每次進場印）。未來新模式各自加行（YAGNI，不建 map） | `b012d9b`（spec `108bc2b`）| pytest ✅ / Pi 待驗 |

## 控制模式重構（本弧核心）

**動機**：demo 由 web UI（client 筆電）+ 觸控/語音呈現，Pi 終端的 echo / 橫幅 / 每次進場提示與 web 鏡像重複、是雜訊；鍵盤控制也非 demo 路徑。

**設計（三輸入路徑共用單一 input queue 的既有架構為基礎）**：
- 鍵盤（`InputReader._loop` 讀 stdin）/ web 觸控（`commands.to_token → input_reader.inject`）/ 語音 STT（`SttWorker(sink=input_reader.inject)`）原本都餵同一 queue。
- **gate 鍵盤** = `SALES_KEYBOARD=0`（預設）時不啟動 stdin reader thread；`inject()`（web/語音）/`read()`/`shutdown()` 全不受影響 → 關鍵盤後 web/語音完整驅動。
- **模式入口改 flag**：L1 選單需鍵盤按 `1` 進叫賣，但 web token 無 `1`、語音在 L1 未開麥 → 純關鍵盤會卡選單。解法用 `--hawk`（`main → logic.run(start_hawk) → SalesMachine.enter_hawk_immediately`）首次進場直接 hawk。
- **啟動防呆**（使用者追加）：無 mode flag 且鍵盤關（會卡無法操作的選單）→ 主動擋下印訊息結束；合法組合 = 有 `--hawk`，或 `SALES_KEYBOARD=1`（選單+鍵盤）。
- **典型 demo 啟動**：`python3.11 -m myProgram --web --hawk` → 直接叫賣、鍵盤無效、web/語音控制、Ctrl+C 退出；終端只剩 `[模式] 叫賣模式` + `[webui] …` 兩行啟動提示。

## 流程沉澱（教訓）

- **迭代式 UX 收斂**：使用者每項 Pi by-ear 實測通過才提下一步（橫幅 → L1 模式 → echo 反轉 → 鍵盤 gate → entry print → 啟動提示）；小改動走 mini-SDD 主 agent 自 patch，中改動（L1 移除 / VOICE 反轉 / --hawk）派 sales-coder + 三段 reviewer。
- **「反過來」需在 approval gate 講清語意**：`SALES_QUIET→SALES_VOICE` 是反轉預設 + 改名，gate 明確「控制整組 echo（非只 `[語音]`）」避免誤解。
- **防呆 > 留坑**：edge case（無 flag + 鍵盤關卡死）從原「不處理」改使用者追加的「主動擋」；連帶把 6 個既有 `--web` 佈線測試補 `--hawk`（否則被防呆擋）。
- **複用既有機制 + YAGNI**：`--hawk` 複用 `enter_hawk_immediately`（首次進場初值改由 flag 帶入，一字之改）；只一個模式 → 不建 mode→name map。
- **worktree Pyright 假警報**：多次 mid-edit「`X` is not defined」/「import could not be resolved」皆環境性（pytest 綠 + Read 實檔已證 runtime OK）；已記 memory `lsp-servers-setup`，往後不據此誤判。
- **Iron Law + 對抗審查持續抓 stale**：每輪親自重跑 pytest + Read 實檔 + grep 驗孤兒；sales-coder 多次透明補抓 plan 漏列的同款 stale 斷言/描述（fix-found-during-refactor）。

## 旁註：反思 / eval（非本 UX 弧，列此供當日全貌）
- 反思處理：`grep-case-sensitive-false-clear`（採納 → conventions.md「清理後 grep 必加 `-i`」`6a9962b`；源自 06-20 OpenCv case-sensitive 漏網教訓）轉 eval 場景 **s12** 並 graduation PASS（`4ff9d86`，落檔 `evals/iteration-7/`，含 `OpenCv→OpenCV` 正規化 `2509921`）；`fake-driver-masks-production-dead-path`（採納，已由 06-20 hawk_loop spec 修，eval 否）。歸檔 `reflections/archive/proposals_archived_2026-06-21b.md`。
