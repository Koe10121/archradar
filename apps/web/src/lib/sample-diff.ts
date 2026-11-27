import { type GraphNode, type GraphResponse } from "@/lib/schemas/repo";

function selectPrimaryNode(nodes: GraphNode[]): GraphNode | null {
  if (nodes.length === 0) return null;
  const sorted = [...nodes].sort(
    (a, b) => b.in_degree - a.in_degree || a.path.localeCompare(b.path)
  );
  return sorted[0] ?? null;
}

function buildLanguageSampleHunk(node: GraphNode): string {
  const symbol = node.exports[0]?.name;
  const lang = node.language.toLowerCase();

  if (lang === "python") {
    const fnName = symbol ?? "process_request";
    return [
      "@@ -1,2 +1,2 @@",
      `-def ${fnName}(payload: dict[str, object]) -> bool:`,
      `+def ${fnName}(payload: dict[str, object], strict: bool = True) -> bool:`,
      "     return bool(payload)",
    ].join("\n");
  }

  if (lang === "go") {
    const fnName = symbol ?? "HandleRequest";
    return [
      "@@ -1,3 +1,3 @@",
      `-func ${fnName}(input string) error {`,
      `+func ${fnName}(input string, strict bool) error {`,
      " \treturn nil",
      " }",
    ].join("\n");
  }

  if (lang === "rust") {
    const fnName = symbol ?? "execute";
    return [
      "@@ -1,3 +1,3 @@",
      `-pub fn ${fnName}(input: &str) -> bool {`,
      `+pub fn ${fnName}(input: &str, strict: bool) -> bool {`,
      "     !input.is_empty()",
      " }",
    ].join("\n");
  }

  if (lang === "java") {
    const methodName = symbol ?? "execute";
    return [
      "@@ -1,3 +1,3 @@",
      `-    public boolean ${methodName}(String input) {`,
      `+    public boolean ${methodName}(String input, boolean strict) {`,
      "         return input != null;",
      "     }",
    ].join("\n");
  }

  const fnName = symbol ?? "handleRequest";
  return [
    "@@ -1,3 +1,3 @@",
    `-export function ${fnName}(input: string): boolean {`,
    `+export function ${fnName}(input: string, strict: boolean): boolean {`,
    "   return Boolean(input);",
    " }",
  ].join("\n");
}

export function buildSampleDiffForGraph(graph: GraphResponse): {
  title: string;
  diff: string;
} {
  const target = selectPrimaryNode(graph.nodes);
  if (!target) {
    return {
      title: "Sample PR Analysis",
      diff: "",
    };
  }

  const symbolLabel = target.exports[0]?.name ?? target.path.split("/").pop() ?? target.path;
  const hunk = buildLanguageSampleHunk(target);

  return {
    title: `Update ${symbolLabel} signature in ${target.path}`,
    diff: [
      `diff --git a/${target.path} b/${target.path}`,
      `--- a/${target.path}`,
      `+++ b/${target.path}`,
      hunk,
    ].join("\n"),
  };
}
