# Pi 端待辦 — S3 同步動作驗證

**建立日期：** 2026-05-27
**對應提交：** worktree commit `888ac76 feat(s3): wire synchronous Act.runAction at L1 hawk / L2 / L3 / L4 / L5 trigger points`（加上本檔 + `projectStructure.md` 收尾 commit）

本輪程式碼層接入 S3 同步動作（[[incremental-rebuild]] 第 3 步）— `do_action(name)` callback 同步阻塞跑廠商 `Act.runAction(name)` 至播完才 return。新增 5 個觸發點：L1 hawk entry、L2/L3 dialog entry、L4 鏈路 A（兩處）、L5 entry。本檔重點是 **驗證 .d6a 動作檔存在 + 全 flow 觀察 5 觸發點 + 廠商 sticky flag 不污染**。

---

## Step 0：確認 git pull 已同步

本機 push 後 PostToolUse hook 會自動跑 `sync_pi.ps1`（SSH 過去 `git pull` + 清 `__pycache__`）。先在 Pi 端確認：

```bash
cd /home/pi/Desktop/project_jiqiren
git log -1 --oneline
```

應看到本輪 S3 commit 標題（含 `feat(s3)` 字樣 + Co-Authored-By Claude）。若沒看到 → hook sync 失敗，使用者本機手動跑 `& sync_pi.ps1`。

---

## Step 1：確認自訂動作檔存在

```bash
ls -la /home/pi/TonyPi/ActionGroups/L2.d6a /home/pi/TonyPi/ActionGroups/L3.d6a
ls -la /home/pi/TonyPi/ActionGroups/wave_hand.d6a /home/pi/TonyPi/ActionGroups/bow.d6a
```

預期 4 個檔都存在：
- `L2.d6a` / `L3.d6a` — 使用者自訂（2026-05-27 新增）
- `wave_hand.d6a` / `bow.d6a` — 廠商原生

若任一缺失：
- `L2.d6a` / `L3.d6a` 缺 → 使用者需在 Hiwonder TonyPi 動作編輯器內建立 + 匯出到此路徑
- `wave_hand.d6a` / `bow.d6a` 缺 → 廠商映像損毀，反查 `/home/pi/TonyPi/ActionGroups/` 是否有對應檔；缺則需從廠商備份還原

---

## Step 2：smoke test 個別動作（不跑主程式，純動作 pipeline）

```bash
cd /home/pi/Desktop/project_jiqiren
python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('wave_hand')"
```

預期：
1. 終端可能印一些廠商 SDK 內部訊息（pigpio / 舵機初始化）
2. **機器人開始揮手**（wave_hand 動作組）
3. 動作播完約 2-4 秒後 Python 阻塞 return，prompt 回來

依序測 4 個動作：

```bash
python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('L2')"
python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('L3')"
python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('bow')"
```

### 故障排除

| 症狀 | 可能原因 | 排查 |
|---|---|---|
| `FileNotFoundError: ... ActionGroups/L2.d6a` | Step 1 確認時沒看到該檔 | 回 Step 1，建立 / 匯出該動作 |
| `ModuleNotFoundError: ActionGroupControl` | 廠商 SDK 路徑問題 | 確認 `/home/pi/TonyPi/HiwonderSDK/` 存在；Pi 重灌可能有差 |
| `pigpio.error` / `BusServoCmd error` | 舵機通訊失敗（電源 / 接線） | 檢查機器人電源開關、舵機線接觸 |
| Python return 但機器人沒動 | 廠商 SDK 載入了但舵機沒回應 | `sudo systemctl status pigpiod`；若 down → `sudo systemctl start pigpiod` |
| 動作做到一半卡住不動 | 廠商 sticky flag 殘留（前一輪呼叫過 `stopAction()`）| 重開機；S3 自身不會呼叫 stopAction，但若手動 / 其他程式呼叫過會殘留 |

---

## Step 3：跑主程式全 flow，觀察 5 個觸發點

```bash
cd /home/pi/Desktop/project_jiqiren
python3.11 -m myProgram
```

