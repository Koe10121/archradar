"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  FolderGit2,
  GitPullRequest,
  Layers,
  Radar,
  Search,
  Sparkles,
} from "lucide-react";

import { AnalyzePRModal } from "@/components/analyze-pr-modal";
import { BlastRadiusPanel } from "@/components/blast-radius-panel";
import { ArchitectureCanvas } from "@/components/graph/architecture-canvas";
import { IndexRepoModal } from "@/components/index-repo-modal";
import { NodeInspectorDrawer } from "@/components/node-inspector-drawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchRepositories,
  fetchRepositoryGraph,
  type HealthCheckResult,
} from "@/lib/api";
import {
  DEMO_GRAPH,
  DEMO_PR_SCENARIOS,
  DEMO_REPOSITORY,
  DEMO_REPO_ID,
} from "@/lib/demo-data";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";
import { type GraphResponse, type RepositorySummary } from "@/lib/schemas/repo";

interface ArchRadarWorkspaceProps {
  initialHealth: HealthCheckResult;
  initialRepos: RepositorySummary[];
  initialGraph: GraphResponse | null;
}

export function ArchRadarWorkspace({
  initialHealth,
  initialRepos,
  initialGraph,
}: ArchRadarWorkspaceProps): React.JSX.Element {
  const [repos, setRepos] = useState<RepositorySummary[]>([
    ...initialRepos,
    DEMO_REPOSITORY,
  ]);
  const [activeRepoId, setActiveRepoId] = useState<string>(
    initialGraph?.repository_id ?? DEMO_REPO_ID
  );
  const [graph, setGraph] = useState<GraphResponse>(initialGraph ?? DEMO_GRAPH);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeAnalysis, setActiveAnalysis] = useState<PRAnalysisResponse | null>(
    initialGraph ? null : (DEMO_PR_SCENARIOS[0] ?? null)
  );
  const [blastOverlayActive, setBlastOverlayActive] = useState<boolean>(!initialGraph);
  const [activeTab, setActiveTab] = useState<"blast" | "inspector">("blast");
  const [searchQuery, setSearchQuery] = useState("");
  const [focusedPaths, setFocusedPaths] = useState<string[]>([]);
  const [focusTrigger, setFocusTrigger] = useState(0);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [indexOpen, setIndexOpen] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const activeRepo = useMemo(
    () => repos.find((r) => r.id === activeRepoId) ?? DEMO_REPOSITORY,
    [repos, activeRepoId]
  );

  const selectedNode = useMemo(
    () => graph.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId]
  );

  const searchMatchesCount = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return 0;
    return graph.nodes.filter(
      (n) =>
        n.path.toLowerCase().includes(q) ||
        n.exports.some((e) => e.name.toLowerCase().includes(q))
    ).length;
  }, [graph.nodes, searchQuery]);

  async function handleSelectRepo(nextRepoId: string): Promise<void> {
    setStatusError(null);
    setSelectedNodeId(null);

    if (nextRepoId === DEMO_REPO_ID) {
      setActiveRepoId(DEMO_REPO_ID);
      setGraph(DEMO_GRAPH);
      setActiveAnalysis(DEMO_PR_SCENARIOS[0] ?? null);
      setBlastOverlayActive(true);
      setActiveTab("blast");
      return;
    }

    const res = await fetchRepositoryGraph(nextRepoId);
    if (!res.ok) {
      setStatusError(`Failed to load repository graph: ${res.error}`);
      return;
    }
    setActiveRepoId(nextRepoId);
    setGraph(res.data);
    setActiveAnalysis(null);
    setBlastOverlayActive(false);
  }

  async function handleRepoIndexed(repositoryId: string): Promise<void> {
    const [reposRes, graphRes] = await Promise.all([
      fetchRepositories(),
      fetchRepositoryGraph(repositoryId),
    ]);
    if (reposRes.ok) {
      setRepos([...reposRes.data, DEMO_REPOSITORY]);
    }
    if (graphRes.ok) {
      setActiveRepoId(repositoryId);
      setGraph(graphRes.data);
      setActiveAnalysis(null);
      setBlastOverlayActive(false);
      setSelectedNodeId(null);
    } else {
      setStatusError(graphRes.error);
    }
  }

  function handleSelectNode(nodeId: string | null): void {
    setSelectedNodeId(nodeId);
    if (nodeId) {
      setActiveTab("inspector");
    }
  }

  function handleNavigateToNode(nodeId: string): void {
    const target = graph.nodes.find((n) => n.id === nodeId);
    setSelectedNodeId(nodeId);
    setActiveTab("inspector");
    if (target) {
      setFocusedPaths([target.path]);
      setFocusTrigger((n) => n + 1);
    }
  }

  function handleFocusPaths(paths: string[]): void {
    if (paths.length === 0) return;
    setFocusedPaths(paths);
    setFocusTrigger((n) => n + 1);
  }

  function handleSimulateDemoPR(scenarioIndex: number): void {
    const scenario = DEMO_PR_SCENARIOS[scenarioIndex];
    if (!scenario) return;
    setActiveRepoId(DEMO_REPO_ID);
    setGraph(DEMO_GRAPH);
    setActiveAnalysis(scenario);
    setBlastOverlayActive(true);
    setActiveTab("blast");
    handleFocusPaths([
      ...scenario.blast_radius.direct,
      ...scenario.blast_radius.hop_1,
    ]);
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card/80 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-400">
              <Radar className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold tracking-tight">ArchRadar</span>
                {activeRepoId === DEMO_REPO_ID && <Badge>Demo Mode</Badge>}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {graph.file_count} files · {graph.edge_count} edges
              </p>
            </div>
          </div>

          <select
            aria-label="Select repository"
            value={activeRepoId}
            onChange={(e) => void handleSelectRepo(e.target.value)}
            className="h-8 rounded-md border border-input bg-slate-950 px-2.5 text-xs text-slate-100 outline-none focus:ring-2 focus:ring-ring"
          >
            {repos.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.id === DEMO_REPO_ID ? "Demo: " : ""}
                {repo.owner}/{repo.name} ({repo.file_count} files)
              </option>
            ))}
          </select>

          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search files or symbols..."
              className="h-8 w-52 rounded-md border border-input bg-slate-950 pl-8 pr-3 text-xs text-slate-100 outline-none focus:ring-2 focus:ring-ring"
            />
            {searchQuery.trim().length > 0 && (
              <span className="ml-2 text-[11px] text-sky-300">
                {searchMatchesCount} match{searchMatchesCount === 1 ? "" : "es"}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="hidden items-center gap-1.5 rounded-md border border-border bg-slate-950/70 px-2.5 py-1 text-[11px] md:flex">
            <Activity className="h-3.5 w-3.5 text-amber-400" />
            {initialHealth.ok ? (
              <span className="text-slate-300">
                API: <strong className="text-emerald-300">{initialHealth.data.status}</strong>{" "}
                · DB:{" "}
                <strong
                  className={
                    initialHealth.data.database === "connected"
                      ? "text-emerald-300"
                      : "text-amber-300"
                  }
                >
                  {initialHealth.data.database}
                </strong>
              </span>
            ) : (
              <span className="text-slate-400">API offline (Demo Mode ready)</span>
            )}
          </div>

          <Button
            size="sm"
            variant="secondary"
            className="h-8 text-xs"
            onClick={() => handleSimulateDemoPR(0)}
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />
            Simulate PR #42
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs"
            onClick={() => setAnalyzeOpen(true)}
          >
            <GitPullRequest className="h-3.5 w-3.5" />
            Analyze PR
          </Button>
          <Button
            size="sm"
            className="h-8 text-xs"
            onClick={() => setIndexOpen(true)}
          >
            <FolderGit2 className="h-3.5 w-3.5" />
            Index Repo
          </Button>
        </div>
      </header>

      {statusError && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-200">
          {statusError}
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_410px]">
        <div className="min-h-[540px] lg:h-[calc(100vh-6.25rem)]">
          <ArchitectureCanvas
            graph={graph}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleSelectNode}
            blastRadius={activeAnalysis?.blast_radius ?? null}
            blastOverlayActive={blastOverlayActive}
            searchQuery={searchQuery}
            focusedPaths={focusedPaths}
            focusTrigger={focusTrigger}
          />
        </div>

        <aside className="flex flex-col overflow-hidden rounded-xl border border-border bg-card lg:h-[calc(100vh-6.25rem)]">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => setActiveTab("blast")}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                  activeTab === "blast"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Blast Radius
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("inspector")}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                  activeTab === "inspector"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Node Inspector
              </button>
            </div>

            {activeRepoId === DEMO_REPO_ID && (
              <div className="flex items-center gap-1 text-[11px]">
                <Layers className="h-3 w-3 text-muted-foreground" />
                <button
                  type="button"
                  onClick={() => handleSimulateDemoPR(0)}
                  className="rounded px-1.5 py-0.5 text-amber-300 hover:bg-secondary"
                >
                  #42
                </button>
                <button
                  type="button"
                  onClick={() => handleSimulateDemoPR(1)}
                  className="rounded px-1.5 py-0.5 text-emerald-300 hover:bg-secondary"
                >
                  #47
                </button>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {activeTab === "blast" ? (
              <BlastRadiusPanel
                analysis={activeAnalysis}
                overlayActive={blastOverlayActive}
                onToggleOverlay={() => setBlastOverlayActive((prev) => !prev)}
                onClearAnalysis={() => {
                  setActiveAnalysis(null);
                  setBlastOverlayActive(false);
                }}
                onFocusPaths={handleFocusPaths}
              />
            ) : (
              <NodeInspectorDrawer
                graph={graph}
                selectedNode={selectedNode}
                activeAnalysis={activeAnalysis}
                blastOverlayActive={blastOverlayActive}
                onNavigateToNode={handleNavigateToNode}
              />
            )}
          </div>
        </aside>
      </div>

      <AnalyzePRModal
        open={analyzeOpen}
        repoId={activeRepoId}
        repoLabel={`${activeRepo.owner}/${activeRepo.name}`}
        graph={graph}
        onClose={() => setAnalyzeOpen(false)}
        onAnalyzed={(analysis) => {
          setActiveAnalysis(analysis);
          setBlastOverlayActive(true);
          setActiveTab("blast");
          handleFocusPaths([
            ...analysis.blast_radius.direct,
            ...analysis.blast_radius.hop_1,
          ]);
        }}
      />

      <IndexRepoModal
        open={indexOpen}
        onClose={() => setIndexOpen(false)}
        onIndexed={handleRepoIndexed}
      />
    </div>
  );
}
