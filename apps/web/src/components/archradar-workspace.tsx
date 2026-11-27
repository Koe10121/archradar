"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  FolderGit2,
  GitPullRequest,
  HelpCircle,
  KeyRound,
  Layers,
  Radar,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import { AnalyzePRModal } from "@/components/analyze-pr-modal";
import { ArchHealthPanel } from "@/components/arch-health-panel";
import { BlastRadiusPanel } from "@/components/blast-radius-panel";
import { DriftTimelinePanel } from "@/components/drift-timeline-panel";
import { GeminiKeyModal } from "@/components/gemini-key-modal";
import { ArchitectureCanvas } from "@/components/graph/architecture-canvas";
import { IndexRepoModal } from "@/components/index-repo-modal";
import { NodeInspectorDrawer } from "@/components/node-inspector-drawer";
import { TelemetryModal } from "@/components/telemetry-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchRepositories,
  fetchRepositoryAnalyses,
  fetchRepositoryGraph,
  fetchRepositorySnapshots,
  fetchSnapshotDiff,
  type HealthCheckResult,
} from "@/lib/api";
import { computeClientArchHealth, findShortestCausalChain } from "@/lib/arch-health";
import {
  computeDemoSnapshotDiff,
  DEMO_BILLING_GRAPH,
  DEMO_BILLING_REPO_ID,
  DEMO_GRAPHS_BY_REPO_ID,
  DEMO_GRAPHS_BY_SNAPSHOT_ID,
  DEMO_PR_SCENARIOS,
  DEMO_REPOSITORIES,
  DEMO_REPOSITORY,
  DEMO_SNAPSHOTS_BY_REPO_ID,
} from "@/lib/demo-data";
import {
  clearSessionGeminiKey,
  getSessionGeminiKey,
  setSessionGeminiKey,
} from "@/lib/gemini-key";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";
import {
  type GraphResponse,
  type RepositorySummary,
  type SnapshotDiffResponse,
  type SnapshotSummary,
} from "@/lib/schemas/repo";

interface ArchRadarWorkspaceProps {
  initialHealth: HealthCheckResult;
  initialRepos: RepositorySummary[];
  initialGraph: GraphResponse | null;
  initialAnalyses?: PRAnalysisResponse[];
  initialSnapshots?: SnapshotSummary[];
}

const SCENARIO_BUTTONS: ReadonlyArray<{
  index: number;
  label: string;
  toneClass: string;
}> = [
  { index: 0, label: "#42 Auth", toneClass: "text-red-300" },
  { index: 1, label: "#51 Webhook", toneClass: "text-amber-300" },
  { index: 2, label: "#47 Refactor", toneClass: "text-emerald-300" },
];

