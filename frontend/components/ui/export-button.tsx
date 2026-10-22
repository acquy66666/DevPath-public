"use client";

import { FileSpreadsheet, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { downloadFile } from "@/lib/api/download";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * "Xuất Excel": downloads the page's `export.xlsx` twin.
 *
 * The workbook is built on the server from the same service call the page
 * reads, so it never disagrees with the screen. A failure is said in words
 * next to the button rather than swallowed.
 */
export function ExportButton({
  path,
  filename,
  label = "Xuất Excel",
  size = "sm",
}: {
  path: string;
  /** Used only if the server does not name the file. */
  filename: string;
  label?: string;
  size?: "sm" | "default";
}) {
  const { accessToken } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    if (!accessToken) return;
    setBusy(true);
    setError(null);
    try {
      await downloadFile(path, accessToken, filename);
    } catch (caught) {
      setError(apiErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        size={size}
        onClick={download}
        disabled={busy || !accessToken}
      >
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : <FileSpreadsheet aria-hidden />}
        {busy ? "Đang xuất…" : label}
      </Button>
      {error ? (
        <span role="alert" className="text-xs text-destructive-text">
          {error}
        </span>
      ) : null}
    </span>
  );
}
