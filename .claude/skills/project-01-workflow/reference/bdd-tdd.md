# BDD + TDD 開發流程（編寫 `myProgram/sales/` 業務邏輯時必走）

> **🎯 何時讀本檔**：要**新增** `myProgram/sales/` 業務邏輯（新商品 / 新對話分支 / 新 L 層）。⚠️ 目前 DORMANT（見下）。

> ## ⚠️ 狀態：DORMANT（2026-05-25 起）
>
> sales/ L0-L5 全層 + wire-up 完成後**休眠**。本檔由 path-scoped 機制在編到 sales/ 相關檔時載入，Claude 看到
> DORMANT 標記後**自行判斷本輪是否真要重啟流程**（純 bug fix / refactor 不需重啟）。後續 S2-S7
> （tts / 廠商動作 / OpenCV / threading）/ HTML 前端等工作大多走「Pi 實機測試 → 回報 → 改 code」迴圈
> （見 [incremental-rebuild.md](incremental-rebuild.md)），邏輯本身較簡單且重 IO / 硬體耦合，不適用 BDD+TDD
> 純 unit test 模型。

S1 v2 起，所有 `myProgram/sales/` 內的業務邏輯實作必須走 **BDD spec → AskUserQuestion 確認 → 單一 subagent
完成 TDD + Implementation → 主 agent 審查跑測試 → 收尾** 四階段。每個 L 層獨立一輪，禁止跨層合併。

---

## 重啟條件（DORMANT → 重啟）

任一條件成立 → 重啟 BDD+TDD 流程：

- 新增 `myProgram/sales/` 內任何業務邏輯（新增第 3 個商品 / 新對話分支 / 新 L 層）
- 修改既有 L0-L5 規格書（`resources/plans/業務程式邏輯規劃/L?.md`）導致 prod 邏輯要動

**不重啟的情境（仍跑既有 tests 當回歸網即可）：**

- 純 docstring / 註解修訂
- bug fix 修一行（依 [incremental-rebuild.md](incremental-rebuild.md) 直接 patch 條款）
- 既有 sales/ prod code 純 refactor（如 callback shape 統一 / L2/L3 合一）
- 配置常數調整（`constants.py` 內單純調數字）
- 廠商 SDK 整合測試（**選項 C 範圍外，本流程完全不涵蓋**）

> **既有 tests 仍 active 為 regression net**：sales/ tests 從 L0-L5 初版 107 持續累加（2026-05-25 達 159 /
> 2026-05-26 P0-P8 review-driven refactor 達 184 / 同日 UX 補強迴圈達 197 / Wave 0-10 二輪 review-driven 達 233 /
> 2026-05-27 Wave 4 hotfix 1-3 + dialog 客服 re-speak fix 達 248 → S2 同步 TTS + S4 worker thread + 9 條 UX 補強
> 迴圈（L5 mute 移除 -1 / stdin reconfigure UnicodeDecodeError test 移除 -2）達 **245 tests**）。
> wire-up / refactor 前後仍要跑 `python -m pytest tests/sales/ -v` 驗證 sales/ 沒被誤動（總數見 SessionStart hook
> 注入快照）。

---

## 觸發條件

**啟用：** 編寫或修改 `myProgram/sales/*.py` 內任何業務邏輯（不含 docstring 純文字編修）。

**不啟用：**

- 純 docstring / 註解修訂
- 配置常數調整（`constants.py` 內單純調數字）
- bug fix 修一行（依 [incremental-rebuild.md](incremental-rebuild.md) 直接 patch 條款）
- 廠商 SDK 整合測試（**選項 C 範圍外，本流程完全不涵蓋**）

---

## 4 階段完整流程

### 階段 1：主 agent 寫 BDD spec（不派 subagent）

**為何主 agent 自己寫：** BDD 屬於 spec 階段（同 plan mode 延伸），不是 implementation。scenario ID 命名要全 5 層
一致，主 agent 寫整齊；且寫完直接 AskUserQuestion 跟使用者對齊，無 context 切換。

**動作：**

