# WebUI Phase 2 — 觸控結帳 token 修正（Mini SDD spec / hotfix）

**日期：** 2026-06-19
**類型：** Pi demo 當下 bug hotfix（先 root-cause 後補 spec，sdd.md 例外）
**對應：** Phase 2 spec `webui_phase2_2026-06-18_design.md`、commit `433b469`（commands.py 原始 token）

## 症狀（Pi 實測 2026-06-19）
顧客觸控加單後（L3），在網頁點「結帳」→ 機器人**不跳語音結帳確認**（「您即將結帳…正確嗎？」），反而回「不好意思我聽不太懂」（B-1 unclear）。語音/鍵盤打「這樣就好」則正常觸發結帳確認。

## Root cause
L3 主迴圈把顧客輸入交 `classify_intent(response, "normal")` 判定（`l2_l3_dialog.py:381` → `DialogSession._dispatch`）。「結帳」意圖由 `nlu._KG_CHECKOUT` 比對 `nlu._KEYWORDS_CHECKOUT`，該集用 **「結帳」(帳)**。

但 Phase 2 的 `commands._CHECKOUT_TOKEN = "結賬"`（**賬**），當初選它是為了對齊 `KEYWORDS_C2_CHECKOUT`（賬）—— 但那個集**只在 C-2 三選一子狀態**（`c2_second_stage` 的 `KG_C2_CHECKOUT`）才比對，**不在主迴圈 dispatch**。顧客在 L3 點結帳走的是主迴圈，需要的是 `nlu._KEYWORDS_CHECKOUT`（帳）。**帳 ≠ 賬**（兩個不同字），故 `classify_intent("結賬","normal")` 落 `無法判斷` → unclear。

實證：
```
classify_intent("結賬"/賬, "normal") -> 無法判斷   ← bug
classify_intent("結帳"/帳, "normal") -> 結帳        ← 修
classify_intent("付款",   "normal") -> 結帳
```

**為何測試沒抓到**：原 `test_checkout_token_is_member_of_keyword_set` 斷言 `token in KEYWORDS_C2_CHECKOUT`（賬）—— 驗到**錯誤的 keyword 集**（C-2 子狀態的，而非主迴圈 dispatch 實際走的 `classify_intent`）→ 測試綠但 token 對主路徑無效。教訓：token 驗證測試要斷言**實際消費路徑**的行為，不是貌似相關的鄰近 keyword 集。

## 修正
| 檔 | 改前 | 改後 |
|---|---|---|
| `myProgram/web/commands.py` | `_CHECKOUT_TOKEN = "結賬"` + 註解引用 `KEYWORDS_C2_CHECKOUT` | `_CHECKOUT_TOKEN = "結帳"` + 註解改引用 `nlu._KEYWORDS_CHECKOUT` / classify_intent（L3 主迴圈結帳路徑） |
| `tests/web/test_commands.py` | `test_checkout_token_is_member_of_keyword_set`：`assert to_token(...) in KEYWORDS_C2_CHECKOUT` | 改**行為斷言**：`assert classify_intent(to_token({"type":"checkout"}), "normal") == "結帳"`（驗 token 真能在 L3 主迴圈觸發結帳）。confirm token 測試維持 `in KEYWORDS_CONFIRM_YES`（confirm 走 `KG_CONFIRM_YES`，集正確、不動）。 |

> 其餘 token（wake `c` / order `品名數量` / confirm `正確` / pay `s`）Pi 實測皆正常，不動。

## Out of scope
- 不動 sales 對話層（NLU / C-2 / classify_intent）——既有 `帳`/`賬` 雙變體是 repo 歷史，本修只讓觸控 token 對齊主迴圈實際比對的字。
- 不統一 `_KEYWORDS_CHECKOUT`(帳) 與 `KEYWORDS_C2_CHECKOUT`(賬) 的字（另議；本 hotfix 只修觸控）。

## 驗證
- Windows：`python -m pytest tests/web/test_commands.py tests/ -q`（全綠；新行為測試會擋未來 token 漂移）。
- Pi 端：觸控加單 → 點「結帳」→ 機器人語音「您即將結帳…正確嗎？」→ 點「確認金額正確」→ 進 QR。
