/** No imports, so `node --test` can run it as it is. */

/**
 * The file name a download response asks for, reading the UTF-8 form first
 * (`filename*=UTF-8''...`) -- the plain `filename=` is the ASCII fallback the
 * backend writes for clients that cannot read the other one.
 */
export function filenameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      // Malformed escape -- fall through to the plain name.
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain ? plain[1].trim() : fallback;
}
