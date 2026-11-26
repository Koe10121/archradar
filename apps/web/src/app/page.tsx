import { GitBranch, Layers, Radar, ShieldCheck } from "lucide-react";

import { HealthStatusCard } from "@/components/health-status-card";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchApiHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

const PIPELINE_STEPS = [
  {
    title: "Tree-sitter AST Mapper",
    description:
      "Deterministic TypeScript, JavaScript, and Python import/export graph extraction.",
    phase: "Phase 1",
    icon: Layers,
  },
  {
    title: "Reverse-BFS Blast Radius",
    description:
      "Up to 3-hop downstream impact scoring with symbol-level precision filtering.",
    phase: "Phase 2",
    icon: GitBranch,
  },
  {
    title: "Grounded AI & Citation Gate",
    description:
      "Strict Pydantic/Zod outputs verifying every cited path against snapshot nodes.",
    phase: "Phase 2",
    icon: ShieldCheck,
  },
] as const;

export default async function HomePage(): Promise<React.JSX.Element> {
  const initialHealth = await fetchApiHealth({ isServer: true });

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-4 border-b border-border pb-8">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-400">
            <Radar className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-tight">ArchRadar</h1>
              <Badge>Phase 0 Bootstrap</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Living Architecture Mapper &amp; PR Blast-Radius Radar
            </p>
          </div>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Deterministic AST static analysis first, grounded LLM risk &amp; doc-drift
          reasoning second. Workspace infrastructure, FastAPI backend, SQLAlchemy schema,
          and Next.js 15 frontend are bootstrapped and wired end-to-end.
        </p>
      </header>

      <HealthStatusCard initialResult={initialHealth} />

      <section className="grid gap-4 md:grid-cols-3">
        {PIPELINE_STEPS.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.title}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Icon className="h-5 w-5 text-amber-400" />
                  <Badge variant="secondary">{step.phase}</Badge>
                </div>
                <CardTitle className="pt-2 text-base">{step.title}</CardTitle>
                <CardDescription>{step.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Ready for implementation in upcoming phase.
                </p>
              </CardContent>
            </Card>
          );
        })}
      </section>
    </main>
  );
}
