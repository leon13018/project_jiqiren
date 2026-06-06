# Workflow 腳本撰寫（dynamic workflows）

> **🎯 何時讀本檔**：要新建 / 修改 `.claude/workflows/` 下的腳本，或判斷某 spec 流程該不該碼化成 workflow。

## 碼化判準

**一句話：這個流程值不值得變成「可重跑的資產」？值得 → 碼化進 `.claude/workflows/`；只跑一次 → 照 spec 做。**

四條件越多越值：穩定（流程不會邊做邊改）｜會重複跑｜機器可判定（schema / assertion）｜可 fan-out（步驟真獨立）。
不適合：中途要人簽核（無 mid-run 輸入 → 拆多個 workflow）、流程需邊做邊調、單線小任務。
帳要算對：省的是**主對話 context 與流程漂移**，總 token 反而 ~15×——拿成本換可靠性，不是省錢。

## 撰寫檢查清單（實測踩過才入列）

1. **args 字串守衛**：`args` 可能以 JSON 字串抵達 → 開頭 `if (typeof args === 'string') { try { args = JSON.parse(args) } catch {} }`。
2. **不硬編碼絕對路徑**：prompt 指路用「工作目錄相對」描述（agent 繼承 cwd，自己組絕對路徑）。
3. **禁 `Date.now()` / `Math.random()` / 無參 `new Date()`**——resume journal 會 throw；時間戳走 args 傳入。
4. **`meta` 純字面量**（不可含計算）；`name` = 檔名 = 具名觸發名。
5. **schema 一律 `additionalProperties: false`** + 欄位帶 `description` 引導；靠 schema 拿結構化輸出，不要「請回 JSON」然後祈禱。
6. **預設 `pipeline()`**（流式零 idle）；只有「某 stage 需要一次拿到全部前序結果」才用 `parallel()` barrier。
7. **失敗韌性**：pipeline 失敗項變 `null` → `.filter(Boolean)`，並 `log()` 報損失與截斷（no silent caps）。
8. **具名註冊非即時**：session 中途新增的存檔，具名觸發可能先 not found；稍後 registry 自動認得，不必重啟。

## 本專案資產

- harness：`.claude/workflows/skill-edd-regression.js`（Navigate→Grade→Verdict EDD 回歸）。
- 題庫 + 跑法：`resources/evals/`（README.md；`task/asserts` 與舊 `prompt/expectations` 雙格式都吃）。
- **skill / reference 去噪後必跑一輪 EDD 回歸守門**。

## 深層理由 / API 全貌（本檔只留行動清單，不重述）

→ `resources/research/workflows_orchestration_research_2026-06-04.md`：API 一手實證 §2、pattern 庫 §4、三大失敗模式 §5、成本判準 §6、踩坑與硬限制 §9、碼化判準 §11。
