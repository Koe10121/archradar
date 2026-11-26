"use client";

import React from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import {
  getFolderColor,
  type BlastTier,
  type LayoutDirection,
} from "@/lib/graph-layout";
import { type GraphNode } from "@/lib/schemas/repo";
import { cn } from "@/lib/utils";

export type DriftNodeStatus = "none" | "added" | "coupling_up" | "coupling_down" | "unchanged";

export type FileNodeData = {
  node: GraphNode;
  blastTier: BlastTier;
  driftStatus?: DriftNodeStatus;
  inDegreeDelta?: number;
  isSelected: boolean;
  isSearchMatch: boolean;
  isFlowHighlighted: boolean;
  direction: LayoutDirection;
};

export type FileFlowNode = Node<FileNodeData, "fileNode">;

function formatLanguageTag(language: string): string {
  const lower = language.toLowerCase();
  if (lower === "typescript") return "TS";
  if (lower === "javascript") return "JS";
  if (lower === "python") return "PY";
  if (lower === "go") return "GO";
  return lower.slice(0, 3).toUpperCase();
}

export const FileNode = React.memo(function FileNode({
  data,
}: NodeProps<FileFlowNode>): React.JSX.Element {
  const {
    node,
    blastTier,
    driftStatus = "none",
    inDegreeDelta = 0,
    isSelected,
    isSearchMatch,
    isFlowHighlighted,
    direction,
  } = data;

  const lastSlash = node.path.lastIndexOf("/");
  const fileName = lastSlash >= 0 ? node.path.slice(lastSlash + 1) : node.path;
  const dirName = lastSlash >= 0 ? node.path.slice(0, lastSlash) : "root";
  const folderColor = getFolderColor(node.module_group);

  const sourcePos = direction === "LR" ? Position.Right : Position.Bottom;
  const targetPos = direction === "LR" ? Position.Left : Position.Top;

  const blastClasses =
    blastTier === "direct"
      ? "ring-2 ring-[#F59E0B] border-[#F59E0B] bg-amber-950/60 shadow-[0_0_24px_rgba(245,158,11,0.28)]"
      : blastTier === "hop_1"
        ? "ring-2 ring-[#EF4444] border-[#EF4444] bg-red-950/55 shadow-[0_0_20px_rgba(239,68,68,0.24)]"
        : blastTier === "hop_2_plus"
          ? "ring-1 ring-[#FCA5A5] border-[#FCA5A5]/80 bg-red-950/30"
          : blastTier === "unaffected"
            ? "opacity-25"
            : "";

  const driftClasses =
    blastTier !== "none" || driftStatus === "none"
      ? ""
      : driftStatus === "added"
        ? "ring-2 ring-emerald-400 border-emerald-400 bg-emerald-950/55 shadow-[0_0_22px_rgba(16,185,129,0.28)]"
        : driftStatus === "coupling_up"
          ? "ring-1 ring-amber-400/80 border-amber-400/70 bg-amber-950/25"
          : driftStatus === "coupling_down"
            ? "ring-1 ring-sky-400/70 border-sky-400/60 bg-sky-950/20"
            : "opacity-45";

  return (
    <div
      className={cn(
        "relative w-[260px] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/95 px-3.5 py-2.5 text-slate-100 shadow-lg transition-all duration-200",
        blastClasses,
        driftClasses,
        isFlowHighlighted && "ring-2 ring-amber-300 opacity-100",
        isSearchMatch && "ring-2 ring-sky-400 opacity-100",
        isSelected && "ring-2 ring-white opacity-100"
      )}
    >
      <div className={cn("absolute inset-y-0 left-0 w-1", folderColor.bar)} />

      <Handle
        type="target"
        position={targetPos}
        className="!h-2.5 !w-2.5 !border-slate-950 !bg-slate-400"
      />

      <div className="flex items-start justify-between gap-2 pl-1.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-100" title={node.path}>
            {fileName}
          </p>
          <p className="truncate font-mono text-[11px] text-slate-400" title={dirName}>
            {dirName}
          </p>
        </div>

        <span className="shrink-0 rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-200">
          {formatLanguageTag(node.language)}
        </span>
      </div>

      <div className="mt-2.5 flex items-center justify-between gap-2 pl-1.5 text-[11px]">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "max-w-[105px] truncate rounded-full border px-2 py-0.5 text-[10px] font-medium",
              folderColor.badge
            )}
          >
            {node.module_group}
          </span>
          <span className="font-mono text-slate-400">{node.loc}L</span>
        </div>

        <div className="flex items-center gap-1">
          {blastTier === "direct" && (
            <span className="rounded bg-[#F59E0B]/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#F59E0B]">
              MOD
            </span>
          )}
          {blastTier === "hop_1" && (
            <span className="rounded bg-[#EF4444]/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#EF4444]">
              1-HOP
            </span>
          )}
          {blastTier === "hop_2_plus" && (
            <span className="rounded bg-[#FCA5A5]/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#FCA5A5]">
              2-3H
            </span>
          )}
          {blastTier === "none" && driftStatus === "added" && (
            <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
              NEW
            </span>
          )}
          {blastTier === "none" && inDegreeDelta !== 0 && driftStatus !== "added" && (
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                inDegreeDelta > 0
                  ? "bg-amber-500/20 text-amber-300"
                  : "bg-sky-500/20 text-sky-300"
              )}
            >
              {inDegreeDelta > 0 ? `+${inDegreeDelta}` : inDegreeDelta}
            </span>
          )}
          <span
            title={`In-degree: ${node.in_degree} files import this`}
            className={cn(
              "rounded px-1.5 py-0.5 font-mono text-[10px]",
              node.in_degree >= 3
                ? "bg-amber-500/20 text-amber-300"
                : "bg-slate-800 text-slate-300"
            )}
          >
            in:{node.in_degree}
          </span>
        </div>
      </div>

      <Handle
        type="source"
        position={sourcePos}
        className="!h-2.5 !w-2.5 !border-slate-950 !bg-amber-400"
      />
    </div>
  );
});
