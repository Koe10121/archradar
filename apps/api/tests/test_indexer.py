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


async def test_index_local_go_repo_with_gomod(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """Indexing a Go module resolves go.mod package imports and degree metrics."""
    (tmp_path / "go.mod").write_text("module example.com/acme/radar\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "internal" / "auth").mkdir(parents=True)
    (tmp_path / "cmd" / "api").mkdir(parents=True)

    (tmp_path / "internal" / "auth" / "jwt.go").write_text(
        "package auth\n\ntype Claims struct { Subject string }\n"
        "func VerifyToken(tok string) bool { return len(tok) > 0 }\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "api" / "main.go").write_text(
        'package main\n\nimport (\n\t"fmt"\n\tauthpkg "example.com/acme/radar/internal/auth"\n)\n\n'
        'func StartServer() { fmt.Println(authpkg.VerifyToken("ok")) }\n',
        encoding="utf-8",
    )

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        index_resp = await client.post(
            "/api/repos/index",
            json={"local_path": str(tmp_path)},
        )
        assert index_resp.status_code == 201
        indexed = RepoIndexResponse.model_validate(index_resp.json())
        assert indexed.file_count == 2
        assert indexed.edge_count == 1

        graph_resp = await client.get(f"/api/repos/{indexed.repository_id}/graph")
        assert graph_resp.status_code == 200
        graph = GraphResponse.model_validate(graph_resp.json())
        by_path = {node.path: node for node in graph.nodes}
        assert by_path["internal/auth/jwt.go"].language == "go"
        assert by_path["internal/auth/jwt.go"].in_degree == 1
        assert by_path["cmd/api/main.go"].out_degree == 1
        assert graph.edges[0].source_path == "cmd/api/main.go"
        assert graph.edges[0].target_path == "internal/auth/jwt.go"
        assert graph.edges[0].imported_symbols == ["authpkg"]
