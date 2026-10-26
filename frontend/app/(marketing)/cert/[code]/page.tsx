import { Award, BadgeCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { CertificateShare } from "@/components/certificates/certificate-share";
import { Alert, AlertDescription } from "@/components/ui/alert";
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

/** "https://devpath-01.me/cert/…" as printed: the host and path, no scheme. */
function printedUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
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
    <div className="mx-auto flex max-w-245 flex-col gap-5 px-4 py-8 sm:py-10">
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

      <Alert variant="success" className="border border-success/30">
        <BadgeCheck aria-hidden />
        <AlertDescription className="text-body-sm sm:text-body">
          <strong className="font-semibold">Chứng chỉ hợp lệ.</strong> DevPath cấp ngày{" "}
          {formatDate(certificate.issued_at)} cho {certificate.recipient_name}, mã{" "}
          <span className="font-mono font-semibold">{certificate.display_code}</span>.
        </AlertDescription>
      </Alert>

      {/* The paper, laid out as the PDF is (A4 landscape) from `lg`; above a
          phone it simply flows. The double frame is the PDF's, in jade. */}
      <section
        aria-label="Nội dung chứng chỉ"
        className="rounded-xs border-[6px] border-jade-700 bg-card p-1.5 sm:border-8 sm:p-2.5 lg:aspect-[297/210]"
      >
        <div className="flex h-full flex-col items-center border border-jade-200 px-5 pt-7 pb-6 text-center sm:px-12 sm:pt-10 lg:px-18">
          <p className="text-h3 font-bold">
            Dev<span className="text-primary">Path</span>
          </p>
          <p className="mt-5 text-eyebrow tracking-[0.16em] text-muted-foreground sm:mt-7 sm:tracking-[0.3em] lg:mt-9">
            CERTIFICATE OF COMPLETION
          </p>
          <h1 className="mt-1.5 font-certificate text-h1 text-link sm:mt-2 sm:text-cert-title lg:text-display lg:font-semibold lg:tracking-normal">
            Chứng nhận hoàn thành
          </h1>
          <p className="mt-5 text-body-sm text-muted-foreground sm:mt-7 sm:text-body lg:mt-9">Trao cho</p>
          <p className="mt-1 max-w-full border-b border-border-strong px-4 pb-1.5 font-certificate text-h1 font-bold break-words sm:px-12 sm:pb-2 sm:text-[2.75rem] sm:leading-[3.625rem]">
            {certificate.recipient_name}
          </p>
          <p className="mt-5 text-body-sm text-muted-foreground sm:text-body lg:mt-7">
            đã hoàn thành toàn bộ khóa học
          </p>
          <p className="mt-1 text-h3 text-balance sm:text-h2">
            {certificate.course_slug ? (
              <Link
                href={`/khoa-hoc/${certificate.course_slug}`}
                className="underline-offset-4 hover:underline"
              >
                {certificate.course_title}
              </Link>
            ) : (
              certificate.course_title
            )}
          </p>

          {/* The PDF's footer: who and when on the left, the code on the
              right, and between them the seal -- a certificate is a reward. */}
          <div className="mt-8 grid w-full items-end gap-4 border-t pt-5 text-left sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:gap-6 sm:border-t-0 sm:pt-8 lg:mt-auto">
            <dl className="grid grid-cols-2 gap-2.5 text-caption sm:flex sm:flex-col">
              <div>
                <dt className="text-muted-foreground">Giảng viên</dt>
                <dd className="text-body-sm font-semibold sm:text-body">{certificate.instructor_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Ngày hoàn thành</dt>
                <dd className="text-body-sm font-semibold sm:text-body">{formatDate(certificate.issued_at)}</dd>
              </div>
            </dl>
            <span
              aria-hidden
              className="order-first flex size-18 flex-col items-center justify-center justify-self-center rounded-full border-2 border-reward-mark bg-reward-soft sm:order-none sm:size-22"
            >
              <Award className="size-6.5 text-reward-mark sm:size-8" strokeWidth={1.75} />
              <span className="text-[0.625rem] leading-3 font-bold tracking-[0.08em] text-reward-foreground">
                DEVPATH
              </span>
            </span>
            <dl className="flex flex-col gap-2.5 text-caption sm:text-right">
              <div>
                <dt className="text-muted-foreground">Mã chứng chỉ</dt>
                <dd className="font-mono text-body-sm font-semibold whitespace-nowrap sm:text-body">{certificate.display_code}</dd>
              </div>
              <div className="hidden sm:block">
                <dt className="text-muted-foreground">Xác thực tại</dt>
                <dd className="break-all text-muted-foreground">{printedUrl(certificate.verify_url)}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <CertificateShare
        code={certificate.code}
        pdfUrl={certificatePdfUrl(certificate.code)}
        pdfReady={certificate.pdf_ready}
      />
    </div>
  );
}
