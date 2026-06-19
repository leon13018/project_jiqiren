"""SttWorker 生命週期 / 事件處理測試（全 fake，無網路無音訊）。"""
import json
import threading
import time

from tests.stt.conftest import FakeAudioSource, FakeWs, wait_until

import myProgram.stt as stt_mod
from myProgram.stt import SttWorker


def _results(transcript: str, speech_final: bool) -> str:
    return json.dumps({
        "type": "Results",
        "speech_final": speech_final,
        "channel": {"alternatives": [{"transcript": transcript}]},
    })


def test_no_key_disables_and_warns_once(capsys):
    calls = []
    worker = SttWorker(sink=calls.append, api_key=None,
                       ws_factory=lambda key: FakeWs(),
                       audio_factory=FakeAudioSource)
    worker.arm()
    worker.arm()  # 第二次不再印
    out = capsys.readouterr().out
    assert out.count("DEEPGRAM_API_KEY") == 1
    assert not worker.is_armed()
    assert calls == []


def _make_worker(messages, chunks=(), ws_factory=None):
    calls = []
    ws = FakeWs(messages)
    worker = SttWorker(
        sink=calls.append,
        api_key="test-key",
        ws_factory=ws_factory or (lambda key: ws),
        audio_factory=lambda: FakeAudioSource(chunks),
    )
    return worker, ws, calls


def test_speech_final_injected_normalized():
    worker, ws, calls = _make_worker([])
    worker.arm()                                       # 先進收音窗（capturing=True）
    ws.feed(_results("我要紅茶", speech_final=False))   # interim → 忽略
    ws.feed(_results("我要紅茶兩杯。", speech_final=True))  # final → 注入（去句號）
    assert wait_until(lambda: calls == ["我要紅茶兩杯"])
    worker.shutdown()


def test_empty_speech_final_falls_back_to_last_interim():
    """空白 speech_final（Deepgram 偶發定稿空、文字在 interim）→ 退用本句最後非空
    interim，不再整輪漏字。"""
    worker, ws, calls = _make_worker([])
    worker.arm()                                          # 進收音窗（capturing=True）
    ws.feed(_results("紅茶三瓶刮刮樂五張", speech_final=False))  # interim 帶文字
    ws.feed(_results("", speech_final=True))              # 空白定稿 → 退用上面的 interim
    assert wait_until(lambda: calls == ["紅茶三瓶刮刮樂五張"])
    worker.shutdown()


def test_interim_empty_and_nonresults_not_injected():
    worker, ws, calls = _make_worker([])
    worker.arm()                                       # 先進收音窗（capturing=True）
    ws.feed(json.dumps({"type": "Metadata"}))          # 非 Results → 忽略
    ws.feed(_results("", speech_final=True))           # 空 transcript → 忽略
    ws.feed(_results("。", speech_final=True))         # 正規化後空 → 忽略
    ws.feed(_results("好", speech_final=True))         # 唯一有效
    assert wait_until(lambda: calls == ["好"])
    worker.shutdown()


def test_sender_streams_audio_chunks():
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02", b"\x03\x04"])
    worker.arm()
    assert wait_until(lambda: ws.sent == [b"\x01\x02", b"\x03\x04"])
    worker.shutdown()


def test_arm_idempotent_single_session():
    factory_calls = []
    def ws_factory(key):
        factory_calls.append(key)
        return FakeWs()
    worker, _, _ = _make_worker([], ws_factory=ws_factory)
    worker.arm()
    worker.arm()  # 已 armed → no-op
    assert factory_calls == ["test-key"]
    worker.shutdown()


def test_disarm_closes_audio_and_allows_rearm():
    audios = []
    def audio_factory():
        a = FakeAudioSource()
        audios.append(a)
        return a
    wss = []
    def ws_factory(key):
        w = FakeWs()
        wss.append(w)
        return w
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=ws_factory, audio_factory=audio_factory)
    worker.arm()
    assert worker.is_armed()
    worker.disarm()
    assert not worker.is_armed()
    assert audios[0].closed            # arecord 已 terminate
    worker.disarm()                    # 冪等：重複 disarm no-op
    worker.arm()                       # re-arm 起全新 session
    assert worker.is_armed() and len(wss) == 1 and len(audios) == 2   # ws 復用、arecord 每輪重開
    worker.shutdown()


