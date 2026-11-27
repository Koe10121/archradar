"""GitHub diff fetching, unified diff parsing, priority truncation, and HMAC verification."""

import hashlib
import hmac
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from unidiff.patch import Hunk, PatchedFile, PatchSet

from app.parser.base import normalize_repo_path
from app.services.blast_radius import SENSITIVE_BOUNDARY_KEYWORDS

_GITHUB_PR_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)/?$"
)
_SYMBOL_DEF_RE = re.compile(
    r"(?:def|async\s+def|class|"
    r"export\s+(?:async\s+)?(?:function|const|class|interface|type|enum)|"
    r"func(?:\s*\([^)]*\))?|type|"
    r"pub\s+(?:async\s+)?(?:fn|struct|enum|trait|type)|"
    r"public\s+(?:class|interface|enum|record))"
    r"\s+([A-Za-z_][A-Za-z0-9_]*)"
)
_SIGNATURE_PREFIXES = (
    "export function ",
    "export async function ",
    "export interface ",
    "export type ",
    "export class ",
    "export enum ",
    "export const ",
    "def ",
    "async def ",
    "class ",
    "func ",
    "type ",
    "pub fn ",
    "pub async fn ",
    "pub struct ",
    "pub enum ",
    "pub trait ",
    "pub type ",
    "public class ",
    "public interface ",
    "public enum ",
    "public record ",
)
_DIFF_PRIORITY_BOUNDARY_KEYWORDS = SENSITIVE_BOUNDARY_KEYWORDS | frozenset(
    {"crypto", "token", "secret", "session", "oauth", "jwt"}
)
_TRUNCATION_FOOTER = "\n... [diff truncated for token budget; prioritized high-impact hunks]"


@dataclass(frozen=True)
class ParsedDiff:
    """Structured files and changed symbols extracted from a unified git diff."""

    changed_files: list[str]
    changed_symbols_by_file: dict[str, set[str]]
    truncated_diff: str
    raw_diff: str = ""
    top_level_edited_files: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _ScoredHunk:
    score: int
    file_idx: int
    hunk_idx: int
    rel_path: str
    file_header: str
    hunk_text: str


def _strip_diff_prefix(raw_file_path: str) -> str | None:
    cleaned = raw_file_path.strip()
    if not cleaned or cleaned == "/dev/null":
        return None
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return normalize_repo_path(cleaned)


def _is_comment_or_blank_line(line_text: str) -> bool:
    stripped = line_text.strip()
    if not stripped:
        return True
    return stripped.startswith(("//", "/*", "*", "*/", "#", '"""', "'''"))


def _touches_sensitive_boundary(rel_path: str, sensitive_files: set[str]) -> bool:
    if rel_path in sensitive_files:
        return True
    parts = rel_path.lower().replace(".", "/").split("/")
    return any(part in _DIFF_PRIORITY_BOUNDARY_KEYWORDS for part in parts)


def _score_hunk(
    rel_path: str,
    hunk: Hunk,
    *,
    in_degree_by_file: Mapping[str, int],
    sensitive_files: set[str],
) -> int:
    score = 0
    if _touches_sensitive_boundary(rel_path, sensitive_files):
        score += 45

    in_degree = max(0, in_degree_by_file.get(rel_path, 0))
    score += min(60, in_degree * 15)

    has_changed_lines = False
    has_non_comment_change = False
    has_signature_change = False

    for line in hunk:
        if not (line.is_added or line.is_removed):
            continue
        has_changed_lines = True
        body = line.value
        if _is_comment_or_blank_line(body):
            continue
        has_non_comment_change = True
        stripped = body.lstrip()
        if _SYMBOL_DEF_RE.search(body) or stripped.startswith(_SIGNATURE_PREFIXES):
            has_signature_change = True

    if (
        has_non_comment_change
        and hunk.section_header
        and _SYMBOL_DEF_RE.search(hunk.section_header)
    ):
        has_signature_change = True

    if has_signature_change:
        score += 55
    if has_non_comment_change:
        score += 15
    elif has_changed_lines:
        score -= 40

    return score


def _build_file_header(patched_file: PatchedFile, rel_path: str) -> str:
    source_label = patched_file.source_file.strip() or f"a/{rel_path}"
    target_label = patched_file.target_file.strip() or f"b/{rel_path}"
    return f"diff --git a/{rel_path} b/{rel_path}\n--- {source_label}\n+++ {target_label}\n"


