/**
 * Where to go after signing in.
 *
 * `?next=` comes from the URL, which means anybody can put anything in it. A
 * redirect target that is not a path on this site is how a sign-in page becomes
 * a way to send people to an attacker's copy of it.
 *
 * Checking the string's prefix is not enough: `/\evil.example` and
 * `/<tab>/evil.example` start with one slash, yet the browser reads both as
 * `//evil.example` -- a backslash counts as a slash in an http URL, and tabs and
 * newlines are dropped before parsing. So the value is resolved exactly the way
 * the router will resolve it, against a stand-in origin, and kept only if it
 * stayed there. What is returned is the resolved path, not the raw string, so
 * the router is handed the same thing that was checked.
 */
const HERE = "http://this-site.invalid";

export function safeNextPath(next: string | string[] | undefined): string {
  const value = Array.isArray(next) ? next[0] : next;
  if (!value || !value.startsWith("/")) return "/";

  let url: URL;
  try {
    url = new URL(value, HERE);
  } catch {
    return "/";
  }

  if (url.origin !== HERE) return "/";
  return url.pathname + url.search + url.hash;
}
