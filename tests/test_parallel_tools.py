"""agent.parallel_tools için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

import time

from agent.parallel_tools import (
    MAX_PARALLEL_FILES,
    read_files_in_parallel,
    run_parallel,
    should_parallelize_file_reads,
)


def test_run_parallel_empty_list_returns_empty() -> None:
    assert run_parallel([]) == []


def test_run_parallel_single_task_returns_single_result() -> None:
    result = run_parallel([lambda: 42])
    assert result == [42]


def test_run_parallel_preserves_input_order() -> None:
    tasks = [lambda i=i: i for i in range(10)]
    result = run_parallel(tasks)
    assert result == list(range(10))


def test_run_parallel_is_actually_faster_than_sequential() -> None:
    """Gerçek eşzamanlılık kanıtı: 4 tane 0.2s'lik bekleme, sıralı ~0.8s
    sürer, paralel çalıştırılırsa (I/O bound, GIL serbest bırakılır)
    belirgin şekilde daha kısa sürmeli."""

    def slow_task() -> int:
        time.sleep(0.2)
        return 1

    tasks = [slow_task for _ in range(4)]

    start = time.monotonic()
    results = run_parallel(tasks, max_workers=4)
    elapsed = time.monotonic() - start

    assert results == [1, 1, 1, 1]
    # Sıralı olsaydı ~0.8s sürerdi; paralelde makul bir üst sınır olarak
    # 0.6s'nin altında bitmesini bekliyoruz (CI/yavaş makine payı ile).
    assert elapsed < 0.6, f"Paralel çalıştırma yeterince hızlı değildi: {elapsed:.2f}s"


def test_run_parallel_catches_exceptions_without_raising() -> None:
    def failing_task() -> None:
        raise ValueError("boom")

    def ok_task() -> str:
        return "ok"

    results = run_parallel([failing_task, ok_task])

    assert isinstance(results[0], ValueError)
    assert results[1] == "ok"


def test_should_parallelize_file_reads_requires_at_least_two() -> None:
    assert should_parallelize_file_reads([]) is False
    assert should_parallelize_file_reads(["a.py"]) is False
    assert should_parallelize_file_reads(["a.py", "b.py"]) is True


def test_should_parallelize_file_reads_respects_max_limit() -> None:
    many_files = [f"file_{i}.py" for i in range(MAX_PARALLEL_FILES + 5)]
    assert should_parallelize_file_reads(many_files) is False
    exactly_max = [f"file_{i}.py" for i in range(MAX_PARALLEL_FILES)]
    assert should_parallelize_file_reads(exactly_max) is True


def test_read_files_in_parallel_maps_paths_to_results() -> None:
    def fake_read(path: str) -> str:
        return f"content-of-{path}"

    result = read_files_in_parallel(["a.py", "b.py", "c.py"], fake_read)

    assert result == {
        "a.py": "content-of-a.py",
        "b.py": "content-of-b.py",
        "c.py": "content-of-c.py",
    }


def test_read_files_in_parallel_isolates_individual_failures() -> None:
    def fake_read(path: str) -> str:
        if path == "bad.py":
            raise FileNotFoundError("yok")
        return f"ok-{path}"

    result = read_files_in_parallel(["good1.py", "bad.py", "good2.py"], fake_read)

    assert result["good1.py"] == "ok-good1.py"
    assert isinstance(result["bad.py"], FileNotFoundError)
    assert result["good2.py"] == "ok-good2.py"


def test_read_files_in_parallel_respects_max_files_limit() -> None:
    many_files = [f"file_{i}.py" for i in range(MAX_PARALLEL_FILES + 10)]
    call_count = {"n": 0}

    def counting_read(path: str) -> str:
        call_count["n"] += 1
        return "content"

    result = read_files_in_parallel(many_files, counting_read)

    assert len(result) == MAX_PARALLEL_FILES
    assert call_count["n"] == MAX_PARALLEL_FILES
