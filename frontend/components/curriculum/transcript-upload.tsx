"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Lesson } from "@/lib/api/curriculum";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  deleteTranscript,
  putTranscript,
  TRANSCRIPT_MAX_CHARS,
  type TranscriptResult,
} from "@/lib/api/video";
import { useAuth } from "@/lib/auth/auth-provider";

const ACCEPTED = [".srt", ".txt"];

/**
 * Before reading a file into memory at all. Vietnamese is up to three bytes a
 * character in UTF-8, so this sits above the backend's character limit; the
 * exact check is on the text once it is read.
 */
const MAX_BYTES = 4 * TRANSCRIPT_MAX_CHARS;

const numberFormat = new Intl.NumberFormat("vi-VN");

/**
 * The words of a video, for the AI teaching assistant.
 *
 * Students never see this file: the chatbot answers from it. So what the
 * instructor needs back is not a preview but proof it was read right — how
 * many characters survived, and when the chatbot will have them.
 */
export function TranscriptUpload({ lesson }: { lesson: Lesson }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [fileError, setFileError] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptResult | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const video = lesson.video;
  const format = video?.transcript_format ?? null;

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["lesson", lesson.id] });
    queryClient.invalidateQueries({ queryKey: ["curriculum"] });
  }

  const upload = useMutation({
    mutationFn: async (file: File) => {
      // The browser decodes as UTF-8. A file in another encoding comes out
      // with U+FFFD in it, which the backend recognises and refuses with a
      // sentence explaining how to re-save the file.
      const content = await file.text();
      if (content.length > TRANSCRIPT_MAX_CHARS) {
        throw new RangeError("too long");
      }
      return putTranscript(accessToken as string, lesson.id, {
        filename: file.name,
        content,
      });
    },
    onSuccess: (data) => {
      setResult(data);
      refresh();
    },
    onSettled: () => {
      if (fileInput.current) fileInput.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteTranscript(accessToken as string, lesson.id),
    onSuccess: () => {
      setConfirmingDelete(false);
      setResult(null);
      refresh();
    },
  });

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    const name = file.name.toLowerCase();
    if (!ACCEPTED.some((extension) => name.endsWith(extension))) {
      setFileError("Chỉ nhận tệp phụ đề .srt hoặc văn bản .txt.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setFileError("Tệp quá lớn để là một transcript.");
      return;
    }

    setFileError(null);
    setResult(null);
    upload.mutate(file);
  }

  const uploadError =
    upload.error instanceof RangeError
      ? `Tệp dài quá ${numberFormat.format(TRANSCRIPT_MAX_CHARS)} ký tự.`
      : upload.isError
        ? apiErrorMessage(upload.error)
        : null;

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">Transcript cho trợ giảng AI</p>
        {format ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <FileText className="size-4" aria-hidden />
            Đã có tệp .{format}
          </span>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        Chatbot trả lời học viên dựa trên lời giảng trong tệp này. Tệp phụ đề .srt hoặc văn
        bản .txt, lưu bằng bảng mã UTF-8. Học viên không tải được tệp này.
      </p>

      {!video ? (
        <p className="text-sm text-muted-foreground">
          Tải video lên trước, rồi mới gắn transcript cho nó.
        </p>
      ) : (
        <>
          {fileError ? (
            <Alert variant="destructive">
              <AlertDescription>{fileError}</AlertDescription>
            </Alert>
          ) : null}

          {uploadError ? (
            <Alert variant="destructive">
              <AlertDescription>{uploadError}</AlertDescription>
            </Alert>
          ) : null}

          {remove.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
            </Alert>
          ) : null}

          {result ? (
            <Alert>
              <AlertDescription>
                Đã nhận {numberFormat.format(result.characters)} ký tự lời giảng.{" "}
                {result.ingest_queued
                  ? "Khóa học đang xuất bản nên trợ giảng AI sẽ đọc lại trong ít phút."
                  : "Trợ giảng AI sẽ đọc được khi khóa học được xuất bản."}
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPTED.join(",")}
              onChange={handleFile}
              className="hidden"
              aria-hidden
              tabIndex={-1}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={upload.isPending || remove.isPending}
            >
              {upload.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Đang đọc tệp…
                </>
              ) : (
                <>
                  <Upload aria-hidden />
                  {format ? "Thay transcript khác" : "Tải transcript lên"}
                </>
              )}
            </Button>

            {format && !confirmingDelete ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setConfirmingDelete(true)}
                disabled={upload.isPending || remove.isPending}
              >
                Gỡ transcript
              </Button>
            ) : null}
          </div>

          {confirmingDelete ? (
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-destructive/5 px-3 py-2">
              <span className="text-sm">
                Gỡ transcript? Trợ giảng AI sẽ không trả lời được về video này nữa.
              </span>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                {remove.isPending ? (
                  <>
                    <Loader2 className="animate-spin" aria-hidden />
                    Đang gỡ…
                  </>
                ) : (
                  "Gỡ"
                )}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setConfirmingDelete(false)}
                disabled={remove.isPending}
              >
                Hủy
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
