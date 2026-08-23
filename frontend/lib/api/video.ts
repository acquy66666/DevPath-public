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