1. 讀規格書對應層（`resources/plans/業務程式邏輯規劃/L?.md`）
2. 在 `tests/spec/L?_<short_name>_scenarios.py` 內寫**只含注解 + 空函數**的 BDD 骨架：
   ```python
   ## L2-B3-001
   ### Scenario: 顧客說「想一下」首次進入 B-3 鏈路
   ### Given 顧客處於 L2 詢問需求狀態，think_count=0
   ### When 顧客輸入「想一下」
   ### Then 系統 speak「請慢慢看」，啟動 6 秒沉默等待，think_count++
   def test_l2_b3_first_想一下_starts_silence_wait() -> None:
       pass
   ```
3. 寫完整層所有 scenarios（依規格書 A / B-1 / B-2 / B-3 / C 等鏈路）
4. **AskUserQuestion 強制確認**（bdd 規範.txt 硬規定）：「以下 N 個 scenarios 是否涵蓋規格書 L? 全部行為？是否要修 /
   增 / 刪？」
5. 通過後才進階段 2；未通過則改 spec 再問

**檔案命名：** `tests/spec/L<N>_<short_name>_scenarios.py`

- 例：`L2_first_order_scenarios.py` / `L3_add_loop_scenarios.py`
- short_name 跟 architecture 文件對齊

**禁止：**

- 此階段任何 import 真實 prod code
- 任何 `def test_...` 體內寫實作（連 `assert False` 都不行，必須 `pass`）

---

### 階段 2：主 agent 進 plan mode 規劃 TDD + Implementation

**動作：**

1. 主 agent 進入 plan mode 規劃本層要做的事：
   - 列出哪些 prod 檔會動（`nlu.py` / `cart.py` / `logic.py` / `states.py` 哪幾個）
   - 列出測試將放 `tests/sales/test_<module>.py` 哪幾檔
   - 列出 callback stub 需要哪些 fixture（先加到 `conftest.py` 還是 inline）
   - 預估 scenarios 數量 + Red-Green-Refactor 輪數
2. ExitPlanMode 給使用者審核
3. 通過 → 進階段 3

---

### 階段 3：派單一 subagent 走 TDD + Implementation（Red-Green-Refactor）

**派發前準備（依 [dispatch.md](dispatch.md)）：**

1. EnterWorktree
2. 塞 prompt 內的規範清單：
   - **subagent 派發協議** 全套（[dispatch.md](dispatch.md)）
   - **vendor-files**（廠商檔禁改 + 嚴格不 import 廠商 SDK，**架構選項 C**；見 [myprogram-vendor.md](myprogram-vendor.md)）
   - **threading-conventions**（雖然 S1 純單線程，先塞給 future-proof；見 [myprogram-threading-paths.md](myprogram-threading-paths.md)）
   - **path-conventions**（Linux 絕對路徑）
   - **output-language**（繁中強制）
   - **karpathy-guidelines**（surgical / verifiable / no over-engineering）
   - **test-driven-development SKILL**（Red-Green-Refactor + Iron Law）
   - **testing-anti-patterns**（禁測 mock 行為 / callback stub 用純函式 lambda）
   - **bdd 規範**（scenario ID 對應）
   - 本檔案（bdd-tdd）對應「subagent 任務描述」段
3. Subagent 模型：**Opus**（subagent 派發預設，prompt 內塞 extended thinking + xhigh effort）

**Subagent 任務描述（必須在 prompt 內明確要求）：**

```
你的任務是把 tests/spec/L?_<short>_scenarios.py 內所有 BDD scenarios
轉成可執行測試 + 對應 prod code，嚴格走 TDD Red-Green-Refactor。

對每個 scenario，按以下順序：

  RED：
  1. 在 tests/sales/test_<module>.py 內把該 scenario 的測試補完整
     （從 spec 搬注解過來、寫 arrange/act/assert 內容）
  2. 跑 `python -m pytest tests/sales/test_<module>.py::test_xxx -v`
  3. 確認測試 FAIL（不是 ERROR / 不是 PASS）
  4. 確認失敗訊息符合預期（feature missing，不是 typo）

  GREEN：
  5. 寫最小 prod code 到 myProgram/sales/<module>.py（避免過度工程）
  6. 跑同一個 pytest 指令
  7. 確認該 scenario PASS + 之前所有 scenario 仍 PASS

  REFACTOR：
  8. 清理（命名 / 重複 / 抽 helper）
  9. 再跑 pytest 確認全綠

跑不起來 pytest → 立刻回報主 agent，不要硬寫下去
寫不出來測試 / 邏輯 → 回報主 agent，由主 agent 決定退規格或調整

絕對禁止：
- import 任何廠商 SDK（ActionGroupControl / Board）
- 對外動作（speak / do_action / show）寫死 print；必須 callback 注入
- 跳過 RED 驗證直接寫 prod code（違反 Iron Law）
- 寫超出當前 scenario 的 prod code
```

