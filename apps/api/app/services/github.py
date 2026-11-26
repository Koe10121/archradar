"""GitHub diff fetching, unified diff parsing, and HMAC webhook verification."""

import hashlib
import hmac
import re
from dataclasses import dataclass

import httpx
from unidiff.patch import PatchSet

from app.parser.base import normalize_repo_path

_GITHUB_PR_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)/?$"
)
_SYMBOL_DEF_RE = re.compile(
    r"(?:def|async\s+def|class|export\s+(?:async\s+)?(?:function|const|class|interface|type|enum))"
    r"\s+([A-Za-z_][A-Za-z0-9_]*)"
)


@dataclass(frozen=True)
class ParsedDiff:
    """Structured files and changed symbols extracted from a unified git diff."""

    changed_files: list[str]
    changed_symbols_by_file: dict[str, set[str]]
    truncated_diff: str


def _strip_diff_prefix(raw_file_path: str) -> str | None:
    cleaned = raw_file_path.strip()
    if not cleaned or cleaned == "/dev/null":
        return None
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return normalize_repo_path(cleaned)


def parse_unified_diff(raw_diff: str, max_chars: int = 12_000) -> ParsedDiff:
    """Parse unified diff into normalized file paths, changed symbols, and bounded diff text."""
    patch_set = PatchSet(raw_diff)
    changed_files: list[str] = []
    seen_files: set[str] = set()
    changed_symbols_by_file: dict[str, set[str]] = {}

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
        for hunk in patched_file:
            if hunk.section_header:
                for match in _SYMBOL_DEF_RE.finditer(hunk.section_header):
                    symbols.add(match.group(1))
            for line in hunk:
                if line.is_added or line.is_removed:
                    for match in _SYMBOL_DEF_RE.finditer(line.value):
                        symbols.add(match.group(1))

    if len(raw_diff) > max_chars:
        truncated_diff = raw_diff[:max_chars] + "\n... [diff truncated for token budget]"
    else:
        truncated_diff = raw_diff

    return ParsedDiff(
        changed_files=changed_files,
        changed_symbols_by_file=changed_symbols_by_file,
        truncated_diff=truncated_diff,
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
