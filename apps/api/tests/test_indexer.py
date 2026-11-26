"""Integration tests for RepoIndexer and repository/graph API endpoints."""

from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.main import create_app
from app.schemas.repo import GraphResponse, RepoIndexResponse, RepositorySummary


async def test_index_local_repo_and_fetch_graph(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """Indexing a local multi-file repo persists nodes, edges, and degree metrics."""
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}',
        encoding="utf-8",
    )
    (tmp_path / "src" / "lib").mkdir(parents=True)
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "src" / "routes").mkdir(parents=True)

    (tmp_path / "src" / "lib" / "crypto.ts").write_text(
        "export function verifyHmac(sig: string): boolean { return sig.length > 0; }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "lib" / "index.ts").write_text(
        "export { verifyHmac } from './crypto';\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "services" / "auth.ts").write_text(
        "import { verifyHmac } from '@/lib';\n"
        "export function authenticate(sig: string): boolean { return verifyHmac(sig); }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "routes" / "webhook.ts").write_text(
        "import { authenticate } from '@/services/auth';\n"
        "export function handleWebhook(sig: string): boolean { return authenticate(sig); }\n",
        encoding="utf-8",
    )
    # Ignored directory must not be indexed
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text("export const x = 1;\n")

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        index_resp = await client.post(
            "/api/repos/index",
            json={"local_path": str(tmp_path), "is_demo": True},
        )
        assert index_resp.status_code == 201
        indexed = RepoIndexResponse.model_validate(index_resp.json())
        assert indexed.status == "ready"
        assert indexed.file_count == 4
        assert indexed.edge_count == 3

        repos_resp = await client.get("/api/repos")
        assert repos_resp.status_code == 200
        repos = [RepositorySummary.model_validate(item) for item in repos_resp.json()]
        assert len(repos) == 1
        assert repos[0].is_demo is True
        assert repos[0].file_count == 4

        graph_resp = await client.get(f"/api/repos/{indexed.repository_id}/graph")
        assert graph_resp.status_code == 200
        graph = GraphResponse.model_validate(graph_resp.json())
        assert len(graph.nodes) == 4
        assert len(graph.edges) == 3

        by_path = {node.path: node for node in graph.nodes}
        assert by_path["src/lib/crypto.ts"].in_degree == 1
        assert by_path["src/lib/crypto.ts"].out_degree == 0
        assert by_path["src/routes/webhook.ts"].out_degree == 1
        assert by_path["src/routes/webhook.ts"].in_degree == 0
