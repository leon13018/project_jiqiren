# oop_docsweep — Mini SDD spec（OOP 重構收尾清掃）

- **檔**：`myProgram/sales/states/l2_l3_dialog.py`（import 區）
- **改前**：`from myProgram.sales.constants import (... AUTO_CHECKOUT_NOTICE ...)` — 該名檔內無任何使用（W4 code-quality reviewer 確認為既有 unused import，非 W4 引入）
- **改後**：自 import 清單移除 `AUTO_CHECKOUT_NOTICE`（常數本身仍在 constants 定義與 export）
- **Why**：OOP 重構全部 wave 完成後的 backlog 清掃（task #24）
- **驗證**：`python -m pytest tests/sales/ -q` 全綠（501）

> 同 commit 附帶（SDD 不觸發項，純註解 / docstring）：`tests/sales/test_states.py`、`tests/sales/test_cancel_confirm.py` docstring 內引用 W4/W1 已改名函式的字樣改為現名（`_dialog_exit_a`→`DialogSession.exit_a()`、`_dialog_main_loop`→`DialogSession.main_loop()`、`_dialog_dispatch_inner_l2/_l3`→`DialogSession._dispatch_inner（L2/L3 mode）`、`_dialog_c2_second_stage`→`DialogSession.c2_second_stage()`、`_l4_exit_b`/`_l4_exit_d_forced`→`_l4_exit_to_l1`）。零行為改變；「既有測試零修改」契約已隨重構完成（等價性證明已交付）功成身退，本清掃經使用者「直接做到全部完成」授權。
