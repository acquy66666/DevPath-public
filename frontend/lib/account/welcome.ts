/**
 * The welcome page that follows sign-up, and the links that carry a visitor's
 * destination through sign-in and sign-up.
 *
 * Pure functions only (`npm test` runs them on bare Node). `next` here is
 * always a value that already went through `safeNextPath`.
 */

const WELCOME = "/chao-mung";

/**
 * What to call someone in a greeting. Vietnamese names put the given name
 * last ("Lê Thu Hà" → "Hà"). A name whose last word is not a word -- "Người
 * mua 08" -- is said whole rather than as "08".
 */
export function greetingName(fullName: string): string | null {
  const words = fullName.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const last = words[words.length - 1];
  return /\p{L}/u.test(last) ? last : words.join(" ");
}

/** Where the sign-up form sends a new account: the welcome page, holding on to `next`. */
export function afterSignUpPath(next: string): string {
  return next === "/" ? WELCOME : `${WELCOME}?next=${encodeURIComponent(next)}`;
}

/**
 * The sign-in ⇄ sign-up links. Someone sent to sign in from a course page who
 * turns out to need an account should still land back on that course.
 */
export function authHref(
  path: "/dang-nhap" | "/dang-ky",
  next: string,
  extra: { email?: string } = {},
): string {
  const params = new URLSearchParams();
  if (next !== "/") params.set("next", next);
  if (extra.email) params.set("email", extra.email);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** The course slug of a course page or of its learn page; null for anything else. */
export function courseSlugFromPath(next: string): string | null {
  const pathname = next.split(/[?#]/)[0];
  const match = /^\/(?:khoa-hoc|hoc)\/([^/]+)$/.exec(pathname);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface WelcomeAction {
  href: string;
  label: string;
}

/**
 * The welcome page's one main button. With nowhere in particular to go back
 * to, it opens the catalogue -- the home page is where they just came from.
 */
export function welcomeAction(next: string, courseTitle: string | null): WelcomeAction {
  if (next === "/") return { href: "/khoa-hoc", label: "Khám phá khóa học" };
  if (courseSlugFromPath(next)) {
    return {
      href: next,
      label: courseTitle ? `Quay lại “${courseTitle}”` : "Quay lại khóa học bạn đang xem",
    };
  }
  return { href: next, label: "Tiếp tục" };
}

/**
 * Sign-up leaves the new account's id in this tab's session storage; the
 * welcome page waves for it once and clears it. Opening `/chao-mung` later,
 * or as somebody else, gets a Naomi who is already standing there.
 */
export const welcomeMarker = {
  key: "devpath:just-signed-up",
  shouldWave(marked: string | null, userId: string): boolean {
    return marked !== null && marked === userId;
  },
};