def test_shutdown_equals_disarm():
    worker, _, _ = _make_worker([])
    worker.arm()
    worker.shutdown()
    assert not worker.is_armed()


class _AuthError(Exception):
    """模擬 websockets InvalidStatus(401)——duck-typing 匹配 _is_auth_error。"""
    def __init__(self):
        super().__init__("HTTP 401")
        self.response = type("R", (), {"status_code": 401})()


def test_connect_retry_once_then_success():
    attempts = []
    ws = FakeWs()
    def flaky_factory(key):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("transient")
        return ws
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=flaky_factory, audio_factory=FakeAudioSource)
    worker.arm()
    assert worker.is_armed() and len(attempts) == 2
    worker.shutdown()


def test_connect_fail_twice_gives_up_but_not_disabled(capsys):
    def dead_factory(key):
        raise ConnectionError("down")
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=dead_factory, audio_factory=FakeAudioSource)
    worker.arm()
    assert not worker.is_armed()
    assert "連線失敗" in capsys.readouterr().out
    worker.arm()                       # 暫時失敗不停用 → 下次 arm 再試
    assert "連線失敗" in capsys.readouterr().out


def test_401_disables_permanently(capsys):
    attempts = []
    def auth_fail_factory(key):
        attempts.append(1)
        raise _AuthError()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=auth_fail_factory, audio_factory=FakeAudioSource)
    worker.arm()
    assert "401" in capsys.readouterr().out
    worker.arm()                       # 已停用 → 不再嘗試連線
    assert len(attempts) == 1 and not worker.is_armed()


def test_stream_interruption_warns(capsys):
    import time
    ws = FakeWs([])
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    ws.close()                         # 模擬伺服器端斷線（stop 未設 → 應印警示）
    time.sleep(0.2)                    # receiver 反應時間（recv 在 close 後立即 raise）
    assert "串流中斷" in capsys.readouterr().out
    worker.shutdown()


def test_default_audio_factory_command(monkeypatch):
    # 只驗指令構造不真起 subprocess（Windows 無 arecord）
    import myProgram.stt as stt_mod
    captured = {}
    class FakeProc:
        stdout = None
        def poll(self): return None
        def terminate(self): pass
    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()
    monkeypatch.setattr(stt_mod.subprocess, "Popen", fake_popen)
    monkeypatch.delenv("STT_ARECORD_DEVICE", raising=False)
    stt_mod._default_audio_factory()
    assert captured["cmd"] == ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
                               "-c", "1", "-t", "raw"]
    assert captured["kwargs"]["stdin"] == stt_mod.subprocess.DEVNULL

    monkeypatch.setenv("STT_ARECORD_DEVICE", "plughw:1,0")
    stt_mod._default_audio_factory()
    assert captured["cmd"][1:3] == ["-D", "plughw:1,0"]


def test_module_api_lazy_singleton(monkeypatch):
    import myProgram.stt as stt_mod
    monkeypatch.setattr(stt_mod, "_worker", None)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    stt_mod.shutdown()                     # singleton 未建 → no-op 不炸
    assert stt_mod._worker is None
    stt_mod.arm()                          # 首次 arm 建 singleton（無 key → 停用警告）
    assert stt_mod._worker is not None
    stt_mod.disarm()
    stt_mod.shutdown()


def test_timing_log_emitted_on_speech_final_when_env_set(monkeypatch, capsys):
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    worker, ws, calls = _make_worker([])
    worker.arm()                                       # 先進收音窗（capturing=True）
    ws.feed(_results("好", speech_final=True))
    assert wait_until(lambda: calls == ["好"])
    worker.shutdown()
    out = capsys.readouterr().out
    assert "[計時]" in out and "開麥後" in out


