export function formatUsdCents(cents: number): string {
  const dollars = (cents / 100).toFixed(2);
  return `$${dollars}`;
}
