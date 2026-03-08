# git-wtf `--upstream` Flag Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--upstream <ref>` / `-u <ref>` flag to `git-wtf` so users can compare any branch against any upstream, overriding the configured tracking branch.

**Architecture:** Parse the new flag in `parse_args()`, resolve the upstream ref against `all_branches` in `main()`, then shallow-copy the target branch info with the overridden `remote_branch` before calling `show_branch_status()`.

**Tech Stack:** Python 3 (stdlib only), pytest for tests.

---

## Background: how git-wtf works

- `git-wtf` is at `/Users/jimmyyan/work/02-git-scripts/git-wtf` (no `.py` extension)
- Tests are at `tests/test_git_wtf.py`
- `parse_args()` reads directly from `sys.argv`; strips known flags, collects remaining args as `targets`
- `main()` builds `all_branches` (a dict of branch name → branch info dict), resolves targets, calls `show_branch_status(branch_info)` per target
- `branch_info` dict keys: `local_branch` (e.g. `heads/main`), `remote_branch` (e.g. `origin/main`), `remote_url`, `name`
- `get_commits_between(from_ref, to_ref)` runs `git log from_ref..to_ref` — both are valid git refs

---

## Task 1: Add `--upstream` / `-u` parsing to `parse_args()`

**Files:**
- Modify: `git-wtf:807-842` (the `parse_args` function)

### Step 1: Write the failing test

Add this class to `tests/test_git_wtf.py` (before the `if __name__ == '__main__':` block):

```python
class TestUpstreamArgParsing(unittest.TestCase):
    """Test --upstream / -u argument parsing."""

    def _import_git_wtf(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "git_wtf",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "git-wtf")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_upstream_long_flag(self):
        """--upstream <ref> is parsed into args['upstream']."""
        mod = self._import_git_wtf()
        with patch.object(sys, 'argv', ['git-wtf', '--upstream', 'origin/develop']):
            args = mod.parse_args()
        self.assertEqual(args['upstream'], 'origin/develop')
        # flag and value are consumed; no leftover targets
        self.assertEqual(args['targets'], [])

    def test_upstream_short_flag(self):
        """-u <ref> is parsed into args['upstream']."""
        mod = self._import_git_wtf()
        with patch.object(sys, 'argv', ['git-wtf', '-u', 'main']):
            args = mod.parse_args()
        self.assertEqual(args['upstream'], 'main')
        self.assertEqual(args['targets'], [])

    def test_no_upstream_flag(self):
        """When --upstream is absent, args['upstream'] is None."""
        mod = self._import_git_wtf()
        with patch.object(sys, 'argv', ['git-wtf']):
            args = mod.parse_args()
        self.assertIsNone(args['upstream'])

    def test_upstream_with_target_branch(self):
        """--upstream can coexist with a positional target branch."""
        mod = self._import_git_wtf()
        with patch.object(sys, 'argv', ['git-wtf', 'my-feature', '--upstream', 'main']):
            args = mod.parse_args()
        self.assertEqual(args['upstream'], 'main')
        self.assertEqual(args['targets'], ['my-feature'])

    def test_upstream_missing_value_exits(self):
        """--upstream without a value exits with code 1."""
        mod = self._import_git_wtf()
        with patch.object(sys, 'argv', ['git-wtf', '--upstream']):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
        self.assertEqual(ctx.exception.code, 1)
```

### Step 2: Run tests to verify they fail

```bash
cd /Users/jimmyyan/work/02-git-scripts
python -m pytest tests/test_git_wtf.py::TestUpstreamArgParsing -v
```

Expected: 5 FAILs — `args` dict has no `'upstream'` key yet.

### Step 3: Implement `--upstream` parsing in `parse_args()`

In `git-wtf`, inside `parse_args()`, add the upstream parsing block **before** the "Remove processed arguments" loop (around line 826):

```python
    # Parse --upstream/-u flag (takes a value)
    upstream = None
    for flag in ['--upstream', '-u']:
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].startswith('-'):
                print(f"Error: {flag} requires a branch argument.", file=sys.stderr)
                sys.exit(ExitCode.ERROR)
            upstream = sys.argv[idx + 1]
            sys.argv.pop(idx + 1)
            sys.argv.pop(idx)
            break
    args['upstream'] = upstream
```

Also add `'upstream': None` to the initial `args` dict so it's always present:

```python
    args = {
        'verbose': '-v' in sys.argv or '--verbose' in sys.argv,
        'long': '--long' in sys.argv or '-l' in sys.argv,
        'short': '--short' in sys.argv or '-s' in sys.argv,
        'all_remotes': '--all' in sys.argv or '-a' in sys.argv,
        'all_commits': '--all-commits' in sys.argv or '-A' in sys.argv,
        'dump_config': '--dump-config' in sys.argv,
        'show_key': '--key' in sys.argv or '-k' in sys.argv,
        'show_relations': '--relations' in sys.argv or '-r' in sys.argv,
        'show_filename': '--filename' in sys.argv or '-f' in sys.argv,
        'upstream': None,  # set below
    }
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_git_wtf.py::TestUpstreamArgParsing -v
```

Expected: 5 PASSes.

### Step 5: Run full test suite to check for regressions

```bash
python -m pytest tests/test_git_wtf.py -v
```

Expected: all existing tests still pass.

### Step 6: Commit

```bash
git add tests/test_git_wtf.py git-wtf
git commit -m "feat(git-wtf): parse --upstream/-u flag in parse_args"
```

---

## Task 2: Resolve and apply upstream override in `main()`

**Files:**
- Modify: `git-wtf:894-918` (the target-resolution + show-status section of `main()`)

### Step 1: Write the failing test

Add this class to `tests/test_git_wtf.py`:

