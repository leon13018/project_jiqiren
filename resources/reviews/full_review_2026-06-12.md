# 四鏡頭效能質檢 findings 報告（Phase 1，2026-06-12）

> 對應傘狀設計：`resources/specs/perf_review_2026-06-12_design.md` §5。
> 四個 fresh reviewer（opus，只讀）並行產出，主 agent 去重＋衝突調解＋抽查驗證（關鍵 file:line 已逐條 Read 原檔核實；一處修正見 F-12）。
> 基線參照：`resources/reviews/perf_baseline_2026-06-12.md`。

## Summary

| 鏡頭 | findings | 採納候選 | 不採納（已評估留檔） |
|---|---:|---:|---:|
| ① 熱路徑效能 | 6 | 3 | 3 |
| ② 阻塞與排程 | 7 | 2 | 5 |
| ③ 重複邏輯與抽象 | 8 | 5 | 3 |
| ④ 架構結構 | 6 | 4 | 2 |
| 合計 | 27 | **14** | 13 |

**三個結構性結論**：

1. **不建議大搬遷**（鏡頭④，理由充分）：import 依賴方向已乾淨（嚴格向下、唯一反向是 F-9）、32 個測試檔深層 import 把路徑釘死、目錄顆粒與職責對應良好。搬遷回歸風險 > 可讀性收益。**傘狀 §2 的「搬遷波」確定不開。**
2. **感知延遲的真實槓桿只在 worker 端**（鏡頭②＋基線定錨）：sales 純邏輯每輪幾十 µs，怎麼優化都無體感；TTS「合成→播放」序列化讓連發句之間有 0.5–2s 靜默合成等待——prefetch 是本 campaign 唯一有體感的優化。
3. **兩輪前置 campaign 收得很乾淨**：無 P0 finding 屬正常結果；殘留以「資料層預算（pre-lower/預編譯）」與「三處數量分類副本」為大宗。

---

## 採納候選（依建議波次分組）

### 建議 perf_w1 — 熱點預編譯（零行為風險，bench 可量測）

**[F-1 | P1 - hot] `sales/keyword_group.py:17-25` — 比對原語每呼叫重算 `kw.lower()`，`equals_strict_short` 每呼叫重建 list**（鏡頭①）
- 證據（已核實）：`contains_any` 內 `any(kw.lower() in text_lower for kw in keywords)`；`equals_strict_short` 內 `text.strip().lower() in [kw.lower() for kw in keywords]`。keyword 全為模組級常數，lower 結果恆定；classify_intent 無命中一輪掃 ~8 集 100+ 詞，是基線 14µs 的主成分。
- 修法：`KeywordGroup.__post_init__`（frozen 用 `object.__setattr__`）預建 lowercased tuple＋strict frozenset；`matches` 直接用預建值。裸原語呼叫點（nlu 內 `_KEYWORDS_THINK/CHECKOUT/SERVICE` 等）同主題預建模組級 lowercased 常數。保守邊界：公開原語簽名不動。
- 收益：classify_intent 無命中估 **-25~40%**（14→9-10µs）。風險：中（原語是 re-export 公開面，測試直呼——只動 KeywordGroup 路徑最保守）。

**[F-2 | P2 - hot] `sales/nlu.py:258,279,184,137` — regex f-string 每呼叫插值＋`str.maketrans` 每呼叫重建**（鏡頭①）
- 證據（已核實）：`_match_tens`/`_parse_compound_chinese` 用 `rf"...{_CHINESE_UNIT_CHARS}..."` 每呼叫插值（re 內部 cache 免重編譯但仍付插值＋lookup）；`normalize_input:139` 每呼叫 `str.maketrans("０..９",...)` 重建 dict。
- 修法：模組級 `_TENS_RE/_HUNDREDS_RE/_CTRL_RE = re.compile(...)`＋`_FULLWIDTH_TABLE = str.maketrans(...)`。
- 收益：低（sub-µs 級）但屬乾淨零成本抽象、零風險。

**[F-3 | P2 - hot] `sales/product_parser.py:94-107` — 20 個商品 keyword 每呼叫 `.lower()`＋重算 len**（鏡頭①）
- 修法：`_PRODUCT_KEYWORD_TO_NAME` 預存 `(kw_lower, len, product)`。收益：雙商品估 -10~15%（7.9→~6.8µs）。風險：低（module-private，需確認測試不斷言其形狀）。

### 建議 perf_w2 — TTS 感知延遲（唯一有體感的波；多線程高風險；需 Pi 驗證）

