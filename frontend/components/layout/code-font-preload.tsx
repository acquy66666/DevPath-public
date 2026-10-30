/**
 * Asks for the code font (Geist Mono, its ASCII part) alongside the stylesheet, on the
 * pages that show it in their first screen: the home page's graded
 * submission, and the course covers ("{}", "</>") on the catalogue and a
 * course's own page -- ASCII only, hence the 14 KB ASCII file of
 * scripts/split-mono-ascii.py rather than the 23 KB latin one.
 *
 * Without it the browser only finds the font inside the CSS, after the CSS
 * has arrived: one more round trip before that text can settle, which is
 * what kept these pages' Largest Contentful Paint over 2.5 s on a slow phone
 * (Phase 7 performance task, docs/report/assets/phase-7/performance.md).
 * Pages without code in view do not get it: 14 KB they would not use.
 *
 * React hoists the <link> into <head>, as it does for the root layout's.
 */
export function CodeFontPreload() {
  return (
    <link
      rel="preload"
      href="/fonts/geist-mono-ascii.woff2"
      as="font"
      type="font/woff2"
      crossOrigin="anonymous"
    />
  );
}
