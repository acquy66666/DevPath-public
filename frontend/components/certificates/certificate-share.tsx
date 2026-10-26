"use client";

import { Check, Download, Hourglass, Link2 } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Mascot } from "@/components/mascot/mascot";
import { Button } from "@/components/ui/button";
import { certificateEarnedKey, readItem, removeItem } from "@/lib/gamification/seen";

/**
 * Whether this tab has just earned the certificate: the finished-course
 * banner leaves a mark in session storage when its "Xem chứng chỉ" is
 * followed. Read once per page load and taken out of storage at once, so a
 * reload, a second tab or a link shared tomorrow is a still picture.
 * The answer is kept for this page load (a module-level map) so every render
 * agrees with the first; leaving the page spends it.
 */
const earned = new Map<string, boolean>();
const leaving = new Map<string, number>();

function claim(code: string): boolean {
  let value = earned.get(code);
  if (value === undefined) {
    const key = certificateEarnedKey(code);
    value = readItem("session", key) !== null;
    if (value) removeItem("session", key);
    earned.set(code, value);
  }
  return value;
}

const never = () => () => {};

/**
 * Under the certificate: Naomi in her cap, the PDF and the link.
 *
 * Naomi reacts once, and only for the learner who has just earned it in this
 * tab (reaction map: `graduate`); anyone else opening the link -- a recruiter
 * checking it -- sees her standing still. The server renders her still, and
 * the browser decides after hydration.
 *
 * One primary button: the PDF while it exists, else copying the link.
 */
export function CertificateShare({
  code,
  pdfUrl,
  pdfReady,
}: {
  code: string;
  pdfUrl: string;
  pdfReady: boolean;
}) {
  const fresh = useSyncExternalStore(never, () => claim(code), () => false);
  // Leaving the page spends the reaction. Deferred a tick: React's development
  // check unmounts and remounts every effect at once, and that is not leaving.
  useEffect(() => {
    window.clearTimeout(leaving.get(code));
    return () => void leaving.set(code, window.setTimeout(() => earned.set(code, false), 0));
  }, [code]);

  const [copied, setCopied] = useState<"yes" | "failed" | null>(null);
  const reset = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(reset.current), []);

  async function copy() {
    // The page itself, without whatever query or hash it was opened with.
    const url = `${window.location.origin}${window.location.pathname}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied("yes");
    } catch {
      setCopied("failed");
    }
    window.clearTimeout(reset.current);
    reset.current = window.setTimeout(() => setCopied(null), 3000);
  }

  return (
    <section aria-label="Chia sẻ chứng chỉ" className="@container rounded-lg border bg-card p-4">
      <div className="flex flex-col gap-4 @2xl:flex-row @2xl:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-3 sm:gap-5">
        <Mascot mood="graduate" event={fresh ? code : null} className="size-18 sm:size-24" />
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-body-sm text-muted-foreground sm:text-body">
            Ai có đường dẫn này đều kiểm tra được chứng chỉ. Mã QR trên bản PDF cũng trỏ về đúng trang
            này.
          </p>
          {pdfReady ? null : (
            <p className="flex items-center gap-1.5 text-body-sm text-muted-foreground">
              <Hourglass className="size-4 shrink-0" aria-hidden />
              Tệp PDF đang được tạo. Tải lại trang sau ít phút.
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-end @2xl:shrink-0">
        {pdfReady ? (
          <Button asChild className="h-11 sm:h-10">
            <a href={pdfUrl} target="_blank" rel="noopener">
              <Download aria-hidden />
              Tải chứng chỉ PDF
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          variant={pdfReady ? "outline" : "default"}
          className="h-11 sm:h-10"
          onClick={copy}
        >
          {copied === "yes" ? <Check aria-hidden /> : <Link2 aria-hidden />}
          {copied === "yes" ? "Đã sao chép" : "Sao chép liên kết"}
        </Button>
      </div>
      </div>
      <p aria-live="polite" className="sr-only">
        {copied === "yes" ? "Đã sao chép liên kết của chứng chỉ." : ""}
      </p>
      {copied === "failed" ? (
        <p role="alert" className="mt-3 text-body-sm text-destructive-text">
          Không sao chép được. Hãy sao chép địa chỉ trên thanh trình duyệt.
        </p>
      ) : null}
    </section>
  );
}
