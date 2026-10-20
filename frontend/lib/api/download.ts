import { apiResponse } from "./client";
import { filenameFrom } from "./filename";

/**
 * Fetch an authenticated file and hand it to the browser as a download.
 *
 * A plain `<a href>` cannot carry the bearer token, so the file is fetched
 * with it, turned into an object URL for the length of one click, and
 * released straight after.
 */
export async function downloadFile(
  path: string,
  accessToken: string,
  fallbackName: string,
): Promise<void> {
  const response = await apiResponse(path, { accessToken });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filenameFrom(response.headers.get("content-disposition"), fallbackName);
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    // Next tick: some browsers start reading the URL after `click` returns.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
