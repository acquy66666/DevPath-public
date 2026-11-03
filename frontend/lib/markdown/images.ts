/**
 * Which pictures a page written by one person shows to another.
 *
 * Markdown lets an author point an image at any address, and a browser that
 * draws it tells that address who is reading, from where, and when. An
 * instructor's article read by a class, or a student's question read by the
 * instructor, is exactly the place not to allow that. So a picture is drawn
 * only when it is served by this platform's own media storage; any other
 * address is shown as a link the reader may choose to open.
 *
 * Where the media storage lives:
 * - production: the site's own origin (`https://<DOMAIN>/devpath-media/…`,
 *   nginx in front of RustFS), which is `NEXT_PUBLIC_SITE_URL`;
 * - development: RustFS on `minio.localhost:9000` (infra/docker-compose.yml).
 * Moving the bucket to another host (R2 with its own domain) means adding
 * that origin here.
 */

/** The dev stack's storage service, as `R2_PUBLIC_BASE_URL` falls back to it. */
export const DEV_MEDIA_ORIGIN = "http://minio.localhost:9000";

/** Where an image placeholder points while its upload is still running. */
export const UPLOAD_PLACEHOLDER_PREFIX = "#dang-tai-anh-";

export function mediaOrigins(
  siteUrl: string | undefined = siteAddress(),
  production: boolean = process.env.NODE_ENV === "production",
): string[] {
  const origins: string[] = [];
  const site = originOf(siteUrl);
  if (site) origins.push(site);
  if (!production) origins.push(DEV_MEDIA_ORIGIN);
  return origins;
}

export type ImageSource =
  | { kind: "hosted"; src: string }
  | { kind: "uploading" }
  | { kind: "external"; href: string | null };

/**
 * What to do with one `![…](src)`.
 *
 * `external.href` is null when the address is not even a web link (a
 * `javascript:` or `data:` URL): such a thing is shown as text, never as a
 * link to click.
 */
export function classifyImage(src: string | undefined, origins: readonly string[]): ImageSource {
  if (!src) return { kind: "external", href: null };
  if (src.startsWith(UPLOAD_PLACEHOLDER_PREFIX)) return { kind: "uploading" };

  let url: URL;
  try {
    url = new URL(src);
  } catch {
    return { kind: "external", href: null };
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return { kind: "external", href: null };
  }
  if (origins.includes(url.origin)) return { kind: "hosted", src: url.href };
  return { kind: "external", href: url.href };
}

/**
 * The site's own address. In the browser that is the page's origin; reading
 * `NEXT_PUBLIC_SITE_URL` there would inline the domain into the browser
 * bundle, which the production image must not carry (CI: "Frontend image
 * carries the site URL, server side only"). Next replaces `typeof window`
 * at build time, so the server branch is dropped from browser chunks.
 */
function siteAddress(): string | undefined {
  if (typeof window !== "undefined") return window.location.origin;
  return process.env.NEXT_PUBLIC_SITE_URL;
}

function originOf(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

/** Mirrors LESSON_IMAGE_TYPES and MAX_LESSON_IMAGE_BYTES in backend/app/services/storage.py. */
export const LESSON_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
export const MAX_LESSON_IMAGE_BYTES = 5 * 1024 * 1024;

/** Why a file cannot go into an article, or null when it can. */
export function lessonImageProblem(file: { type: string; size: number }): string | null {
  if (!LESSON_IMAGE_TYPES.includes(file.type)) {
    return "Chỉ chèn được ảnh PNG, JPEG, WebP hoặc GIF.";
  }
  if (file.size > MAX_LESSON_IMAGE_BYTES) {
    return "Ảnh trong bài đọc tối đa 5 MB.";
  }
  return null;
}

/**
 * The description an uploaded file starts with: its name without the
 * extension, tidied. A pasted screenshot is called `image.png` by every
 * browser, which describes nothing -- that one starts as "Ảnh".
 */
export function defaultAltText(filename: string): string {
  const base = filename.replace(/\.[^./\\]+$/, "");
  const words = base.replace(/[_-]+/g, " ").replace(/[[\]()]/g, "").replace(/\s+/g, " ").trim();
  if (!words || /^image( \d+)?$/i.test(words)) return "Ảnh";
  return words.slice(0, 120);
}