**Commit 時機：** 全部 scenarios 走完 → 一個 commit；commit message 列「本輪實作哪些 scenarios / prod 檔」+
pytest 最終輸出摘要。

**Subagent 自主決策範圍**（2026-05-24 L0 第一輪歸納，避免每次都來問）：

**✅ 允許自主新增（不請示主 agent）：**

- `pytest.ini` / `pyproject.toml [tool.pytest.ini_options]`（testpaths / python_files 等 pytest 設定）
- `tests/conftest.py` 補 fixture
- 個別 test 檔內 inline stub class（如 `FakeScheduler`）— 符合 testing-anti-patterns 推薦
- pytest 設定相關的 `.gitignore` 補充（如 `.pytest_cache/`）

**⛔ 必須請示主 agent：**

- 新增 plan 內沒列的 prod 模組
- 改動 plan 內標「不動」的檔（如 L0 輪不動 `logic.py`）
- 引入新依賴（除 stdlib + pytest 外的 import）
- 修改規格書（`tests/spec/` 內檔案 — subagent 永遠唯讀）

**狀態機 / dispatcher 類型 prod code 的 RED 排程 pitfall**（2026-05-24 L1 第一輪實測踩到）：

當本輪 prod code 是「主迴圈 + dispatch 到多個鏈路」這種狀態機（如 `run_l1` 含 service / standby / hawk 三個鏈路），
**禁止**在 ENTRY scenario 的 GREEN 階段一次寫完整個路由骨架 — 這會導致後續 A/B/C 鏈路 scenarios 加入時直接 PASS
（prod code 早於 test = 違反 Iron Law「順序倒」條款）。

**正確順序：**

1. ENTRY GREEN 只寫**最小可印選單 + q 退出**的 impl（不寫任何鏈路 dispatch）
2. L?-A scenario 加入 → 「按 3 應印電話」FAIL（路由不存在）→ 寫 service dispatch + `_run_l?_service` → PASS
3. L?-B scenario 加入 → 「按 2 應進待機」FAIL → 寫 standby dispatch + `_run_l?_standby` → PASS
4. L?-C 同理

**Subagent 派發 prompt 內必須明確指出**：「狀態機型 prod code，每個鏈路獨立 RED-GREEN，禁止 ENTRY 一次寫完整路由」。
違反 → 標 `[DEGRADED-TDD-PARTIAL-L?]`。

歷史案例：commit `3cff233`（L1 第一輪），subagent 在 ENTRY GREEN 一次寫完 `run_l1` 完整 dispatch，後續 11 個
scenarios 直接 PASS。已接受 commit（49 PASS 品質 OK），但本段加入是為了 L2-L5 避免再犯。

**DEGRADED-TDD-PARTIAL 容許條款**（2026-05-24 L2 第一輪實測歸納）：

實測結果：L2 第一輪 subagent prompt 已**明確警告本 pitfall**（含 step-by-step ENTRY→A→B→C 順序示範），subagent
仍踩到（commit `df382ca`）。

**結論：dispatcher 型 prod code 即使警告也常踩**，因為：

1. 「最小 prod code」對 dispatcher 的客觀定義模糊（subagent 把「能讓 ENTRY-001 過的最小寫法」誤判為「完整 run_l?
   雛形」）
2. dispatcher 是 architectural unit，工程師直覺上想一次設計
3. redo 成本不划算（已 PASS）且第二次很可能仍踩

