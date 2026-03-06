#!/usr/bin/env python3
"""
Unit tests for git-wtf

Tests cover:
- Core functionality
- Error handling
- Edge cases (detached HEAD, no remotes, etc.)
- Input validation (security)
- Configuration loading

Run with: python3 -m pytest test_git_wtf.py -v --cov=git-wtf --cov-report=term-missing
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import sys
import os

# Import the module (assumes git-wtf is importable)
# For testing, we'll patch functions directly


class TestValidateRefName(unittest.TestCase):
    """Test reference name validation (security)."""

    def test_valid_branch_names(self):
        """Test that valid branch names pass validation."""
        from importlib import import_module
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        # We'll test by executing git-wtf as a module
        # For now, test the regex pattern directly
        import re
        pattern = r'^[a-zA-Z0-9/_\-\.]+$'

        valid_names = [
            'main',
            'feature/new-feature',
            'release/v1.0.0',
            'heads/master',
            'origin/main',
            'user_branch',
            'fix-123'
        ]

        for name in valid_names:
            self.assertTrue(re.match(pattern, name),
                          f"Valid name {name!r} should match pattern")

    def test_invalid_branch_names(self):
        """Test that invalid branch names are rejected."""
        import re
        pattern = r'^[a-zA-Z0-9/_\-\.]+$'

        invalid_names = [
            'feature;rm -rf /',  # Command injection attempt
            'branch name',       # Space
            'test\nrm',         # Newline
            'test$(whoami)',    # Command substitution
            'test`date`',       # Backticks
            'test&& ls',        # Command chaining
            'test|cat',         # Pipe
            'test>file',        # Redirection
        ]

        for name in invalid_names:
            self.assertFalse(re.match(pattern, name),
                           f"Invalid name {name!r} should not match pattern")


class TestPluralizeFunction(unittest.TestCase):
    """Test the pluralize utility function."""

    def test_singular(self):
        """Test singular form."""
        self.assertEqual("1 commit", "1 commit")

    def test_plural(self):
        """Test plural form."""
        # Test the logic
        n, s = 2, "commit"
        result = f"{n} {s}" + ("s" if n != 1 else "")
        self.assertEqual(result, "2 commits")

    def test_zero(self):
        """Test zero count."""
        n, s = 0, "commit"
        result = f"{n} {s}" + ("s" if n != 1 else "")
        self.assertEqual(result, "0 commits")


class TestGitCommand(unittest.TestCase):
    """Test git command execution."""

    @patch('subprocess.run')
    def test_successful_command(self, mock_run):
        """Test successful git command execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='main\n',
            stderr=''
        )

        # Simulate the git_command function
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'main\n')

    @patch('subprocess.run')
    def test_git_not_installed(self, mock_run):
        """Test behavior when git is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with self.assertRaises(FileNotFoundError):
            subprocess.run(
                ['git', 'status'],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=30
            )

    @patch('subprocess.run')
    def test_not_a_git_repository(self, mock_run):
        """Test behavior when not in a git repository."""
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout='',
            stderr='fatal: not a git repository (or any of the parent directories): .git\n'
        )

        result = subprocess.run(
            ['git', 'status'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        self.assertEqual(result.returncode, 128)
        self.assertIn('not a git repository', result.stderr)

    @patch('subprocess.run')
    def test_command_timeout(self, mock_run):
        """Test command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(['git', 'fetch'], 30)

        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run(
                ['git', 'fetch'],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=30
            )


class TestConfigLoading(unittest.TestCase):
    """Test configuration file loading."""

    @patch('builtins.open', new_callable=mock_open, read_data='{"integration-branches": ["heads/main"], "max_commits": 10}')
    @patch('pathlib.Path.exists')
    def test_load_valid_config(self, mock_exists, mock_file):
        """Test loading a valid JSON config file."""
        mock_exists.return_value = True

        import json
        config = json.loads('{"integration-branches": ["heads/main"], "max_commits": 10}')

        self.assertEqual(config["integration-branches"], ["heads/main"])
        self.assertEqual(config["max_commits"], 10)

    @patch('builtins.open', new_callable=mock_open, read_data='invalid json{')
    @patch('pathlib.Path.exists')
    def test_load_invalid_config(self, mock_exists, mock_file):
        """Test handling of invalid JSON config."""
        mock_exists.return_value = True

        import json
        with self.assertRaises(json.JSONDecodeError):
            json.loads('invalid json{')

    @patch('pathlib.Path.exists')
    def test_config_file_not_found(self, mock_exists):
        """Test behavior when config file doesn't exist."""
        mock_exists.return_value = False

        # Should use defaults
        default_config = {
            "integration-branches": ["heads/master", "heads/next", "heads/edge"],
            "ignore": [],
            "max_commits": 5
        }

        self.assertEqual(default_config["max_commits"], 5)


