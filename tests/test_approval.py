"""agent.approval için birim testleri (sunucu gerektirmez)."""

from __future__ import annotations

from agent.approval import (
    is_destructive_shell_command,
    is_outside_project,
    is_read_only_tool,
    requires_approval,
)


def test_read_only_tools_never_require_approval() -> None:
    for tool_name in ("read_file", "glob_search", "grep_search"):
        assert is_read_only_tool(tool_name)
        needs_approval, reason = requires_approval(
            tool_name, {"path": "x"}, autonomous_mode=False
        )
        assert needs_approval is False
        assert reason is None


def test_run_shell_requires_approval_by_default() -> None:
    needs_approval, reason = requires_approval(
        "run_shell", {"command": "ls -la"}, autonomous_mode=False
    )
    assert needs_approval is True
    assert reason is not None


def test_run_shell_skips_approval_in_autonomous_mode() -> None:
    needs_approval, _ = requires_approval(
        "run_shell", {"command": "ls -la"}, autonomous_mode=True
    )
    assert needs_approval is False


def test_destructive_commands_detected() -> None:
    destructive = [
        "rm -rf /tmp/foo",
        "rm -fr /tmp/foo",
        "git push origin main --force",
        "git push -f origin main",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git branch -D feature/x",
    ]
    for command in destructive:
        assert is_destructive_shell_command(command), f"Tespit edilmedi: {command}"


def test_non_destructive_commands_not_flagged() -> None:
    safe = ["ls -la", "pytest -v", "git status", "git push origin main", "cat file.txt"]
    for command in safe:
        assert not is_destructive_shell_command(command), f"Yanlış pozitif: {command}"


def test_destructive_command_requires_approval_even_in_autonomous_mode() -> None:
    """K8 mutlak sınırı: otonom mod açıkken de yıkıcı komut onay istemeli."""
    needs_approval, reason = requires_approval(
        "run_shell", {"command": "rm -rf /tmp/foo"}, autonomous_mode=True
    )
    assert needs_approval is True
    assert "yıkıcı" in reason.lower() or "geri alınamaz" in reason.lower()


def test_is_outside_project_detects_traversal(tmp_path) -> None:
    assert is_outside_project("../../etc/passwd", tmp_path)
    assert is_outside_project("/etc/passwd", tmp_path)
    assert not is_outside_project("src/main.py", tmp_path)
    assert not is_outside_project(".", tmp_path)


def test_outside_project_path_requires_approval_even_in_autonomous_mode(tmp_path) -> None:
    """K8 mutlak sınırı: otonom mod açıkken de proje-dışı erişim onay istemeli."""
    needs_approval, reason = requires_approval(
        "write_file",
        {"path": "/etc/passwd"},
        autonomous_mode=True,
        project_root=tmp_path,
    )
    assert needs_approval is True
    assert "proje" in reason.lower()


def test_unknown_tool_defaults_to_requiring_approval() -> None:
    needs_approval, _ = requires_approval("mystery_tool", {}, autonomous_mode=True)
    assert needs_approval is True
