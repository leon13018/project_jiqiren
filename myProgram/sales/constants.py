"""L0 共通常數（S1 v2）。

對應規格書：resources/plans/業務程式邏輯規劃/L0_共通.md

包含：
    - 時間常數：WAIT_NO_RESPONSE / HAWK_INTERVAL / OPENCV_MUTE / THANK_DELAY
                AUTO_CHECKOUT_NOTICE / L4_MAX_LOOPS / OPENCV_DWELL
    - 商品定義：PRODUCTS（冰紅茶、刮刮樂）
    - 關鍵字白名單（7 類）：商品 / 數量 / 結帳意圖 / 拒絕意圖 / 想一下意圖 /
                          無法判斷 / 客服觸發
    - 6 組叫賣術語

設計原則：純資料常數，無 IO、無副作用。
"""

# TODO: S1 v2 實作（從 L0_共通.md 直接搬常數）
