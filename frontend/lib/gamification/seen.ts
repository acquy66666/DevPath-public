/**
 * What this browser has already shown, so Naomi reacts once per event rather
 * than on every visit: the streak day she lit the torch for, the rank last
 * seen on each board, a certificate just earned in this tab.
 *
 * A convenience, not a record: storage can be missing (private window,
 * blocked site data) or cleared, and then the worst case is one reaction too
 * many or none at all. Every access is wrapped for that reason.
 */

type Area = "local" | "session";

function area(which: Area): Storage | null {
  try {
    return which === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function readItem(which: Area, key: string): string | null {
  try {
    return area(which)?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function writeItem(which: Area, key: string, value: string): void {
  try {
    area(which)?.setItem(key, value);
  } catch {
    // Full or blocked: the next visit simply reacts again.
  }
}

export function removeItem(which: Area, key: string): void {
  try {
    area(which)?.removeItem(key);
  } catch {
    // Nothing to undo.
  }
}

/** JSON `StreakSeen` per account: two people on one computer each get their own reactions. */
export function streakSeenKey(userId: string): string {
  return `devpath:streak-seen:${userId}`;
}

/** The rank last seen, per account, board and period (a new week is a new board). */
export function rankSeenKey(userId: string, period: string, startsOn: string | null): string {
  return `devpath:rank-seen:${userId}:${period}:${startsOn ?? "all"}`;
}

/**
 * Set by the finished-course banner when the course was finished in this tab
 * and its "Xem chứng chỉ" is followed; read once by the certificate page.
 * Session storage: a certificate opened tomorrow is no longer news.
 */
export function certificateEarnedKey(code: string): string {
  return `devpath:cert-earned:${code}`;
}
