"""agent.loop_detector için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

from agent.loop_detector import (
    AMBIGUITY_THRESHOLD,
    MAX_TURNS_WITHOUT_PROGRESS,
    REPEAT_THRESHOLD,
    LoopDetector,
    contains_uncertainty_phrase,
    summarize_loop_detection,
)


def test_no_signal_when_history_is_empty() -> None:
    detector = LoopDetector()
    result = detector.check()
    assert result.triggered is False


def test_successful_tool_calls_do_not_trigger_repeat_detection() -> None:
    detector = LoopDetector()
    for _ in range(REPEAT_THRESHOLD + 1):
        detector.record_tool_call("read_file", {"path": "a.py"}, succeeded=True)
    result = detector.check()
    assert result.triggered is False


def test_repeated_failing_identical_calls_trigger_detection() -> None:
    detector = LoopDetector()
    for _ in range(REPEAT_THRESHOLD):
        detector.record_tool_call("edit_file", {"path": "a.py", "diff": "x"}, succeeded=False)
    result = detector.check()
    assert result.triggered is True
    assert "edit_file" in result.reason


def test_repeated_failing_similar_but_not_identical_calls_trigger_detection() -> None:
    """K19: fuzzy benzerlik - argümanlar birebir aynı olmasa da (örn. farklı
    satır) tekrar olarak sayılmalı."""
    detector = LoopDetector()
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "line 10 old->new"}, succeeded=False)
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "line 11 old->new"}, succeeded=False)
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "line 12 old->new"}, succeeded=False)
    result = detector.check()
    assert result.triggered is True


def test_different_tools_do_not_trigger_repeat_detection() -> None:
    detector = LoopDetector()
    detector.record_tool_call("read_file", {"path": "a.py"}, succeeded=False)
    detector.record_tool_call("grep_search", {"query": "x"}, succeeded=False)
    detector.record_tool_call("glob_search", {"pattern": "*.py"}, succeeded=False)
    result = detector.check()
    assert result.triggered is False


def test_dissimilar_arguments_do_not_trigger_repeat_detection() -> None:
    detector = LoopDetector()
    detector.record_tool_call("read_file", {"path": "a.py"}, succeeded=False)
    detector.record_tool_call("read_file", {"path": "completely_different_file_xyz.md"}, succeeded=False)
    detector.record_tool_call("read_file", {"path": "another_unrelated_thing.json"}, succeeded=False)
    result = detector.check()
    assert result.triggered is False


def test_one_success_among_recent_calls_resets_repeat_detection() -> None:
    detector = LoopDetector()
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "x"}, succeeded=False)
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "x"}, succeeded=True)
    detector.record_tool_call("edit_file", {"path": "a.py", "diff": "x"}, succeeded=False)
    result = detector.check()
    assert result.triggered is False


def test_ambiguity_threshold_triggers_detection() -> None:
    detector = LoopDetector()
    for _ in range(AMBIGUITY_THRESHOLD):
        detector.record_ambiguous_response()
    result = detector.check()
    assert result.triggered is True
    assert "belirsiz" in result.reason.lower()


def test_ambiguity_below_threshold_does_not_trigger() -> None:
    detector = LoopDetector()
    for _ in range(AMBIGUITY_THRESHOLD - 1):
        detector.record_ambiguous_response()
    result = detector.check()
    assert result.triggered is False


def test_no_progress_threshold_triggers_detection() -> None:
    detector = LoopDetector()
    for _ in range(MAX_TURNS_WITHOUT_PROGRESS):
        detector.record_tool_call("read_file", {"path": f"file_{_}.py"}, succeeded=False)
    result = detector.check()
    assert result.triggered is True


def test_progress_resets_no_progress_counter() -> None:
    detector = LoopDetector()
    for i in range(MAX_TURNS_WITHOUT_PROGRESS - 1):
        detector.record_tool_call("read_file", {"path": f"totally_unrelated_file_{i}.py"}, succeeded=False)
    detector.record_progress()
    assert detector.turns_without_progress == 0

    triggered, _ = detector.detect_no_progress()
    assert triggered is False


def test_contains_uncertainty_phrase_detects_known_patterns() -> None:
    assert contains_uncertainty_phrase("Bunu nasıl yapacağımı bilmiyorum.")
    assert contains_uncertainty_phrase("I'm not sure how to proceed.")
    assert contains_uncertainty_phrase("Could you please clarify?")


def test_contains_uncertainty_phrase_returns_false_for_normal_text() -> None:
    assert not contains_uncertainty_phrase("Dosya başarıyla okundu.")
    assert not contains_uncertainty_phrase("")
    assert not contains_uncertainty_phrase(None)


def test_summarize_loop_detection_includes_reason_and_actions() -> None:
    detector = LoopDetector()
    for _ in range(REPEAT_THRESHOLD):
        detector.record_tool_call("edit_file", {"path": "a.py", "diff": "x"}, succeeded=False)
    result = detector.check()

    summary = summarize_loop_detection(result, ["edit_file çağrıldı: a.py", "edit_file çağrıldı: a.py"])

    assert "DÖNGÜ TESPİTİ" in summary
    assert result.reason in summary
    assert "edit_file çağrıldı: a.py" in summary
    assert "Nasıl ilerlemek istersiniz?" in summary
