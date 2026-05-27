"""sales 常數 subpackage（2026-05-26 P8 拆分；原 constants.py 274 行已分散到子模組）。

對外 import path 保持向前相容：所有 `from myProgram.sales.constants import XXX`
仍 work。subpackage 內部子模組（timing / products / keywords / shared / l1_text / ... / l5_text）
按職責分組，新增常數時依語意放入對應子模組即可。

子模組職責：
    timing.py    — 時間常數與計數常數（秒 / 次數）
    products.py  — PRODUCTS dict + 商品追問語音模板
    keywords.py  — CONFIRM_YES/NO 關鍵字集 + HAWK_SLOGANS + 商品 keyword + 中文數字映射
    shared.py    — 跨層共用文案（SERVICE_PHONE / DIALOG_VAGUE_BUY_REASK）
    actions.py   — 動作組常數（S3 同步 runAction 動作名，對應 ActionGroups/*.d6a）
    l1_text.py   — L1 文字常數（選單 / 進入提示）
    l2_text.py   — L2 文字常數（首次點餐對話層）
    l3_text.py   — L3 文字常數（加單 / 結帳確認對話層）
    l4_text.py   — L4 文字常數（付款對話層）
    l5_text.py   — L5 文字常數（致謝離場對話層）
"""

from myProgram.sales.constants.timing import *
from myProgram.sales.constants.products import *
from myProgram.sales.constants.keywords import *
from myProgram.sales.constants.shared import *
from myProgram.sales.constants.actions import *
from myProgram.sales.constants.l1_text import *
from myProgram.sales.constants.l2_text import *
from myProgram.sales.constants.l3_text import *
from myProgram.sales.constants.l4_text import *
from myProgram.sales.constants.l5_text import *
