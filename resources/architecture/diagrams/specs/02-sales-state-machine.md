# 圖② L0–L5 銷售對話狀態機 — 畫圖 spec

> 來源:`20-sales-state-machine.md`(依碼寫的權威 digest)+ 實讀 `states/machine.py`(2026-06-21 核對 backbone 無誤)。圖①theme 為基準。

## 主題一句話
單線程規則匹配對話狀態機:`SalesMachine.run()` while-loop 在 4 個運行層 **L1 → dialog → L4 → L5** 間轉移,**由世界狀態(cart 空/非空)驅動**,非動作歷史;交易結束經 `enter_hawk` 連續叫賣回 L1。L0 是底層共通 NLU(非運行層)。所有 confirm 閘**錢包保守**(silent/timeout 退保守側)。

## 核對過的運行層(權威)

| 層 | state key | entry invariant | display phase | run_* → Transition |
|---|---|---|---|---|
| **L1** 商家模式(叫賣/待機) | `l1` | cart 空 | `standby` | `run_l1 → "L2"`→dialog;`→ None`→程式終止 |
| **dialog** L2/L3 合一(cart 驅動) | `dialog` | cart 空 | `ordering`(+`checkout_confirm`) | `run_dialog → "L4"`→l4;`"L1_enter_hawk"`→l1(hawk) |
| **L4** 結帳(印金額+掃碼) | `l4` | cart 非空 | `checkout` | `run_l4 → "L5"`→l5;`"L1_enter_hawk"`→l1(hawk) |
| **L5** 致謝(do_action→clear→sleep) | `l5` | cart 非空 | `thankyou`(帶 paid) | `run_l5 →` 無條件 →l1(hawk) |

> **L0** 不是運行層 → 底層共通 NLU/keyword 白名單(`nlu.py`+`constants/keywords.py`),被所有層共用,無 `run_l0`。畫成底部基座帶。

## 轉移表(箭頭 + 條件標籤)
```
[start] ─────────────────────────────────────────→ L1
L1   ──('t' 觸控開始點餐)──────────────────────────→ dialog
L1   ──(q 兩次 / exit)─────────────────────────────→ [程式終止]
dialog(L2,cart空)──(加單成功 cart→非空)────────────→ dialog  (自迴圈:下輪自動 L3 模式,無 transition)
dialog(L2)──(timeout/3rd 想一下/unclear 上限/拒絕)─→ L1  (exit_a;cart 空不清) ★enter_hawk
dialog(L3)──(結帳 confirm = yes)──────────────────→ L4
dialog(L3)──(拒絕/C-2 取消/checkout 否認超時)──────→ L1  (清 cart) ★enter_hawk
L4   ──(終端 's' / 客服 scan = 鏈路A)──────────────→ L5
L4   ──(cancel / 客服 no / 36s budget 耗盡 = B/D)──→ L1  (清 cart) ★enter_hawk
L4   ──(客服 yes「繼續」)──────────────────────────→ L4  (自迴圈:reset 兩計時器,不轉移)
L5   ──(無條件)───────────────────────────────────→ L1  ★enter_hawk
```
★ **enter_hawk 回流(本圖核心循環)**:4 個出口(dialog reject/timeout、L4 cancel、L5 完成)設 `enter_hawk_immediately=True` → 下次 L1 跳主選單**直接連續叫賣**。

## 跨層 confirm 閘(錢包保守 · 橫切,畫成獨立 cluster)
| 閘 | 計時 | 規則 | 觸發層 |
|---|---|---|---|
| Cancel confirm | 6s | NO 先於 YES;silent/timeout → **YES(取消)** | dialog 拒絕 / checkout cancel / unclear / L4 拒絕 / invalid_qty 否定 |
| Service confirm | 24s | yes/no/scan;default **no**(退) | L2/L3/qty/invalid(`SERVICE_CONFIRM`)、L4(`_SCAN`,啟 's' fast path) |
| Checkout confirm | 12s | 六態;**必須明確才進 L4**(保護錢包) | dialog L3 C-1 |
| C-2 自動結帳 | 6s | L3 timeout(12s)/4th 想一下 → CANCEL 優先;silent → 經 confirm 結帳 | dialog L3 |
| qty / invalid-qty reask | 12s | 缺/無效數量重問(max 3 / reset 2) | dialog 加單 |

> L4 wall-clock **v3 雙計時器**:`L4_TOTAL_BUDGET=36s`(耗盡=鏈路 D 清 cart 退)+ `QR_REFRESH=12s`(36=12×3,每循環重印明細+重 speak);confirm 期間暫停+補償。

## 色彩語意(本圖專用,配 legend)
藍=L1 待機 / 綠=dialog 對話(cart 驅動)/ 橘=L4 結帳 / 紫=L5 致謝 / 青=confirm 閘(錢包保守)/ 灰=L0 共通 · 終止 · 外部。

## 版面(1960×1280 基準,沿用圖①theme;不夠再加寬)
- 標題 FIG.02 頂置中。
- 主流:**L1 → dialog → L4 → L5 橫排**(上半),每格 eyebrow 標 `phase` + cart invariant;自迴圈(dialog 加單、L4 客服繼續)畫小 loop。
- **enter_hawk 回流**:4 出口 → L1 的弧線(下方繞回),高亮為核心循環;終止節點(灰)接 L1。
- **confirm 閘 cluster**(青):獨立子框列 5 閘 + 計時 + 錢包保守規則,虛線連 dialog/L4(標「任一 read 點偵測拒絕→進閘」)。
- **L0 共通 NLU** 灰基座帶(底部,橫跨,標「被所有層共用」)。
- legend 左上;note(核心設計:cart 唯一驅動 / 錢包保守 / enter_hawk)補空角。
- 箭頭標籤一律壓在線中段(圖① 慣例);卡片內容垂直置中;組件間隙 ≥30px 不相碰。