```python
class TestUpstreamOverrideInMain(unittest.TestCase):
    """Test that --upstream overrides remote_branch in show_branch_status."""

    def _import_git_wtf(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "git_wtf",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "git-wtf")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_upstream_override_changes_remote_branch(self):
        """When --upstream is set, show_branch_status receives overridden remote_branch."""
        mod = self._import_git_wtf()

        all_branches = {
            'feature': {
                'name': 'feature',
                'local_branch': 'heads/feature',
                'remote_branch': 'origin/feature',
                'remote_url': 'git@github.com:org/repo.git',
            },
            'main': {
                'name': 'main',
                'local_branch': 'heads/main',
                'remote_url': '',
            },
        }

        captured = []
        def fake_show_branch_status(branch_info):
            captured.append(branch_info.copy())

        with patch.object(sys, 'argv', ['git-wtf', 'feature', '--upstream', 'main']), \
             patch.object(mod, 'get_remotes', return_value={}), \
             patch.object(mod, 'get_tracked_branches', return_value={}), \
             patch.object(mod, 'get_all_branches', return_value=(all_branches, {})), \
             patch.object(mod, 'assemble_remote_refs', return_value=None), \
             patch.object(mod, 'show_branch_status', side_effect=fake_show_branch_status), \
             patch.object(mod, 'show_branch_relations', return_value=None):
            mod.main()

        self.assertEqual(len(captured), 1)
        # remote_branch should be heads/main (local_branch of 'main')
        self.assertEqual(captured[0]['remote_branch'], 'heads/main')

    def test_upstream_not_found_exits_with_error(self):
        """When --upstream branch doesn't exist, main() returns error code."""
        mod = self._import_git_wtf()

        all_branches = {
            'feature': {
                'name': 'feature',
                'local_branch': 'heads/feature',
            },
        }

        with patch.object(sys, 'argv', ['git-wtf', 'feature', '--upstream', 'nonexistent']), \
             patch.object(mod, 'get_remotes', return_value={}), \
             patch.object(mod, 'get_tracked_branches', return_value={}), \
             patch.object(mod, 'get_all_branches', return_value=(all_branches, {})), \
             patch.object(mod, 'assemble_remote_refs', return_value=None):
            result = mod.main()

        self.assertEqual(result, mod.ExitCode.ERROR)
```

### Step 2: Run tests to verify they fail

```bash
python -m pytest tests/test_git_wtf.py::TestUpstreamOverrideInMain -v
```

Expected: 2 FAILs — `main()` ignores `upstream` key for now.

### Step 3: Implement upstream override in `main()`

In `git-wtf`, in `main()`, after the `assemble_remote_refs` call and the `except GitError` block (around line 890), add upstream resolution:

```python
    # Resolve upstream override (--upstream / -u)
    upstream_branch_info = None
    if args.get('upstream'):
        upstream_ref = args['upstream']
        if upstream_ref not in all_branches:
            print(f"Error: can't find upstream branch {upstream_ref!r}.", file=sys.stderr)
            return ExitCode.ERROR
        upstream_branch_info = all_branches[upstream_ref]
```

Then replace the "Show status for each target" loop (around line 914):

```python
    # Show status for each target
    for branch_info in target_branches:
        display_info = branch_info
        if upstream_branch_info is not None:
            upstream_ref = (upstream_branch_info.get('remote_branch') or
                            upstream_branch_info.get('local_branch'))
            display_info = dict(branch_info)
            display_info['remote_branch'] = upstream_ref
            display_info['remote_url'] = upstream_branch_info.get('remote_url', '')
        show_branch_status(display_info)
        if args['show_relations'] or not display_info.get('remote_branch'):
            show_branch_relations(display_info, all_branches)
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_git_wtf.py::TestUpstreamOverrideInMain -v
```

Expected: 2 PASSes.

### Step 5: Run full test suite

```bash
python -m pytest tests/test_git_wtf.py -v
```

Expected: all tests pass.

### Step 6: Commit

```bash
git add git-wtf tests/test_git_wtf.py
git commit -m "feat(git-wtf): resolve and apply --upstream override in main()"
```

---

## Task 3: Update USAGE string

**Files:**
- Modify: `git-wtf:115-144` (the `USAGE` constant)

### Step 1: Update the USAGE string

In `git-wtf`, update the `USAGE` string. Find the options block and add the new line after `-f, --filename`:

Current (around line 127):
```
  -f, --filename      show changes of filename
```

Replace with:
```
  -f, --filename      show changes of filename
  -u, --upstream <b>  compare against branch <b> instead of the configured
                      tracking branch (e.g. --upstream origin/develop)
```

### Step 2: Verify USAGE renders correctly

```bash
cd /Users/jimmyyan/work/02-git-scripts
./git-wtf --help | grep -A2 upstream
```

Expected output:
```
  -u, --upstream <b>  compare against branch <b> instead of the configured
                      tracking branch (e.g. --upstream origin/develop)
```

### Step 3: Commit

```bash
git add git-wtf
git commit -m "docs(git-wtf): document --upstream/-u flag in USAGE"
```

---

## Task 4: Final check

### Step 1: Run full test suite one more time

```bash
cd /Users/jimmyyan/work/02-git-scripts
python -m pytest tests/test_git_wtf.py -v
```

Expected: all tests pass, no failures.

### Step 2: Smoke test with real git repo

```bash
cd /Users/jimmyyan/work/02-git-scripts
./git-wtf --upstream main
```

Expected: shows status comparing current branch against `main`.

### Step 3: Test error case

```bash
./git-wtf --upstream nonexistent-branch-xyz
```

Expected: `Error: can't find upstream branch 'nonexistent-branch-xyz'.` and exit code 1.