def test_timing_log_silent_when_env_unset(monkeypatch, capsys):
    monkeypatch.delenv("STT_TTS_TIMING", raising=False)
    worker, ws, calls = _make_worker([])
    worker.arm()                                       # 先進收音窗（capturing=True）
    ws.feed(_results("好", speech_final=True))
    assert wait_until(lambda: calls == ["好"])
    worker.shutdown()
    assert "[計時]" not in capsys.readouterr().out


def test_connect_timing_logged_when_env_set(monkeypatch, capsys):
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    worker, ws, calls = _make_worker([])
    worker.arm()
    worker.shutdown()
    out = capsys.readouterr().out
    assert "[計時]" in out and "開麥連線" in out


def test_first_chunk_timing_logged_when_env_set(monkeypatch, capsys):
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02", b"\x03\x04"])
    worker.arm()
    assert wait_until(lambda: ws.sent == [b"\x01\x02", b"\x03\x04"])
    worker.shutdown()
    out = capsys.readouterr().out
    assert "[計時]" in out and "開麥→第一個音框" in out


def test_connection_reused_across_arm_disarm():
    """連兩輪 arm/disarm → ws_factory 只被呼叫 1 次（整場共用一條連線）。"""
    factory_calls = []
    ws = FakeWs()
    def factory(key):
        factory_calls.append(key)
        return ws
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.arm(); worker.disarm()
    worker.arm(); worker.disarm()
    assert factory_calls == ["test-key"]
    worker.shutdown()


def test_speech_final_not_injected_when_not_capturing():
    """收音窗外（disarm 後）到達的 speech_final 不注入；再 arm 才注入。"""
    calls = []
    ws = FakeWs()
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()                                   # capturing=False，連線/receiver 仍在
    ws.feed(_results("殘響", speech_final=True))       # 非收音窗
    time.sleep(0.1)                                   # 給 receiver 處理
    assert calls == []                                # 閘門擋住
    worker.arm()                                      # 收音窗
    ws.feed(_results("正確", speech_final=True))
    assert wait_until(lambda: calls == ["正確"])
    worker.shutdown()


def test_dead_connection_reconnects_on_next_arm():
    """連線死亡（ws.close）→ 標記 _ws None → 下次 arm 重連（ws_factory 再呼叫）。"""
    wss = []
    def factory(key):
        w = FakeWs()
        wss.append(w)
        return w
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.arm()
    assert wait_until(lambda: len(wss) == 1)
    wss[0].close()                                    # 模擬斷線 → receiver recv 拋出
    assert wait_until(lambda: worker._ws is None)     # 標記死亡
    worker.disarm()
    worker.arm()                                      # 重連
    assert wait_until(lambda: len(wss) == 2)
    worker.shutdown()


def _control_sent(ws, name):
    return any(isinstance(s, str) and name in s for s in ws.sent)


def test_keepalive_sent_when_idle(monkeypatch):
    """disarm 後（capturing=False）keepalive thread 送 KeepAlive 撐住連線。"""
    monkeypatch.setattr(stt_mod, "_KEEPALIVE_INTERVAL", 0.02)
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()
    assert wait_until(lambda: _control_sent(ws, "KeepAlive"))
    worker.shutdown()


def test_finalize_not_sent_on_disarm():
    """disarm 不送 Finalize：逐輪 mid-stream Finalize 會破壞 Deepgram 對後續 utterance
    的 finalization（speech_final 空白、辨識整輪漏掉）。改靠 endpointing 自然 finalize。"""
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.disarm()
    assert not _control_sent(ws, "Finalize")
    worker.shutdown()


def test_closestream_sent_on_shutdown():
    """shutdown 送 CloseStream 優雅關閉。"""
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    worker.shutdown()
    assert _control_sent(ws, "CloseStream")


def test_malformed_message_does_not_kill_connection():
    """單則壞訊息（非 JSON）→ receiver 略過該則、連線存活；隨後正常 speech_final 仍注入。"""
    calls = []
    ws = FakeWs()
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=FakeAudioSource)
    worker.arm()
    ws.feed("這不是 JSON{{{")                          # 壞訊息：json.loads 會炸
    ws.feed(_results("正確", speech_final=True))        # 正常訊息
    assert wait_until(lambda: calls == ["正確"])        # 壞訊息被略過、loop 存活、正常訊息照注入
    assert worker._ws is not None                       # 連線未被壞訊息殺掉
    worker.shutdown()


