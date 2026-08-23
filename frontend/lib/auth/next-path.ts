/**
 * Where to go after signing in.
 *
 * `?next=` comes from the URL, which means anybody can put anything in it. A
 * redirect target that is not a path on this site is how a sign-in page becomes
 * a way to send people to an attacker's copy of it, so only a plain path is
 * accepted: no scheme, and no leading `//`, which the browser reads as
 * "another host" even though it looks relative.
 */
export function safeNextPath(next: string | string[] | undefined): string {
  const value = Array.isArray(next) ? next[0] : next;

  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}
