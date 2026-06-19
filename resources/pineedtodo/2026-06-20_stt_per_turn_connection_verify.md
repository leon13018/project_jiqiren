# Pi 驗收 — STT 每輪新連線（per-turn，棄持久連線）2026-06-20

> 對應：spec `resources/specs/stt_per_turn_connection_2026-06-20_spec.md`；commit `4d8d388`。
> **核心假設驗證**：持久連線用久累積辨識 lag（第 2 輪起 interim 空、結果 disarm 後才回）→ 改每輪新連線（disarm 即收線、下輪 prearm/arm 重連、移除 keepalive）是否解掉 lag。

## 步驟
`git pull` 後 `STT_TTS_TIMING=1 python3.11 -m myProgram`，跑**一段完整多輪**點餐（≥4 輪）。

## 驗收項
- [ ] **每輪都重連**：`[計時] 開麥連線 Xms` **每一輪都出現**（持久連線版只第一輪印；per-turn 每輪都印）。
- [ ] **重連藏在提示音裡**：`開麥連線` 出現在提示音**播放期間**（prearm 背景建線），arm 不卡頓、開麥不延遲。
- [ ] **lag 消失（核心）**：辨識結果**即時回**——interim 不再空 10s、完整結果**不會到 disarm 之後才出現**（對比上次 `cap=False` 才回的 lag）。每輪講完就有反應、不再莫名 timeout 取消。
- [ ] **全流程通**：點餐→結帳→付款→次客全跑通。

## ⚠️ 假設成立 / 否證
- **lag 消失** → 假設成立,per-turn 收。回報後我整理進 changelog。
- **lag 仍在**（即使每輪新連線，結果還是延遲回）→ **假設否證**：lag 非連線、是 Deepgram 端/網路。回報,可 revert 回持久連線版（`4ff428e` 那條線是退路），STT 改走別的方向或收手。

## 備註（已知 invariant，code reviewer 標）
- per-turn 的 `disarm` 是每輪收線權威點,**依賴 caller 序列化**（`read_customer_input` 是 disarm 完整返回後才下輪 prearm）。目前如此、無 bug。**若未來改成「disarm 後不等返回就 prearm」**（並發飛行中的 prearm）→ 需重評「prearm 飛行中、disarm 收線 no-op、prearm 完成後留下活連線」的洩漏窗（現不觸發、不加碼）。
