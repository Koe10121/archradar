export function recordSecurityEvent(eventName: string, actorId: string): void {
  if (!eventName || !actorId) {
    throw new Error("Invalid audit event");
  }
}
