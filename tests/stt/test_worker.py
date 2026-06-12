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
