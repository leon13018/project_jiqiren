"""動作組常數 — S3 同步廠商 runAction 用（incremental rebuild S3 階段加）。

動作名對應 /home/pi/TonyPi/ActionGroups/<name>.d6a 廠商動作組檔案。
L2.d6a / L3.d6a 為使用者自訂；其他為廠商原生。

設計選擇：常數放 sales/constants/actions.py 而非 myProgram 頂層或 vendor 目錄。
    - sales/ 業務邏輯透過 do_action(name) callback 介面拿動作名字串
    - 嚴格不 import 廠商 SDK（架構選項 C；ActionGroupControl 在 myProgram/vendor/）
    - 動作名變動只需改本檔；business state 函式只認常數
"""

__all__ = [
    "ACTION_L1_HAWK",
    "ACTION_L2",
    "ACTION_L3",
    "ACTION_L4_PAY",
    "ACTION_L5_FAREWELL",
]

# L1 hawk entry — 揮手向潛在顧客打招呼（廠商原生動作）
ACTION_L1_HAWK: str = "wave_hand"

# L2 dialog entry（cart 空，首次點餐） — 使用者自訂 .d6a
ACTION_L2: str = "L2"

# L3 dialog entry（cart 非空，加單 / 結帳分支） — 使用者自訂 .d6a
ACTION_L3: str = "L3"

# L4 鏈路 A 掃碼付款成功 — 鞠躬致謝（廠商原生動作）
ACTION_L4_PAY: str = "bow"

# L5 致謝離場 — 揮手送客（廠商原生動作，與 L1 同動作名但語境不同）
ACTION_L5_FAREWELL: str = "wave_hand"
