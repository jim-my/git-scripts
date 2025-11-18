# Git Scripts MCP Server

A Model Context Protocol (MCP) server that provides advanced Git safety operations for Claude Code and other LLM development tools. This server wraps a collection of battle-tested Git scripts with enhanced safety features, confirmations, and intelligent automation.

## 🚀 What This Provides

This MCP server goes beyond basic Git operations to provide **advanced safety workflows** that existing Git MCP servers don't offer:

### 🔄 Safe Commit Operations
- **`git_undo`** - Safely undo commits while preserving changes
- **`git_redo`** - Intelligently restore undone commits
- **`git_recommit`** - Reuse commit messages after modifications

### 🔍 Duplicate Detection & Cleanup
- **`git_check_dup`** - Find duplicate commits by content (not hash)
- **`git_dedupe`** - Automatically clean redundant commits with backups

### 📊 Branch Analysis Tools
- **`git_branch_diff`** - Visual branch comparison
- **`git_find_file`** - Search files across branches

## 🛡️ Safety First Design

Every operation includes:
- **Confirmation prompts** (can be bypassed)
- **Automatic backups** for destructive operations
- **Dry-run mode** by default for complex operations
- **Detailed error messages** and recovery instructions

## 📦 Installation

1. **Install the MCP server:**
   ```bash
   cd mcp-server
   pip install -e .
   ```

2. **Ensure Git scripts are accessible:**
   ```bash
   # From the git-scripts root directory
   ./install.sh
   ```

3. **Add to your Claude Code configuration:**
   Add to your `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "git-scripts-mcp": {
         "command": "git-scripts-mcp",
         "args": []
       }
     }
   }
   ```

## 🔧 Usage Examples

### Safe Commit Modifications
```
# Undo last commit but keep changes staged
Use git_undo

# Make additional changes
# ... edit files ...

# Recommit with original message
Use git_recommit with confirm=true
```

### Branch Cleanup Before Merging
```
# Check for duplicate commits
Use git_check_dup with remote_branch="origin/main"

# Clean up redundant commits (dry-run first)
Use git_dedupe with onto_branch="origin/main"

# Apply the cleanup if dry-run looks good
Use git_dedupe with onto_branch="origin/main", apply=true
```

### Cross-Branch Analysis
```
# Compare current branch with main
Use git_branch_diff with branch2="origin/main"

# Find configuration files across branches
Use git_find_file with pattern="*.config", local=false
```

## 🆚 Comparison with Existing Git MCP Servers

| Feature | Basic Git MCP | GitHub MCP | **Git Scripts MCP** |
|---------|---------------|------------|---------------------|
| Basic Git ops | ✅ | ✅ | ✅ |
| Safety confirmations | ❌ | ❌ | ✅ |
| Duplicate detection | ❌ | ❌ | ✅ |
| Intelligent undo/redo | ❌ | ❌ | ✅ |
| Automatic backups | ❌ | ❌ | ✅ |
| Branch analysis | ❌ | ❌ | ✅ |
| Cross-branch file search | ❌ | ❌ | ✅ |

## 🛠️ Tool Reference

### git_undo
Safely undo the last commit while preserving changes in staging area.

**Parameters:**
- `confirm` (boolean, optional): Skip confirmation prompt

**Use cases:**
- Modify last commit message
- Split last commit into multiple commits
- Add more changes to last commit

### git_redo
Redo the most recently undone commit with two modes.

**Parameters:**
- `message_only` (boolean, optional): Only use original message, don't restore content
- `confirm` (boolean, optional): Skip confirmation prompt

**Use cases:**
- Restore accidentally undone commits
- Reuse commit messages after making changes

### git_recommit
Convenience tool for committing staged changes with original commit message.

**Parameters:**
- `confirm` (boolean, optional): Skip confirmation prompt

**Use cases:**
- Common workflow after git_undo + additional changes

### git_check_dup
Find duplicate commits between branches based on content (patch-id).

**Parameters:**
- `remote_branch` (string, optional): Branch to compare against (default: "origin/main")
- `quiet` (boolean, optional): Output only essential data

**Use cases:**
- Before rebasing to identify redundant commits
- After cherry-picking to verify which commits were applied
- Branch cleanup preparation

### git_dedupe
Automatically remove redundant commits and cleanly rebase branch.

**Parameters:**
- `onto_branch` (string, optional): Branch to rebase onto (default: "origin/main")
- `apply` (boolean, optional): Actually perform cleanup (default: dry-run only)

**Use cases:**
- Clean branch history before merging
- Remove duplicate commits from cherry-picking/rebasing
- Prepare linear history for pull requests

### git_branch_diff
Visual comparison of commit logs between branches.

**Parameters:**
- `branch1` (string, optional): First branch (default: "HEAD")
- `branch2` (string, optional): Second branch (default: "origin/main")

**Use cases:**
- Understand branch divergence
- Prepare for merges or rebases
- Review what changes will be included in PR

### git_find_file
Search for files matching a pattern across Git branches.

**Parameters:**
- `pattern` (string, required): File pattern or regex to search for
- `local` (boolean, optional): Search local branches only (default: remote branches)

**Use cases:**
- Find configuration files across branches
- Track file renames or moves
- Locate build files in different contexts

## 🧪 Development

### Running Tests
```bash
cd mcp-server
pip install -e ".[dev]"
pytest
```

### Code Quality
```bash
# Format code
black git_scripts_mcp/

# Lint
ruff git_scripts_mcp/

# Type check
mypy git_scripts_mcp/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-tool`
3. Add your Git script to the root directory
4. Add corresponding MCP tool handler to `server.py`
5. Update documentation and tests
6. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## ⚠️ Safety Notes

- Always review dry-run output before applying destructive operations
- Backup branches are created automatically for safety
- Scripts include comprehensive error handling and recovery instructions
- Test in a non-critical repository first

## 🔗 Related Projects

- [Official MCP Git Server](https://github.com/modelcontextprotocol/servers/tree/main/src/git) - Basic Git operations
- [GitHub MCP Server](https://github.com/github/github-mcp-server) - GitHub integration
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
