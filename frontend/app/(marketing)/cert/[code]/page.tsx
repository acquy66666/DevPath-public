import { BadgeCheck, Download, Hourglass } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import {
  certificatePdfUrl,
  getCertificate,
  type Certificate,
} from "@/lib/api/certificates";
import { formatDate } from "@/lib/format";

// The name is the one thing on a certificate that has to come out right, and
// Vietnamese names stack two marks on one letter (ồ, ễ, ậ). `font-serif` falls
// back to Georgia on Windows, which has no such glyphs: Chrome then splits the
// letter into its base and a combining mark Georgia cannot place, and "Luồng"
// prints as "Luô`ng". Noto Serif, which has the Vietnamese subset: declared in
// app/fonts.css as `.font-certificate`, and fetched on this page only, since
// nothing else on the site is set in serif.
const CERTIFICATE_FONTS = [
  "/fonts/noto-serif-latin.woff2",
  "/fonts/noto-serif-vietnamese.woff2",
];

/**
 * The public page a certificate's QR code points at.
 *
 * Server-rendered, and checked before anything streams -- like the course
 * page, and for the same reason: a code that is not a certificate must answer
 * a real 404, not a 200 that happens to say "không tìm thấy". Somebody
 * verifying a certificate is asking exactly that question.
 *
 * Not indexed. Whoever holds the code may look; a search engine that learned
 * the name on it would be telling everyone else.
 */
const loadCertificate = cache(async (code: string): Promise<Certificate | null> => {
  try {
    return await getCertificate(code);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const certificate = await loadCertificate(code);
  if (certificate === null) {
    return { title: "Không tìm thấy chứng chỉ — DevPath", robots: { index: false } };
  }
  return {
    title: `Chứng chỉ của ${certificate.recipient_name} — DevPath`,
    description: `${certificate.recipient_name} đã hoàn thành khóa học “${certificate.course_title}” trên DevPath.`,
    robots: { index: false },
  };
}

export default async function CertificatePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const certificate = await loadCertificate(code);
  if (certificate === null) notFound();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      {CERTIFICATE_FONTS.map((href) => (
        <link
          key={href}
          rel="preload"
          href={href}
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
      ))}
      <div className="flex items-start gap-3 rounded-xl border border-emerald-600/30 bg-emerald-50 p-4 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
        <BadgeCheck className="mt-0.5 size-5 shrink-0" aria-hidden />
        <div>
          <p className="font-semibold">Chứng chỉ hợp lệ</p>
          <p className="text-sm">
            Do DevPath cấp ngày {formatDate(certificate.issued_at)}, mã{" "}
            <span className="font-mono font-medium">{certificate.display_code}</span>.
          </p>
        </div>
      </div>

      <section
        aria-label="Nội dung chứng chỉ"
        className="mt-6 rounded-2xl border-4 border-double border-primary/60 bg-card px-6 py-10 text-center sm:px-12"
      >
        <p className="text-sm font-semibold tracking-wide text-primary">DevPath</p>
        <p className="mt-6 text-xs tracking-[0.3em] text-muted-foreground">
          CERTIFICATE OF COMPLETION
        </p>
        <h1
          className="mt-2 font-certificate text-3xl font-semibold text-primary sm:text-4xl"
        >
          Chứng nhận hoàn thành
        </h1>
        <p className="mt-8 text-sm text-muted-foreground">Trao cho</p>
        <p
          className="mt-1 break-words font-certificate text-3xl font-bold sm:text-4xl"
        >
          {certificate.recipient_name}
        </p>
        <p className="mt-6 text-sm text-muted-foreground">đã hoàn thành toàn bộ khóa học</p>
        <p className="mt-1 text-xl font-semibold">
          {certificate.course_slug ? (
            <Link href={`/khoa-hoc/${certificate.course_slug}`} className="hover:underline">
              {certificate.course_title}
            </Link>
          ) : (
            certificate.course_title
          )}
        </p>

        <dl className="mt-10 grid gap-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Giảng viên</dt>
            <dd className="font-medium">{certificate.instructor_name}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Ngày hoàn thành</dt>
            <dd className="font-medium">{formatDate(certificate.issued_at)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Mã chứng chỉ</dt>
            <dd className="font-mono font-medium">{certificate.display_code}</dd>
          </div>
        </dl>
      </section>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {certificate.pdf_ready ? (
          <Button asChild>
            <a href={certificatePdfUrl(certificate.code)} target="_blank" rel="noopener">
              <Download aria-hidden />
              Tải chứng chỉ PDF
            </a>
          </Button>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Hourglass className="size-4" aria-hidden />
            Tệp PDF đang được tạo — tải lại trang sau ít phút.
          </p>
        )}
      </div>
    </div>
  );
}
