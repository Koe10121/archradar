"""Deterministic symbol-, route-, and env-anchored documentation section retriever."""

import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_ENV_VAR_RE = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")
_ROUTE_PATH_RE = re.compile(r"(/api/[A-Za-z0-9_{}/-]+)")


@dataclass(frozen=True)
class _DocChunk:
    doc_path: str
    heading: str
    text: str
    order_idx: int


def _split_markdown_chunks(doc_path: str, content: str) -> list[_DocChunk]:
    if not content.strip():
        return []
    if not doc_path.lower().endswith(".md"):
        return [
            _DocChunk(
                doc_path=doc_path,
                heading="Specification",
                text=content[:3500],
                order_idx=0,
            )
        ]

    chunks: list[_DocChunk] = []
    cur_heading = "Overview"
    cur_lines: list[str] = []
    order_idx = 0

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match and cur_lines:
            body = "\n".join(cur_lines).strip()
            if body:
                chunks.append(
                    _DocChunk(
                        doc_path=doc_path,
                        heading=cur_heading,
                        text=body,
                        order_idx=order_idx,
                    )
                )
                order_idx += 1
            cur_heading = match.group(2).strip()
            cur_lines = [line]
        else:
            if match:
                cur_heading = match.group(2).strip()
            cur_lines.append(line)

    if cur_lines:
        body = "\n".join(cur_lines).strip()
        if body:
            chunks.append(
                _DocChunk(
                    doc_path=doc_path,
                    heading=cur_heading,
                    text=body,
                    order_idx=order_idx,
                )
            )
    return chunks


def retrieve_relevant_doc_excerpts(
    documents: Mapping[str, str],
    *,
    changed_files: list[str],
    hop_1_files: list[str],
    changed_symbols_by_file: Mapping[str, set[str]],
    raw_diff: str,
    budget_chars: int = 4_000,
) -> tuple[dict[str, str], list[str]]:
    """Select relevant Markdown sections and candidate doc files for a PR diff."""
    if not documents or budget_chars <= 0:
        return {}, []

    exact_symbols: set[str] = set()
    for syms in changed_symbols_by_file.values():
        for sym in syms:
            if len(sym) >= 3 and sym != "default":
                exact_symbols.add(sym)

    file_stems: set[str] = set()
    exact_paths = set(changed_files) | set(hop_1_files[:8])
    for fpath in exact_paths:
        stem = posixpath.splitext(posixpath.basename(fpath))[0]
        if len(stem) >= 3 and stem not in {"index", "main", "mod", "lib", "init", "__init__"}:
            file_stems.add(stem.lower())

    diff_changed_lines = "\n".join(
        line[1:]
        for line in raw_diff.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith(("+++ ", "--- "))
    )
    diff_envs = set(_ENV_VAR_RE.findall(diff_changed_lines))
    diff_routes = set(_ROUTE_PATH_RE.findall(diff_changed_lines))
    touches_env_or_settings = (
        bool(diff_envs)
        or "settings" in diff_changed_lines.lower()
        or "environ" in diff_changed_lines.lower()
    )
    touches_routes = bool(diff_routes) or any(
        seg in f.lower() for f in changed_files for seg in ("route", "api", "webhook", "auth")
    )

    scored: list[tuple[int, _DocChunk]] = []
    candidate_docs: set[str] = set()

    for doc_path in sorted(documents):
        chunks = _split_markdown_chunks(doc_path, documents[doc_path])
        is_primary_doc = doc_path.upper().startswith("README") or "ARCHITECTURE" in doc_path.upper()
        for chunk in chunks:
            score = 4 if is_primary_doc else 1
            text_lower = chunk.text.lower()
            heading_lower = chunk.heading.lower()

            for fpath in changed_files:
                if fpath in chunk.text:
                    score += 30
                    candidate_docs.add(doc_path)

            for sym in exact_symbols:
                if sym in chunk.text:
                    score += 25
                    candidate_docs.add(doc_path)

            for env_name in diff_envs:
                if env_name in chunk.text:
                    score += 25
                    candidate_docs.add(doc_path)

            for route in diff_routes:
                if route in chunk.text:
                    score += 25
                    candidate_docs.add(doc_path)

            for stem in file_stems:
                if re.search(rf"\b{re.escape(stem)}\b", text_lower):
                    score += 10
                    if score >= 15:
                        candidate_docs.add(doc_path)

            if touches_env_or_settings and any(
                kw in heading_lower for kw in ("env", "config", "setup", "variable")
            ):
                score += 18
                candidate_docs.add(doc_path)

            if touches_routes and any(
                kw in heading_lower for kw in ("api", "route", "endpoint", "auth", "webhook")
            ):
                score += 18
                candidate_docs.add(doc_path)

            scored.append((score, chunk))

    scored.sort(key=lambda item: (-item[0], item[1].doc_path, item[1].order_idx))

    selected_by_doc: dict[str, list[_DocChunk]] = {}
    remaining = budget_chars
    for score, chunk in scored:
        if remaining <= 120:
            break
        if score <= 1 and selected_by_doc:
            continue
        snippet = chunk.text[:remaining]
        if not snippet:
            continue
        selected_by_doc.setdefault(chunk.doc_path, []).append(
            _DocChunk(
                doc_path=chunk.doc_path,
                heading=chunk.heading,
                text=snippet,
                order_idx=chunk.order_idx,
            )
        )
        remaining -= len(snippet) + 4

    assembled: dict[str, str] = {}
    for doc_path, doc_chunks in selected_by_doc.items():
        ordered_chunks = sorted(doc_chunks, key=lambda c: c.order_idx)
        assembled[doc_path] = "\n\n".join(c.text for c in ordered_chunks)

    return assembled, sorted(candidate_docs)