**新政策（dispatcher 型 prod，僅限 L1-L5 業務鏈路層）：**

- 主 agent **接受** DEGRADED commit，**不退回** redo
- subagent 必須在 commit message 明確標 `[DEGRADED-TDD-PARTIAL-L?]` + 誠實描述哪幾個 scenarios 違反
- 主 agent 在階段 3b commit 內補記，後續 bug 排查時優先檢查該批次
- prompt 內仍要警告（給 subagent 機會走嚴格 TDD；偶爾會成功）

**仍嚴格要求（不容許 DEGRADED）：**

- 純函式 / 純資料 prod code（如 `nlu.py` / `cart.py` / `constants.py`）— 必須嚴格逐 scenario RED
- subagent 寫測試**前**先寫 prod code（純順序倒，連 ENTRY 都沒 RED）
- 沒看見任何 fail 就寫 prod code（dispatcher 例外是「先見 ENTRY fail，後續鏈路 fail 沒見」，仍有部分 watch fail；
  純倒置順序不容許）

**Subagent commit 範圍 pitfall**（2026-05-24 L1 第一輪實測踩到）：

主 agent 在 worktree 階段 1 / 2 寫的 BDD spec 檔（`tests/spec/L?_*.py`）若**尚未 commit**就派 subagent，subagent
在自己 commit 階段可能**只 add 自己改動的 prod / test 檔**，漏掉這個 untracked spec 檔。

歷史案例：L0 subagent commit `a10895f` 包了 spec 檔（同 worktree 內 untracked 全包）。L1 subagent commit `3cff233`
**漏包** `tests/spec/L1_mode_select_scenarios.py` → 主 agent 階段 3b 補 add 進去。

**預防：subagent 派發 prompt 內 commit 範例必須明列：**

```
git status                                          # 先看所有 untracked + modified
git add tests/spec/L?_*_scenarios.py \             # 本輪新增 BDD spec（若 untracked）
        tests/sales/test_<module>.py \
        myProgram/sales/<module>.py \
        ...
```

或主 agent 在派發前先把 BDD spec commit 一次（拆兩個 commit）— 但這破壞「一個 commit 一輪」的整潔性。
**推薦：prompt 內明列 git add 範圍**。

---

### 階段 4：主 agent 審查 + 收尾

**動作：**

1. Read worktree 內所有改動的檔對照 CLAUDE.md（繁中 / 廠商檔 / 路徑 / git 操作）
2. **主 agent 自己跑一次 pytest 確認全綠**：
   ```bash
   python -m pytest tests/sales/ -v
   ```
3. 若失敗或紅 → 退回 subagent 或自己修
4. **必跑：條件性步驟 3a / 3b**
   - 3a（pineedtodo）：通常本流程不觸發（Windows 跑測試，無 Pi 操作）
   - 3b（code_map）：巢狀 code_map——只在改到某層 code_map 已列的**直接**子項目時更新該層。`tests/spec/` / `tests/sales/` 下的**個別測試檔通常不需動**（`tests/` code_map 粗顆粒不列個別檔）；新增子資料夾才更 `tests/.claude/code_map.md`。詳見 `pi-and-structure.md`
5. ExitWorktree keep → ff-merge → push（hook 自動 sync）→ cleanup

---

## 例外：subagent 跑不起來 pytest

**Fallback 順序：**

1. Subagent 回報「測試寫完、邏輯應 fail/pass、但 `python -m pytest` 跑不起來」+ 完整錯誤輸出
2. 主 agent 自己跑 → 通常是 import path / cwd 問題，修 conftest 或 `pytest.ini` / `pyproject.toml`
3. 主 agent 也跑不起來 → 退回讓使用者跑 + 回報結果（degraded mode）

**degraded mode 限制：** subagent 無法 watch test fail → 違反 Iron Law → 必須在 commit message 明確標
`[DEGRADED-TDD]`，後續可疑 bug 排查時優先檢查該批次。

---

## Iron Law 判定（審查 subagent 是否真的走 TDD 用）

**✅ 算「精神有守」（不標 DEGRADED）：**

