import { apiFetch } from "./client";

export type VideoStatus = "uploading" | "processing" | "ready" | "failed";

export interface VideoAsset {
  id: string;
  status: VideoStatus;
  duration_s: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  /** Playable manifest. Present once the transcode finished. */
  hls_url: string | null;
  /** Which transcript the instructor uploaded, if any. The file itself never
   * reaches the browser — only the chatbot reads it. */
  transcript_format: TranscriptFormat | null;
}

export type TranscriptFormat = "srt" | "txt";

/** Mirrors TRANSCRIPT_MAX_CHARS in backend/app/services/storage.py. */
export const TRANSCRIPT_MAX_CHARS = 1_000_000;

export interface TranscriptResult {
  format: TranscriptFormat;
  /** Characters the chatbot will read, after timings and tags are gone. */
  characters: number;
  /** True on a published course: the re-ingest is already queued. */
  ingest_queued: boolean;
}

export interface VideoUploadTicket {
  video_asset_id: string;
  upload_url: string;
  storage_key: string;
  expires_in: number;
  /** Must be sent back verbatim as the Content-Type of the PUT: it is signed. */
  content_type: string;
}

export interface VideoUploadRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
}

/** Ask the backend where to put a video. Does not move any bytes. */
export function createVideoUpload(
  accessToken: string,
  lessonId: string,
  input: VideoUploadRequest,
): Promise<VideoUploadTicket> {
  return apiFetch<VideoUploadTicket>(`/api/v1/lessons/${lessonId}/video`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

/** Tell the backend the bytes arrived, so the transcode can be queued. */
export function completeVideoUpload(
  accessToken: string,
  videoAssetId: string,
): Promise<VideoAsset> {
  return apiFetch<VideoAsset>(`/api/v1/video-assets/${videoAssetId}/complete`, {
    method: "POST",
    accessToken,
  });
}

/**
 * Run the transcode again on a video already in the bucket.
 *
 * Most failures are the bucket blinking or a worker being killed, not the
 * file — asking for half a gigabyte again would be the wrong answer.
 */
export function retryVideoTranscode(
  accessToken: string,
  videoAssetId: string,
): Promise<VideoAsset> {
  return apiFetch<VideoAsset>(`/api/v1/video-assets/${videoAssetId}/retry`, {
    method: "POST",
    accessToken,
  });
}

export function getVideoAsset(
  accessToken: string,
  videoAssetId: string,
): Promise<VideoAsset> {
  return apiFetch<VideoAsset>(`/api/v1/video-assets/${videoAssetId}`, { accessToken });
}

/**
 * Give a video its transcript, replacing any earlier one.
 *
 * The text goes through the backend rather than straight to the bucket like
 * the video does: a transcript is small, and the backend reads it before
 * keeping it — a file that is not UTF-8 is refused here instead of being
 * quoted back to students as gibberish.
 */
export function putTranscript(
  accessToken: string,
  lessonId: string,
  input: { filename: string; content: string },
): Promise<TranscriptResult> {
  return apiFetch<TranscriptResult>(`/api/v1/lessons/${lessonId}/transcript`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteTranscript(accessToken: string, lessonId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/lessons/${lessonId}/transcript`, {
    method: "DELETE",
    accessToken,
  });
}