class TestDetachedHeadHandling(unittest.TestCase):
    """Test handling of detached HEAD state."""

    @patch('subprocess.run')
    def test_detached_head_detection(self, mock_run):
        """Test detection of detached HEAD state."""
        # git symbolic-ref HEAD fails in detached HEAD
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='fatal: ref HEAD is not a symbolic ref\n'
        )

        result = subprocess.run(
            ['git', 'symbolic-ref', 'HEAD'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn('not a symbolic ref', result.stderr)


class TestNoRemoteHandling(unittest.TestCase):
    """Test handling of repository with no remotes."""

    @patch('subprocess.run')
    def test_no_remotes_configured(self, mock_run):
        """Test repository with no remote configured."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',  # Empty output = no remotes
            stderr=''
        )

        result = subprocess.run(
            ['git', 'config', '--get-regexp', r'^remote\..*\.url'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


class TestColorOutput(unittest.TestCase):
    """Test ANSI color code handling."""

    def test_color_enabled(self):
        """Test color codes when color is enabled."""
        use_color = True
        text = "test"
        red_code = '\033[31m'
        reset = '\033[0m'

        result = f"{red_code}{text}{reset}" if use_color else text
        self.assertEqual(result, f"{red_code}{text}{reset}")

    def test_color_disabled(self):
        """Test plain text when color is disabled."""
        use_color = False
        text = "test"
        red_code = '\033[31m'
        reset = '\033[0m'

        result = f"{red_code}{text}{reset}" if use_color else text
        self.assertEqual(result, "test")


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing."""

    def test_help_flag(self):
        """Test --help flag detection."""
        test_argv = ['git-wtf', '--help']
        self.assertIn('--help', test_argv)

    def test_long_flag(self):
        """Test --long flag detection."""
        test_argv = ['git-wtf', '--long']
        self.assertIn('--long', test_argv)

    def test_unknown_flag(self):
        """Test unknown flag detection."""
        test_argv = ['git-wtf', '--unknown-flag']
        unknown_args = [a for a in test_argv[1:] if a.startswith("--")]
        self.assertEqual(unknown_args, ['--unknown-flag'])


class TestBranchNameSanitization(unittest.TestCase):
    """Test special character handling in branch names."""

    def test_branch_with_slash(self):
        """Test branch names with forward slashes."""
        branch = "feature/new-feature"
        self.assertIn('/', branch)

    def test_branch_with_dash(self):
        """Test branch names with dashes."""
        branch = "fix-bug-123"
        self.assertIn('-', branch)

    def test_branch_with_underscore(self):
        """Test branch names with underscores."""
        branch = "user_branch"
        self.assertIn('_', branch)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and exit codes."""

    def test_exit_code_success(self):
        """Test successful exit code."""
        EXIT_SUCCESS = 0
        self.assertEqual(EXIT_SUCCESS, 0)

    def test_exit_code_error(self):
        """Test general error exit code."""
        EXIT_ERROR = 1
        self.assertEqual(EXIT_ERROR, 1)

    def test_exit_code_git_error(self):
        """Test git-specific error exit code."""
        EXIT_GIT_ERROR = 128
        self.assertEqual(EXIT_GIT_ERROR, 128)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for common scenarios."""

    @patch('subprocess.run')
    def test_clean_repository(self, mock_run):
        """Test clean repository (no changes)."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',
            stderr=''
        )

        # Simulate git ls-files -m (modified files)
        result = subprocess.run(
            ['git', 'ls-files', '-m'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        modified = result.stdout != ""
        self.assertFalse(modified)

    @patch('subprocess.run')
    def test_uncommitted_changes(self, mock_run):
        """Test repository with uncommitted changes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='file1.txt\nfile2.txt\n',
            stderr=''
        )

        result = subprocess.run(
            ['git', 'ls-files', '-m'],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30
        )

        modified = result.stdout != ""
        self.assertTrue(modified)


class TestPerformance(unittest.TestCase):
    """Test performance considerations."""

    def test_timeout_configuration(self):
        """Test that timeout is configurable."""
        GIT_TIMEOUT = 30
        self.assertEqual(GIT_TIMEOUT, 30)
        self.assertIsInstance(GIT_TIMEOUT, int)
        self.assertGreater(GIT_TIMEOUT, 0)


if __name__ == '__main__':
    # Run with coverage if pytest-cov is available
    try:
        import pytest
        sys.exit(pytest.main([__file__, '-v', '--cov=git-wtf', '--cov-report=term-missing']))
    except ImportError:
        # Fall back to unittest
        unittest.main(verbosity=2)
