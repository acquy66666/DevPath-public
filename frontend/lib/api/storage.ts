/**
 * Sending one file straight to the bucket.
 *
 * Every upload in this app has the same three steps — ask our API for a signed
 * URL, PUT the bytes to Cloudflare, tell our API it worked — so the middle step
 * lives here rather than once per feature. A lecture video and a profile
 * picture differ in size and in nothing else.
 */

/** The half of an upload ticket that describes the PUT itself. */
export interface UploadTicket {
  upload_url: string;
  /** Must be sent back verbatim as the Content-Type of the PUT: it is signed. */
  content_type: string;
}

export class UploadError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "UploadError";
  }
}

/**
 * PUT the file straight to the bucket.
 *
 * Not `apiFetch`: this request goes to Cloudflare, not to our API. It must
 * carry no cookie and no bearer token — the signature in the URL is the whole
 * authorization, and sending credentials to another origin is how they leak.
 *
 * XHR rather than fetch because fetch still cannot report upload progress, and
 * a 400 MB upload with no progress bar looks like a frozen page.
 */
export function uploadToStorage(
  ticket: UploadTicket,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", ticket.upload_url, true);
    request.setRequestHeader("Content-Type", ticket.content_type);

    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    });

    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        resolve();
        return;
      }
      reject(
        new UploadError(
          `Kho lưu trữ từ chối tệp (HTTP ${request.status}).`,
          request.status,
        ),
      );
    });

    request.addEventListener("error", () =>
      reject(
        new UploadError(
          "Không gửi được tệp lên kho lưu trữ. Kiểm tra mạng, hoặc cấu hình CORS của bucket.",
        ),
      ),
    );
    request.addEventListener("abort", () =>
      reject(new UploadError("Đã hủy tải lên.")),
    );

    request.send(file);
  });
}