- 模組完全空白時，subagent **一次跑 pytest 看到全部 `AttributeError: module has no attribute 'xxx'`**（全部測試因
  同根因失敗）→ 算 watch fail
- 此後逐 scenario 寫 prod code + 跑 GREEN，subagent 親見「FAIL → PASS」轉換
- 理由：Iron Law 核心是「prod code 寫之前必須先看見 fail」，**不是**「每 scenario 必須各自獨立的 RED 跑」。空白模組
  批次 fail 滿足此精神（2026-05-24 L0 第一輪實測決定）

**⛔ 算「真正違反」（必標 DEGRADED）：**

- subagent 寫測試**前**先寫 prod code（順序倒）
- subagent 跑不起來 pytest 但硬塞 prod code「應該會通過」
- 沒看見任何 fail 就寫 GREEN code
- **狀態機 ENTRY 一次寫完整路由** → 後續鏈路 scenarios 直接 PASS（順序倒的具體變體；見階段 3「狀態機 pitfall」段）

**主 agent 審查時看 subagent 回報是否清楚描述：**

- 「我先看見 X 個測試 fail（含失敗訊息），才寫 prod code」→ 通過
- 描述模糊 / 邏輯倒置 → 標 DEGRADED
- 「ENTRY 寫完整路由骨架，後續鏈路測試立即 PASS」→ 標 `[DEGRADED-TDD-PARTIAL-L?]`

---

## tests/ 目錄結構

> tests/ 結構見 `tests/.claude/code_map.md`。本節只說明 BDD 的組織原則：`tests/spec/` 按 L 層組織（BDD 階段產出），`tests/sales/` 按 prod 模組組織（TDD 階段最終測試）。

**spec/ vs sales/ 對應關係：**

- spec/ 按 **L 層** 組織 — 對應規格書檔案結構，scenario ID 帶 L 層編號
- sales/ 按 **prod 模組** 組織 — 對應 `myProgram/sales/*.py`，subagent 把 spec/ 的 scenarios 搬過來 + 補實作
- spec/ 寫完不刪 — 當「規格書的可執行版」永久存活；後續修規格時 spec/ 跟著修

**子資料夾 / 子檔何時建：**

- L0 第一輪 BDD 開始時：建 `tests/spec/__init__.py` + `tests/spec/L0_common_scenarios.py`
- L0 進 TDD 階段 3 時：建 `tests/sales/__init__.py` + `tests/sales/test_<module>.py` 第一份
- 後續每 L 層第一輪 BDD 跟著建對應檔
- **禁止預先建空殼檔**（依「不預先做後續推測」原則）

---

## 推進節奏（每 L 層獨立一輪）

**順序：** L0 → L1 → L2 → L3 → L4 → L5（依規格書依賴關係）

**每層走完完整 4 階段 + push（hook 自動 sync）才開下一層。** 跨層合併 = race window 太大 / 違反
[incremental-rebuild.md](incremental-rebuild.md)「每步只一變數」原則。

**L 層內可分多輪？** 可，若 scenarios 過多（>15）可分成多次 subagent 派發，但每次仍走完整 Red-Green-Refactor +
commit + push。

---

## 環境設定（一次性，使用者手動執行）

- **Windows 端：** Python 3.14.4 全域裝 pytest（使用者 2026-05-24 已執行 `pip install pytest`）
- **Pi 端：** 不需要裝 pytest（選項 C：所有測試在 Windows 跑；Pi 上跑的是 production）
- **subagent / 主 agent 跑測試指令：** `python -m pytest tests/sales/ -v`（在專案根目錄跑）

---

## 為何選這套流程

**為何 BDD 主 agent 寫（不派 subagent）：**

- spec 階段需跟使用者連續對話確認，主 agent 已有 context
- scenario ID 命名一致性最重要
- 屬 subagent 派發例外條「純文件 + spec 編輯」（見 [dispatch.md](dispatch.md)）

**為何 TDD + Implementation 同一個 subagent（不拆兩個）：**

- TDD SKILL Iron Law 要求 same agent 連續走 Red-Green-Refactor
- 「watch test fail」與「watch test pass」是同一個迴圈內必要動作
- 拆兩個 subagent → 第二個無法 watch fail → 違反 Iron Law