export function ArchRadarWorkspace({
  initialHealth,
  initialRepos,
  initialGraph,
  initialAnalyses = [],
  initialSnapshots = [],
}: ArchRadarWorkspaceProps): React.JSX.Element {
  const initialSnapshotList =
    initialGraph === null
      ? (DEMO_SNAPSHOTS_BY_REPO_ID[DEMO_BILLING_REPO_ID] ?? [])
      : initialSnapshots;
  const latestInitialSnap = initialSnapshotList[initialSnapshotList.length - 1];
  const prevInitialSnap =
    initialSnapshotList.length >= 2
      ? initialSnapshotList[initialSnapshotList.length - 2]
      : latestInitialSnap;

  const [liveRepos, setLiveRepos] = useState<RepositorySummary[]>(initialRepos);
  const [activeRepoId, setActiveRepoId] = useState<string>(
    initialGraph?.repository_id ?? DEMO_BILLING_REPO_ID
  );
  const [graph, setGraph] = useState<GraphResponse>(initialGraph ?? DEMO_BILLING_GRAPH);
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>(initialSnapshotList);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>(
    initialGraph?.snapshot_id ?? latestInitialSnap?.id ?? ""
  );
  const [fromSnapshotId, setFromSnapshotId] = useState<string>(prevInitialSnap?.id ?? "");
  const [toSnapshotId, setToSnapshotId] = useState<string>(latestInitialSnap?.id ?? "");
  const [snapshotDiff, setSnapshotDiff] = useState<SnapshotDiffResponse | null>(null);
  const [driftOverlayActive, setDriftOverlayActive] = useState<boolean>(false);
  const [driftLoading, setDriftLoading] = useState<boolean>(false);
  const [driftError, setDriftError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [repoAnalyses, setRepoAnalyses] = useState<PRAnalysisResponse[]>(
    initialGraph
      ? initialAnalyses
      : DEMO_PR_SCENARIOS.filter((s) => s.repository_id === DEMO_BILLING_REPO_ID)
  );
  const [activeAnalysis, setActiveAnalysis] = useState<PRAnalysisResponse | null>(
    initialGraph ? (initialAnalyses[0] ?? null) : (DEMO_PR_SCENARIOS[0] ?? null)
  );
  const [blastOverlayActive, setBlastOverlayActive] = useState<boolean>(
    initialGraph ? initialAnalyses.length > 0 : true
  );
  const [isolateSubgraph, setIsolateSubgraph] = useState<boolean>(false);
  const [activeCyclePaths, setActiveCyclePaths] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"blast" | "health" | "drift" | "inspector">("blast");
  const [searchQuery, setSearchQuery] = useState("");
  const [focusedPaths, setFocusedPaths] = useState<string[]>([]);
  const [focusTrigger, setFocusTrigger] = useState(0);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [indexOpen, setIndexOpen] = useState(false);
  const [telemetryOpen, setTelemetryOpen] = useState(false);
  const [keyModalOpen, setKeyModalOpen] = useState(false);
  const [showGuide, setShowGuide] = useState(true);
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    setGeminiApiKey(getSessionGeminiKey());
  }, []);

  const backendRepoIds = useMemo(
    () => new Set(liveRepos.map((repo) => repo.id)),
    [liveRepos]
  );

  const repos = useMemo(() => {
    const liveUrls = new Set(liveRepos.map((repo) => repo.url));
    const missingOfflineDemos = DEMO_REPOSITORIES.filter(
      (demoRepo) => !liveUrls.has(demoRepo.url)
    );
    return [...liveRepos, ...missingOfflineDemos];
  }, [liveRepos]);

  const activeRepo = useMemo(
    () => repos.find((r) => r.id === activeRepoId) ?? DEMO_REPOSITORY,
    [repos, activeRepoId]
  );

  const isOfflineDemo = !backendRepoIds.has(activeRepoId);

  const matchingDemoScenarios = useMemo(
    () =>
      DEMO_PR_SCENARIOS.filter((scenario) => {
        const demoRepo = DEMO_REPOSITORIES.find((r) => r.id === scenario.repository_id);
        return (
          scenario.repository_id === activeRepo.id ||
          (demoRepo !== undefined && demoRepo.url === activeRepo.url)
        );
      }),
    [activeRepo]
  );

  const selectedNode = useMemo(
    () => graph.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId]
  );

  const effectiveHealth = useMemo(
    () => graph.arch_health ?? computeClientArchHealth(graph),
    [graph]
  );

  const healthSmellCount =
    effectiveHealth.cycle_count + effectiveHealth.layer_violation_count;

  const causalChainEdgeKeys = useMemo(() => {
    const keys = new Set<string>();
    if (!selectedNode || !blastOverlayActive || !activeAnalysis) return keys;
    const hops = findShortestCausalChain(
      selectedNode.path,
      activeAnalysis.blast_radius,
      graph.edges
    );
    for (const hop of hops) {
      keys.add(`${hop.sourcePath}=>${hop.targetPath}`);
    }
    return keys;
  }, [selectedNode, blastOverlayActive, activeAnalysis, graph.edges]);

  const cycleEdgeKeys = useMemo(() => {
    const keys = new Set<string>();
    for (let i = 0; i + 1 < activeCyclePaths.length; i += 1) {
      const from = activeCyclePaths[i];
      const to = activeCyclePaths[i + 1];
      if (from && to) keys.add(`${from}=>${to}`);
    }
    return keys;
  }, [activeCyclePaths]);

  const searchMatchesCount = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return 0;
    return graph.nodes.filter(
      (n) =>
        n.path.toLowerCase().includes(q) ||
        n.exports.some((e) => e.name.toLowerCase().includes(q))
    ).length;
  }, [graph.nodes, searchQuery]);

  async function loadSnapshotDiff(
    repoId: string,
    fromId: string,
    toId: string,
    snapList: SnapshotSummary[],
    offlineMode: boolean
  ): Promise<void> {
    if (!fromId || !toId) {
      setSnapshotDiff(null);
      return;
    }
    setDriftError(null);
    if (offlineMode) {
      const fromSnap = snapList.find((s) => s.id === fromId);
      const toSnap = snapList.find((s) => s.id === toId);
      const fromGraph = DEMO_GRAPHS_BY_SNAPSHOT_ID[fromId];
      const toGraph = DEMO_GRAPHS_BY_SNAPSHOT_ID[toId];
      if (fromSnap && toSnap && fromGraph && toGraph) {
        setSnapshotDiff(computeDemoSnapshotDiff(fromSnap, toSnap, fromGraph, toGraph));
      } else {
        setSnapshotDiff(null);
      }
      return;
    }

    setDriftLoading(true);
    const diffRes = await fetchSnapshotDiff(repoId, fromId, toId);
    setDriftLoading(false);
    if (!diffRes.ok) {
      setDriftError(diffRes.error);
      return;
    }
    setSnapshotDiff(diffRes.data);
  }

  function applySnapshotState(
    nextRepoId: string,
    nextSnaps: SnapshotSummary[],
    currentSnapshotId: string
  ): { fromId: string; toId: string } {
    setSnapshots(nextSnaps);
    setSelectedSnapshotId(currentSnapshotId);
    const latest = nextSnaps[nextSnaps.length - 1];
    const prev = nextSnaps.length >= 2 ? nextSnaps[nextSnaps.length - 2] : latest;
    const fromId = prev?.id ?? "";
    const toId = latest?.id ?? "";
    setFromSnapshotId(fromId);
    setToSnapshotId(toId);
    setSnapshotDiff(null);
    setDriftError(null);
    if (nextSnaps.length < 2 || !fromId || !toId) {
      setDriftOverlayActive(false);
    } else if (activeTab === "drift") {
      void loadSnapshotDiff(nextRepoId, fromId, toId, nextSnaps, !backendRepoIds.has(nextRepoId));
    }
    return { fromId, toId };
  }

  async function handleSelectRepo(nextRepoId: string): Promise<void> {
    setStatusError(null);
    setSelectedNodeId(null);
    setIsolateSubgraph(false);
    setActiveCyclePaths([]);

    if (!backendRepoIds.has(nextRepoId)) {
      const offlineGraph = DEMO_GRAPHS_BY_REPO_ID[nextRepoId] ?? DEMO_BILLING_GRAPH;
      const offlineSnaps = DEMO_SNAPSHOTS_BY_REPO_ID[nextRepoId] ?? [];
      const offlineList = DEMO_PR_SCENARIOS.filter((s) => s.repository_id === nextRepoId);
      const defaultScenario = offlineList[0] ?? null;
      setActiveRepoId(nextRepoId);
      setGraph(offlineGraph);
      setRepoAnalyses(offlineList);
      setActiveAnalysis(defaultScenario);
      setBlastOverlayActive(defaultScenario !== null);
      setDriftOverlayActive(false);
      applySnapshotState(nextRepoId, offlineSnaps, offlineGraph.snapshot_id);
      setActiveTab(defaultScenario ? "blast" : "health");
      return;
    }

    const [graphRes, analysesRes, snapsRes] = await Promise.all([
      fetchRepositoryGraph(nextRepoId),
      fetchRepositoryAnalyses(nextRepoId),
      fetchRepositorySnapshots(nextRepoId),
    ]);
    if (!graphRes.ok) {
      setStatusError(`Failed to load repository graph: ${graphRes.error}`);
      return;
    }
    const fetchedAnalyses = analysesRes.ok ? analysesRes.data : [];
    const latestAnalysis = fetchedAnalyses[0] ?? null;
    const nextSnaps = snapsRes.ok ? snapsRes.data : [];
    setActiveRepoId(nextRepoId);
    setGraph(graphRes.data);
    setRepoAnalyses(fetchedAnalyses);
    setActiveAnalysis(latestAnalysis);
    setBlastOverlayActive(latestAnalysis !== null);
    setDriftOverlayActive(false);
    applySnapshotState(nextRepoId, nextSnaps, graphRes.data.snapshot_id);
    setActiveTab(latestAnalysis ? "blast" : "health");
  }

  async function handleRepoIndexed(repositoryId: string): Promise<void> {
    setIsolateSubgraph(false);
    setActiveCyclePaths([]);
    const [reposRes, graphRes, analysesRes, snapsRes] = await Promise.all([
      fetchRepositories(),
      fetchRepositoryGraph(repositoryId),
      fetchRepositoryAnalyses(repositoryId),
      fetchRepositorySnapshots(repositoryId),
    ]);
    if (reposRes.ok) {
      setLiveRepos(reposRes.data);
    }
    if (graphRes.ok) {
      const fetchedAnalyses = analysesRes.ok ? analysesRes.data : [];
      const latestAnalysis = fetchedAnalyses[0] ?? null;
      const nextSnaps = snapsRes.ok ? snapsRes.data : [];
      setActiveRepoId(repositoryId);
      setGraph(graphRes.data);
      setRepoAnalyses(fetchedAnalyses);
      setActiveAnalysis(latestAnalysis);
      setBlastOverlayActive(latestAnalysis !== null);
      setDriftOverlayActive(false);
      setSnapshots(nextSnaps);
      setSelectedSnapshotId(graphRes.data.snapshot_id);
      const latest = nextSnaps[nextSnaps.length - 1];
      const prev = nextSnaps.length >= 2 ? nextSnaps[nextSnaps.length - 2] : latest;
      setFromSnapshotId(prev?.id ?? "");
      setToSnapshotId(latest?.id ?? "");
      setSnapshotDiff(null);
      setSelectedNodeId(null);
      setActiveTab(latestAnalysis ? "blast" : "health");
    } else {
      setStatusError(graphRes.error);
    }
  }

  async function handleOpenDriftTab(): Promise<void> {
    setActiveTab("drift");
    setBlastOverlayActive(false);
    setActiveCyclePaths([]);
    if (snapshots.length >= 2) {
      setDriftOverlayActive(true);
      if (!snapshotDiff && fromSnapshotId && toSnapshotId) {
        await loadSnapshotDiff(activeRepoId, fromSnapshotId, toSnapshotId, snapshots, isOfflineDemo);
      }
    }
  }

  async function handleScrubSnapshot(snapshotId: string): Promise<void> {
    setStatusError(null);
    setSelectedNodeId(null);
    setBlastOverlayActive(false);

    if (isOfflineDemo) {
      const offlineGraph = DEMO_GRAPHS_BY_SNAPSHOT_ID[snapshotId];
      if (offlineGraph) {
        setGraph(offlineGraph);
        setSelectedSnapshotId(snapshotId);
      }
    } else {
      const graphRes = await fetchRepositoryGraph(activeRepoId, { snapshotId });
      if (!graphRes.ok) {
        setDriftError(graphRes.error);
        return;
      }
      setGraph(graphRes.data);
      setSelectedSnapshotId(snapshotId);
    }

    if (snapshots.length >= 2) {
      setDriftOverlayActive(true);
      if (!snapshotDiff && fromSnapshotId && toSnapshotId) {
        await loadSnapshotDiff(activeRepoId, fromSnapshotId, toSnapshotId, snapshots, isOfflineDemo);
      }
    }
  }

  async function handleChangeDriftRange(nextFromId: string, nextToId: string): Promise<void> {
    setFromSnapshotId(nextFromId);
    setToSnapshotId(nextToId);
    setBlastOverlayActive(false);
    setDriftOverlayActive(true);
    await loadSnapshotDiff(activeRepoId, nextFromId, nextToId, snapshots, isOfflineDemo);
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

  function handleInspectPath(path: string): void {
    const target = graph.nodes.find((n) => n.path === path);
    if (target) {
      handleNavigateToNode(target.id);
    }
  }

  function handleFocusPaths(paths: string[]): void {
    if (paths.length === 0) return;
    setActiveCyclePaths([]);
    setFocusedPaths(paths);
    setFocusTrigger((n) => n + 1);
  }

  function handleFocusCycle(cyclePaths: string[]): void {
    if (cyclePaths.length === 0) return;
    setBlastOverlayActive(false);
    setDriftOverlayActive(false);
    setActiveCyclePaths(cyclePaths);
    const unique = [...new Set(cyclePaths)];
    setFocusedPaths(unique);
    setIsolateSubgraph(true);
    setFocusTrigger((n) => n + 1);
  }

  async function handleSimulateDemoPR(scenarioIndex: number): Promise<void> {
    const scenario = DEMO_PR_SCENARIOS[scenarioIndex];
    if (!scenario) return;
    setStatusError(null);
    setSelectedNodeId(null);
    setActiveCyclePaths([]);

    const demoRepoMeta = DEMO_REPOSITORIES.find((r) => r.id === scenario.repository_id);
    const matchedLiveRepo = demoRepoMeta
      ? liveRepos.find((r) => r.id === demoRepoMeta.id || r.url === demoRepoMeta.url)
      : undefined;

    if (matchedLiveRepo) {
      const [graphRes, analysesRes, snapsRes] = await Promise.all([
        activeRepoId === matchedLiveRepo.id && graph.snapshot_id === matchedLiveRepo.latest_snapshot_id
          ? Promise.resolve({ ok: true as const, data: graph })
          : fetchRepositoryGraph(matchedLiveRepo.id),
        fetchRepositoryAnalyses(matchedLiveRepo.id),
        fetchRepositorySnapshots(matchedLiveRepo.id),
      ]);
      if (graphRes.ok) {
        const fetchedList = analysesRes.ok ? analysesRes.data : [];
        const matchedAnalysis = fetchedList.find((a) => a.pr_number === scenario.pr_number);
        const resolvedAnalysis = matchedAnalysis ?? scenario;
        const nextSnaps = snapsRes.ok ? snapsRes.data : [];
        setActiveRepoId(matchedLiveRepo.id);
        setGraph(graphRes.data);
        setRepoAnalyses(fetchedList.length > 0 ? fetchedList : [resolvedAnalysis]);
        setActiveAnalysis(resolvedAnalysis);
        setBlastOverlayActive(true);
        setDriftOverlayActive(false);
        applySnapshotState(matchedLiveRepo.id, nextSnaps, graphRes.data.snapshot_id);
        setActiveTab("blast");
        handleFocusPaths([
          ...resolvedAnalysis.blast_radius.direct,
          ...resolvedAnalysis.blast_radius.hop_1,
        ]);
        return;
      }
    }

    const offlineGraph =
      DEMO_GRAPHS_BY_REPO_ID[scenario.repository_id] ?? DEMO_BILLING_GRAPH;
    const offlineSnaps = DEMO_SNAPSHOTS_BY_REPO_ID[scenario.repository_id] ?? [];
    const offlineList = DEMO_PR_SCENARIOS.filter(
      (s) => s.repository_id === scenario.repository_id
    );
    setActiveRepoId(scenario.repository_id);
    setGraph(offlineGraph);
    setRepoAnalyses(offlineList);
    setActiveAnalysis(scenario);
    setBlastOverlayActive(true);
    setDriftOverlayActive(false);
    applySnapshotState(scenario.repository_id, offlineSnaps, offlineGraph.snapshot_id);
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
                {activeRepo.is_demo && <Badge>Demo Mode</Badge>}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {graph.file_count} files · {graph.edge_count} edges · Health{" "}
                {effectiveHealth.health_score}/100
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
                {repo.is_demo ? "Demo: " : ""}
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
              <span className="text-emerald-300/90">Interactive Demo Mode</span>
            )}
          </div>

          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs"
            onClick={() => setKeyModalOpen(true)}
            title="Configure optional session-only Gemini API key"
          >
            <KeyRound
              className={`h-3.5 w-3.5 ${geminiApiKey ? "text-emerald-400" : "text-slate-400"}`}
            />
            {geminiApiKey ? "AI Key Set" : "Free AI Key"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs"
            onClick={() => setTelemetryOpen(true)}
          >
            <BarChart3 className="h-3.5 w-3.5 text-emerald-400" />
            Telemetry
          </Button>
          <Button
            size="sm"
            variant={showGuide ? "secondary" : "outline"}
            className="h-8 text-xs"
            onClick={() => setShowGuide((prev) => !prev)}
            title="Show or hide 3-step testing guide"
          >
            <HelpCircle className="h-3.5 w-3.5 text-sky-400" />
            Guide
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

      {showGuide && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-slate-950/70 px-4 py-2 text-xs">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-slate-300">
            <span className="font-semibold text-amber-300">Quick Start:</span>
            <span className="flex items-center gap-1.5">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500/20 font-mono text-[10px] font-bold text-amber-300">
                1
              </span>
              Pick a repo or{" "}
              <button
                type="button"
                onClick={() => setIndexOpen(true)}
                className="font-medium text-amber-300 underline-offset-2 hover:underline"
              >
                Index any public GitHub repo
              </button>{" "}
              <span className="text-muted-foreground">(monorepo + 5 languages + docs)</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-red-500/20 font-mono text-[10px] font-bold text-red-300">
                2
              </span>
              Test blast radius via{" "}
              <button
                type="button"
                onClick={() => void handleSimulateDemoPR(0)}
                className="inline-flex items-center gap-1 font-medium text-red-300 underline-offset-2 hover:underline"
              >
                <Sparkles className="h-3 w-3" />
                Demo PR #42
              </button>{" "}
              or{" "}
              <button
                type="button"
                onClick={() => setAnalyzeOpen(true)}
                className="font-medium text-slate-100 underline-offset-2 hover:underline"
              >
                Analyze PR
              </button>{" "}
              <span className="text-muted-foreground">(1-click GitHub PRs or sample diff)</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 font-mono text-[10px] font-bold text-emerald-300">
                3
              </span>
              Optional:{" "}
              <button
                type="button"
                onClick={() => setKeyModalOpen(true)}
                className="font-medium text-emerald-300 underline-offset-2 hover:underline"
              >
                {geminiApiKey ? "Gemini AI Key active" : "Add free session Gemini key"}
              </button>
            </span>
          </div>
          <button
            type="button"
            aria-label="Dismiss quick start guide"
            onClick={() => setShowGuide(false)}
            className="rounded p-1 text-slate-400 hover:bg-secondary hover:text-slate-200"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {statusError && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-200">
          {statusError}
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_420px]">
        <div className="min-h-[540px] lg:h-[calc(100vh-6.25rem)]">
          <ArchitectureCanvas
            graph={graph}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleSelectNode}
            blastRadius={activeAnalysis?.blast_radius ?? null}
            blastOverlayActive={blastOverlayActive}
            isolateSubgraph={isolateSubgraph}
            onToggleIsolateSubgraph={() => setIsolateSubgraph((prev) => !prev)}
            causalChainEdgeKeys={causalChainEdgeKeys}
            cycleEdgeKeys={cycleEdgeKeys}
            snapshotDiff={snapshotDiff}
            driftOverlayActive={driftOverlayActive}
            searchQuery={searchQuery}
            focusedPaths={focusedPaths}
            focusTrigger={focusTrigger}
          />
        </div>

        <aside className="flex flex-col overflow-hidden rounded-xl border border-border bg-card lg:h-[calc(100vh-6.25rem)]">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("blast");
                  setActiveCyclePaths([]);
                  if (activeAnalysis) {
                    setDriftOverlayActive(false);
                  }
                }}
                className={`rounded-md px-2 py-1 text-xs font-medium transition ${
                  activeTab === "blast"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Blast
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("health")}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition ${
                  activeTab === "health"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Health
                {healthSmellCount > 0 && (
                  <span className="rounded-full bg-violet-500/30 px-1.5 py-0.2 font-mono text-[10px] text-violet-200">
                    {healthSmellCount}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => void handleOpenDriftTab()}
                className={`rounded-md px-2 py-1 text-xs font-medium transition ${
                  activeTab === "drift"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Drift
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("inspector")}
                className={`rounded-md px-2 py-1 text-xs font-medium transition ${
                  activeTab === "inspector"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary"
                }`}
              >
                Inspector
              </button>
            </div>

            <div className="flex items-center gap-1 text-[11px]">
              <Layers className="h-3 w-3 text-muted-foreground" />
              {SCENARIO_BUTTONS.map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  onClick={() => void handleSimulateDemoPR(btn.index)}
                  className={`rounded px-1.5 py-0.5 hover:bg-secondary ${btn.toneClass}`}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {activeTab === "blast" ? (
              <BlastRadiusPanel
                analysis={activeAnalysis}
                analysesHistory={repoAnalyses}
                onSelectAnalysis={(picked) => {
                  setActiveAnalysis(picked);
                  setBlastOverlayActive(true);
                  setDriftOverlayActive(false);
                  setActiveCyclePaths([]);
                  handleFocusPaths([
                    ...picked.blast_radius.direct,
                    ...picked.blast_radius.hop_1,
                  ]);
                }}
                overlayActive={blastOverlayActive}
                isolateSubgraph={isolateSubgraph}
                onToggleIsolateSubgraph={() => setIsolateSubgraph((prev) => !prev)}
                isOfflineDemo={isOfflineDemo}
                onToggleOverlay={() => {
                  setBlastOverlayActive((prev) => {
                    const next = !prev;
                    if (next) {
                      setDriftOverlayActive(false);
                      setActiveCyclePaths([]);
                    } else {
                      setIsolateSubgraph(false);
                    }
                    return next;
                  });
                }}
                onClearAnalysis={() => {
                  setActiveAnalysis(null);
                  setBlastOverlayActive(false);
                  setIsolateSubgraph(false);
                }}
                onFocusPaths={handleFocusPaths}
              />
            ) : activeTab === "health" ? (
              <ArchHealthPanel
                health={effectiveHealth}
                onFocusCycle={handleFocusCycle}
                onFocusPaths={handleFocusPaths}
                onInspectPath={handleInspectPath}
              />
            ) : activeTab === "drift" ? (
              <DriftTimelinePanel
                snapshots={snapshots}
                activeSnapshotId={selectedSnapshotId || graph.snapshot_id}
                fromSnapshotId={fromSnapshotId}
                toSnapshotId={toSnapshotId}
                snapshotDiff={snapshotDiff}
                driftOverlayActive={driftOverlayActive}
                loading={driftLoading}
                error={driftError}
                isBillingDemoActive={activeRepo.url === DEMO_REPOSITORY.url}
                onScrubSnapshot={(snapId) => void handleScrubSnapshot(snapId)}
                onChangeRange={(fromId, toId) => void handleChangeDriftRange(fromId, toId)}
                onToggleDriftOverlay={() => {
                  setDriftOverlayActive((prev) => {
                    const next = !prev;
                    if (next) setBlastOverlayActive(false);
                    return next;
                  });
                }}
                onFocusPaths={handleFocusPaths}
                onSwitchToBillingDemo={() => {
                  const billingRepo =
                    repos.find((r) => r.url === DEMO_REPOSITORY.url) ?? DEMO_REPOSITORY;
                  void handleSelectRepo(billingRepo.id).then(() => void handleOpenDriftTab());
                }}
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
        isOfflineDemo={isOfflineDemo}
        isDemoRepo={activeRepo.is_demo}
        demoScenarios={matchingDemoScenarios}
        graph={graph}
        geminiApiKey={geminiApiKey}
        onOpenGeminiKeyModal={() => setKeyModalOpen(true)}
        onClose={() => setAnalyzeOpen(false)}
        onAnalyzed={(analysis) => {
          setRepoAnalyses((prev) => [
            analysis,
            ...prev.filter((item) => item.id !== analysis.id),
          ]);
          setActiveAnalysis(analysis);
          setBlastOverlayActive(true);
          setDriftOverlayActive(false);
          setActiveCyclePaths([]);
          setActiveTab("blast");
          handleFocusPaths([
            ...analysis.blast_radius.direct,
            ...analysis.blast_radius.hop_1,
          ]);
        }}
      />

      <GeminiKeyModal
        open={keyModalOpen}
        currentKey={geminiApiKey}
        apiOnline={initialHealth.ok}
        onSaveKey={(key) => {
          setSessionGeminiKey(key);
          setGeminiApiKey(key);
        }}
        onClearKey={() => {
          clearSessionGeminiKey();
          setGeminiApiKey("");
        }}
        onClose={() => setKeyModalOpen(false)}
      />

      <IndexRepoModal
        open={indexOpen}
        onClose={() => setIndexOpen(false)}
        onIndexed={handleRepoIndexed}
      />

      <TelemetryModal
        open={telemetryOpen}
        isOfflineDemo={isOfflineDemo}
        offlineAnalyses={DEMO_PR_SCENARIOS}
        onClose={() => setTelemetryOpen(false)}
      />
    </div>
  );
}
