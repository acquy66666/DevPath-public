"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, TriangleAlert, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import type { Lesson } from "@/lib/api/curriculum";
import {
  completeVideoUpload,
  createVideoUpload,
  getVideoAsset,
  retryVideoTranscode,
  uploadToStorage,
  type VideoAsset,
} from "@/lib/api/video";
import { useAuth } from "@/lib/auth/auth-provider";

/** Mirrors ALLOWED_VIDEO_TYPES in backend/app/services/storage.py. */
const ACCEPTED = ["video/mp4", "video/quicktime", "video/x-matroska", "video/webm"];
const MAX_BYTES = 2 * 1024 * 1024 * 1024;

/** How often to ask whether the transcode finished. */
const POLL_MS = 4000;

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const parts = hours > 0 ? [hours, minutes, rest] : [minutes, rest];
  return parts.map((part) => String(part).padStart(2, "0")).join(":");
}

type Phase = "idle" | "signing" | "sending" | "finishing";

export function VideoUpload({ lesson }: { lesson: Lesson }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [percent, setPercent] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);

  const assetId = lesson.video?.id ?? null;

  // Only polls while there is something to wait for; `refetchInterval` returns
  // false the moment the answer stops changing.
  const poll = useQuery({
    queryKey: ["video-asset", assetId],
    queryFn: () => getVideoAsset(accessToken as string, assetId as string),
    enabled: assetId !== null && lesson.video?.status === "processing",
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? POLL_MS : false,
    initialData: lesson.video ?? undefined,
  });

  const asset: VideoAsset | null = poll.data ?? lesson.video;

  const upload = useMutation({
    mutationFn: async (file: File) => {
      setPhase("signing");
      const ticket = await createVideoUpload(accessToken as string, lesson.id, {
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });

      setPhase("sending");
      setPercent(0);
      await uploadToStorage(ticket, file, setPercent);

      setPhase("finishing");
      return completeVideoUpload(accessToken as string, ticket.video_asset_id);
    },
    onSettled: () => {
      setPhase("idle");
      if (fileInput.current) fileInput.current.value = "";
      // The lesson carries the asset, and the row above shows it too.
      queryClient.invalidateQueries({ queryKey: ["lesson", lesson.id] });
      queryClient.invalidateQueries({ queryKey: ["curriculum"] });
    },
  });

  const retry = useMutation({
    mutationFn: () => retryVideoTranscode(accessToken as string, assetId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lesson", lesson.id] });
      queryClient.invalidateQueries({ queryKey: ["video-asset", assetId] });
    },
  });

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!ACCEPTED.includes(file.type)) {
      setFileError("Định dạng chưa hỗ trợ. Dùng MP4, MOV, MKV hoặc WebM.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setFileError("Video tối đa 2 GB.");
      return;
    }

    setFileError(null);
    upload.mutate(file);
  }

  const busy = phase !== "idle";

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">Video bài giảng</p>
        {asset ? <StatusPill asset={asset} /> : null}
      </div>

      {fileError ? (
        <Alert variant="destructive">
          <AlertDescription>{fileError}</AlertDescription>
        </Alert>
      ) : null}

      {upload.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(upload.error)}</AlertDescription>
        </Alert>
      ) : null}

      {asset?.status === "failed" ? (
        <Alert variant="destructive">
          <AlertDescription className="space-y-2">
            <span className="block">
              Xử lý video thất bại: {asset.error_message ?? "không rõ nguyên nhân"}
            </span>
            <span className="block text-xs">
              Tệp vẫn còn trên kho lưu trữ. Nếu lỗi chỉ là trục trặc nhất thời thì xử lý
              lại là đủ, không cần tải lên lần nữa.
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => retry.mutate()}
              disabled={retry.isPending}
            >
              {retry.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Đang xếp hàng lại…
                </>
              ) : (
                "Xử lý lại"
              )}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {retry.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(retry.error)}</AlertDescription>
        </Alert>
      ) : null}

      {busy ? (
        <div className="space-y-2">
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-[width] duration-200"
              style={{ width: `${phase === "sending" ? percent : 100}%` }}
            />
          </div>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {phase === "signing"
              ? "Đang xin đường dẫn tải lên…"
              : phase === "sending"
                ? `Đang tải lên… ${percent}%`
                : "Đang bàn giao cho máy chủ xử lý…"}
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
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
          >
            <Upload aria-hidden />
            {asset ? "Thay video khác" : "Chọn video để tải lên"}
          </Button>
          <p className="text-xs text-muted-foreground">
            MP4, MOV, MKV hoặc WebM, tối đa 2 GB. Video được chuyển sang HLS để phát
            mượt trên mạng yếu.
          </p>
        </div>
      )}

      {asset?.status === "ready" ? (
        <p className="text-sm text-muted-foreground">
          {asset.duration_s !== null
            ? `Thời lượng ${formatDuration(asset.duration_s)}. `
            : null}
          {asset.hls_url ? (
            <a
              href={asset.hls_url}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-4"
            >
              Xem tệp manifest
            </a>
          ) : (
            "Chưa cấu hình đường dẫn công khai nên chưa phát được."
          )}
        </p>
      ) : null}
    </div>
  );
}

function StatusPill({ asset }: { asset: VideoAsset }) {
  if (asset.status === "ready") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <CheckCircle2 className="size-4" aria-hidden />
        Sẵn sàng
      </span>
    );
  }

  if (asset.status === "processing") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Đang xử lý…
      </span>
    );
  }

  if (asset.status === "failed") {
    return (
      <span className="flex items-center gap-1 text-xs text-destructive">
        <TriangleAlert className="size-4" aria-hidden />
        Thất bại
      </span>
    );
  }

  // `uploading` after a reload means the browser never confirmed the upload --
  // the tab was closed mid-transfer, most likely.
  return (
    <span className="text-xs text-muted-foreground">Chưa tải lên xong</span>
  );
}
