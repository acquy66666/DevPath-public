import Link from "next/link";

import { BrandMark } from "@/components/layout/brand-mark";

const LINKS = [
  { href: "/khoa-hoc", label: "Khóa học" },
  { href: "/bang-xep-hang", label: "Bảng xếp hạng" },
  // The only way in for a visitor: the user menu offers it once signed in.
  { href: "/tro-thanh-giang-vien", label: "Trở thành giảng viên" },
  // Google's consent screen points here; keep it on every page.
  { href: "/chinh-sach-bao-mat", label: "Chính sách bảo mật" },
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t bg-card print:hidden">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
        <div className="min-w-0 space-y-1">
          <p className="text-lg font-bold">
            <BrandMark />
          </p>
          <p className="max-w-prose text-sm text-muted-foreground">
            Nền tảng học lập trình trực tuyến: chấm code tự động, gợi ý khóa học và trợ giảng AI.
          </p>
        </div>
        <nav aria-label="Chân trang" className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-xs text-muted-foreground transition-colors hover:text-foreground hover:underline hover:underline-offset-4"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="border-t">
        <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-muted-foreground">
          Next.js · FastAPI · PostgreSQL · Docker · {new Date().getFullYear()}
        </p>
      </div>
    </footer>
  );
}
