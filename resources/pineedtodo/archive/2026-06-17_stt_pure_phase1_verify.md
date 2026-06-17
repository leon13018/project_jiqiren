# Pi 端待辦 — STT 退回 pure Phase 1（確認錄得到 + 辨識正常）

- **建立日期**：2026-06-17
- **對應提交**：`4fdd9fa`（revert(stt): 退回 pure Phase 1 — 移除全部 prewarm）
- **簡介**：prewarm 三輪皆出事（最後 warm-arecord 連音都收不到）→ 全部放棄,退回你確認「辨識正常」的 pure Phase 1（無 prewarm、`-c 1` 降混、arm 才開麥）。本輪確認:錄得到、辨識回到正常。裝置維持 plughw、無新依賴。

## Step 1 — 裝置（維持 plughw，不用改）
```bash
echo $STT_ARECORD_DEVICE     # 應為 plughw:CARD=ArrayUAC10
```
不是的話 → `export STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`。**喇叭插樹莓派板載 3.5mm。**

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```

## 驗證段
進顧客層講幾句:
- **✅ 核心驗收 1：錄得到** —— warm-arecord 那個「我說的話收不到」已修掉,你的話有被錄進、辨識出來。
- **✅ 核心驗收 2：辨識回到正常** —— 跟你印象中 pure Phase 1「辨識正常」一致。
- 順便:講「刮刮樂五張」幾次,看還會不會誤辨成數字。

**回報**：
1. **錄得到嗎**（最重要,確認回歸已修）；
2. **「刮刮樂」準不準** —— 若還是偶爾錯,那就是 Deepgram + 降混對難詞的固有上限（prewarm/聲道都試完了,不是那些）,我們開**最後一案**:keyterm 強化 / Deepgram 參數調校。

---

## 完成說明（2026-06-17 階段定案，歸檔）
- Pi 實測**錄得到**（pure Phase 1 收音正常,如「三瓶」有被辨識）→ warm-arecord「收不到音」回歸已修。
- 殘留**開麥裁切**（arecord 冷啟、搶快講掉開頭）為固有問題、warm-arecord 修法失敗 → **接受**;**Demo 操作=提示音播完停 ~0.5s 再答**避裁切（記於 roadmap）。
- 後續 `[計時]` 診斷 log 亦清除（`d25aea8`）。STT 階段告一段落,本檔歸檔。難詞精修（keyterm/Deepgram 參數）demo 真需要再開。
