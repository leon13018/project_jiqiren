"""時間常數與計數常數（P8 拆分自 constants.py）。

包含所有與時間（秒）或循環次數相關的常數：
    WAIT_NO_RESPONSE / DNC_TIMEOUT / DYC_TIMEOUT / HAWK_INTERVAL / OPENCV_MUTE /
    THANK_DELAY / AUTO_CHECKOUT_NOTICE / UNCLEAR_MAX / OPENCV_DWELL /
    CHECKOUT_CONFIRM_TIMEOUT / CHECKOUT_CONFIRM_UNCLEAR_MAX /
    L4_TOTAL_BUDGET / L4_QR_REFRESH_INTERVAL / L4_C_CONFIRM_TIMEOUT /
    CANCEL_CONFIRM_TIMEOUT
"""

__all__ = [
    "WAIT_NO_RESPONSE",
    "QTY_FOLLOWUP_TIMEOUT",
    "DNC_TIMEOUT",
    "DYC_TIMEOUT",
    "HAWK_INTERVAL",
    "OPENCV_MUTE",
    "THANK_DELAY",
    "AUTO_CHECKOUT_NOTICE",
    "C2_DECISION_TIMEOUT",
    "UNCLEAR_MAX",
    "OPENCV_DWELL",
    "CHECKOUT_CONFIRM_TIMEOUT",
    "CHECKOUT_CONFIRM_UNCLEAR_MAX",
    "L4_TOTAL_BUDGET",
    "L4_QR_REFRESH_INTERVAL",
    "L4_C_CONFIRM_TIMEOUT",
    "CANCEL_CONFIRM_TIMEOUT",
]

# ============================================================
# 時間常數（單位：秒，UNCLEAR_MAX 為次數）
# ============================================================

# L2 / L3 / L4 顧客無回應 timeout
WAIT_NO_RESPONSE: int = 6

# L2 / L3 qty followup 專屬 timeout（2026-05-30 加；user demo UX 反饋）
# 通用 WAIT_NO_RESPONSE=6s 對「請問X要幾Y？」追問過於急促 — 顧客可能正在
# 看商品 / 數錢 / 思考數量；改 12s 給更寬鬆回答時間。
# 不影響其他 6s 子流程（B-3/B-4 沉默 / unclear_final / L4 子流程
# 仍走 WAIT_NO_RESPONSE）— 只覆蓋 _qty_follow_up_sub_loop 內 read。
QTY_FOLLOWUP_TIMEOUT: int = 12

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

# L3 C-2 第二段三選一倒數秒數（2026-05-28 加；新設計從 AUTO_CHECKOUT_NOTICE=12 縮短為 6）
# wall-clock budget — 亂答消耗 budget 防無限拖延；倒數歸零視為「結賬」path
# 直接進 L4（跳過 _dialog_checkout_confirm），符合 user prompt 字面 promise
# 「如 6 秒內未答復將進行結賬」— silent customer 預期被結帳而非清 cart 退。
C2_DECISION_TIMEOUT: int = 6

# L2 / L3 鏈路 B-1「無法判斷」累積上限（2026-05-25 加）
# L2: 達上限 → 走鏈路 A 拒絕
# L3: 達上限 → 進「最終確認」子狀態
# （L4 不再使用此常數；2026-05-30 重構移除 L4 unclear_count 機制 → 改用單一 budget）
UNCLEAR_MAX: int = 3

# OpenCV 偵測到人持續多久才視為有效觸發（防路人 / 光影誤觸）
OPENCV_DWELL: float = 1.5

# L3 結帳前 confirm 子狀態專用 timeout / 亂答上限（2026-05-26 加，比通用值寬鬆）
# 通用 WAIT_NO_RESPONSE=6s / UNCLEAR_MAX=3 對「結帳前確認金額」這步驟過於嚴格 —
# 顧客可能正在數錢 / 看商品 / 確認數量；給 12s + 5 次容忍空間，再清 cart 退。
CHECKOUT_CONFIRM_TIMEOUT: int = 12
CHECKOUT_CONFIRM_UNCLEAR_MAX: int = 5

# L4 結帳場景全程 wall-clock 預算（2026-05-31 v3 雙計時器設計：30 → 36）
# 36 = L4_QR_REFRESH_INTERVAL × 3，總 budget 期間共 3 個 QR 刷新循環。
# 從進入 L4 entry prompt 播完起算；達 0 → forced exit（speak L4_D_FORCED_EXIT
# + clear cart + 退 L1）。
# 客服 yes「繼續」返回會 reset；cancel_confirm / 客服子狀態期間暫停 + 補償。
# 取代原 v2「30s 單一 budget + 12s 重提示」（v2 supersedes 舊「60s + loop_count
# 6 次循環 4 階段語氣 + unclear_count + final confirmation 18s + 獨立 60s 客服」）。
# 詳見 resources/specs/L4_v3_dual_timer_spec.md
L4_TOTAL_BUDGET: int = 36

# L4 QR 視覺刷新循環間隔（2026-05-31 v3 加；取代 L4_PROMPT_INTERVAL）
# 每循環開頭：重印結帳區塊 + 重 speak L4_REMIND_PROMPT（無條件，不論顧客是否回應）。
# 模擬「QR code 每 12s 重新生成」的 UX。子鏈路 ack 不影響此循環。
# 與 L4_TOTAL_BUDGET=36s 關係：36 = 12 × 3，總 budget 內共 3 個循環。
# 詳見 resources/specs/L4_v3_dual_timer_spec.md
L4_QR_REFRESH_INTERVAL: int = 12

# L4 / L2 / L3 三層 + qty followup 客服模式「請問是否繼續交易？」確認子狀態 wall-clock 預算
# （2026-05-30 加；2026-05-31 從 12s 提升至 24s — user 反饋打電話聯絡客服需更充裕時間）
# 取代舊版「L4_PROMPT_INTERVAL=12s × N 次 retry loop + cancel_confirm 雙重 gate」設計。
# 一次性 24s 決策：silent / NO 視為取消（直接清 cart 退 L1，不雙重確認）；YES 回原鏈路。
# 對齊 CANCEL_CONFIRM_TIMEOUT=6s pattern 但語意 inverse（cancel_confirm 問「是否取消」
# silent=取消；此處問「是否繼續」silent=取消）— 兩者都是「保守 default 取消」。
# 24s 比 6s 寬鬆，user 反饋客服需充裕思考時間（顧客可能正在打電話聯絡客服）。
L4_C_CONFIRM_TIMEOUT: int = 24

# Cross-L cancel confirm 子狀態 wall-clock 預算（2026-05-29 加）
# 跨 L2/L3/L4 任何 read 點偵測到 cancel intent 後進此確認狀態。
# 與 C2_DECISION_TIMEOUT 對齊（6s）— 都是「已警告倒數中」的緊湊子狀態，避免顧客等太久。
# silent / 倒數歸零 → 視為 YES（取消），跟 _dialog_c2_second_stage 同樣 wall-clock 行為。
CANCEL_CONFIRM_TIMEOUT: float = 6.0
