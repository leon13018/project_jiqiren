# quality_fix_w2 實作計畫（plan — HOW）

> **執行者**：sales-coder。對應 spec：`resources/specs/quality_fix_w2_2026-06-11_spec.md`（行為矩陣與等價論證以 spec §2 為準）。
> 純重構 TDD 規約：**綠 → 改 → 綠 → commit**；單一 commit；任一步 pytest 不是 `502 passed` 即停下回報。

**Goal**：`main_loop` 內聯分派與 `_dispatch_inner` 統一為單一 `_dispatch(response, *, in_main_loop)`，行為零改變。

**改檔**：僅 `myProgram/sales/states/l2_l3_dialog.py`。測試零修改。

---

## Task 0：基線驗證

- [ ] **Step 0.1**：`python -m pytest tests/sales/` → 預期 `502 passed`。不是 → 停下回報。

---

## Task 1：統一 dispatch 核心

**Files**：Modify `myProgram/sales/states/l2_l3_dialog.py`

- [ ] **Step 1.1：Read worktree 內 `l2_l3_dialog.py` 全檔**（Edit 前必 Read 此絕對路徑；確認 `_dispatch_inner` 約 347-424 行、`_think_silence` 約 426-436 行、`main_loop` 約 438-576 行）

- [ ] **Step 1.2：把整個 `_dispatch_inner` method 替換為 `_dispatch`**

刪除邊界：從 `    def _dispatch_inner(self, response: str):` 起，到其結尾 `        self.io.speak(policy.clarify)` + `        return None`（即 `    def _think_silence(self):` 的前一行）止，整段換成：

```python
    def _dispatch(self, response: str, *, in_main_loop: bool):
        """單一意圖分派核心——主迴圈（in_main_loop=True）與沉默期語境（False）共用。

        quality_fix_w2：統一原 main_loop 內聯分派與 _dispatch_inner 雙份（後者又
        源自 _dialog_dispatch_inner_l2 / _l3 雙胞胎）。兩語境差異全部顯式參數化：
            - Q2：unclear_count 歸零 / 累加 / 上限分流只在主迴圈語境（inner 完全不碰）
            - Q1：L2 沉默鏈 think 增量不回寫主迴圈——saved/writeback 包裹只在主迴圈語境
            - B11：L2→L3 cart 轉場 reset think_count 只在主迴圈語境（inner 由主迴圈
              writeback 分支事後處理）
        分支序採原 inner 序（想買無商品先於商品 parse）：兩分支互斥（classify_intent
        商品判定先於想買無商品，且其 keyword 集與 parse_products 一致），與原主迴圈
        序等價，省一次 parse_products。

        Returns:
            tuple — 退出 dialog（caller 直接 return）
            None  — 已處理（主迴圈 continue 下一輪；沉默鏈回傳給上層 think 分支）
        """
        policy = self.policy()
        intent = classify_intent(response, policy.nlu_mode)

        # 拒絕意圖 → 先過 cancel_confirm gate（2026-05-29 cross-L cancel）
        # True → 鏈路 A（依 cart 狀態決定是否清 cart）；False → speak 合成 voice 後回等待
        if intent == "拒絕":
            if CANCEL_CONFIRM.run(self.io):
                return self.exit_a()
            # cancel_confirm NO → speak 合成 voice（DECLINED + 對應 mode entry 重啟），
            # 一次 speak cover 兩件事，顧客不失去上下文
            # （2026-05-30 改：從 CANCEL_DECLINED_NOTICE 替換為 mode-aware 合成版）
            self.io.speak(policy.cancel_declined_resume)
            return None

        # 想一下意圖 → B-3/B-4（行為依 policy；計數歸屬依語境）
        if intent == "想一下":
            if in_main_loop:
                self.unclear_count = 0
                self.think_count += 1
                if self.think_count >= policy.think_limit:
                    return policy.on_think_exhausted(self)
                saved = self.think_count
                result = self._think_silence()
                if isinstance(result, tuple):
                    return result
                if not policy.silence_think_writeback:
                    # Q1：L2 沉默鏈的 think 增量不回寫主迴圈（原 _dialog_think_silence_l2
                    # 回 None 不回 int；L3 版回 int 回寫）
                    self.think_count = saved
                    # B11：沉默期內顧客加單使 cart 從空變非空（L2→L3 切換）→ reset think_count
                    if not cart_module.is_empty(self.cart):
                        self.think_count = 0
                return None
            # 沉默期內又說想一下 → 遞增 think_count + 再走沉默鏈（互遞迴，原樣）
            self.think_count += 1
            if self.think_count >= policy.think_limit:
                return policy.on_think_exhausted(self)
            return self._think_silence()

        # 結帳意圖 → policy 分流（L2 當 B-1 unclear；L3 走 C-1 confirm）
        # Q2：inner 語境用 on_checkout_inner（不碰 unclear）
        if intent == "結帳":
            if in_main_loop:
                result = policy.on_checkout_main(self)
                return result if isinstance(result, tuple) else None
            return policy.on_checkout_inner(self)

        # 客服 → B-2（2026-05-31 對齊 L4 service mode pattern：24s confirm gate）
        # YES → 回主迴圈當下層 entry/reask 重啟；NO/silent → exit_a 退 L1
        if intent == "客服":
            if in_main_loop:
                self.unclear_count = 0
            result = SERVICE_CONFIRM.run(self.io)
            if result == "yes":
                self.io.speak(policy.service_yes_prompt)
                return None
            # result == "no" → exit_a（cart 空 = L2 thanks 不清 cart；
            # cart 非空 = L3 thanks 清 cart）
            return self.exit_a()

        # 「想買無商品」溫和引導（與 L4「等待安撫」pattern 一致）：不 ++unclear、不 ++think
        if intent == "想買無商品":
            self.io.speak(DIALOG_VAGUE_BUY_REASK)
            return None

        # 商品 → C / B-3（多商品 parser + 各自缺數量追問）
        products = parse_products(response)
        if products:
            if in_main_loop:
                self.unclear_count = 0
            was_empty = cart_module.is_empty(self.cart)
            added, cancel_notices, control = resolve_and_add_products(
                products=products,
                cart=self.cart,
                speak=self.io.speak,
                print_terminal=self.io.print_terminal,
                read_customer_input=self.io.read_customer_input,
                classify_intent_mode=policy.nlu_mode,
                speak_and_wait=self.io.speak_and_wait,
            )
            if control == "exit_l1":
                return self.exit_a()
            if control in ("reenter_timeout", "reenter_cancel"):
                self._reenter_speak(control)
                return None
            if added and was_empty:
                # cart 從空 → 非空：speak L2_TO_L3_TRANSITION（合成 voice，原 L2_C_ADDED +
                # L3_ENTRY_PROMPT 合併為一句連貫播報；漏播會讓顧客以為對話結束、
                # 6s timeout 直接觸發 C-2 自動結帳）
                if in_main_loop:
                    # B11：L2→L3 cart-state 切換點 reset think_count——各 mode 獨立計數，
                    # L2 think_count 不應污染 L3；inner 語境不直接改（由主迴圈 writeback
                    # 分支事後處理）
                    self.think_count = 0
                # S3 同步動作（2026-05-27 fix）：L2→L3 transition 觸發 ACTION_L3
                self.io.do_action(ACTION_L3)
                # 2026-05-30 合成 speak：cancel notices 拼接到 transition 前
                self.io.speak(_prepend_cancel_notices(cancel_notices, L2_TO_L3_TRANSITION))
                return None
            if added:
                # cart 已非空語境：額外加單後重問（cancel notices 拼接到 L3_REASK 前）
                self.io.speak(_prepend_cancel_notices(cancel_notices, L3_REASK))
                return None
            # 全部商品在追問內取消 → re-prompt 依當前 mode reask
            self.io.speak(_prepend_cancel_notices(cancel_notices, policy.reask))
            return None

        # 都沒命中 → B-1 兜底（Q2：主迴圈計數 + 上限分流；inner 只 clarify 不計數）
        if in_main_loop:
            self.unclear_count += 1
            if self.unclear_count >= UNCLEAR_MAX:
                result = policy.on_unclear_exhausted(self)
                return result if isinstance(result, tuple) else None
            self.io.speak(policy.clarify)
            return None
        self.io.speak(policy.clarify)
        return None
```

