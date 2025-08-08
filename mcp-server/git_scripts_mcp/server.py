#!/usr/bin/env python3
"""
Git Scripts MCP Server

Advanced Git safety operations through MCP for Claude Code and other LLM tools.
Each tool corresponds to a battle-tested Git script with enhanced safety features.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("git-scripts-mcp")

# Find the git scripts directory (parent of mcp-server)
SCRIPT_DIR = Path(__file__).parent.parent.parent.absolute()


class GitScriptsMCP:
    """MCP server for Git Scripts collection with improved dispatch pattern."""

    def __init__(self):
        self.server = Server("git-scripts-mcp")
        self.setup_tools()

        # Tool handler registry - cleaner than if/elif chain
        self.handlers = {
            "git_undo": self._handle_git_undo,
            "git_redo": self._handle_git_redo,
            "git_recommit": self._handle_git_recommit,
            "git_check_dup": self._handle_git_check_dup,
            "git_remove_redundant_commits": self._handle_git_remove_redundant_commits,
            "git_branch_diff": self._handle_git_branch_diff,
            "git_find_file": self._handle_git_find_file,
            "git_diff_patch": self._handle_git_diff_patch,
            "git_extract_conflict_files": self._handle_git_extract_conflict_files,
            "git_remerge_from_files": self._handle_git_remerge_from_files,
        }

    def setup_tools(self):
        """Register all Git script tools."""
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)

    async def list_tools(self) -> List[Tool]:
        """List all available Git script tools with safety focus."""
        return [
            Tool(
                name="git_undo",
                description=(
                    """🔄 Safely undo the last commit while preserving changes in staging area.
                    Perfect for when you need to modify, split, or enhance your last commit.
                    Uses 'git reset --soft HEAD^' with safety checks and confirmations.

                    📋 USE WHEN: Need to modify last commit, split commit into multiple parts,
                    or add more changes to last commit. Safer than 'git reset --hard'."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "boolean",
                            "description": "Skip confirmation prompt (default: false - will prompt user)",
                            "default": False,
                        },
                    },
                },
            ),

            Tool(
                name="git_redo",
                description=(
                    """↩️ Redo the most recently undone commit. Works by finding reset operations
                    in reflog and restoring the undone commit. Two modes available:
                    • Full restore: Cherry-picks original commit completely
                    • Message-only: Commits staged changes with original message

                    📋 USE WHEN: Want to restore an undone commit or reuse its commit message.
                    Perfect partner to git_undo for safe commit modifications."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message_only": {
                            "type": "boolean",
                            "description": "Only use original commit message, don't restore content",
                            "default": False,
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Skip confirmation prompt",
                            "default": False,
                        },
                    },
                },
            ),

            Tool(
                name="git_recommit",
                description=(
                    """📝 Convenience alias for 'git_redo --message-only'. Commits currently
                    staged changes using the commit message from the most recently undone commit.

                    📋 USE WHEN: You've undone a commit, made additional changes, and want to
                    commit with the original message. Common workflow after git_undo."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "boolean",
                            "description": "Skip confirmation prompt",
                            "default": False,
                        },
                    },
                },
            ),

            Tool(
                name="git_check_dup",
                description=(
                    """🔍 Find duplicate commits between branches based on content (patch-id),
                    not commit hash. Identifies commits that make identical code changes
                    but have different hashes due to cherry-picking, rebasing, etc.

                    📋 USE WHEN: Before rebasing, after cherry-picking, cleaning up branches,
                    or preparing pull requests to identify redundant commits that can be safely removed."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "remote_branch": {
                            "type": "string",
                            "description": "Branch to compare against (default: origin/main)",
                            "default": "origin/main",
                        },
                        "quiet": {
                            "type": "boolean",
                            "description": "Output only essential data for parsing",
                            "default": False,
                        },
                    },
                },
            ),

            Tool(
                name="git_remove_redundant_commits",
                description=(
                    """🧹 Automatically remove redundant/duplicate commits and cleanly rebase
                    branch. Uses two-phase approach:
                    1. Removes content duplicates via rebase onto remote
                    2. Rebases cleaned commits onto target branch

                    ⚠️ Always creates timestamped backup branch for safety.
                    🔒 Dry-run by default - use --apply to execute.

                    📋 USE WHEN: Branch has redundant commits from cherry-picking/rebasing
                    and needs clean history before merging."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "onto_branch": {
                            "type": "string",
                            "description": "Branch to rebase onto (default: origin/main)",
                            "default": "origin/main",
                        },
                        "apply": {
                            "type": "boolean",
                            "description": "Actually perform the cleanup (default: dry-run only)",
                            "default": False,
                        },
                    },
                },
            ),

            Tool(
                name="git_branch_diff",
                description=(
                    """📊 Visual comparison of commit logs between two branches.
                    Shows commits unique to each branch in side-by-side format.
                    Great for understanding branch divergence and planning merges.

                    📋 USE WHEN: Need to see what commits differ between branches,
                    understand branch history, or prepare for merges/rebases."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "branch1": {
                            "type": "string",
                            "description": "First branch to compare (default: HEAD)",
                            "default": "HEAD",
                        },
                        "branch2": {
                            "type": "string",
                            "description": "Second branch to compare (default: origin/main)",
                            "default": "origin/main",
                        },
                    },
                },
            ),

            Tool(
                name="git_find_file",
                description=(
                    """🔎 Search for files matching a pattern across Git branches.
                    Useful for finding where specific files exist in different branches,
                    tracking file renames, or locating configuration files.
                    Pattern is treated as grep regex.

                    📋 USE WHEN: Need to find files across branches, track file history,
                    or locate configuration/build files in different branch contexts."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "File pattern or regex to search for (required)",
                        },
                        "local": {
                            "type": "boolean",
                            "description": "Search local branches only (default: remote branches)",
                            "default": False,
                        },
                    },
                    "required": ["pattern"],
                },
            ),
            Tool(
                name="git_diff_patch",
                description=(
                    """↔️  Compare two commits for functional equivalence using patch-id.
                    Useful for checking if two commits are the same after a rebase or cherry-pick.

                    📋 USE WHEN: You need to verify if two different commits introduce the exact same code changes."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "commit1": {
                            "type": "string",
                            "description": "The first commit to compare.",
                        },
                        "commit2": {
                            "type": "string",
                            "description": "The second commit to compare.",
                        },
                    },
                    "required": ["commit1", "commit2"],
                },
            ),

            Tool(
                name="git_extract_conflict_files",
                description=(
                    """🔄 Extract conflict files for manual editing during merge conflicts.
                    Creates temporary files containing 'ours', 'theirs', and 'base' versions
                    of a conflicted file. Returns file paths for manual editing.

                    📋 USE WHEN: Need to manually resolve complex merge conflicts by editing
                    individual versions before re-merging."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Path to the conflicted file",
                        },
                    },
                    "required": ["file"],
                },
            ),

            Tool(
                name="git_remerge_from_files",
                description=(
                    """🔧 Re-merge using edited conflict files. Performs a fresh 3-way merge
                    using previously extracted and edited 'ours', 'theirs', and 'base' files.
                    Automatically shows diff and stages the result if merge is clean.

                    📋 USE WHEN: After editing extracted conflict files, need to apply the
                    changes back to the original conflicted file."""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Path to the original conflicted file",
                        },
                        "ours_path": {
                            "type": "string",
                            "description": "Path to the edited 'ours' file",
                        },
                        "base_path": {
                            "type": "string",
                            "description": "Path to the 'base' file",
                        },
                        "theirs_path": {
                            "type": "string",
                            "description": "Path to the edited 'theirs' file",
                        },
                    },
                    "required": ["file", "ours_path", "base_path", "theirs_path"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute a Git script tool using improved dispatch pattern."""
        try:
            handler = self.handlers.get(name)
            if not handler:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True,
                )

            return await handler(arguments)

        except subprocess.CalledProcessError as e:
            error_msg = f"Git script failed: {e.stderr.decode() if e.stderr else str(e)}"
            return CallToolResult(
                content=[TextContent(type="text", text=error_msg)],
                isError=True,
            )
        except Exception as e:
            logger.exception(f"Error executing {name}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool execution failed: {e!s}")],
                isError=True,
            )

    def _get_script_path(self, script_name: str) -> Path:
        """Get the full path to a Git script."""
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            msg = f"Script not found: {script_path}"
            raise FileNotFoundError(msg)
        return script_path

    async def _run_command(self, cmd: List[str], input_text: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run a command with proper error handling."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if input_text else None,
            )

            stdout, stderr = await process.communicate(
                input=input_text.encode() if input_text else None,
            )

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except Exception as e:
            raise subprocess.CalledProcessError(1, cmd, str(e).encode(), str(e).encode())

    # Tool handlers using improved naming convention
    async def _handle_git_undo(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-undo script."""
        script_path = self._get_script_path("git-undo")
        cmd = [str(script_path)]

        # Auto-confirm if requested
        input_text = "y\n" if args.get("confirm") else None

        result = await self._run_command(cmd, input_text)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"✅ Git undo completed successfully:\n\n{result.stdout.decode()}",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git undo failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_redo(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-redo script."""
        script_path = self._get_script_path("git-redo")
        cmd = [str(script_path)]

        if args.get("message_only"):
            cmd.append("--message-only")

        # Auto-confirm if requested
        input_text = "y\n" if args.get("confirm") else None

        result = await self._run_command(cmd, input_text)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"✅ Git redo completed successfully:\n\n{result.stdout.decode()}",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git redo failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_recommit(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-recommit script."""
        script_path = self._get_script_path("git-recommit")
        cmd = [str(script_path)]

        # Auto-confirm if requested
        input_text = "y\n" if args.get("confirm") else None

        result = await self._run_command(cmd, input_text)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"✅ Git recommit completed successfully:\n\n{result.stdout.decode()}",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git recommit failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_check_dup(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-check-dup script."""
        script_path = self._get_script_path("git-check-dup")
        cmd = [str(script_path)]

        if args.get("quiet"):
            cmd.append("--quiet")

        remote_branch = args.get("remote_branch", "origin/main")
        if remote_branch != "origin/main":
            cmd.append(remote_branch)

        result = await self._run_command(cmd)

        if result.returncode == 0:
            output = result.stdout.decode()
            if output.strip():
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"🔍 Duplicate commits found:\n\n{output}",
                    )],
                )
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="✅ No duplicate commits detected.",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git check-dup failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_remove_redundant_commits(
        self,
        args: Dict[str, Any],
    ) -> CallToolResult:
        """Execute git-remove-redundant-commits script."""
        script_path = self._get_script_path("git-remove-redundant-commits")
        cmd = [str(script_path)]

        onto_branch = args.get("onto_branch", "origin/main")
        if onto_branch != "origin/main":
            cmd.extend(["--onto", onto_branch])

        if args.get("apply"):
            cmd.append("--apply")

        result = await self._run_command(cmd)

        if result.returncode == 0:
            mode = "🔧 Applied changes" if args.get("apply") else "🔍 Dry-run analysis"
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        f"✅ Git remove redundant commits - {mode}:\n\n{result.stdout.decode()}"
                    ),
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    f"❌ Git remove redundant commits failed:\n{result.stderr.decode()}"
                ),
            )],
            isError=True,
        )

    async def _handle_git_branch_diff(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-branch-diff script with text-based comparison."""
        branch1 = args.get("branch1", "HEAD")
        branch2 = args.get("branch2", "origin/main")

        try:
            # Get the commit logs for comparison
            log1_cmd = ["git", "log", "--oneline", "--max-count=20", branch1]
            log2_cmd = ["git", "log", "--oneline", "--max-count=20", branch2]

            log1_result = await self._run_command(log1_cmd)
            log2_result = await self._run_command(log2_cmd)

            if log1_result.returncode == 0 and log2_result.returncode == 0:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=(
                            f"📊 Branch comparison ({branch1} vs {branch2}):\n\n"
                            f"=== {branch1} commits ===\n{log1_result.stdout.decode()}\n"
                            f"=== {branch2} commits ===\n{log2_result.stdout.decode()}\n"
                            f"💡 Tip: Use 'git log --oneline --graph {branch1} {branch2}' for visual graph"
                        ),
                    )],
                )
            error_msg = log1_result.stderr.decode() or log2_result.stderr.decode()
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"❌ Git branch diff failed:\n{error_msg}",
                )],
                isError=True,
            )

        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"❌ Git branch diff failed: {e!s}",
                )],
                isError=True,
            )

    async def _handle_git_find_file(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-find_file script."""
        script_path = self._get_script_path("git-find_file")
        cmd = [str(script_path)]

        pattern = args.get("pattern")
        if not pattern:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="❌ Error: pattern parameter is required",
                )],
                isError=True,
            )

        cmd.append(pattern)

        if args.get("local"):
            cmd.append("--local")

        result = await self._run_command(cmd)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"🔎 Git find file results:\n\n{result.stdout.decode()}",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git find file failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_diff_patch(self, args: Dict[str, Any]) -> CallToolResult:
        """Execute git-diff-patch script."""
        script_path = self._get_script_path("git-diff-patch")
        commit1 = args.get("commit1")
        commit2 = args.get("commit2")

        if not commit1 or not commit2:
            return CallToolResult(
                content=[
                    TextContent(type="text", text="❌ Error: commit1 and commit2 are required.")
                ],
                isError=True,
            )

        cmd = [str(script_path), commit1, commit2]
        result = await self._run_command(cmd)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"✅ Patch comparison results:\n\n{result.stdout.decode()}",
                )],
            )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git diff-patch failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_extract_conflict_files(self, args: Dict[str, Any]) -> CallToolResult:
        """Extract conflict files using git-diff-123 --extract."""
        file = args.get("file")
        if not file:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="❌ Error: file parameter is required",
                )],
                isError=True,
            )

        script_path = self._get_script_path("git-diff-123")
        cmd = [str(script_path), "--extract", file]

        result = await self._run_command(cmd)

        if result.returncode == 0:
            output = result.stdout.decode().strip()
            # Parse the output: tmpdir:ours:base:theirs
            parts = output.split(":")
            if len(parts) >= 4:
                tmpdir, ours, base, theirs = parts[0], parts[1], parts[2], parts[3]
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=(
                            f"🔄 Conflict files extracted successfully:\n\n"
                            f"📁 Temp directory: {tmpdir}\n"
                            f"📄 Ours file: {ours}\n"
                            f"📄 Base file: {base}\n"
                            f"📄 Theirs file: {theirs}\n\n"
                            f"💡 Edit the 'ours' and/or 'theirs' files as needed, then use git_remerge_from_files to apply changes."
                        ),
                    )],
                )
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"❌ Unexpected output format:\n{output}",
                )],
                isError=True,
            )

        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git extract conflict files failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )

    async def _handle_git_remerge_from_files(self, args: Dict[str, Any]) -> CallToolResult:
        """Re-merge using edited files via git-diff-123 --remerge."""
        file = args.get("file")
        ours_path = args.get("ours_path")
        base_path = args.get("base_path")
        theirs_path = args.get("theirs_path")

        if not all([file, ours_path, base_path, theirs_path]):
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="❌ Error: file, ours_path, base_path, and theirs_path are all required",
                )],
                isError=True,
            )

        script_path = self._get_script_path("git-diff-123")
        cmd = [str(script_path), "--remerge", file, ours_path, base_path, theirs_path]

        result = await self._run_command(cmd)

        if result.returncode == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"🔧 Re-merge completed successfully:\n\n{result.stdout.decode()}",
                )],
            )

        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"❌ Git remerge from files failed:\n{result.stderr.decode()}",
            )],
            isError=True,
        )


async def main():
    """Main entry point for the MCP server."""
    git_scripts = GitScriptsMCP()

    # Check if git-scripts are available
    try:
        git_scripts._get_script_path("git-undo")
        logger.info(f"Git scripts found in: {SCRIPT_DIR}")
    except FileNotFoundError:
        logger.error("Git scripts not found in: %s", SCRIPT_DIR)
        logger.error("Please ensure git scripts are installed and accessible")
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        logger.info("🚀 Git Scripts MCP Server starting...")
        await git_scripts.server.run(
            read_stream,
            write_stream,
            git_scripts.server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())


def main_sync():
    """Synchronous entry point for poetry scripts."""
    asyncio.run(main())
