import type { Metadata } from "next";
import "./fonts.css";
import "./globals.css";
import { Providers } from "./providers";

// Self-hosted, not next/font/google: see app/fonts.css. Every page shows
// Vietnamese, so both of these are wanted before first paint -- without the
// vietnamese subset each letter with a stacked mark (ồ, ễ, ậ) would come
// from the fallback font, mid-word.
const PRELOADED_FONTS = ["/fonts/lexend-latin.woff2", "/fonts/lexend-vietnamese.woff2"];

export const metadata: Metadata = {
  // Every relative canonical and Open Graph URL below is resolved against this,
  // so a page never has to know the site's own address. Set explicitly rather
  // than left to Next's localhost guess, which it warns about at build time.
  // Inlined by `next build`; the production image refuses to build without it
  // (frontend/Dockerfile), so the localhost fallback is for development only.
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: "DevPath — Học lập trình trực tuyến",
  description:
    "Nền tảng học lập trình với chấm bài tự động, gợi ý khóa học và trợ giảng AI.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        {/* React hoists these into <head>. ReactDOM.preload() from a server
            component only reached the RSC payload, not the HTML. */}
        {PRELOADED_FONTS.map((href) => (
          <link
            key={href}
            rel="preload"
            href={href}
            as="font"
            type="font/woff2"
            crossOrigin="anonymous"
          />
        ))}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
