"""agent.tools için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

import pytest

from agent.tools import ToolError, execute_tool, glob_search, grep_search, read_file, run_shell


@pytest.fixture
def sample_project(tmp_path):
    """Basit bir örnek proje ağacı oluşturur."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    print('hello world')\n")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "README.md").write_text("# Proje\n\nBu bir test projesidir.\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git internal file, taranmamalı")
    return tmp_path


def test_read_file_returns_content(sample_project) -> None:
    content = read_file("README.md", root=sample_project)
    assert "test projesidir" in content


def test_read_file_missing_raises_tool_error(sample_project) -> None:
    with pytest.raises(ToolError, match="bulunamadı"):
        read_file("yok.txt", root=sample_project)


def test_read_file_rejects_path_traversal(sample_project) -> None:
    with pytest.raises(ToolError, match="reddedildi"):
        read_file("../../etc/passwd", root=sample_project)


def test_read_file_truncates_large_files(sample_project, monkeypatch) -> None:
    import agent.tools as tools_module

    monkeypatch.setattr(tools_module, "MAX_READ_FILE_BYTES", 10)
    (sample_project / "big.txt").write_text("0123456789ABCDEF")
    content = read_file("big.txt", root=sample_project)
    assert content.startswith("0123456789")
    assert "kırpıldı" in content


def test_glob_search_finds_py_files(sample_project) -> None:
    results = glob_search("*.py", root=sample_project)
    assert "src/main.py" in results
    assert "src/utils.py" in results


def test_glob_search_excludes_git_directory(sample_project) -> None:
    results = glob_search("*", root=sample_project)
    assert not any(".git" in r for r in results)


def test_grep_search_finds_matching_line(sample_project) -> None:
    results = grep_search("hello world", root=sample_project)
    assert len(results) == 1
    assert results[0]["file"] == "src/main.py"
    assert "hello world" in results[0]["content"]


def test_grep_search_is_case_insensitive(sample_project) -> None:
    results = grep_search("HELLO WORLD", root=sample_project)
    assert len(results) == 1


def test_grep_search_respects_file_pattern(sample_project) -> None:
    results = grep_search("def", root=sample_project, file_pattern="*.md")
    assert results == []


def test_execute_tool_dispatches_to_read_file(sample_project) -> None:
    result = execute_tool("read_file", {"path": "README.md"}, root=sample_project)
    assert "test projesidir" in result


def test_execute_tool_unknown_name_raises(sample_project) -> None:
    with pytest.raises(ToolError, match="Bilinmeyen tool"):
        execute_tool("delete_everything", {}, root=sample_project)


def test_execute_tool_normalizes_argument_case(sample_project) -> None:
    """Model 'Pattern' gibi yanlış büyük/küçük harfli argüman üretse bile
    execute_tool bunu normalize edip doğru çalışmalı."""
    result = execute_tool("glob_search", {"Pattern": "*.py"}, root=sample_project)
    assert "src/main.py" in result


def test_execute_tool_invalid_arguments_raise_tool_error(sample_project) -> None:
    with pytest.raises(ToolError, match="geçersiz argümanlar"):
        execute_tool("read_file", {"nonexistent_kwarg": "x"}, root=sample_project)


def test_glob_search_matches_double_star_pattern_at_root(sample_project) -> None:
    """`**/*.txt` gibi desenler kök dizindeki dosyalarla da eşleşmeli
    (fnmatch'in doğal davranışı bunu desteklemez, tools.py'de düzeltildi)."""
    (sample_project / "kok.txt").write_text("kök dosya")
    results = glob_search("**/*.txt", root=sample_project)
    assert "kok.txt" in results


def test_run_shell_returns_stdout_and_exit_code(sample_project) -> None:
    result = run_shell("echo merhaba", root=sample_project)
    assert result["exit_code"] == 0
    assert "merhaba" in result["stdout"]


def test_run_shell_captures_nonzero_exit_code(sample_project) -> None:
    result = run_shell("exit 3", root=sample_project)
    assert result["exit_code"] == 3


def test_run_shell_captures_stderr(sample_project) -> None:
    result = run_shell("echo hata 1>&2", root=sample_project)
    assert "hata" in result["stderr"]


def test_run_shell_runs_in_project_root(sample_project) -> None:
    result = run_shell("pwd", root=sample_project)
    assert str(sample_project) in result["stdout"]


def test_run_shell_times_out_on_long_command(sample_project, monkeypatch) -> None:
    import agent.tools as tools_module

    monkeypatch.setattr(tools_module, "SHELL_TIMEOUT_SECONDS", 1)
    with pytest.raises(ToolError, match="zaman aşımı"):
        run_shell("sleep 5", root=sample_project)


def test_execute_tool_dispatches_to_run_shell(sample_project) -> None:
    result = execute_tool("run_shell", {"command": "echo test"}, root=sample_project)
    assert result["exit_code"] == 0