def _clip_to_line_boundary(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    cut = text.rfind("\n", 0, max_len)
    if cut <= 0:
        return text[:max_len]
    return text[: cut + 1]


def prioritize_and_truncate_diff(
    raw_diff: str,
    *,
    max_chars: int = 12_000,
    in_degree_by_file: Mapping[str, int] | None = None,
    sensitive_files: set[str] | None = None,
) -> str:
    """Prioritize hunks touching sensitive boundaries, high in_degree hubs, and signatures."""
    if len(raw_diff) <= max_chars:
        return raw_diff

    degrees = in_degree_by_file or {}
    sensitive = sensitive_files or set()
    patch_set = PatchSet(raw_diff)

    scored_hunks: list[_ScoredHunk] = []
    for file_idx, patched_file in enumerate(patch_set):
        target = _strip_diff_prefix(patched_file.target_file)
        source = _strip_diff_prefix(patched_file.source_file)
        rel_path = target or source
        if rel_path is None:
            continue
        file_header = _build_file_header(patched_file, rel_path)
        for hunk_idx, hunk in enumerate(patched_file):
            hunk_score = _score_hunk(
                rel_path,
                hunk,
                in_degree_by_file=degrees,
                sensitive_files=sensitive,
            )
            scored_hunks.append(
                _ScoredHunk(
                    score=hunk_score,
                    file_idx=file_idx,
                    hunk_idx=hunk_idx,
                    rel_path=rel_path,
                    file_header=file_header,
                    hunk_text=str(hunk),
                )
            )

    if not scored_hunks:
        budget = max(0, max_chars - len(_TRUNCATION_FOOTER))
        return raw_diff[:budget] + _TRUNCATION_FOOTER

    scored_hunks.sort(key=lambda item: (-item.score, item.file_idx, item.hunk_idx))
    budget = max(0, max_chars - len(_TRUNCATION_FOOTER))

    chunks: list[str] = []
    used = 0
    last_file_idx: int | None = None

    for item in scored_hunks:
        prefix = "" if item.file_idx == last_file_idx else item.file_header
        candidate = f"{prefix}{item.hunk_text}"
        if not candidate.endswith("\n"):
            candidate += "\n"

        if used + len(candidate) <= budget:
            chunks.append(candidate)
            used += len(candidate)
            last_file_idx = item.file_idx
            continue

        remaining = budget - used
        min_useful_chunk = len(prefix) + 80
        if remaining >= min_useful_chunk:
            clipped = _clip_to_line_boundary(candidate, remaining)
            if clipped:
                chunks.append(clipped)
                used += len(clipped)
        break

    if not chunks:
        return _clip_to_line_boundary(raw_diff, budget) + _TRUNCATION_FOOTER

    assembled = "".join(chunks).rstrip("\n")
    return f"{assembled}{_TRUNCATION_FOOTER}"


def _is_pure_import_header(line_text: str) -> bool:
    stripped = line_text.strip()
    if stripped.startswith("export "):
        return False
    return stripped.startswith(("import ", "from ", "package ", "use "))


def _extract_symbol_spans(
    raw_exports: Sequence[Mapping[str, object]],
) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for item in raw_exports:
        name = item.get("name")
        start = item.get("start_line")
        end = item.get("end_line")
        if (
            isinstance(name, str)
            and name
            and isinstance(start, int)
            and isinstance(end, int)
            and start <= end
        ):
            spans.append((start, end, name))
    return spans


def parse_unified_diff(
    raw_diff: str,
    max_chars: int = 12_000,
    *,
    in_degree_by_file: Mapping[str, int] | None = None,
    sensitive_files: set[str] | None = None,
    exports_by_file: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> ParsedDiff:
    """Parse unified diff into normalized file paths, AST-mapped symbols, and bounded diff text."""
    patch_set = PatchSet(raw_diff)
    changed_files: list[str] = []
    seen_files: set[str] = set()
    changed_symbols_by_file: dict[str, set[str]] = {}
    top_level_edited_files: set[str] = set()

    for patched_file in patch_set:
        target = _strip_diff_prefix(patched_file.target_file)
        source = _strip_diff_prefix(patched_file.source_file)
        rel_path = target or source
        if rel_path is None:
            continue

        if rel_path not in seen_files:
            seen_files.add(rel_path)
            changed_files.append(rel_path)

        symbols = changed_symbols_by_file.setdefault(rel_path, set())
        file_spans = (
            _extract_symbol_spans(exports_by_file.get(rel_path, ()))
            if exports_by_file is not None
            else []
        )

        for hunk in patched_file:
            hunk_has_code_edit = False
            for line in hunk:
                if not (line.is_added or line.is_removed):
                    continue
                for match in _SYMBOL_DEF_RE.finditer(line.value):
                    symbols.add(match.group(1))

                if _is_comment_or_blank_line(line.value):
                    continue
                hunk_has_code_edit = True

                line_no = line.target_line_no if line.is_added else line.source_line_no
                if file_spans and line_no is not None:
                    matched_span = False
                    for s_start, s_end, s_name in file_spans:
                        if s_start <= line_no <= s_end:
                            symbols.add(s_name)
                            matched_span = True
                    if not matched_span and not _is_pure_import_header(line.value):
                        top_level_edited_files.add(rel_path)

            if hunk_has_code_edit and hunk.section_header and not file_spans:
                for match in _SYMBOL_DEF_RE.finditer(hunk.section_header):
                    symbols.add(match.group(1))

    truncated_diff = prioritize_and_truncate_diff(
        raw_diff,
        max_chars=max_chars,
        in_degree_by_file=in_degree_by_file,
        sensitive_files=sensitive_files,
    )

    return ParsedDiff(
        changed_files=changed_files,
        changed_symbols_by_file=changed_symbols_by_file,
        truncated_diff=truncated_diff,
        raw_diff=raw_diff,
        top_level_edited_files=top_level_edited_files,
    )


def parse_github_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Extract (owner, repo, pr_number) from a GitHub Pull Request URL."""
    match = _GITHUB_PR_RE.match(pr_url.strip())
    if match is None:
        raise ValueError(f"Unsupported GitHub PR URL: {pr_url}")
    owner, repo, num_str = match.group(1), match.group(2), match.group(3)
    return owner, repo, int(num_str)


async def fetch_github_pr_diff(
    pr_url: str,
    github_token: str = "",
) -> tuple[str, str, int, str]:
    """Fetch PR title, description, number, and unified diff from GitHub."""
    owner, repo, pr_number = parse_github_pr_url(pr_url)
    base_headers = {
        "User-Agent": "ArchRadar-PR-Analyzer/0.1",
    }
    if github_token:
        base_headers["Authorization"] = f"Bearer {github_token}"

    pr_api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        meta_resp = await client.get(
            pr_api_url,
            headers={**base_headers, "Accept": "application/vnd.github+json"},
        )
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        diff_resp = await client.get(
            pr_api_url,
            headers={**base_headers, "Accept": "application/vnd.github.v3.diff"},
        )
        diff_resp.raise_for_status()

    title = str(meta.get("title") or f"PR #{pr_number}")
    body = str(meta.get("body") or "")
    return title, body, pr_number, diff_resp.text


async def fetch_github_repo_prs(
    owner: str,
    repo: str,
    *,
    github_token: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Fetch recent open and closed Pull Requests for a GitHub repository."""
    headers = {
        "User-Agent": "ArchRadar-PR-Analyzer/0.1",
        "Accept": "application/vnd.github+json",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params: dict[str, str | int] = {
        "state": "all",
        "sort": "updated",
        "direction": "desc",
        "per_page": max(1, min(limit, 20)),
    }
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        payload = resp.json()

    if not isinstance(payload, list):
        return []

    results: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        num = item.get("number")
        html_url = item.get("html_url")
        if not isinstance(num, int) or not isinstance(html_url, str):
            continue
        user_obj = item.get("user")
        author = (
            str(user_obj.get("login"))
            if isinstance(user_obj, dict) and user_obj.get("login")
            else "unknown"
        )
        merged_at = item.get("merged_at")
        raw_state = str(item.get("state") or "open")
        effective_state = "merged" if (raw_state == "closed" and merged_at) else raw_state
        results.append(
            {
                "number": num,
                "title": str(item.get("title") or f"PR #{num}"),
                "state": effective_state,
                "author": author,
                "html_url": html_url,
                "updated_at": str(item.get("updated_at") or ""),
                "draft": bool(item.get("draft", False)),
            }
        )
    return results


def verify_github_webhook_signature(
    payload_body: bytes,
    signature_header: str | None,
    webhook_secret: str,
) -> bool:
    """Validate GitHub X-Hub-Signature-256 HMAC using constant-time comparison."""
    if not webhook_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    digest = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header)
