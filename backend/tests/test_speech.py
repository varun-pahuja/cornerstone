"""Speech output engine tests — Phase 8."""

from __future__ import annotations

from silentos.output import SpeechEngine, speak_decision


def test_unavailable_when_binary_missing():
    eng = SpeechEngine(binary="definitely-not-a-real-binary-xyz")
    assert not eng.available
    assert eng.speak("hello") is False


def test_speak_noop_when_unavailable():
    eng = SpeechEngine(binary="definitely-not-a-real-binary-xyz")
    assert eng.speak("hello", force=True) is False


def test_empty_text_noop():
    eng = SpeechEngine(binary="definitely-not-a-real-binary-xyz")
    assert eng.speak("") is False


def test_cooldown_blocks_second_call(monkeypatch):
    # Use a fake binary that exists so available=True, but stub subprocess.run.
    calls = []

    class _FakeProc:
        returncode = 0

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc()

    monkeypatch.setattr("silentos.output.speech.shutil.which", lambda b: "/usr/bin/fake")
    monkeypatch.setattr("silentos.output.speech.subprocess.run", fake_run)

    eng = SpeechEngine(cooldown_ms=10_000, binary="fake")
    assert eng.available
    assert eng.speak("one") is True
    # within cooldown -> blocked
    assert eng.speak("two") is False
    assert len(calls) == 1
    # force bypasses cooldown
    assert eng.speak("three", force=True) is True
    assert len(calls) == 2


def test_speak_decision_respects_enabled_and_abstain():
    eng = SpeechEngine(binary="definitely-not-a-real-binary-xyz")
    abstain = "PLEASE REPEAT"
    # disabled -> no speak
    assert speak_decision(eng, "hello", abstain, enabled=False) is False
    # None label -> no speak
    assert speak_decision(eng, None, abstain, enabled=True) is False
    # abstain label -> no speak
    assert speak_decision(eng, abstain, abstain, enabled=True) is False