預期觀察序列（含動作觸發位置 ★）：

1. 印操作小抄 → L1 主選單朗讀
2. 按 `1` 進叫賣模式
   - ★ **L1 hawk entry**：機器人**揮手**（`wave_hand`）↻ 同步阻塞約 2-4s
   - 揮手播完才聽到「來喔！冰紅茶 27 元、刮刮樂 180 元...」第 1 句叫賣
   - **後續輪播叫賣（60s HAWK_INTERVAL）只 speak，不動作** ← 此為設計（servo 過熱防護）
3. 按 `c` 模擬偵測顧客 → 進 L2
   - ★ **L2 dialog entry（cart 空）**：機器人跑 **L2 動作**（使用者自訂） ↻ 同步阻塞
   - 動作播完才聽到「歡迎光臨！...請問要什麼？」
4. 輸入「冰紅茶一杯」→ cart 非空，加單 → L3
   - ★ **L3 dialog entry（cart 非空）**：機器人跑 **L3 動作**（使用者自訂） ↻ 同步阻塞
   - 動作播完才聽到 L3 加單回應
5. 輸入「結帳」→ 進 L4
6. 終端輸入 `s` 模擬掃碼成功
   - ★ **L4 鏈路 A（主 dispatcher）**：聽到「付款成功，謝謝惠顧」+ 機器人**鞠躬**（`bow`）↻ 同步阻塞約 2-4s
   - 鞠躬播完才進 L5
7. L5 自動跑致謝
   - ★ **L5 entry**：聽到「謝謝光臨，歡迎下次再來」+ 機器人**揮手**（`wave_hand`）↻ 同步阻塞
   - 揮手播完才 sleep `THANK_DELAY` 秒，自動回 L0 子例程 A

**注意對話節奏：S3 是同步阻塞動作 — `do_action()` 必須等動作播完才 return**。對比 S2 是純 TTS 阻塞，S3 多加了動作阻塞。L1/L2/L3 觸發點動作時 dialogue 會停下；L4/L5 觸發點本來就是 exit 路徑無傷。

---

## Step 4：vendor sticky flag 不污染驗證（連續兩輪交易）

S3 規格特別檢核項。流程：完成 Step 3 完整一輪交易後 **不重啟主程式**，繼續第二輪：

8. L5 回 L0 → 按 `1` 重進叫賣 → 按 `c` 進 L2 → 全 flow 跑第二輪
9. **觀察第二輪所有 5 個動作觸發點仍正常播完整動作**（不應有「動作只播一半就 return」「動作直接跳過」等症狀）

預期：第二輪所有動作行為與第一輪一致。

若第二輪動作異常 → 廠商 sticky flag 污染嫌疑（雖然 S3 本身不呼叫 `stopAction`，但廠商 SDK 內部可能有其他殘留旗號）→ 截錯誤訊息 + 描述哪個觸發點異常回報主 agent。

---

## 完成後

跑通 Step 3 + Step 4 即代表 S3 接入成功。請跟主 agent 回報：

1. **Step 1 動作檔確認狀況**（`L2.d6a` / `L3.d6a` 存在嗎？大小看起來合理嗎？）
2. **Step 2 個別動作 smoke test 結果**（4 個動作是否都播完整）
3. **Step 3 全 flow 5 個觸發點觀察**（每個觸發點是否都聽到動作 + 動作後才繼續 speak / 推進狀態）
4. **Step 4 第二輪行為**（與第一輪一致嗎？有沒有動作截斷 / 跳過 / 異常停留？）
5. **體感反饋**：哪些觸發點同步阻塞感覺**OK**、哪些感覺**太卡**（特別 L1/L2/L3 dialogue 期間的阻塞 — 為 S5 worker 改造優先序排序用）

任一步卡住把錯誤訊息貼給主 agent 協助診斷。**S5 非阻塞動作 worker**（廠商 `Act.runAction()` 推到 background thread）會在 S3 驗證通過 + 評估體驗後才開工。
