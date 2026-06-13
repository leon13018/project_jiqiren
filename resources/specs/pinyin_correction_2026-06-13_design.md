# 本地拼音糾錯層 — 統領設計（合音還原 + 拼音近音糾錯）

> 2026-06-13 brainstorming 定案（keyterm 對中文無效後 pivot 本地）。本檔為統領設計；分 Phase 實作，各 Phase 另開 spec+plan。
> **最高判準（user）：極致效能、超低延遲、最先進技術、最快算法**——本地拼音比對在小詞域微秒級，符合此判準（學術 SOTA 的 LLM 後處理糾錯因延遲不可接受被否決）。

## 1. 背景與動機

Deepgram keyterm 對中文 streaming 無效（已查證 + 實測），pivot 到本地糾錯。痛點（Pi 實測）：
- **三瓶→商品**（sān-píng/shāng-pǐn，平翹舌＋前後鼻音雙重混淆，問數量 context）
- **尬尬樂/刮樂→刮刮樂**（介音脫落 gua→ga ＋疊字連音，問商品 context）
- **醬就好→這樣就好**（台灣合音 zhèyàng→jiàng，已從 NLU hardcode 撤回待此層處理）

本質：雲端 ASR 對「短中文詞 + 台灣國語系統性混淆」不可靠，但**我們握有對話 context（合法詞域極小）**——用領域知識在本地兜底。

## 2. 架構：新檔 `myProgram/sales/phonetic.py`，兩個子機制

掛在 **NLU 放棄出口**（既有 NLU 正常解析的零影響——既有測試零衝擊）：

| 子機制 | 處理 | 機制 | 掛載觸發 |
|---|---|---|---|
| **合音還原** | 醬就好→這樣就好 | 固定合音表（醬→這樣）展開後重走 classify_intent | classify 回「無法判斷」 |
| **拼音近音糾錯** | 三瓶←商品、刮刮樂←尬尬樂 | pypinyin 取聲韻母 + 模糊等價 + 疊字去重 + 歧義安全閥，比對 context 合法詞域 | parse 失敗（無數量／無法判斷） |

### 2.1 合音還原 `expand_fusion(text) -> str`
固定合音表 `{"醬": "這樣"}`（未來可加 甭→不用、表→不要…）。text 含合音字 → 展開（醬就好→這樣就好）→ caller 重走 classify_intent → 既有「這樣就好」keyword 命中。無合音則原樣返回。FP 低（醬在點餐場景幾乎只是合音；無醬料商品）。

### 2.2 拼音近音糾錯 `phonetic_match(text, candidates, *, to_pinyin=None) -> str | None`
- pypinyin 取每字**聲母 + 韻母**（注入式 `to_pinyin` seam——production 用 pypinyin lazy import、Windows 測試注入預標字典）。
- **預處理**：疊字去重規整（刮刮樂→刮樂；同施於候選與 text，解連音）。
- **模糊等價類**：聲母 `s/sh`、`c/ch`、`z/zh`（平翹舌）、`n/l`、`f/h`；韻母 `in/ing`、`en/eng`、`an/ang`（前後鼻音）；介音 `ua/a`、`uo/o`、`ie/e`（介音脫落，解尬尬樂）。
- **相似度**：逐字聲韻母模糊比對，相似度 = 模糊匹配音節比例。
- **歧義安全閥**：top-1 ≥ 閾值 **且** 與 top-2 差距 ≥ margin → 唯一夠近 → 修正；否則 None（退回現有 reprompt）。閾值/margin Pi 實測調校（不寫死神奇數字）。
- 不同字數（茶←紅茶 不完整辨識）：補**唯一子串規則**（text 是某候選唯一子串 → 該候選）。

## 3. 掛載點（NLU 放棄出口；candidates 由 caller 依 context 提供）

| context | 檔 / 出口 | 候選域 | 命中後 |
|---|---|---|---|
| 問數量 | `_l2_l3_qty_followup.py` qty sub-loop（parse_quantity 無數字分支） | `{一瓶…十瓶}`／`{一張…十張}`（依商品） | 用修正詞重解數量 |
| 問商品 | `l2_l3_dialog.py` `_dispatch`（classify 無法判斷 + parse_products 空的 unclear 出口） | `{冰紅茶, 紅茶, 刮刮樂}` | ① 先 expand_fusion 重 classify ② 否則 phonetic_match 商品域 |

**糾錯只掛 NLU 放棄出口**——既有正常解析路徑零改動；歧義/無夠近一律回 None → 落回今天的 reprompt（最壞不比現狀差）。confirm/錢包敏感 context 不碰。

## 4. pypinyin 依賴（三道防線守 Windows 紅線）
1. `phonetic.py` 頂層**禁** import pypinyin（lazy 在 production `_default_to_pinyin` 內）。
2. 測試注入 fake `to_pinyin`（預標 `{字:(聲母,韻母)}` 小字典），**不碰真 pypinyin**——測決策邏輯非測庫。
3. Pi 端 `pip install pypinyin`（純 Python、piwheels 安全）→ pineedtodo。

## 5. Phase 切分（incremental：拼音算法效力對中文是最大未知，先驗證核心）

- **Phase A（核心驗證）**：`phonetic.py` 拼音近音糾錯（聲韻母 + 疊字去重 + 介音等價 + 歧義閥 + pypinyin 注入）+ **問數量掛載**（解三瓶→商品）。先 Pi 實測拼音算法對台灣國語混淆的實際效力 + 調閾值。
- **Phase B（擴展）**：**問商品掛載**（解尬尬樂/刮樂→刮刮樂）+ **合音還原**（解醬就好）。Phase A 驗證核心算法 OK 後才擴。

Phase A 驗證的是「聲韻母模糊比對對真實 ASR 輸出到底準不準」——這是整層成敗關鍵，先單點驗證避免一次做大後重調。

## 6. Out of scope（明示不動）
既有 NLU 正常解析路徑｜confirm/錢包敏感 context｜「四瓶↔十瓶」兩合法量詞混淆（靠結帳複述 UX）｜合音表大規模擴充（YAGNI，初版只醬→這樣）｜STT Phase 2 barge-in（另一條線）。

## 7. 流程
```
[design 核可] → Phase A SDD（spec/plan→approval→sales-coder→3 段審→merge→push→Pi 實測調閾值）
            → 算法效力 OK → Phase B SDD（問商品 + 合音還原）→ Pi 驗收 → 收尾
```
