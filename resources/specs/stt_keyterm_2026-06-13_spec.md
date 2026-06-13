# STT keyterm prompting — 詞表偏置（解近音誤辨識）— SDD spec

> 統領設計：`resources/specs/stt_bargein_2026-06-12_design.md`；本 spec 是 Phase 1 的**辨識準確度調優**（獨立於 barge-in，可即上）。
> Plan（HOW）：`resources/plans/stt_keyterm_2026-06-13_plan.md`。

## 1. 背景與動機

Phase 1 Pi 實測：顧客講「三瓶」常被 Deepgram 誤辨識為「商品」→ NLU 收到合法詞「商品」當商品意圖 → 回「聽不懂」，顧客錯愕。根因為台灣國語雙重聲學混淆：**平翹舌（sān/shāng）＋前後鼻音（-ing/-in）**，非 NLU 邏輯錯。

Deepgram Nova-3 **keyterm prompting**（contextual biasing）根治：連線時傳點餐場景高頻詞表，模型在近音模糊時偏向「在清單內」的詞。對「一邊在清單（三瓶）、一邊不在（商品）」的混淆效果最佳——正是本案。已查證：keyterm 支援單語言 zh-TW、live streaming、上限 500 tokens；機制為 inference 內偏置，**零額外網路往返 / 零額外延遲**（符合專案終極目標「最低延遲、最新技術」——學術 SOTA 的 LLM 後處理糾錯因延遲不可接受，keyterm 是延遲約束下的最優）。

## 2. 設計核心與行為規約

### 2.1 改動本質
純連線參數：`stt.py` 模組層新增 `KEYTERMS` 詞表常數 + `DEEPGRAM_URL` 末尾 append 各詞的 `&keyterm=<percent-encoded>`。**不動** `SttWorker` 任何方法、不動 sales/、不動 arm/disarm/session 邏輯。

### 2.2 詞表（29 詞，遠低於 500 token 上限）
| 類別 | 詞 |
|---|---|
| 數量×瓶（冰紅茶量詞） | 一瓶 兩瓶 三瓶 四瓶 五瓶 六瓶 七瓶 八瓶 九瓶 十瓶 |
| 數量×張（刮刮樂量詞） | 一張 兩張 三張 四張 五張 六張 七張 八張 九張 十張 |
| 商品名 | 冰紅茶 紅茶 刮刮樂 |
| 意圖詞 | 結帳 取消 繼續 繼續選購 幾瓶 幾張 |

- **數量用中文數字**（顧客口語＋既有 NLU 吃中文數字 CHINESE_DIGIT_MAP；非阿拉伯）。
- **完整 1–10**：即使「四↔十」keyterm 分不出（兩者都在清單、純聲學差異），完整列入讓模型確認都是合法量詞、擋掉非量詞誤判；「四/十」殘留靠既有結帳複述 UX 兜底。
- **「商品」絕不入清單**（反向 boost 會加劇本 bug）——測試鎖定。
- 詞表為 living：顧客新高頻詞之後增補（YAGNI，現只放已知）。

### 2.3 URL 編碼
中文 keyterm 必須 percent-encode（URL 非 ASCII 規範）：`urllib.parse.quote("三瓶")` → `%E4%B8%89%E7%93%B6`。`urllib.parse` 為 stdlib，頂層 import 安全（**非** websockets——不觸 Windows 紅線）。

## 3. 改檔範圍（高層）

| 檔 | 類型 | 估行數 |
|---|---|---|
| `myProgram/stt.py` | 修改：+`from urllib.parse import quote`、+`KEYTERMS` 常數、`DEEPGRAM_URL` append join | +~12 |
| `tests/stt/test_keyterm.py` | 新增：詞表完整性 + URL 編碼驗證 | +~30 |

## 4. Out of scope（明示不動）

barge-in（Phase 2）｜本地拼音模糊比對兜底（keyterm 實測後若殘留近音詞錯誤才議的後備）｜NLU/sales 任何改動｜「四↔十」數字聲學分辨（靠結帳複述 UX，非本 spec）｜其他混淆音的主動處理（詞表已涵蓋場景詞，足夠）｜阿拉伯數字 numerals（中文不支援且 NLU 不需要）。

## 5. 規範與參考

- 改 worker 檔 `stt.py` → 派 **sales-coder**（karpathy frontmatter 預載）。
- 對齊：現有 `DEEPGRAM_URL` 風格（模組常數）；`_normalize_transcript` 等同層純函式註解密度。
- 紅線：`urllib.parse` 頂層 import OK（stdlib）；**仍禁** websockets 頂層 import（不動 `_default_ws_factory` 的 lazy）。

## 6. 測試指令與預期

- `python -m pytest tests/stt/test_keyterm.py -q` → 新增測試全綠。
- `python -m pytest tests/ -q` → 既有 540 + 新增（test_keyterm）全綠，0 failed。
- 測試覆蓋：每個 KEYTERM 以 percent-encoded 形式出現在 DEEPGRAM_URL｜裸中文「三瓶」**不**出現在 URL（強制 encode）｜詞表含「三瓶」「冰紅茶」「刮刮樂」｜「商品」**不**在詞表｜1–10 完整瓶/張。
- Pi 實機驗收（merge 後，主 agent 寫 pineedtodo）：重測「三瓶/四瓶」等，比較加 keyterm 前後辨識率（目標：「三瓶→商品」誤辨識明顯下降）。

## 7. Commit 規範

worktree `worktree-stt-keyterm`（首 commit = 本 spec + plan）。實作依 plan：英文標題（`feat(stt): ...` / `test(stt): ...`）+ 繁中 body + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；`git add` 明列檔名。

## 8. 流程鳥瞰

```
spec+plan commit → sales-coder 實作（TDD）→ Iron Law（pytest 全量 + branch verify）
→ spec-reviewer → code-quality-reviewer → pineedtodo（主 agent）
→ ff-merge → push（hook sync Pi）→ 使用者 Pi 重測辨識率
```
