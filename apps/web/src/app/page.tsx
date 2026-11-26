import { ArchRadarWorkspace } from "@/components/archradar-workspace";
import {
  fetchApiHealth,
  fetchRepositories,
  fetchRepositoryAnalyses,
  fetchRepositoryGraph,
  fetchRepositorySnapshots,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage(): Promise<React.JSX.Element> {
  const [initialHealth, reposRes] = await Promise.all([
    fetchApiHealth({ isServer: true }),
    fetchRepositories({ isServer: true }),
  ]);

  const initialRepos = reposRes.ok ? reposRes.data : [];
  const firstRepo = initialRepos[0];
  const [graphRes, analysesRes, snapshotsRes] = firstRepo
    ? await Promise.all([
        fetchRepositoryGraph(firstRepo.id, { isServer: true }),
        fetchRepositoryAnalyses(firstRepo.id, { isServer: true }),
        fetchRepositorySnapshots(firstRepo.id, { isServer: true }),
      ])
    : [null, null, null];

  return (
    <ArchRadarWorkspace
      initialHealth={initialHealth}
      initialRepos={initialRepos}
      initialGraph={graphRes && graphRes.ok ? graphRes.data : null}
      initialAnalyses={analysesRes && analysesRes.ok ? analysesRes.data : []}
      initialSnapshots={snapshotsRes && snapshotsRes.ok ? snapshotsRes.data : []}
    />
  );
}
