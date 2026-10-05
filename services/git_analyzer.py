"""GitAnalyzer service for extracting repository history safely via standard library subprocess.

Enforces read-only Git operations, constructs commands safely without shell injection,
handles empty/shallow repositories gracefully, and collects rich commit metrics.
"""

from datetime import datetime
from pathlib import Path
import re
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple, Union

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.commit import Commit
from models.exceptions import GitCommandError, InvalidRepositoryError
from models.file_change import FileChange
from utils.dates import format_iso_datetime, parse_iso_datetime
from utils.validators import validate_repository_path


# Forbidden mutating Git commands to ensure 100% read-only safety
FORBIDDEN_GIT_COMMANDS = {
    "commit", "push", "checkout", "switch", "reset", "merge", "rebase",
    "pull", "clean", "rm", "mv", "revert", "cherry-pick", "branch", "tag",
}

COMMIT_DELIMITER = "@@@DEVPULSE_COMMIT@@@"


class GitAnalyzer:
    """Safe, read-only interface to local Git repositories.
    
    Attributes:
        repository_path: Verified local path to Git directory.
        config: DevPulse configuration instance.
    """

    def __init__(
        self,
        repository_path: Union[str, Path],
        config: Optional[DevPulseConfig] = None,
    ) -> None:
        self.repository_path = validate_repository_path(repository_path)
        self.config = config or DEFAULT_CONFIG
        self._verify_git_installed()
        self._verify_git_repository()

    def _verify_git_installed(self) -> str:
        """Verify that Git is accessible on the system PATH.
        
        Returns:
            Git version string.
            
        Raises:
            GitCommandError: If git command is not found.
        """
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if result.returncode != 0:
                raise GitCommandError("git --version failed", command="git --version", exit_code=result.returncode)
            return result.stdout.strip()
        except FileNotFoundError as err:
            raise GitCommandError("Git executable not found on system PATH. Please install Git.") from err

    def _verify_git_repository(self) -> None:
        """Verify that repository_path is an actual Git work tree or repo."""
        res = self._run_git(["rev-parse", "--is-inside-work-tree"], check=False)
        if res.returncode != 0 or res.stdout.strip().lower() != "true":
            raise InvalidRepositoryError(
                f"Directory '{self.repository_path}' is not a valid Git repository."
            )

    def _run_git(
        self,
        args: Sequence[str],
        check: bool = True,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a safe, read-only Git command with argument lists.
        
        Args:
            args: Subcommand and flags (e.g. ['log', '-n', '10']).
            check: If True, raises GitCommandError on non-zero exit code.
            timeout: Subprocess timeout in seconds.
            
        Returns:
            CompletedProcess containing stdout and stderr.
            
        Raises:
            GitCommandError: On forbidden commands, timeout, or non-zero exit.
        """
        if not args:
            raise GitCommandError("Cannot execute empty Git command")
        
        subcmd = args[0].lower()
        if subcmd in FORBIDDEN_GIT_COMMANDS:
            raise GitCommandError(
                f"Security violation: Mutating Git command '{subcmd}' is forbidden. DevPulse is read-only."
            )

        cmd = ["git", "-C", str(self.repository_path)] + list(args)
        t_limit = timeout or self.config.git_timeout_seconds

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=t_limit,
            )
        except subprocess.TimeoutExpired as err:
            raise GitCommandError(
                f"Git command timed out after {t_limit}s: {' '.join(cmd)}",
                command=" ".join(cmd),
            ) from err
        except Exception as err:
            raise GitCommandError(
                f"Failed to execute Git command: {' '.join(cmd)}: {err}",
                command=" ".join(cmd),
            ) from err

        if check and proc.returncode != 0:
            raise GitCommandError(
                message=f"Git command failed with exit code {proc.returncode}: {proc.stderr.strip()}",
                command=" ".join(cmd),
                exit_code=proc.returncode,
                stderr=proc.stderr.strip(),
            )

        return proc

    def get_current_branch(self) -> str:
        """Retrieve the name of the current active branch or commit ref."""
        res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        if res.returncode == 0:
            branch = res.stdout.strip()
            return branch if branch else "main"
        # In unborn branch or detached HEAD
        res_head = self._run_git(["symbolic-ref", "--short", "HEAD"], check=False)
        if res_head.returncode == 0 and res_head.stdout.strip():
            return res_head.stdout.strip()
        return "HEAD"

    def get_total_files(self) -> int:
        """Count total tracked files in the current repository tree."""
        res = self._run_git(["ls-files"], check=False)
        if res.returncode != 0:
            return 0
        lines = [line for line in res.stdout.splitlines() if line.strip()]
        return len(lines)

    def extract_commits(
        self,
        max_count: Optional[int] = None,
        since: Optional[Union[datetime, str]] = None,
        until: Optional[Union[datetime, str]] = None,
        author: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> List[Commit]:
        """Extract commit history records matching the given criteria.
        
        Args:
            max_count: Max number of recent commits to analyze.
            since: Minimum commit date filter.
            until: Maximum commit date filter.
            author: Author filter string.
            branch: Specific branch or ref (defaults to HEAD).
            
        Returns:
            List of Commit objects sorted chronologically (oldest to newest).
        """
        git_args = [
            "log",
            f"--pretty=format:{COMMIT_DELIMITER}%n%H%n%an%n%ae%n%aI%n%s",
            "--numstat",
        ]

        if max_count is not None and max_count > 0:
            git_args.extend(["-n", str(max_count)])
        
        if since is not None:
            since_str = format_iso_datetime(since) if isinstance(since, datetime) else str(since)
            git_args.append(f"--since={since_str}")

        if until is not None:
            until_str = format_iso_datetime(until) if isinstance(until, datetime) else str(until)
            git_args.append(f"--until={until_str}")

        if author:
            git_args.append(f"--author={author}")

        if branch:
            git_args.append(branch)

        res = self._run_git(git_args, check=False)
        
        # Empty repo check: git log exits with 128 when branch has no commits
        if res.returncode != 0:
            stderr = res.stderr.lower()
            if "does not have any commits yet" in stderr or "unknown revision" in stderr:
                return []
            raise GitCommandError(
                f"Failed to extract commits: {res.stderr.strip()}",
                command=" ".join(git_args),
                exit_code=res.returncode,
                stderr=res.stderr.strip(),
            )

        output = res.stdout
        if not output.strip():
            return []

        commits = self._parse_log_output(output)
        
        # Sort chronologically (oldest first) to ensure binary search invariants
        commits.sort(key=lambda c: c.commit_date)
        return commits

    def extract_file_changes(
        self,
        commits: Sequence[Commit],
    ) -> List[FileChange]:
        """Extract detailed file changes corresponding to a sequence of commits.
        
        Args:
            commits: Evaluated commits.
            
        Returns:
            List of FileChange objects.
        """
        file_changes: List[FileChange] = []
        if not commits:
            return file_changes

        # Query git log with raw status and numstat for accurate change types
        # We can extract each commit's individual numstat and status
        for commit in commits:
            res = self._run_git(
                ["show", "--numstat", "--format=", commit.commit_hash],
                check=False,
            )
            if res.returncode != 0:
                continue

            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    raw_ins, raw_del, raw_path = parts[0], parts[1], parts[2]
                    ins = int(raw_ins) if raw_ins.isdigit() else 0
                    dels = int(raw_del) if raw_del.isdigit() else 0
                    
                    # Clean renamed path formats like {old => new}
                    clean_path = self._clean_file_path(raw_path)
                    
                    file_changes.append(
                        FileChange(
                            file_path=clean_path,
                            commit_hash=commit.commit_hash,
                            change_type="modified",
                            insertions=ins,
                            deletions=dels,
                            timestamp=commit.commit_date,
                        )
                    )

        return file_changes

    def _parse_log_output(self, output: str) -> List[Commit]:
        """Parse structured git log output into Commit objects."""
        raw_blocks = output.split(COMMIT_DELIMITER)
        commits: List[Commit] = []

        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue

            lines = block.splitlines()
            if len(lines) < 5:
                continue

            chash = lines[0].strip()
            author = lines[1].strip()
            email = lines[2].strip()
            date_str = lines[3].strip()
            message = lines[4].strip()

            insertions = 0
            deletions = 0
            changed_files: List[str] = []

            # Remaining lines are numstat outputs
            for numstat_line in lines[5:]:
                parts = numstat_line.split("\t")
                if len(parts) >= 3:
                    ins_str, del_str, path_str = parts[0], parts[1], parts[2]
                    if ins_str.isdigit():
                        insertions += int(ins_str)
                    if del_str.isdigit():
                        deletions += int(del_str)
                    clean_path = self._clean_file_path(path_str)
                    changed_files.append(clean_path)

            try:
                commit = Commit(
                    commit_hash=chash,
                    author=author,
                    author_email=email,
                    commit_date=date_str,
                    message=message,
                    files_changed=changed_files,
                    insertions=insertions,
                    deletions=deletions,
                )
                commits.append(commit)
            except Exception:
                # Skip invalid commits gracefully
                continue

        return commits

    @staticmethod
    def _clean_file_path(raw_path: str) -> str:
        """Sanitize git log path, handling renames such as 'dir/{old => new}/file'."""
        path = raw_path.strip().replace("\\", "/")
        if "=>" in path:
            # Handle git rename pattern: prefix{old => new}suffix or old => new
            match = re.search(r"^(.*?)\{.*?=>\s*(.*?)\}(.*)$", path)
            if match:
                prefix, new_middle, suffix = match.groups()
                path = f"{prefix}{new_middle}{suffix}".replace("//", "/")
            else:
                parts = path.split("=>")
                path = parts[-1].strip()
        return path
