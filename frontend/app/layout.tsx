import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// "vietnamese" as well as "latin": without it every letter with a stacked mark
// (ồ, ễ, ậ) comes from a fallback font, mid-word.
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "vietnamese"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin", "vietnamese"],
});

export const metadata: Metadata = {
  // Every relative canonical and Open Graph URL below is resolved against this,
  // so a page never has to know the site's own address. Set explicitly rather
  // than left to Next's localhost guess, which it warns about at build time.
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: "DevPath — Học lập trình trực tuyến",
  description:
    "Nền tảng học lập trình với chấm bài tự động, gợi ý khóa học và trợ giảng AI.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="vi"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
