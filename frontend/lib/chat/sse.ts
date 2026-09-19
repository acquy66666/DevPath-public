/**
 * Reading server-sent events out of a `fetch` body.
 *
 * `EventSource` would do this for free, but it can only send a GET with no
 * body and no `Authorization` header -- and asking the assistant is a POST
 * carrying both. So the stream is read by hand: bytes to text, text split at
 * the blank line that ends each event.
 */

export interface SseFrame {
  event: string;
  data: string;
}

/** One event's lines, as the spec reads them. Null for a comment-only frame. */
export function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const data: string[] = [];

  for (const line of raw.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }

  return data.length === 0 ? null : { event, data: data.join("\n") };
}

/**
 * Every complete event in the stream, as it arrives.
 *
 * A frame is only handed out once its closing blank line has arrived, so a
 * JSON payload split across two network packets is never parsed half-read.
 * Leaving the loop early -- the reader stopped the answer -- cancels the
 * body, which closes the connection; the backend sees the disconnect and
 * stores nothing.
 */
export async function* readServerSentEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseFrame> {
  const reader = body.getReader();
  // `stream: true` keeps a Vietnamese letter split across two packets -- its
  // UTF-8 bytes arriving half in each -- from decoding as two broken ones.
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) return;

      // The backend ends lines with "\n". A "\r\n" from something in between
      // would otherwise hide every blank line, and no event would ever end.
      buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = parseFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (frame) yield frame;
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}
