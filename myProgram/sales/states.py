"""L1-L5 各層鏈路實作（S1 v2）。

對應規格書：
    - L1：模式選擇（叫賣 / 待機 / 客服）
    - L2：詢問需求（鏈路 A 拒絕 / B-1 無法判斷 / B-2 客服 / B-3 想一下 / C 點到商品）
    - L3：加單迴圈（鏈路 A 拒絕 / B-1 無法判斷 / B-2 客服 / B-3 想一下 /
                   B-4 結帳意圖 / C-1/C-2 自動結帳）
    - L4：結帳（鏈路 A-E，含客服特殊模式 / 6 次循環 / 無法判斷 fallback）
    - L5：致謝

設計原則：
    - 對外動作以 callback 注入（speak / do_action / show）
    - 不直接 import logic.py（避免循環引用），由 logic 呼叫 state functions
    - 單檔起步，等長到 >300 行再拆 states/ 子資料夾
      （見 resources/architecture/backend-module-structure.md「擴展觸發條件」）
"""

# TODO: S1 v2 實作（待 BDD/TDD 規劃完成後動手）
