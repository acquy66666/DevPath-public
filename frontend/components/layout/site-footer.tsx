import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t print:hidden">
      <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>DevPath — nền tảng học lập trình trực tuyến</p>
        <p>
          <Link href="/chinh-sach-bao-mat" className="hover:text-foreground hover:underline">
            Chính sách bảo mật
          </Link>
          {" · "}Next.js · FastAPI · PostgreSQL · Docker · {new Date().getFullYear()}
        </p>
      </div>
    </footer>
  );
}
