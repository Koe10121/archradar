"""Repository indexing service using deterministic Tree-sitter parsing."""

import io
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DependencyEdge, FileNode, GraphSnapshot, Repository
from app.parser.base import (
    AliasConfig,
    ParsedFile,
    ensure_within_root,
    normalize_repo_path,
)
from app.parser.go import load_go_module_path
from app.parser.registry import ParserRegistry
from app.parser.typescript import load_tsconfig_aliases

logger = logging.getLogger(__name__)

IGNORED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".next",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "target",
        "coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".turbo",
        "out",
    }
)
_GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
MAX_ZIPBALL_BYTES = 25 * 1024 * 1024
MAX_INDEXED_FILES = 600


def parse_github_repo_url(url: str) -> tuple[str, str]:
    """Extract and validate (owner, repo_name) from a GitHub HTTPS repository URL."""
    match = _GITHUB_REPO_RE.match(url.strip())
    if match is None:
        raise ValueError(f"Unsupported GitHub repository URL: {url}")
    owner, name = match.group(1), match.group(2)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError(f"Invalid GitHub repository identifier: {url}")
    return owner, name


class RepoIndexer:
    """Walks source files safely, runs Tree-sitter AST parsing, and stores snapshots."""

    def __init__(self, registry: ParserRegistry | None = None) -> None:
        self._registry = registry or ParserRegistry()

    def _collect_source_files(self, repo_root: Path) -> list[tuple[str, Path]]:
        files: list[tuple[str, Path]] = []
        resolved_root = repo_root.resolve()

        for path in sorted(resolved_root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(resolved_root)
            if any(part in IGNORED_DIRS for part in rel.parts[:-1]):
                continue
            rel_posix = normalize_repo_path(rel.as_posix())
            if self._registry.get_adapter(rel_posix) is None:
                continue
            ensure_within_root(resolved_root, path)
            files.append((rel_posix, path))
            if len(files) >= MAX_INDEXED_FILES:
                logger.warning(
                    "Repository %s reached MAX_INDEXED_FILES (%d); truncating remaining files",
                    resolved_root,
                    MAX_INDEXED_FILES,
                )
                break

        return files

    async def index_local_directory(
        self,
        session: AsyncSession,
        repo_root: Path,
        owner: str,
        name: str,
        url: str,
        commit_sha: str = "HEAD",
        default_branch: str = "main",
        is_demo: bool = False,
    ) -> tuple[Repository, GraphSnapshot]:
        """Parse a local directory read-only and persist a complete GraphSnapshot."""
        resolved_root = repo_root.resolve()
        if not resolved_root.is_dir():
            raise ValueError(f"Repository path does not exist or is not a directory: {repo_root}")

        repo_result = await session.execute(select(Repository).where(Repository.url == url))
        repo = repo_result.scalar_one_or_none()
        if repo is None:
            repo = Repository(
                id=uuid4(),
                owner=owner,
                name=name,
                url=url,
                default_branch=default_branch,
                is_demo=is_demo,
                last_indexed_sha=commit_sha,
            )
            session.add(repo)
            await session.flush()
        else:
            repo.default_branch = default_branch
            repo.last_indexed_sha = commit_sha
            if is_demo:
                repo.is_demo = True

        snapshot = GraphSnapshot(
            id=uuid4(),
            repository_id=repo.id,
            commit_sha=commit_sha,
            file_count=0,
            edge_count=0,
            status="indexing",
        )
        session.add(snapshot)
        await session.flush()

        try:
            source_entries = self._collect_source_files(resolved_root)
            known_files = {rel_path for rel_path, _ in source_entries}
            ts_aliases = load_tsconfig_aliases(resolved_root)
            go_module_path = load_go_module_path(resolved_root)
            alias_config = AliasConfig(
                base_url=ts_aliases.base_url,
                paths=ts_aliases.paths,
                go_module_path=go_module_path,
            )

            parsed_by_path: dict[str, ParsedFile] = {}
            for rel_path, abs_path in source_entries:
                adapter = self._registry.get_adapter(rel_path)
                if adapter is None:
                    continue
                content = abs_path.read_text(encoding="utf-8", errors="replace")
                parsed_by_path[rel_path] = adapter.parse(rel_path, content)

            # Resolve directed edges and merge symbols per (source, target, edge_type)
            edge_symbols: dict[tuple[str, str, str], list[str]] = {}
            in_degree: dict[str, int] = {p: 0 for p in parsed_by_path}
            out_degree: dict[str, int] = {p: 0 for p in parsed_by_path}

            for rel_path, parsed in parsed_by_path.items():
                adapter = self._registry.get_adapter(rel_path)
                if adapter is None:
                    continue
                for raw_imp in parsed.imports:
                    targets = adapter.resolve_import(
                        source_path=rel_path,
                        raw_import=raw_imp,
                        known_files=known_files,
                        alias_config=alias_config,
                    )
                    for target in targets:
                        if target == rel_path or target not in parsed_by_path:
                            continue
                        key = (rel_path, target, raw_imp.edge_type)
                        existing_syms = edge_symbols.setdefault(key, [])
                        for sym in raw_imp.imported_symbols:
                            if sym not in existing_syms:
                                existing_syms.append(sym)

            for src_path, dst_path, _ in edge_symbols:
                out_degree[src_path] += 1
                in_degree[dst_path] += 1

            node_by_path: dict[str, FileNode] = {}
            for rel_path, parsed in sorted(parsed_by_path.items()):
                node = FileNode(
                    id=uuid4(),
                    snapshot_id=snapshot.id,
                    path=parsed.path,
                    language=parsed.language,
                    module_group=parsed.module_group,
                    loc=parsed.loc,
                    exports_json=[exp.to_dict() for exp in parsed.exports],
                    in_degree=in_degree[rel_path],
                    out_degree=out_degree[rel_path],
                )
                node_by_path[rel_path] = node
                session.add(node)

            await session.flush()

            for (src_path, dst_path, edge_type), symbols in sorted(edge_symbols.items()):
                edge = DependencyEdge(
                    id=uuid4(),
                    snapshot_id=snapshot.id,
                    source_node_id=node_by_path[src_path].id,
                    target_node_id=node_by_path[dst_path].id,
                    edge_type=edge_type,
                    imported_symbols=symbols,
                )
                session.add(edge)

            snapshot.file_count = len(node_by_path)
            snapshot.edge_count = len(edge_symbols)
            snapshot.status = "ready"
            await session.commit()
            await session.refresh(repo)
            await session.refresh(snapshot)
            return repo, snapshot
        except Exception:
            logger.error("Repository indexing failed for %s", url, exc_info=True)
            snapshot.status = "failed"
            await session.commit()
            raise

    async def index_github_repository(
        self,
        session: AsyncSession,
        repo_url: str,
        branch: str | None = None,
        github_token: str = "",
        is_demo: bool = False,
    ) -> tuple[Repository, GraphSnapshot]:
        """Download a public/authorized GitHub repo zipball read-only and index it."""
        owner, name = parse_github_repo_url(repo_url)
        canonical_url = f"https://github.com/{owner}/{name}"

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ArchRadar-Indexer/0.1",
        }
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                meta_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{name}",
                    headers=headers,
                )
                meta_resp.raise_for_status()
                meta = meta_resp.json()
                target_branch = branch or str(meta.get("default_branch") or "main")

                commit_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{name}/commits/{target_branch}",
                    headers=headers,
                )
                commit_resp.raise_for_status()
                commit_sha = str(commit_resp.json().get("sha") or target_branch)

                zip_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{name}/zipball/{commit_sha}",
                    headers=headers,
                )
                zip_resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise ValueError(
                        f"GitHub repository or branch not found (or private): {owner}/{name}"
                    ) from exc
                if exc.response.status_code in {403, 429}:
                    raise ValueError(
                        "GitHub API rate limit exceeded. Configure GITHUB_TOKEN or retry shortly."
                    ) from exc
                raise

        if len(zip_resp.content) > MAX_ZIPBALL_BYTES:
            raise ValueError(
                "Repository archive exceeds the 25 MB size limit for serverless indexing."
            )

        with tempfile.TemporaryDirectory(prefix="archradar_") as tmp_dir:
            extract_root = Path(tmp_dir)
            with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    parts = Path(member.filename).parts
                    # Strip top-level GitHub archive wrapper directory (<owner>-<repo>-<sha>/)
                    stripped = Path(*parts[1:]) if len(parts) > 1 else Path(member.filename)
                    dest = extract_root / stripped
                    ensure_within_root(extract_root, dest)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src_f, dest.open("wb") as dst_f:
                        dst_f.write(src_f.read())

            return await self.index_local_directory(
                session=session,
                repo_root=extract_root,
                owner=owner,
                name=name,
                url=canonical_url,
                commit_sha=commit_sha,
                default_branch=target_branch,
                is_demo=is_demo,
            )