**[F-4 | P1 - hot] `tts.py:176→210` — synth 與 play 嚴格序列化，連發句間有一整段靜默合成等待**（鏡頭②）
- 證據（已核實）：`_process` 每句 `asyncio.run(_synthesize)` 完才 `Popen(mpg123).wait()`；queue 中下一句要等當前句播完才開始合成。
- 修法：單 worker 內 1-deep prefetch——當前句播放（不持 lock 的 `wait()` 期間）背景預取下一句到雙 buffer 暫存檔（避免 `TMP_MP3` 覆寫 race）。**不變式**：`_pending` 語義不動（wait_idle 仍等最後一句真播完）、FIFO 順序不動、print 時序不動。
- 收益：連發場景（hawk→L2 entry、L4 循環刷新）每句間省一次 synth round-trip ≈ **0.5–2s**；單發句無收益。風險：中（新 race window：雙 buffer、shutdown 時序、_pending 計數）。
- Pi 驗證：連發兩句量「第一句播完→第二句出聲」間隔，應從一次 synth 時間降至接近 0。

**[F-5 | P1 - hot] `tts.py:176` — `asyncio.run()` 每句重建＋銷毀 event loop**（鏡頭②；F-4 的前置）
- 修法：`on_thread_start` 建常駐 loop（顯式 `new_event_loop`，不可 `get_event_loop`），`_process` 改 `run_until_complete`；shutdown 時 close。
- 收益：每句省 ms 級 loop 建拆；**真正價值是為 F-4 prefetch 鋪路**。風險：中（loop 生命週期跨 thread 全程；Windows pytest 不受影響需驗證）。

### 建議 perf_w3 — 重複邏輯收斂（cold，零接層）

**[F-6 | P1 - cold] 數量分類決策樹三份手寫副本收斂為 `classify_qty` 純函式**（鏡頭③）
- 位置（已核實兩處，第三處同型）：`_l2_l3_qty_followup.py:121-141`（Pass 1）、`:218-251`（sub-loop）、`_invalid_qty_reask.py:86-95`（`_classify_into_pending`）。三處都是「remaining_capacity → at-cap / zero / over_limit / ok」同一邊界，只差後續動作（寫 pending vs 即時 funnel vs add）。
- 修法：抽 `classify_qty(cart, product, qty) -> "at_cap"|"zero"|"over_limit"|"ok"` 純函式，三 caller 各自保留動作。切點精準在「分類」與「動作」之間。
- 收益：消兩份易漂移的決策邊界副本，未來改規則只動一處。風險：中（funnel 時機是設計取捨，不可混淆批次與單筆重問語境）。

**[F-7 | P2 - cold] `l2_l3_dialog.py:663-671 / 743-750` — 兩個確認子狀態的 cancel-gate 區塊近逐行相同**（鏡頭③；可選）
- 修法：抽 `_cancel_gate(io, response, reprompt_text)` 小 helper（已知這兩個子狀態刻意不入 TimedConfirm，本條只收 8 行 ×2 的 gate 段）。收益：小。風險：中（錢包保守路徑）。

### 建議 perf_w4 — sweep（結構正名＋小項）

**[F-8 | P2 - cold] `l2_l3_dialog.py:152/323` — `L2_ENTRY_PROMPT if 空 else L3_ENTRY_PROMPT` 同字面三元式 ×2**（鏡頭③）：抽 `_entry_prompt_for(cart)`。
**[F-9 | P1 - cold] `constants/keywords.py:15` — 資料層 import 邏輯層 `KeywordGroup`（唯一反向依賴）**（鏡頭④）
- 二選一裁決：(a) `keyword_group.py` 移入 `constants/`（消視覺反向；改 2 處 import＋2 個測試檔 import，機械）；(b) 零碼動，在 constants CLAUDE.md 正名「允許依賴 keyword_group 純值原語」為例外。
- 與 F-1 同檔，若選 (a) 建議與 perf_w1 同波處理避免兩波碰同檔。
**[F-10 | P2 - cold] `nlu.py:34` — re-export `contains_any/equals_strict_short` 純相容墊片**（鏡頭④）：生產碼已無人從 nlu 取用；查測試後刪墊片或機械改測試 import。
**[F-11 | P2 - cold] code_map drift：constants「七檔」實為 10 個資料模組**（鏡頭④）：修 `constants/.claude/code_map.md` 文字。
**[F-12 | P2 - cold] `constants/timing.py:71` — `AUTO_CHECKOUT_NOTICE` prod 死常數，但測試仍引用**（鏡頭③；**主 agent 修正版**）
- 主 agent 核實：prod 零引用（C-2 已改用 `C2_DECISION_TIMEOUT=6`），但 `test_constants.py:32` 守值斷言＋`test_states.py:29` import。**非無腦可刪**——刪除屬「死常數＋守值測試伴隨移除」，斷言會消失（非語義調整），需 user 明示同意才動。
**[F-13 | P2 - cold] `timed_call` 計時包裝 helper（`_invalid_qty_reask.py:162-170` vs `l4.py:291-300` 暫停補償 pattern ×2）**（鏡頭③）：收益薄（只收兩行量測），可不做。
**[F-14 | P2 - cold] `tts.py:251` ALSA drain 與 prefetch 重疊化**（鏡頭②）：不獨立動，若 F-4 落地則 drain 期間自然與下一句 synth 並行，列為 F-4 的附帶收益驗證點。

