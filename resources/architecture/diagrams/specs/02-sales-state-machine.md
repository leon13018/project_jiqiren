# 圖② L0–L5 銷售對話狀態機 — 畫圖 spec

> 來源:`20-sales-state-machine.md`(依碼寫的權威 digest)+ 實讀 `states/machine.py`(2026-06-21 核對 backbone 無誤)。圖①theme 為基準。

> ✅ **已交付（2026-06-22 Wave A）**：`02-sales-state-machine.{html,png,svg}` 三式同名。最終版面：4 運行層橫排 + enter_hawk 金回流主角 + confirm 閘 cluster + L0 基座 + 底排（enter_hawk 圖例左 / L0 內容小卡右），**以交付 html 為準**。

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

---

## 畫圖計畫（SDD plan, 2026-06-22 重畫；2026-06-22 全碼複核完成）

> step 3–4 設計定案。**碼複核（鐵則 1）**:逐項讀 `machine.py`(backbone/_emit/_PHASE_BY_STATE)、`timing.py`(全計時常數)、`l2_l3_dialog.py`(轉移+confirm)、`l4.py`(雙計時器+鏈路)、`_timed_confirm.py`(Cancel/Service/InvalidQty 行為)、`l1.py`('t'→L2·'q'×2→終止·hawk 輪播)、`l5.py`(序列→無條件 L1)、`_cancel_confirm.py`/`_invalid_qty_reask.py` —— **全數核對無誤**,計時與行為皆對得上。座標為近似 + lane 規則,實際像素由實作者 render 迴圈微調。骨架 + theme 同圖①。

### thesis / 主角
**enter_hawk 回流循環**:4 個交易結束出口(dialog reject/timeout、L4 cancel、L5 完成)設 `enter_hawk_immediately=True` → 下輪 L1 跳主選單直接連續叫賣 —— 點明「這是循環(攤位連續做生意)不是直線」。用**暖金 `.hawk` 弧 + `ah-hawk`** 把回流弧做成視覺焦點(下方繞回 L1);其餘轉移安靜 `.flow`。

### 畫布
`.stage` **1960 × 1360**(沿用圖②舊基準;confirm cluster + 回流弧 + L0 基座需空間)。不包 process 外框(本圖非 process 視角);背景 theme。

### 色彩 legend（左上 `.legend`，6 列）
藍=L1 待機(standby) / 綠=dialog 對話(cart 驅動,ordering) / 橘=L4 結帳(checkout) / 紫=L5 致謝(thankyou,帶 paid) / 青=confirm 閘(錢包保守) / 灰=L0 共通 · 終止 · 外部。

### 主流節點（4 運行層卡,上半橫排;eyebrow=phase+cart invariant）
- **L1**(blue) — eyebrow `STANDBY · cart 空`;name `L1State · run_l1`;meta `叫賣輪播 + 主選單`;desc `'t'(觸控/web wake)→dialog;'q'×2→終止`。
- **dialog**(green) — eyebrow `ORDERING · cart 驅動`;name `DialogState · run_dialog`;meta `L2/L3 合一,cart 即時推導模式`;desc `加單成功→自迴圈;結帳 confirm→L4`。
- **L4**(orange) — eyebrow `CHECKOUT · cart 非空`;name `L4State · run_l4`;meta `雙計時器 budget 36s + QR 12s`;desc `掃碼→L5;cancel/客服no/36s→L1`。
- **L5**(purple) — eyebrow `THANKYOU · cart 非空·帶 paid`;name `L5State · run_l5`;meta `do_action→clear cart→sleep 3s`;desc `無條件→L1`。

### 自迴圈（小 loop 箭頭,標籤在 loop 上）
- dialog 自迴圈:`加單成功 cart 空→非空`(mode L2→L3,無 transition;cart 驅動核心)。
- L4 自迴圈:`客服(24s)=yes 繼續 → reset 兩計時器`。

### 轉移邊（`.flow`,標籤壓線中段;條件已碼核對）
- `[start]`(灰)→ L1。
- L1 → dialog:標 `'t' 開始點餐`。
- L1 → `[程式終止]`(灰):標 `'q'×2 / exit_program`。
- dialog → L4:標 `結帳 confirm(12s)=明確 yes`。
- L4 → L5:標 `終端 's' / 客服 scan(鏈路 A 掃碼)`。
- **enter_hawk 回流(★金弧,3 條匯入 L1,共標 `enter_hawk · 連續叫賣`)**:
  - dialog → L1:子標 `timeout / 想一下上限 / unclear上限 / 拒絕(cancel 6s) / 客服(24s)否`(cart 非空清 cart、空不清)。
  - L4 → L1:子標 `cancel(鏈路B) / 客服(24s)否 / 36s budget 耗盡(鏈路D)`(清 cart)。
  - L5 → L1:子標 `無條件`。

### confirm 閘 cluster（青,獨立子框列 5 閘;虛線 `.async` 連 dialog/L4,標「任一 read 點偵測 → 進閘」）
| 閘 | 計時 | 規則(錢包保守) | 觸發 |
|---|---|---|---|
| Cancel confirm | 6s | NO 先於 YES;silent/timeout→**取消** | dialog 拒絕 / checkout-confirm cancel / unclear-final 退出 / L4 拒絕 |
| Service confirm | 24s | yes/no/scan;default **no(退)** | dialog 客服 / L4 客服(啟 scan) / qty·invalid_qty 客服 |
| Checkout confirm | 12s(亂答上限 5) | 六態;**必須明確才進 L4** | dialog L3 C-1(語音/沉默自動/UI 三源殊途同歸) |
| C-2 自動結帳 | 6s | 三選一(繼續/結帳/取消);**CANCEL 優先**;silent→經 confirm 結帳 | dialog L3 timeout(12s) / 第 4 次想一下 |
| qty / invalid-qty reask | 12s(reset 2,總 36s) | 缺/無效數量重問;否定→二選一 6s(保守**保 cart**) | dialog 加單缺/無效數量 |

### L0 共通 NLU（灰基座帶,底部橫跨）
標 `L0 · nlu.classify_intent + constants/keywords 白名單;被所有運行層共用;非運行層、無 run_l0`。意圖:拒絕/想一下/結帳/客服/想買無商品/商品/退出/繼續。

### note（空角 `.note`,3 點）
- **cart 是唯一驅動**:L1↔dialog↔L4↔L5 由世界狀態(cart 空/非空)決定、非動作歷史;dialog 內 cart 即時推導 L2/L3 模式(刪商品 cart 變空 → 自動回問需求,無需 transition)。
- **錢包保守**:所有 confirm 閘 silent/timeout 退保守側(取消側 / 不進 L4),保護顧客錢包。
- **enter_hawk 回流**:交易結束 4 出口設旗號 → 下輪 L1 跳選單連續叫賣(攤位連續做生意)。

### 自檢必裁區（先全圖再局部）
① enter_hawk 金弧匯入 L1 的匯聚區(3 弧不交纏、不穿卡、有金箭頭頭)。② 4 層卡最長 desc/meta 不溢出。③ confirm cluster 5 閘表列字完整、虛線連接點清楚不亂。④ L0 基座帶橫跨不壓主流卡。⑤ 自迴圈小 loop 不與回流弧纏。⑥ 跨 band y 不重疊(主流列 / confirm cluster / L0 基座)。⑦ 四角無黑邊。