def test_disarm_skips_finalize_when_sender_stuck():
    """sender 卡死（join 逾時仍 alive）→ disarm 仍 ~1s 內返回不掛死、且不送 Finalize
    （已移除逐輪 Finalize；卡死的 sender 不影響 disarm 收尾）。"""
    release = threading.Event()

    class _BlockingAudio:
        def __init__(self):
            self.closed = False
        def read(self, n):
            release.wait(timeout=5.0)   # 卡住模擬 sender 不收（真實情境為卡在 ws.send）
            return b""
        def close(self):
            self.closed = True

    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=_BlockingAudio)
    worker.arm()
    assert wait_until(lambda: worker._capturing)
    start = time.monotonic()
    worker.disarm()                                  # sender 卡在 read → join(1.0) 逾時
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"disarm 不應掛死，實際 {elapsed:.2f}s"
    assert not _control_sent(ws, "Finalize"), "sender 卡死時不應送 Finalize"
    release.set()                                    # cleanup：放行 sender
    worker.shutdown()


def test_prearm_connects_in_background():
    """未連時 prearm 背景建線；隨後 arm 復用同一連線（ws_factory 仍 1 次）。"""
    factory_calls = []
    ws = FakeWs()
    def factory(key):
        factory_calls.append(key)
        return ws
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=factory, audio_factory=FakeAudioSource)
    worker.prearm()
    assert wait_until(lambda: worker._ws is not None)   # 背景已建線
    worker.arm()                                        # 復用
    worker.disarm()
    assert factory_calls == ["test-key"]                # 只連一次
    worker.shutdown()


def test_prearm_noop_when_already_connected():
    factory_calls = []
    ws = FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: factory_calls.append(key) or ws,
                       audio_factory=FakeAudioSource)
    worker.arm()                                        # 已連
    worker.prearm()                                     # no-op
    worker.disarm()
    assert factory_calls == ["test-key"]
    worker.shutdown()


def test_diagnostic_logs_interim_when_timing_set(monkeypatch, capsys):
    """殭屍診斷埋點：STT_TTS_TIMING 設時 receiver 把每則 Deepgram 訊息（含 interim）
    印出——用以判定殭屍輪有無 interim 文字（(B) arecord 嫌疑 vs (A) 連線真殭屍）。"""
    monkeypatch.setenv("STT_TTS_TIMING", "1")
    worker, ws, calls = _make_worker([])
    worker.arm()                                       # 進收音窗（capturing=True）
    ws.feed(_results("紅茶", speech_final=False))       # interim（現狀被早 continue 掉看不到）
    assert wait_until(lambda: "Deepgram Results final=False" in capsys.readouterr().out)
    worker.shutdown()


def test_shutdown_does_not_join_unstarted_thread():
    """receiver-start race：shutdown 搶在 _ensure_connected 存 ref 與 start() 之間時，
    join 未 start 的 thread 不應拋 RuntimeError（is_alive 守衛跳過未 start thread）。"""
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: FakeWs(), audio_factory=FakeAudioSource)
    # 手動重現 race 窗：thread 物件已存但尚未 start
    worker._receiver = threading.Thread(target=lambda: None)
    worker._keepalive = threading.Thread(target=lambda: None)
    worker._ws = FakeWs()
    worker._conn_stop = threading.Event()
    worker.shutdown()  # 未 start thread → 不應 RuntimeError: cannot join thread before it is started


def test_prearm_noop_without_key():
    factory_calls = []
    worker = SttWorker(sink=lambda t: None, api_key=None,
                       ws_factory=lambda key: factory_calls.append(key),
                       audio_factory=FakeAudioSource)
    worker.prearm()
    time.sleep(0.1)
    assert factory_calls == []                          # 缺 key → 不建線