---

## 不採納清單（已評估，留檔防重提）

| # | 項目 | 不採理由 |
|---|---|---|
| N-1 | nlu REJECT 雙集連掃合併（`nlu.py:213-221`） | L3_STRICT 命中→拒絕、KG_REJECT 命中→結帳，語意反向不可併集；收益 <5% 不抵錢包保守紅線風險 |
| N-2 | parse_products dedup O(n²) 改寫 | 真實 n≤2 無差；三條 dedup 規則語意微妙，重寫易破行為 |
| N-3 | classify_intent / parse_* 加 lru_cache | 自由文本輸入命中率近零，反增開銷 |
| N-4 | intent 分派 if-elif 查表化 | 各分支行為異質＋嚴格優先序，硬表化犧牲可讀性與不變式可維護性 |
| N-5 | mpg123 常駐（`-R` 模式） | 與 stdin=DEVNULL 防呆（Pi 實機坑 f7dab09）直接衝突；播放控制/ALSA 長佔用全要重寫，風險遠超 ~100ms/句 |
| N-6 | ALSA drain 0.3s 縮短 | Pi 實機調出的經驗值（防尾音截斷），Windows 測不出回歸 |
| N-7 | worker 啟動順序顯式化 | lazy import 是 Windows pytest seam 核心設計；啟動彼此獨立無依賴 |
| N-8 | wait_idle / lock 持有範圍 | 已最小（Condition no-op µs 級；wait-then-count 是 UX 不變式） |
| N-9 | queue 消費迴圈 | 阻塞 `get()` 已零延遲，無輪詢 sleep 可刪 |
| N-10 | `_build_order_summary` vs `_l4_print_entry_detail` 合併 | 輸出形狀/通道/用途全異，合併造參數化怪物 |
| N-11 | `_dispatch` 拒絕/客服雙分支抽象 | 落熱路徑且兩 confirm 語意 inverse，抽象=非零成本接層 |
| N-12 | `shared.py` 拆分 | 13 常數 62 行可控；設軟上限（>20 常數或 >120 行）入 watch-list |
| N-13 | main.py wire-up Context dataclass 化 | 顯式 kwargs 是 machine/logic 測試 stub 的 mock seam 契約；動了傷自文件性 |
| N-14 | **大搬遷（目錄/檔名極大化重構）** | 依賴方向已乾淨、32 測試檔深層 import 釘死路徑、顆粒恰當；成本/收益不成正比（鏡頭④全文論證） |

---

## 建議波次與順序

```
perf_w1  熱點預編譯（F-1, F-2, F-3；F-9 若選 (a) 併入）    零行為風險｜bench 直接驗證
perf_w3  數量分類收斂（F-6；F-7 可選）                      cold｜504 回歸網守
perf_w4  sweep（F-8, F-9(b)/F-10, F-11, F-12 裁決後, F-13 可選） 文件＋微項
perf_w2  TTS prefetch＋常駐 loop（F-4, F-5, F-14 驗證點）    最後做：風險最高、
                                                            需 Pi 端集中驗證時點
```

排序理由：純邏輯波（w1/w3/w4）Windows 可全程驗證、先收割；worker 波（w2）押後集中一次 Pi 實測（傘狀 §7 的兩個 Pi 驗證時點之一）。無搬遷波。

## 裁決選項

- **A. 全採**：14 項候選全做（F-9 選 (a) 或 (b)、F-12 含測試伴隨移除需在此一併明示）。
- **B. 只採 P1 核心**：F-1（keyword 預 lower）＋ F-4/F-5（TTS prefetch 波）＋ F-6（classify_qty）＋ F-9（裁決 a/b）。
- **C. 逐項勾選**：按 F-1 ~ F-14 編號回覆要/不要。

請同時裁決：F-9 選 (a) 搬檔或 (b) 正名；F-12 死常數是否連測試一併移除。
