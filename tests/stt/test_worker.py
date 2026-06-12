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
