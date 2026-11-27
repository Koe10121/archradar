"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { verifyGeminiApiKey } from "@/lib/api";
import { isPlausibleGeminiKey, maskApiKey } from "@/lib/gemini-key";

interface GeminiKeyModalProps {
  open: boolean;
  currentKey: string;
  apiOnline: boolean;
  onSaveKey: (key: string) => void;
  onClearKey: () => void;
  onClose: () => void;
}

export function GeminiKeyModal({
  open,
  currentKey,
  apiOnline,
  onSaveKey,
  onClearKey,
  onClose,
}: GeminiKeyModalProps): React.JSX.Element | null {
  const [draftKey, setDraftKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraftKey("");
    setShowKey(false);
    setError(null);
    setSuccessMsg(null);
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  async function handleVerifyAndSave(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    const trimmed = draftKey.trim();
    if (!isPlausibleGeminiKey(trimmed)) {
      setError("Please paste a valid Gemini API key (20+ characters, no spaces).");
      return;
    }

    if (!apiOnline) {
      onSaveKey(trimmed);
      setDraftKey("");
      setSuccessMsg("Saved for this browser session (offline format check passed).");
      return;
    }

    setVerifying(true);
    const res = await verifyGeminiApiKey(trimmed);
    setVerifying(false);

    if (!res.ok) {
      setError(res.error);
      return;
    }

    onSaveKey(trimmed);
    setDraftKey("");
    setSuccessMsg(`Verified with Google (${res.data.model}) and saved for this session!`);
  }

  function handleClear(): void {
    onClearKey();
    setDraftKey("");
    setError(null);
    setSuccessMsg("Session key cleared from memory.");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <KeyRound className="h-5 w-5 text-emerald-400" />
            <div>
              <h2 className="text-base font-semibold">Protected Gemini AI Key (Optional)</h2>
              <p className="text-xs text-muted-foreground">
                Bring your own free Google AI Studio key for live AI PR risk reports
              </p>
            </div>
          </div>
          <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <form onSubmit={(e) => void handleVerifyAndSave(e)} className="space-y-4 p-5 text-sm">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-100">
            <div className="flex items-center gap-1.5 font-semibold text-emerald-300">
              <ShieldCheck className="h-4 w-4" />
              How your key is protected
            </div>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-emerald-100/90">
              <li>
                Stored in browser <code className="font-mono">sessionStorage</code> only —
                automatically wiped when you close this tab.
              </li>
              <li>
                Sent only over HTTPS via the <code className="font-mono">X-Gemini-Api-Key</code>{" "}
                header for your request.
              </li>
              <li>Never saved in Neon Postgres, never cached, and never written to server logs.</li>
            </ul>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-slate-950/60 px-3 py-2 text-xs">
            <div>
              <span className="text-muted-foreground">Need a free key? </span>
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-medium text-amber-300 hover:underline"
              >
                Get one free at Google AI Studio
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            {currentKey ? (
              <Badge variant="success">Active: {maskApiKey(currentKey)}</Badge>
            ) : (
              <Badge variant="secondary">Not set</Badge>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300" htmlFor="gemini-byok-input">
              Gemini API Key
            </label>
            <div className="relative">
              <input
                id="gemini-byok-input"
                type={showKey ? "text" : "password"}
                autoComplete="off"
                spellCheck={false}
                value={draftKey}
                onChange={(e) => setDraftKey(e.target.value)}
                className="w-full rounded-md border border-input bg-slate-950 py-2 pl-3 pr-10 font-mono text-xs text-slate-100 outline-none focus:ring-2 focus:ring-ring"
                placeholder="AIzaSy..."
              />
              <button
                type="button"
                aria-label={showKey ? "Hide API key" : "Show API key"}
                onClick={() => setShowKey((prev) => !prev)}
                className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-200"
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {error}
            </div>
          )}

          {successMsg && (
            <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
            <div>
              {currentKey && (
                <Button type="button" size="sm" variant="outline" onClick={handleClear}>
                  <Trash2 className="h-3.5 w-3.5 text-red-400" />
                  Clear Key
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Close
              </Button>
              <Button type="submit" disabled={verifying || !draftKey.trim()}>
                {verifying && <Loader2 className="h-4 w-4 animate-spin" />}
                {verifying ? "Verifying..." : "Verify & Save for Session"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
