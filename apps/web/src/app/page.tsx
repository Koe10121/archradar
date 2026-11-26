import { ArchRadarWorkspace } from "@/components/archradar-workspace";
import {
  fetchApiHealth,
  fetchRepositories,
  fetchRepositoryGraph,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage(): Promise<React.JSX.Element> {
  const [initialHealth, reposRes] = await Promise.all([
    fetchApiHealth({ isServer: true }),
    fetchRepositories({ isServer: true }),
  ]);

  const initialRepos = reposRes.ok ? reposRes.data : [];
  const firstRepo = initialRepos[0];
  const graphRes = firstRepo
    ? await fetchRepositoryGraph(firstRepo.id, { isServer: true })
    : null;

  return (
    <ArchRadarWorkspace
      initialHealth={initialHealth}
      initialRepos={initialRepos}
      initialGraph={graphRes && graphRes.ok ? graphRes.data : null}
    />
  );
}
