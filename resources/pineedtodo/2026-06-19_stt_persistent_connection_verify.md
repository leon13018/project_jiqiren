# Pi 驗收 — STT 整場共用一條 Deepgram 連線（持久連線，2026-06-19）

> 對應：spec `resources/specs/stt_persistent_connection_2026-06-19_spec.md`、plan `..._plan.md`；commits `5a11739`→`724ef74`（3 個）。
> 前因：冷啟動量測證實每輪空檔 ~0.72s 中**連線握手佔 ~580ms**、裝置只 ~140ms → 改整場共用一條連線、第 2 輪起只開麥。
> **零新依賴**；對話層零改動（arm/disarm 介面不變）。

## 步驟
1. Pi：`git pull`（拉 3 個 commit）。
2. `STT_TTS_TIMING=1 python3.11 -m myProgram`，跑**一段多輪**點餐（至少 4~5 輪一問一答）。

## 驗收項
- [ ] **連線只建一次**：終端的 `[計時] 開麥連線 Xms` **只在第一輪出現**，第 2 輪起**不再印**（= 連線復用成功）。
- [ ] **「五張」開頭不再被裁**：語音播完後馬上講「五張刮刮樂三瓶冰紅茶」，開頭的「五張」**有錄到**（第 2 輪起 mic 幾乎即時，因為只剩 arecord ~140ms、不再付 580ms 握手）。
- [ ] **`開麥→第一個音框`**：第 2 輪起仍 ~0.14s（裝置冷啟動，這段本輪不處理）。
- [ ] **長對話 / 回 hawk 後再來客**：機器人長回應（兩輪間隔 >10s）後、或一單做完回 hawk 再接新客 → 連線**未斷**、辨識正常（keepalive 每 5s 撐住，未撞 Deepgram session 上限）。
- [ ] **斷網重連 fallback**：對話中途手動把 Pi 網路斷一下再復原 → 終端應印「串流中斷…下次開麥重連」，**下一輪 arm 自動重連**（會再印一次「開麥連線」），不卡死、不需重啟程式。

## 回報
- 各項 OK / NG；NG 附終端 log（尤其 `[計時]` 行 + 任何「串流中斷」訊息）。
- 「五張」開頭裁切問題是否解決（體感）。
- 若撞 Deepgram session 上限（長時間後連線莫名斷且不重連）→ 回報，改 per-conversation（回 hawk 即關、新客重連）。

## 追加（2026-06-19 後續：hardening + prearm，commits `f6b3c3f`→`d69e61f`）
> 修 3 個併發 freeze-risk + prearm 首連線（spec/plan `stt_conn_harden_prearm_2026-06-19`）。
- [ ] **prearm 藏首輪握手**：`STT_TTS_TIMING=1` 跑 → **第一輪也看不到開頭裁切感**（540ms 握手藏進 L2 提示音播放；「開麥連線」log 可能在提示音播放期間就印出、而非播完才印）。
- [ ] **正常多輪無回歸**：辨識、結帳收尾、付款全鏈路與之前一致（hardening 不改行為）。
- [ ] **斷網重連仍穩**：中途斷網 → 下輪重連、不卡死（A2 建線移出鎖 → 即使建線逾時也不凍 disarm/q 退出）。
- [ ]（選測，極端）若曾遇機器人「按 q 退不掉 / disarm 卡住」→ 現已加 join 逾時跳 Finalize 守衛，應不再掛死。

## 追加（2026-06-19 再後續：辨識 robustness，commit `802c646`）
> 修「空定稿 → 整輪漏字」+ 減少拆句（spec `stt_recognition_robustness_2026-06-19`）。
- [ ] **空定稿不再漏字**：之前 `Deepgram Results final=True ''`（空定稿）的輪，現在退用「最後非空 interim」→ 不再整輪漏字 / 莫名「不好意思我聽不太懂」。
- [ ] **endpointing 維持 300**（試調 450 已回歸——450 在背景音下害 Deepgram 等不到靜默、speech_final 永遠不發 → 整輪 timeout）。中途停頓拆句靠「一口氣講」+ 上面的 fallback 吸收。若仍偶發「講完零反應」→ 回報，需加 stable-interim 安全網（speech_final 不發時靠 interim 穩定偵測補發）。

## 追加（2026-06-19 warm-arecord：修開頭裁頭，commits `8369fd2`→`370e0d0`）
> 收音層搬 prearm（念提示音時就開麥暖機、sender discard 丟機器人音、arm 翻送出）；spec `stt_warm_arecord_2026-06-19`。**動到 working 收音層、已過雙 reviewer，務必 Pi 全流程驗收**。
- [ ] **arm→首框送出趨近 0**：`[計時]` 出現 `arm→首框送出 0.0Xs（麥克風已暖）`（取代舊「開麥→第一個音框 0.14s」）= 暖機生效。
- [ ] **搶快不裁頭**：提示音剛收尾就馬上講「紅茶三瓶刮刮樂五張」，開頭「紅茶」字頭**收得到、不被切**。
- [ ] **無自我回授**：機器人提示音 / 尾音**不會**被當成顧客輸入冒出辨識。
- [ ] **全流程無回歸**：點餐→結帳→付款→次客全通。
- ⚠️ 若異常（漏首框 / 收到機器人音 / 卡住）→ 回報，可單獨 revert warm-arecord（現版 STT 為退路）。

## 備註（已知設計取捨）
- hawk 待機期 keepalive 每 5s 持續送（無害，撐住連線）。
- prearm 已實作（首輪握手藏進提示音）；shutdown 剛好撞首輪建線瞬間的殘留 daemon thread 屬已接受的極罕見邊界。
