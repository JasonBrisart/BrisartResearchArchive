"""
File: export/git_state.py

Purpose
-------
Read optional Git context for an export (branch, HEAD commit, clean or dirty working tree,
  modified and untracked files, recent first-parent commits) straight from the .git folder
  using the standard library, without running a git executable.

Communication / relationships
-----------------------------
Imports nothing from the application. Imported by export/pipeline.py (build_git_state) and
  export/render.py (GitState).

Settings / parameters
---------------------
build_git_state takes the project root, the export's directory and file exclusions (so the
  output folder and excluded folders are not reported as untracked), and a commit limit
  (default 5). Working files are compared to HEAD by Git blob SHA-1.

Edge cases
----------
Supports a .git folder or a gitdir: pointer file at the selected root. A detached HEAD has no
  branch. Missing or packed objects add warnings, and dirty status becomes None (unverified)
  when no tree data is readable. A repeated commit in the parent chain stops the history walk
  with a warning. Unexpected parser errors return a GitState carrying the error as a warning,
  never an exception. Excluded tracked files are reported as deleted.

Known limitations
-----------------
Does not search parent folders, read packfiles, apply .gitignore, compare the index, or
  support linked-worktree common directories or SHA-256 repositories. Raw-byte comparison
  ignores Git filters, file modes, and symlink semantics. Treat the result as supplementary
  context, not Git verification.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from export.git_state import build_git_state

    state = build_git_state(Path("/path/to/repository"), commit_limit=5)
    print(state.branch, state.head_commit_short, state.is_dirty, state.warnings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import zlib

GIT_DIRNAME = ".git"
HEAD_FILENAME = "HEAD"
PACKED_REFS_FILENAME = "packed-refs"
TREE_DIR_MODES = ("40000", "040000")
TREE_SUBMODULE_MODE = "160000"


@dataclass(frozen=True, slots=True)
class GitState:
    is_git_repo: bool
    branch: str | None = None
    head_commit: str | None = None
    head_commit_short: str | None = None
    is_dirty: bool | None = None
    dirty_status: str = "unknown"
    modified_files: tuple[str, ...] = field(default_factory=tuple)
    untracked_files: tuple[str, ...] = field(default_factory=tuple)
    recent_commits: tuple[str, ...] = field(default_factory=tuple)
    detection_method: str = "loose_object_parse"
    warnings: tuple[str, ...] = field(default_factory=tuple)


def find_git_dir(root: Path) -> Path | None:
    candidate = root / GIT_DIRNAME
    if candidate.is_dir():
        return candidate
    if candidate.is_file():
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return None
        if text.startswith("gitdir:"):
            linked = text.split(":", 1)[1].strip()
            linked_path = (root / linked).resolve()
            if linked_path.is_dir():
                return linked_path
    return None


HEADS_REF_PREFIX = "refs/heads/"


def read_head_ref(git_dir: Path) -> tuple[str | None, str | None]:
    """
    Return (branch, None) for a symbolic HEAD or (None, sha) when detached. The
    refs/heads/ prefix is stripped rather than split on '/', so feature/login keeps
    its full name and still resolves to its ref file.
    """
    head_path = git_dir / HEAD_FILENAME
    try:
        text = head_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None, None
    if text.startswith("ref:"):
        ref_path = text.split(":", 1)[1].strip()
        if ref_path.startswith(HEADS_REF_PREFIX):
            branch = ref_path[len(HEADS_REF_PREFIX):]
        else:
            # An unusual ref namespace (not a normal local branch) --
            # fall back to the full ref path rather than guessing at
            # a single path segment.
            branch = ref_path
        return branch, None
    if text:
        return None, text
    return None, None


def is_valid_sha(value: str) -> bool:
    """
    Accept only 4-40 hex characters. Object paths are built from this value, so
    a crafted packed-refs entry such as ../../etc/passwd must never reach a path.
    """
    if not value:
        return False
    if len(value) < 4 or len(value) > 40:
        return False
    return all(char in "0123456789abcdefABCDEF" for char in value)


def resolve_branch_sha(git_dir: Path, branch: str) -> str | None:
    loose_ref = git_dir / "refs" / "heads" / branch
    if loose_ref.is_file():
        try:
            sha = loose_ref.read_text(encoding="utf-8", errors="replace").strip()
            if sha and is_valid_sha(sha):
                return sha
        except Exception:
            pass
    packed = git_dir / PACKED_REFS_FILENAME
    if packed.is_file():
        try:
            target_ref = f"refs/heads/{branch}"
            for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[1].strip() == target_ref:
                    candidate_sha = parts[0].strip()
                    if is_valid_sha(candidate_sha):
                        return candidate_sha
        except Exception:
            pass
    return None


def read_loose_object(git_dir: Path, sha: str) -> tuple[str, bytes] | None:
    if not is_valid_sha(sha) or len(sha) < 3:
        return None
    object_path = git_dir / "objects" / sha[:2] / sha[2:]
    if not object_path.is_file():
        return None
    try:
        raw = zlib.decompress(object_path.read_bytes())
    except Exception:
        return None
    header, _, content = raw.partition(b"\x00")
    try:
        obj_type = header.split(b" ", 1)[0].decode("ascii")
    except Exception:
        return None
    return obj_type, content


def parse_commit_object(content: bytes) -> dict:
    text = content.decode("utf-8", errors="replace")
    header_part, _, message = text.partition("\n\n")
    tree_sha = None
    parents: list[str] = []
    author_line = ""
    committer_line = ""
    for line in header_part.splitlines():
        if line.startswith("tree "):
            tree_sha = line[len("tree "):].strip()
        elif line.startswith("parent "):
            parents.append(line[len("parent "):].strip())
        elif line.startswith("author "):
            author_line = line[len("author "):].strip()
        elif line.startswith("committer "):
            committer_line = line[len("committer "):].strip()
    return {"tree": tree_sha, "parents": parents, "author": author_line,
            "committer": committer_line, "message": message.strip()}


def parse_tree_object(content: bytes) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    i = 0
    length = len(content)
    while i < length:
        try:
            space_index = content.index(b" ", i)
            mode = content[i:space_index].decode("ascii")
            null_index = content.index(b"\x00", space_index)
            name = content[space_index + 1:null_index].decode("utf-8", errors="replace")
            sha_bytes = content[null_index + 1:null_index + 21]
            if len(sha_bytes) < 20:
                break
            entries.append((mode, name, sha_bytes.hex()))
            i = null_index + 21
        except ValueError:
            break
    return entries


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def walk_tree(git_dir: Path, tree_sha: str, prefix: str = "") -> tuple[dict[str, str], list[str]]:
    blob_paths: dict[str, str] = {}
    warnings: list[str] = []
    object_result = read_loose_object(git_dir, tree_sha)
    if object_result is None:
        warnings.append(
            f"tree object {tree_sha[:12]} at '{prefix or '.'}' is not "
            "stored as a loose object (likely packed); its contents "
            "were skipped for the dirty-tree comparison."
        )
        return blob_paths, warnings
    _, content = object_result
    for mode, name, sha_hex in parse_tree_object(content):
        relative_name = f"{prefix}{name}"
        if mode in TREE_DIR_MODES:
            sub_paths, sub_warnings = walk_tree(git_dir, sha_hex, prefix=f"{relative_name}/")
            blob_paths.update(sub_paths)
            warnings.extend(sub_warnings)
        elif mode == TREE_SUBMODULE_MODE:
            warnings.append(f"'{relative_name}' is a submodule (gitlink); excluded from the dirty-tree comparison.")
        else:
            blob_paths[relative_name] = sha_hex
    return blob_paths, warnings


def compute_working_tree_status(
    root: Path, git_dir: Path, tree_sha: str, exclude_dirs: set[str], exclude_files: set[str]
) -> tuple[bool | None, str, list[str], list[str], list[str]]:
    """
    Compare the working tree against HEAD's tree. Exclusions are case-insensitive,
    matching export/scan.py, so a Node_Modules folder is not listed as untracked.
    """
    tracked_blobs, warnings = walk_tree(git_dir, tree_sha)
    if not tracked_blobs and warnings:
        return None, "could not be verified (repository objects are packed)", [], [], warnings
    modified: list[str] = []
    seen_relative_paths: set[str] = set()
    exclude_dirs_lower = {d.lower() for d in exclude_dirs}
    exclude_files_lower = {f.lower() for f in exclude_files}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if GIT_DIRNAME in relative_parts:
            continue
        if any(part.lower() in exclude_dirs_lower for part in relative_parts[:-1]):
            continue
        if relative_parts[-1].lower() in exclude_files_lower:
            continue
        relative_posix = "/".join(relative_parts)
        seen_relative_paths.add(relative_posix)
        expected_sha = tracked_blobs.get(relative_posix)
        if expected_sha is None:
            continue
        try:
            actual_sha = git_blob_sha1(path.read_bytes())
        except Exception:
            warnings.append(f"could not read '{relative_posix}' to verify against HEAD.")
            continue
        if actual_sha != expected_sha:
            modified.append(relative_posix)
    missing = sorted(set(tracked_blobs) - seen_relative_paths)
    for path in missing:
        modified.append(f"{path} (deleted)")
    untracked = sorted(p for p in seen_relative_paths if p not in tracked_blobs)
    is_dirty = bool(modified or untracked)
    status = "uncommitted changes present" if is_dirty else "clean (matches HEAD)"
    return is_dirty, status, sorted(modified), untracked, warnings


def collect_recent_commits(git_dir: Path, head_sha: str, limit: int = 5) -> tuple[list[str], list[str]]:
    commits: list[str] = []
    warnings: list[str] = []
    current_sha: str | None = head_sha
    seen_shas: set[str] = set()
    while current_sha and len(commits) < limit:
        if current_sha in seen_shas:
            warnings.append(
                f"detected a repeated commit sha ({current_sha[:12]}) while "
                "walking history; stopped to avoid an infinite loop on a "
                "corrupted parent chain."
            )
            break
        seen_shas.add(current_sha)
        object_result = read_loose_object(git_dir, current_sha)
        if object_result is None:
            warnings.append(f"stopped walking commit history at {current_sha[:12]} (not stored as a loose object, likely packed).")
            break
        obj_type, content = object_result
        if obj_type != "commit":
            warnings.append(f"object {current_sha[:12]} was not a commit; stopped walking commit history.")
            break
        parsed = parse_commit_object(content)
        message = parsed["message"]
        subject = message.splitlines()[0] if message else "(no commit message)"
        commits.append(f"{current_sha[:10]} {subject}")
        parents = parsed["parents"]
        current_sha = parents[0] if parents else None
    return commits, warnings


def build_git_state(
    root: Path,
    exclude_dirs: set[str] | None = None,
    exclude_files: set[str] | None = None,
    commit_limit: int = 5,
) -> GitState:
    warnings: list[str] = []
    try:
        git_dir = find_git_dir(root)
        if git_dir is None:
            return GitState(is_git_repo=False, warnings=("no .git directory was found under the project root.",))
        branch, detached_sha = read_head_ref(git_dir)
        head_sha = detached_sha
        if branch and head_sha is None:
            head_sha = resolve_branch_sha(git_dir, branch)
            if head_sha is None:
                warnings.append(f"branch '{branch}' could not be resolved to a commit sha via loose refs or packed-refs.")
        if head_sha is None:
            return GitState(is_git_repo=True, branch=branch,
                             warnings=tuple(warnings) or ("HEAD commit could not be determined.",))
        is_dirty: bool | None = None
        dirty_status = "unknown"
        modified_files: tuple[str, ...] = ()
        untracked_files: tuple[str, ...] = ()
        commit_object = read_loose_object(git_dir, head_sha)
        if commit_object is not None and commit_object[0] == "commit":
            parsed_head = parse_commit_object(commit_object[1])
            tree_sha = parsed_head.get("tree")
            if tree_sha:
                (is_dirty, dirty_status, modified_list, untracked_list, dirty_warnings) = compute_working_tree_status(
                    root, git_dir, tree_sha, exclude_dirs or set(), exclude_files or set()
                )
                modified_files = tuple(modified_list)
                untracked_files = tuple(untracked_list)
                warnings.extend(dirty_warnings)
        else:
            warnings.append(f"HEAD commit {head_sha[:12]} is not stored as a loose object (likely packed); the dirty-tree comparison was skipped.")
        recent_commits, commit_warnings = collect_recent_commits(git_dir, head_sha, limit=commit_limit)
        warnings.extend(commit_warnings)
        return GitState(
            is_git_repo=True, branch=branch, head_commit=head_sha,
            head_commit_short=head_sha[:10], is_dirty=is_dirty, dirty_status=dirty_status,
            modified_files=modified_files, untracked_files=untracked_files,
            recent_commits=tuple(recent_commits), warnings=tuple(warnings),
        )
    except Exception as exc:
        return GitState(is_git_repo=True, warnings=(f"git state detection failed unexpectedly: {exc}",))
