"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, FolderGit2, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { indexRepository } from "@/lib/api";

interface IndexRepoModalProps {
  open: boolean;
  onClose: () => void;
  onIndexed: (repositoryId: string) => Promise<void>;
}

const PROGRESS_STEPS = [
  "Fetching repository source tree (read-only)",
  "Running Tree-sitter AST parser across TS/JS/Python/Go/Rust/Java",
  "Resolving imports, degrees & persisting snapshot",
] as const;

export function IndexRepoModal({
  open,
  onClose,
  onIndexed,
}: IndexRepoModalProps): React.JSX.Element | null {
  const [sourceType, setSourceType] = useState<"github" | "local">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [branch, setBranch] = useState("");
  const [stepIdx, setStepIdx] = useState(0);
  const [isIndexing, setIsIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!isIndexing) return;
    setStepIdx(0);
    const t1 = window.setTimeout(() => setStepIdx(1), 650);
    const t2 = window.setTimeout(() => setStepIdx(2), 1400);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [isIndexing]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);
    setIsIndexing(true);

    const res = await indexRepository({
      repo_url: sourceType === "github" ? repoUrl.trim() : undefined,
      local_path: sourceType === "local" ? localPath.trim() : undefined,
      branch: branch.trim() || undefined,
    });

    if (!res.ok) {
      setIsIndexing(false);
      setError(res.error);
      return;
    }

    await onIndexed(res.data.repository_id);
    setIsIndexing(false);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <FolderGit2 className="h-5 w-5 text-amber-400" />
            <div>
              <h2 className="text-base font-semibold">Index Repository</h2>
              <p className="text-xs text-muted-foreground">
                Deterministic Tree-sitter parsing (zero code execution)
              </p>
            </div>
          </div>
          <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5 text-sm">
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={sourceType === "github" ? "default" : "outline"}
              onClick={() => setSourceType("github")}
            >
              GitHub Repo URL
            </Button>
            <Button
              type="button"
              size="sm"
              variant={sourceType === "local" ? "default" : "outline"}
              onClick={() => setSourceType("local")}
            >
              Local Directory Path
            </Button>
          </div>

          {sourceType === "github" ? (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300" htmlFor="repo-url-input">
                Public GitHub Repository URL
              </label>
              <input
                id="repo-url-input"
                required
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="w-full rounded-md border border-input bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-ring"
                placeholder="https://github.com/owner/repository"
              />
            </div>
          ) : (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300" htmlFor="local-path-input">
                Local Folder Path (on API host)
              </label>
              <input
                id="local-path-input"
                required
                value={localPath}
                onChange={(e) => setLocalPath(e.target.value)}
                className="w-full rounded-md border border-input bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:ring-2 focus:ring-ring"
                placeholder="C:\Users\User\Desktop\archradar"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300" htmlFor="branch-input">
              Branch (optional)
            </label>
            <input
              id="branch-input"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              className="w-full rounded-md border border-input bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-ring"
              placeholder="Defaults to repository default branch"
            />
          </div>

          {isIndexing && (
            <div className="space-y-2 rounded-lg border border-border bg-slate-950/80 p-3 text-xs">
              {PROGRESS_STEPS.map((label, idx) => (
                <div key={label} className="flex items-center gap-2">
                  {idx < stepIdx ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  ) : idx === stepIdx ? (
                    <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
                  ) : (
                    <span className="h-4 w-4 rounded-full border border-slate-700" />
                  )}
                  <span className={idx <= stepIdx ? "text-slate-100" : "text-slate-500"}>
                    {label}
                  </span>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isIndexing}>
              {isIndexing && <Loader2 className="h-4 w-4 animate-spin" />}
              {isIndexing ? "Indexing..." : "Index & Map Architecture"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