- [ ] **Step 1.3：`_think_silence` 末行改呼 `_dispatch`**

舊：

```python
        return self._dispatch_inner(inner)
```

新：

```python
        return self._dispatch(inner, in_main_loop=False)
```

（docstring 不動——「有回應重 dispatch」描述仍準確。）

- [ ] **Step 1.4：`main_loop` 迴圈體的分派段換成統一呼叫**

刪除邊界：從 `            # === 判定優先序（policy 決定 NLU mode + 行為）===` 起、到 while 迴圈結尾 `            self.io.speak(policy.clarify)`（B-1 兜底最末行）止，整段換成：

```python
            # === 判定優先序統一於 _dispatch（quality_fix_w2：與沉默期語境共用）===
            result = self._dispatch(response, in_main_loop=True)
            if isinstance(result, tuple):
                return result
```

保留不動：method 開頭 `self.unclear_count = 0`、`while True:`、`policy = self.policy()`（仍供 `read_timeout` 用）、read、timeout 分流（`return policy.on_timeout(self)`）、docstring 全文。

- [ ] **Step 1.5：grep 確認零殘留**

執行：`grep -rn "_dispatch_inner" myProgram/ tests/`（或 Grep 工具）
預期：**0 個 code 命中**（tests 內僅 docstring/註解提及屬可接受——測試檔零修改原則優先，不去改測試註解）。

- [ ] **Step 1.6：跑全套測試**

執行：`python -m pytest tests/sales/`
預期：`502 passed`

- [ ] **Step 1.7：commit + branch 自驗**

```bash
git add myProgram/sales/states/l2_l3_dialog.py
git commit -m "refactor(sales): unify dialog dispatch core for main-loop and inner contexts"
git branch --contains HEAD
```

commit body：繁中說明統一範圍（main_loop 內聯分派 + _dispatch_inner → _dispatch）、quirk 參數化清單（Q1/Q2/B11）、分支序等價依據（keyword 集一致 → 互斥），附 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。
`git branch --contains HEAD` 須含 `worktree-quality-fix-w2`；顯示 `main` = Gotcha M，停下回報。

---

## 完成回報

依 sales-coder 規約回 4-status + commit SHA + pytest 末行輸出 + TaskList 摘要。
