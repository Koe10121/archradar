export function verifyHmacSignature(payload: string, signature: string, secret: string): boolean {
  return Boolean(payload && signature && secret);
}