**為何選項 C（純 unit test，無整合測試）：**

- 廠商 SDK Windows 無法 import（見 [myprogram-vendor.md](myprogram-vendor.md)）→ 整合測試必須 Pi 上跑 → 違反工作邊界
  （subagent 不能 SSH）
- 純 unit test + callback 注入足以覆蓋業務邏輯
- 廠商 SDK 整合行為靠使用者實機驗證（本來就是 [incremental-rebuild.md](incremental-rebuild.md) S1-S7 的精神）

**為何每 L 層獨立一輪：**

- [incremental-rebuild.md](incremental-rebuild.md)「每步只一變數」
- 使用者偏好（step-by-step pace）
- 失敗範圍可控（一層 bug 不會污染其他層）

---

## 既有產出（dormant 後不會消失）

| 項目 | 數量 | 位置 |
|---|---|---|
| BDD spec | 87 scenarios | `tests/spec/L0-L5_*.py` |
| TDD test | 245 tests | `tests/sales/test_*.py`（持續累加：L0-L5 初版 107 → 159 → 197 → Wave 0-10 後 233 → 2026-05-27 Wave 4 hotfix 1-3 + dialog 客服 re-speak fix 後 248）|
| Prod code | 6 個 `run_?` 函式 | `myProgram/sales/states/` 子資料夾（2026-05-26 P6.S9 改層編號命名：`l0_subroutine_a` / `l1` / `l2_l3_dialog` / `l4` / `l5` + `_l2_l3_qty_followup`）|
| 完整規則檔 | 4 階段 playbook | 本檔（bdd-tdd.md） |
| TDD SKILL | Iron Law + 反模式 | `.claude/skills/test-driven-development/` |

---

## 重要決策保留（重啟才看細節，平時知道存在即可）

- **選項 C**：sales/ 嚴格不 import 廠商 SDK，純 unit test + callback 注入（理由 + A/B/C 對比見上方「為何選這套
  流程」段）
- **dispatcher pitfall**：狀態機 prod code 的 RED 排程容易踩 → DEGRADED 容許條款（含 L1/L2/L3 三次實測歸納，見階段 3）
- **Iron Law 精神 vs 字面**：模組空白時批次 fail 算「精神有守」不標 DEGRADED（見上方「Iron Law 判定」段完整判定指引）
- **Subagent commit 範圍**：spec 檔須明列 git add（L1 第一輪曾漏，後續預防成功；見階段 3 commit 範圍 pitfall）

---

## 為何 dormant 而非全刪

- 245 tests 是 sales/ 的 regression 安全網 — S2-S7 wire-up 萬一誤動 dispatch 邏輯立即可知，**絕不能刪**
- BDD+TDD playbook 已驗證可行（L0-L5 五輪實踐 + 多次 pitfall 補強）— 未來若有新業務邏輯，重新 derive 成本高，保留即
  直接複用
- CLAUDE.md 已縮到 1 行 dormant marker + pointer，平時 context 成本極低

---

## 相關規則 / reference

- 派發協議：[dispatch.md](dispatch.md)
- Worktree：[worktree.md](worktree.md)
- Incremental rebuild：[incremental-rebuild.md](incremental-rebuild.md)（S2-S7 階段的主要工作流程）
- SDD 流程：[sdd.md](sdd.md)（與 BDD-TDD 互補：BDD = scenarios / TDD = 測試先行 / SDD = 實作前契約）
- 廠商 SDK 禁改背景：[myprogram-vendor.md](myprogram-vendor.md)
- 多線程規範：[myprogram-threading-paths.md](myprogram-threading-paths.md)
- BDD 規範：`resources/plans/bdd規範.txt`
- BDD 範例：`resources/examples/bdd-寫法範例.txt`
- TDD SKILL：`.claude/skills/test-driven-development/SKILL.md`
- 反模式：`.claude/skills/test-driven-development/testing-anti-patterns.md`
- 業務規格：`resources/plans/業務程式邏輯規劃/L0-L5.md`
- 架構決策：`resources/architecture/backend-module-structure.md`（含 testing 段）
