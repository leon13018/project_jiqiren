# Iteration-3 回歸 — dispatch.md CLAUDE.md 事實修正 + sdd.md 精修 + evals.json S1/S2 修正

> 本輪三項改動後，對受影響 4 場景跑 fresh navigator（general-purpose，S1 另跑 sonnet）+ grader 逐條判 + comparator 統整。**全 pass、零退化、零誤砍。** 結構化全紀錄見 `raw-result.json`。
> S3（threading）/ S4（sales）/ S5（dormant/conv）本輪不受任何改動影響（不讀 dispatch.md/sdd.md，assertion 未變）→ 沿用 `iteration-2/` 結果，未重跑。

## 本輪改動
- **dispatch.md:7 事實修正**：原「subagent 讀不到 CLAUDE.md」為錯（官方 sub-agents.md 證實 general-purpose / 自訂 subagent 啟動載入 CLAUDE.md + git status，只 built-in Explore/Plan 跳過；讀不到的只是本對話歷史）→ 已改正。
- **sdd.md:19 精修**：「只看 spec + 必要 reference」→「不繼承本對話、只收 spec 委派；CLAUDE.md 仍照常載入」，與 dispatch.md:7 一致。
- **evals.json S1**：場景由單 const（屬「超級小」→ 與 sales-coder/三段 reviewer assertion 矛盾）上修為跨檔 + 業務邏輯，使完整 SDD 成為一致正解、保住 SDD/reviewer 壓測意圖。
- **evals.json S2**：sync assertion 由過時「永遠手動跑 sync_pi.ps1」改為現行「Stop hook 自動 + marker 自我修正」（權威 standard-workflow.md L35/41）。

## 4 場景結果（全 overall=pass）
- **1-opus**（6/6）：跨檔場景正確判完整 SDD（非 mini）、派 sales-coder、三段 reviewer（含 examples 範本 + 模型分配）、Iron Law + branch 驗證。forced_second_hop=false，sdd.md/dispatch.md 各自自足。
- **1-sonnet**（6/6）：sonnet 對照組同樣命中完整 SDD 全鏈，精簡後仍讀得懂、不需二跳。
- **2**（5/5）：Gotcha M 完整解法鏈 + worktree 5 階段 + **sync 正確答為 Stop hook 自動**（主動勸阻手動 sync），命中修正後 assertion。
- **dispatch-policy**（7/7）：subagent_type=sales-coder、opus 預設、前 4 步 + ⛔越權收尾 + Wave 6 招 + branch 驗證、Wave 大小判斷正確；**核心事實題答對**——sales-coder 啟動載入 CLAUDE.md（紅線本就看得到），只 Explore/Plan 跳過，要餵的是本對話特有任務 context。

## Verdict（comparator）
`regression_detected=false`｜`claude_md_fact_correct=true`｜`dispatch_self_sufficient=true`｜`s1_now_full_sdd=true`｜`s2_sync_now_automatic=true`｜`failed_assertions=[]`｜`lost_load_bearing_content=[]`。

精簡後 sdd.md / dispatch.md 經逐檔比對仍完整保留全部 load-bearing 內容（觸發條件、完整版 spec+plan 範本、4 階段 + 三段 reviewer、Iron Law gate + 必跑指令表、規模門檻 + 超級小五條件、Wave 6 招、CLAUDE.md 可見性）。四場景 forced_second_hop 全 false。grader 標的 weak_assertion（assertion 1 近恆真、Iron Law/branch 偏 recall、OR 條件降門檻）屬既有 eval 設計弱點，非本輪造成。

## 結論
dispatch.md 去噪（-33%）+ CLAUDE.md 事實修正 + sdd.md 精修 + evals.json S1/S2 修正，**全部驗證無退化、dispatch 範圍自足、無誤砍**。
