export async function loadPlugin(name: string): Promise<unknown> {
  const staticMod = await import("./plugin");
  const legacyMod = require("./legacy");
  if (name === "computed") {
    return import(`./plugins/${name}`);
  }
  return { staticMod, legacyMod };
}
