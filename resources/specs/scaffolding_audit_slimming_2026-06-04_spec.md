# Scaffolding 盤點瘦身 — Spec

> 日期：2026-06-04 ｜ 狀態：已過 brainstorming 四題釐清 + 設計核可
> 依據：`resources/research/CC_large_codebases_best_practices_2026-06-01.md`（3–6 個月 review、為舊 model 建的限制綁住新 model）+ `CC_hooks_automation_blog_supplement_2026-06-03.md` B3/B4。
> 後續：實施 plan → `resources/plans/scaffolding_audit_slimming_2026-06-04_plan.md`（writing-plans 產出）。

## 1. 目標與動機

盤點全專案 scaffolding（CLAUDE.md / code_map / hooks / skill 流程門檻 / memory），找出**為舊 model 限制而建、對現行 model 已成 overhead** 的規則與機制，經使用者逐項核可後執行瘦身。方向是「往回收」：減 context 負擔與流程摩擦，不新增機制。

**成功標準**：(1) 五類各有一份證據化 finding 清單；(2) 每項有三級處置裁決；(3) 核可項全部執行完畢且驗證通過；(4) 留觀察清單落檔。

## 2. 範圍與優先序

| 優先 | 類別 | 內容 | 尺 |
|---|---|---|---|
| 高 | 機制 / 流程門檻 | 10 支 hook script + settings.json + NOTES.md；SDD 三段 reviewer / worktree 5 階段 / dispatch 門檻 / Iron Law 等機制本身 | 機制尺 |
| 高 | 恆載文字層 | CLAUDE.md ×8 + code_map ×8 | 訊號密度尺 |
| 中 | memory ×4 + 跨類重複 | 同一規則跨層出現、權威版定位 | 訊號密度尺 |
| 低 | skill refs 字句層 | 剛經 round-3 denoise，只輕量複核**不重掃** | — |

**不在候選內（明文豁免）**：不可逆損害防線——vendor SDK 保護、`git add -A` 禁令、Windows 不裝依賴。機制尺天然保護（誤擋成本低、誤刪成本極高），盤點 agent 不得提議刪除。

## 3. 判準（雙軌）

- **文字類**（CLAUDE.md / code_map / skill ref / memory）→ **訊號密度尺**：拿掉後現行 model 仍會做對 → 砍。另查：跨層重複解釋、指向不存在檔案的 pointer、root/子層行數超標（≤~100 / ≤~60）。
- **機制類**（hooks / 流程門檻）→ **代價 vs 風險尺**：hook 不吃 context、誤擋成本低 → 從寬留；流程門檻（吃時間/輪次）→ 認真審「該門檻防的失敗模式，現行 model 還會犯嗎」。

## 4. 處置（三級）

| 級 | 條件 | 動作 |
|---|---|---|
| 刪 | 高信心過時 | 直接移除 |
| 降級 | 中信心 | 不刪，從恆載層移到按需層（如 root CLAUDE.md → skill ref） |
| 留觀察 | 低信心 | 不動，記入留觀察清單（附「出現什麼訊號就回頭處理」） |

## 5. 方法 — 盤點波（方案 B：fresh-eyes subagent ×4，全程唯讀）

| # | 盤什麼 | 校準筆記（prompt 內指定必讀） |
|---|---|---|
| ① | settings.json + 10 hooks + NOTES.md：死狀態檔、重複邏輯、為舊 model 行為而建的攔截、log 堆積 | `CC_hooks_automation_best_practices_2026-06-03.md`、`CC-hooks.md` |
| ② | CLAUDE.md ×8 + code_map ×8：跨層重複、壞 pointer、model 本來就會做對的叮嚀、行數超標 | `CC_large_codebases_best_practices_2026-06-01.md`、`large_codebases_official_guide_2026-06-02.md` |
| ③ | skill 流程門檻（SDD 三段 reviewer / worktree 5 階段 / dispatch 門檻 / Iron Law；字句層不重掃） | `skills_best_practices_research_2026-06-03.md`、`SDD_best_practices_2026-05-31.md` |
| ④ | memory ×4 輕掃 + 跨類重複偵測 | `memory_official_guide_2026-06-02.md` |

**選 subagent 而非主 agent 自盤的理由**：scaffolding 多為主 agent 歷輪所建，自審有 self-preferential bias；subagent 無對話包袱（fresh perspective）+ context 隔離（30+ 檔不進主對話）。

**Finding 強制格式**（無證據不收）：
```
位置（檔:行）｜現況｜為何疑似 overhead｜證據（含 git 考證，若有）｜建議處置級｜誤刪風險
```

## 6. 彙整與報告

主 agent 收 4 份結果 → 去重、調和衝突、按雙軌判準複核、定三級初判 → 報告存 `resources/reviews/scaffolding_audit_2026-06-04.md`，分三組呈現（刪除組 / 降級組 / 留觀察組）。

## 7. 核可關

逐組以選項題請使用者裁決（照單執行 / 逐項挑 / 整組擱置）。**未核可項一律不動**；爭議項擱置。

## 8. 執行波

- 高信心項先動。全是 tracked 文件/設定改動 → **worktree 5 階段**（鐵則）；純 doc/config、非 sales code → 主 agent 親自編輯，不觸發 SDD/sales-coder。
- 結構變動同步該層 code_map / SKILL.md 路由表 / NOTES.md。
- git 收尾 5 步；Pi sync 由 Stop hook 自動。

## 9. 驗證

- **hook script 改動**：echo 餵 stdin 手測 exit code / 輸出（NOTES.md 既有手測法）+ 下一 turn 觀察 fire 正常。
- **文字層改動**：改後逐檔重讀確認 pointer 有效（引用的檔案/路由存在）。
- **Iron Law**：未跑驗證不宣告完成。
- 留觀察清單附在報告末。

## 10. 邊界 case

- 盤點波發現判準缺口（筆記沒涵蓋的官方準則）→ 暫停、經使用者授權後派 agent 上官方渠道補研究（授權已給，仍先告知再派）。
- subagent finding 互相矛盾 → 主 agent 複核原檔裁決，不直接採信任一方。
- 執行中發現 finding 證據錯誤 → 該項退回留觀察，不硬改。
