"use client";

import "./fonts.css";
import "./globals.css";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * When the root layout itself throws (the providers, say), `app/error.tsx`
 * cannot help: it lives inside that layout. Next then renders this file in
 * place of the whole document -- its own <html> and <body>, and its own copy
 * of the styles, which the root layout would otherwise have brought. Without
 * it the visitor got Next's built-in page, in English.
 *
 * No link home: home goes through the same root layout. Retrying fetches the
 * page again, which is the one thing that can fix it.
 */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <title>Lỗi hệ thống — DevPath</title>
        <main className="flex flex-1 items-center">
          <StatePanel
            mood="sorry"
            title="DevPath đang gặp lỗi"
            detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
            actions={<Button onClick={retry}>Thử lại</Button>}
          >
            Lỗi phía hệ thống, không phải do bạn. Thử lại sau ít phút.
          </StatePanel>
        </main>
      </body>
    </html>
  );
}
