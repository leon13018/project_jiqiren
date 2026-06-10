"""S5 非阻塞動作模組 — daemon worker thread + FIFO queue + shutdown 守衛。

S5 範圍（incremental-rebuild 第 5 步）：
    - 對外 API：`do(name)` 模組層函式 + `shutdown()` cleanup，對齊 tts.speak / tts.shutdown
    - 行為：caller thread 立即返回（不阻塞），實際 Act.runAction 在背景 daemon
      thread 內 FIFO 順序消費（不中斷 — 中斷邏輯是 S7 的選擇性升級）

S5 動機（S3 同步阻塞實機踩到的問題）：
    主線程在 do_action 內呼叫 Act.runAction 阻塞 2~5 秒，期間 TTS worker 雖在
    背景跑但 dialog flow 仍被卡住（input 讀不到、下一句 speak enqueue 延遲）。
    把動作也推背景 worker thread → 動作 + 語音可真正並行。

設計準則（依 `.claude/rules/incremental-rebuild.md` S5 段）：
    - **預設 FIFO 不中斷**：do(name) 只 put 進 queue，不終止當前動作、不清 queue
    - **單 queue 單消費者**：對齊 tts.py，避免旗號分流 race
    - **Vendor SDK lazy import**：頂層不 import ActionGroupControl，Windows pytest
      環境可 import myProgram.action 模組不觸發 vendor ImportError；worker thread
      內第一次 dispatch 時才 import
    - **Sticky 旗號守衛**：shutdown 內 `if Act.runningAction:` 才呼叫 stopAction，
      避免空轉時設旗號污染下次 runAction（見 [[vendor-stop-action-sticky]] memory）
    - **print 在 caller thread**：對齊 tts.speak — `do()` 內立即印 `[動作] xxx`，
      不放 _loop 內，保持 SSH log 時序跟 dialog flow 一致

差異對比 tts.py：
    - 無 subprocess.Popen 持有 → 不需 self._proc / self._lock（中斷靠 vendor 旗號）
    - 無 ALSA drain（動作完不需 buffer 等待）
    - 失敗策略單階段：runAction 不分 synth / play 兩階段，統一 catch Exception

caller（main.py 的 do_action callback / main 函式）使用方式：
    >>> from myProgram import action
    >>> action.do("bow")  # 立即返回（入 queue，不阻塞）
    >>> # ... 主線程做別的事 ...
    >>> action.shutdown()  # 程式退出前 cleanup（守衛 stopAction + 清 queue）
"""

from myProgram.queue_worker import QueueWorker


