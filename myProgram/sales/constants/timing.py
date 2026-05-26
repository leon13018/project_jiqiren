"""時間常數與計數常數（P8 拆分自 constants.py）。

包含所有與時間（秒）或循環次數相關的常數：
    WAIT_NO_RESPONSE / DNC_TIMEOUT / DYC_TIMEOUT / HAWK_INTERVAL / OPENCV_MUTE /
    THANK_DELAY / AUTO_CHECKOUT_NOTICE / L4_MAX_LOOPS / UNCLEAR_MAX / OPENCV_DWELL /
    CHECKOUT_CONFIRM_TIMEOUT / CHECKOUT_CONFIRM_UNCLEAR_MAX / L4_SERVICE_TIMEOUT
"""

# ============================================================
# 時間常數（單位：秒，L4_MAX_LOOPS / UNCLEAR_MAX 為次數）
# ============================================================

# L2 / L3 / L4 顧客無回應 timeout
WAIT_NO_RESPONSE: int = 6

# DnC（L2 cart-empty 詢問需求）專用 timeout（2026-05-26 加，比通用值寬鬆）
# 顧客被 OpenCV 偵測到後可能還在挑商品 / 看招牌；給 12s 比 6s 更實際。
# 不影響 L3 / B-3 沉默 / L4 等子流程（仍走 WAIT_NO_RESPONSE）。
DNC_TIMEOUT: int = 12

# DyC（L3 cart-non-empty 詢問加單）專用 timeout（2026-05-26 加，跟 DnC 對稱）
# 顧客剛加完一個商品後可能還在考慮要不要再買其他東西；給 12s 比 6s 更實際。
# timeout 後仍走 C-2 兩段自動結帳（不影響後續流程）。
DYC_TIMEOUT: int = 12

# L1 叫賣模式每一輪間隔
HAWK_INTERVAL: int = 12

# 「回 L1 叫賣」時屏蔽 OpenCV 偵測的時長，避免折返顧客被重複招呼
# （2026-05-26 從 12 → 6：實測 12s 對展演節奏太久；6s 已足夠擋掉「同一顧客剛走又走回」）
OPENCV_MUTE: int = 6

# L5 致謝完成後等待時長
THANK_DELAY: int = 3

# L3 鏈路 C-2「請問是否要結帳？」嚴格 yes/no 子狀態的 wall-clock 倒數秒數
# （2026-05-26 從 10 → 12：跟 DnC/DyC/checkout-confirm 對齊；同時改嚴格 yes/no
#   倒數不重置 — 亂答忽略不重置計時器，只認 CONFIRM_YES / CONFIRM_NO + 終端 1/2）
AUTO_CHECKOUT_NOTICE: int = 12

# L4 印金額循環最多次數（達到強制退）；總長 42 秒
L4_MAX_LOOPS: int = 6

# L2 / L3 / L4 鏈路 B-1 / E「無法判斷」累積上限（2026-05-25 加，跟 L4 對齊）
# L2: 達上限 → 走鏈路 A 拒絕
# L3: 達上限 → 進「最終確認」子狀態
# L4: 達上限 → 自動進客服模式（既有 L4 E→C 邏輯，未引用此常數，沿用 hardcoded 3）
UNCLEAR_MAX: int = 3

# OpenCV 偵測到人持續多久才視為有效觸發（防路人 / 光影誤觸）
OPENCV_DWELL: float = 1.5

# L3 結帳前 confirm 子狀態專用 timeout / 亂答上限（2026-05-26 加，比通用值寬鬆）
# 通用 WAIT_NO_RESPONSE=6s / UNCLEAR_MAX=3 對「結帳前確認金額」這步驟過於嚴格 —
# 顧客可能正在數錢 / 看商品 / 確認數量；給 12s + 5 次容忍空間，再清 cart 退。
CHECKOUT_CONFIRM_TIMEOUT: int = 12
CHECKOUT_CONFIRM_UNCLEAR_MAX: int = 5

# L4 客服模式 timeout（60 秒）
L4_SERVICE_TIMEOUT: int = 60

# L4 結帳場景全程 wall-clock 預算（2026-05-26 方案 B；防 ack spam 無限拖延）
# 從進入 L4 起算，含所有 ack/timeout/unclear 路徑共用；達 0 → 強制 exit
# 60s 是合理上限：D 鏈路 6 次 × 6s = 36s + buffer ≈ 60s，與 L4_SERVICE_TIMEOUT 對稱
L4_TOTAL_BUDGET: int = 60
