"""Regression tests for MCP remerge error reporting."""

import asyncio
import subprocess
import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "mcp-server"))

# Minimal stubs so server module can import without the external mcp package.
mcp_module = types.ModuleType("mcp")
mcp_server_module = types.ModuleType("mcp.server")
mcp_stdio_module = types.ModuleType("mcp.server.stdio")
mcp_types_module = types.ModuleType("mcp.types")


class StubServer:
    def __init__(self, _name):
        pass

    def list_tools(self):
        def decorator(fn):
            return fn
        return decorator

    def call_tool(self):
        def decorator(fn):
            return fn
        return decorator


async def stub_stdio_server():
    raise RuntimeError("not used in tests")


class StubCallToolResult:
    def __init__(self, content, isError=False):
        self.content = content
        self.isError = isError


class StubTextContent:
    def __init__(self, type, text):
        self.type = type
        self.text = text


class StubTool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


mcp_server_module.Server = StubServer
mcp_stdio_module.stdio_server = stub_stdio_server
mcp_types_module.CallToolResult = StubCallToolResult
mcp_types_module.TextContent = StubTextContent
mcp_types_module.Tool = StubTool

sys.modules.setdefault("mcp", mcp_module)
sys.modules.setdefault("mcp.server", mcp_server_module)
sys.modules.setdefault("mcp.server.stdio", mcp_stdio_module)
sys.modules.setdefault("mcp.types", mcp_types_module)

from git_scripts_mcp.server import GitScriptsMCP


def test_remerge_handler_reports_stdout_when_stderr_empty(monkeypatch):
    server = GitScriptsMCP()

    async def fake_run_command(cmd, input_text=None):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout=b"Re-merge still has conflicts after manual edits for f.txt.\n",
            stderr=b"",
        )

    monkeypatch.setattr(server, "_run_command", fake_run_command)
    monkeypatch.setattr(server, "_get_script_path", lambda _: Path("/tmp/git-diff-123"))

    result = asyncio.run(
        server._handle_git_remerge_from_files(
            {
                "file": "f.txt",
                "ours_path": "/tmp/ours",
                "base_path": "/tmp/base",
                "theirs_path": "/tmp/theirs",
            }
        )
    )

    assert result.isError is True
    assert "Re-merge still has conflicts" in result.content[0].text


def test_remerge_handler_parses_json_still_conflicted_payload(monkeypatch):
    server = GitScriptsMCP()
    captured_cmd = {}

    async def fake_run_command(cmd, input_text=None):
        captured_cmd["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout=b'{"status":"still_conflicted","message":"still conflicted"}\n',
            stderr=b"",
        )

    monkeypatch.setattr(server, "_run_command", fake_run_command)
    monkeypatch.setattr(server, "_get_script_path", lambda _: Path("/tmp/git-diff-123"))

    result = asyncio.run(
        server._handle_git_remerge_from_files(
            {
                "file": "f.txt",
                "ours_path": "/tmp/ours",
                "base_path": "/tmp/base",
                "theirs_path": "/tmp/theirs",
            }
        )
    )

    assert "--tool-remerge" in captured_cmd["cmd"]
    assert result.isError is True
    assert "still conflicted" in result.content[0].text


def test_find_file_handler_passes_history_and_deleted_flags(monkeypatch):
    server = GitScriptsMCP()
    captured_cmd = {}

    async def fake_run_command(cmd, input_text=None):
        captured_cmd["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr(server, "_run_command", fake_run_command)
    monkeypatch.setattr(server, "_get_script_path", lambda _: Path("/tmp/git-find_file"))

    result = asyncio.run(
        server._handle_git_find_file(
            {"pattern": "foo", "local": True, "history": True, "deleted": True}
        )
    )

    assert result.isError is False
    assert "--local" in captured_cmd["cmd"]
    assert "--history" in captured_cmd["cmd"]
    assert "--deleted" in captured_cmd["cmd"]