class ActionWorker(QueueWorker):
    """非阻塞動作 daemon worker：FIFO queue + lazy vendor import + sticky 旗號守衛。

    Thread model（依 [[threading-conventions]] 推薦：blocking 任務全推背景）：
        - 主線程：呼叫 do(name)（非阻塞 put queue）+ shutdown()（cleanup）
        - 背景 daemon thread：依序消費 queue（阻塞 Act.runAction）

    骨架（FIFO queue + daemon thread + get→_process→on_done 迴圈）在 QueueWorker
    基底；本子類別覆寫 on_thread_start（worker thread 內 lazy import vendor）+
    _process（Act.runAction + 失敗兜底）。
    """

    thread_name = "ActionWorker"

    def __init__(self) -> None:
        # 無自有欄位需先於 thread 啟動 → 直接 super().__init__()（基底建 _q +
        # 啟動 daemon thread。daemon=True：主程式退出時自動 die，不卡住整個程序
        # 退出；跟 tts.py 不同：vendor SDK 沒有 subprocess 可被「殺」— 中斷靠
        # vendor 內部 stop_action 旗號，daemon die 不會自動 reset → 仍需顯式
        # shutdown()）。
        super().__init__()

    def do(self, name: str) -> None:
        """非阻塞 producer：name 入 queue 立即 return。FIFO 順序消費（不中斷）。

        預設不中斷：name 入 queue 排隊；當前動作播完才播下一個。中斷邏輯
        （新任務覆蓋舊）是 S7 的選擇性升級，S5 不做。
        """
        self.submit(name)

    def on_thread_start(self) -> None:
        """基底 _loop 啟動後、首次 get 前的回調：lazy import vendor SDK。

        Lazy import：worker thread 啟動後（首次 _process 前）才 import vendor。
        對齊 main.py do_action callback 的 lazy import pattern；模組層仍零 vendor
        import → Windows pytest 環境 import action 模組本身不觸發 vendor ImportError
        （但 module-level singleton 啟動的 worker thread 進 on_thread_start 會 import
        vendor → Windows 上該 daemon thread 因 ImportError 死掉，主流程不受影響 —
        對齊現行 _loop 頂端先 import 的等價行為）。
        """
        from myProgram.vendor import ActionGroupControl as Act
        self._act = Act

    def _process(self, name: str) -> None:
        """處理單一動作：Act.runAction（阻塞至播完）+ 失敗兜底（基底 _loop 每輪呼叫一次）。"""
        try:
            # 阻塞至動作播完（典型 2-5 秒）。vendor runAction 內建重入保護：
            # 一進入 check `runningAction is False` 才執行；又因本 worker
            # 是單線程 FIFO 消費，不會有並發 runAction 呼叫。
            self._act.runAction(name)
        except Exception as e:
            # vendor runAction 罕見 raise（sqlite 連結錯 / setBusServoPulse
            # 拋錯等），但 .d6a 不存在是 silent print 不 raise。兜底 catch
            # Exception 確保 worker 不被單次失敗炸死、繼續消費下一輪。
            print(f"[動作] ⚠️ runAction 失敗")
            print(f"[動作]   exception = {type(e).__name__}: {e!r}")
            print(f"[動作]   name      = {name!r}")
            print(f"[動作] 此動作略過，繼續下一輪")

    def shutdown(self) -> None:
        """程式退出 cleanup：清 queue + 守衛 stopAction。

        Sticky 旗號處理（見 [[vendor-stop-action-sticky]] memory）：
            Act.stopAction() 設 stop_action=True 是 sticky，只在 runAction
            內部 loop 才被消耗 reset。若空轉時呼叫 → 污染下次 runAction
            一進入就被打斷。守衛 `if Act.runningAction:` 確保只在 worker
            真的在跑 runAction 時才 stop。

        清空 queue：避免 daemon die 前還消費剩餘任務（雖然 daemon 主退出時
        會被 runtime 清掉，但 drain 一下更乾淨）。

        daemon thread 隨主程式退出自動 die，不需 join。
        """
        from myProgram.vendor import ActionGroupControl as Act
        # 1. 清 queue（避免 daemon die 前消費剩餘任務；共用 drain_queue helper）
        self.drain()
        # 2. 守衛呼叫 stopAction：只在 vendor 正在跑 runAction 時才設旗號，
        # 空轉時呼叫會污染下次 runAction（sticky 旗號 reset 只發生在 runAction
        # 內部 loop 內，空轉時沒人消費 → 設了就一直 True）。
        if Act.runningAction:
            Act.stopAction()


# Module-level singleton：import 時自動啟動 daemon thread。
# 使用者多次 `from myProgram import action` 不會重複建（Python module cache）。
_worker = ActionWorker()


def do(name: str) -> None:
    """對外 API：非阻塞動作（入 queue 立即返回）。

    `print(f"[動作] {name}")` 在 **caller thread** 立即印 — 不放到 worker
    內 — 對齊 tts.speak 的 print 時序，確保 SSH log 跟 dialog flow 一致
    （user 看到「[動作] xxx」緊接著對話進展，不會因 worker 延遲導致 log 亂序）。

    對比 S3 同步版：對外 signature 完全相容（接 name、回 None），但行為從
    「阻塞至動作播完」改為「立即返回（背景排隊播）」。
    """
    print(f"[動作] {name}")
    _worker.do(name)


def shutdown() -> None:
    """對外 API：清 queue + 守衛 stopAction（main.py exit 時呼叫）。

    使用情境：main() 的 finally block 內呼叫，跟 tts.shutdown 對稱 —
    程式退出時確保不留下 sticky 旗號污染（雖然程式都要退了，但 cleanup
    語義一致比較好維護）。
    """
    _worker.shutdown()
