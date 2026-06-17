"""SttWorker 生命週期 / 事件處理測試（全 fake，無網路無音訊）。"""
import json

from tests.stt.conftest import FakeAudioSource, FakeWs, wait_until

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
    worker, ws, calls = _make_worker([
        _results("我要紅茶", speech_final=False),     # interim → 忽略
        _results("我要紅茶兩杯。", speech_final=True),  # final → 注入（去句號）
    ])
    worker.arm()
    assert wait_until(lambda: calls == ["我要紅茶兩杯"])
    worker.disarm()


def test_interim_empty_and_nonresults_not_injected():
    worker, ws, calls = _make_worker([
        json.dumps({"type": "Metadata"}),              # 非 Results → 忽略
        _results("", speech_final=True),               # 空 transcript → 忽略
        _results("。", speech_final=True),             # 正規化後空 → 忽略
        _results("好", speech_final=True),             # 唯一有效
    ])
    worker.arm()
    assert wait_until(lambda: calls == ["好"])
    worker.disarm()


def test_sender_streams_audio_chunks():
    worker, ws, calls = _make_worker([], chunks=[b"\x01\x02", b"\x03\x04"])
    worker.arm()
    assert wait_until(lambda: ws.sent == [b"\x01\x02", b"\x03\x04"])
    worker.disarm()


def test_arm_idempotent_single_session():
    factory_calls = []
    def ws_factory(key):
        factory_calls.append(key)
        return FakeWs()
    worker, _, _ = _make_worker([], ws_factory=ws_factory)
    worker.arm()
    worker.arm()  # 已 armed → no-op
    assert factory_calls == ["test-key"]
    worker.disarm()


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
    assert worker.is_armed() and len(wss) == 2 and len(audios) == 2
    worker.disarm()


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
    worker.disarm()


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
    worker.disarm()


def test_default_audio_factory_command(monkeypatch):
    # 只驗指令構造 + 預設聲道，不真起 subprocess（Windows 無 arecord）
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
    monkeypatch.delenv("STT_MIC_CHANNEL", raising=False)
    src = stt_mod._default_audio_factory()
    assert captured["cmd"] == ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
                               "-c", "6", "-t", "raw"]
    assert captured["kwargs"]["stdin"] == stt_mod.subprocess.DEVNULL
    assert src._channel == 1                      # 預設抽 ch1（第一支生麥）

    monkeypatch.setenv("STT_ARECORD_DEVICE", "hw:CARD=ArrayUAC10")
    stt_mod._default_audio_factory()
    assert captured["cmd"][1:3] == ["-D", "hw:CARD=ArrayUAC10"]


def test_extract_channel_picks_requested_channel():
    import struct
    from myProgram.stt import _extract_channel
    buf = (struct.pack("<6h", 10, 11, 12, 13, 14, 15)
           + struct.pack("<6h", 20, 21, 22, 23, 24, 25))
    assert struct.unpack("<2h", _extract_channel(buf, 0)) == (10, 20)
    assert struct.unpack("<2h", _extract_channel(buf, 1)) == (11, 21)
    assert struct.unpack("<2h", _extract_channel(buf, 4)) == (14, 24)


def test_extract_channel_drops_partial_frame():
    import struct
    from myProgram.stt import _extract_channel
    buf = struct.pack("<6h", 1, 2, 3, 4, 5, 6)
    assert _extract_channel(buf + b"\x09\x09", 1) == _extract_channel(buf, 1)


def test_mic_channel_env_parsing(monkeypatch):
    import myProgram.stt as stt_mod
    monkeypatch.delenv("STT_MIC_CHANNEL", raising=False)
    assert stt_mod._mic_channel() == 1            # 未設 → 預設 ch1
    monkeypatch.setenv("STT_MIC_CHANNEL", "3")
    assert stt_mod._mic_channel() == 3
    monkeypatch.setenv("STT_MIC_CHANNEL", "abc")  # 非法 → fallback
    assert stt_mod._mic_channel() == 1
    monkeypatch.setenv("STT_MIC_CHANNEL", "9")    # 越界（非 0..5）→ fallback
    assert stt_mod._mic_channel() == 1


def test_arecord_source_extracts_channel():
    import io, struct
    from myProgram.stt import _ArecordSource
    buf = b"".join(struct.pack("<6h", v, v + 1, v + 2, v + 3, v + 4, v + 5)
                   for v in (10, 20, 30))
    class _P:
        stdout = io.BytesIO(buf)
        def poll(self): return None
        def terminate(self): pass
    out = _ArecordSource(_P(), channel=1).read(6)  # 6 bytes mono = 3 樣本（內部讀 36 bytes）
    assert struct.unpack("<3h", out) == (11, 21, 31)


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


def test_prewarm_connects_keepalive_no_audio():
    ws = FakeWs([])
    audios = []
    def audio_factory():
        a = FakeAudioSource()
        audios.append(a)
        return a
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=lambda key: ws, audio_factory=audio_factory,
                       keepalive_interval=0.01)
    worker.prewarm()
    assert worker.is_armed()                          # session 已起（連線熱著）
    assert audios == []                               # 未開麥（arecord 沒被建）
    assert wait_until(lambda: len(ws.sent) > 0)       # 有送東西
    assert all(json.loads(m).get("type") == "KeepAlive" for m in ws.sent)  # 全是 KeepAlive、非音訊
    worker.disarm()


def test_arm_after_prewarm_sends_audio():
    ws = FakeWs([_results("我要紅茶兩杯。", speech_final=True)])
    calls = []
    worker = SttWorker(sink=calls.append, api_key="test-key",
                       ws_factory=lambda key: ws,
                       audio_factory=lambda: FakeAudioSource([b"\x01\x02"]),
                       keepalive_interval=0.01)
    worker.prewarm()                                  # 連線 + KeepAlive
    worker.arm()                                      # 停 KeepAlive → 開麥送真實
    assert wait_until(lambda: b"\x01\x02" in ws.sent)  # 真實音訊送出
    assert wait_until(lambda: calls == ["我要紅茶兩杯"])  # 顧客辨識注入
    worker.disarm()


def test_prewarm_then_arm_reuses_connection():
    factory_calls = []
    def ws_factory(key):
        factory_calls.append(key)
        return FakeWs()
    worker = SttWorker(sink=lambda t: None, api_key="test-key",
                       ws_factory=ws_factory, audio_factory=FakeAudioSource,
                       keepalive_interval=0.01)
    worker.prewarm()
    worker.arm()                                      # 重用 prewarm 連線，不另開 ws
    assert factory_calls == ["test-key"]
    worker.disarm()


def test_module_prewarm_delegates(monkeypatch):
    import myProgram.stt as stt_mod
    monkeypatch.setattr(stt_mod, "_worker", None)
    monkeypatch.setattr(stt_mod, "_default_ws_factory", lambda key: FakeWs())
    monkeypatch.setattr(stt_mod, "_default_audio_factory", lambda: FakeAudioSource())
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    stt_mod.prewarm()
    assert stt_mod._worker.is_armed()
    stt_mod.disarm()
