import { readServerSentEvents } from "@/lib/chat/sse";

import { apiFetch, apiResponse } from "./client";
import type { Page } from "./courses";

/**
 * The course assistant. Types mirror `backend/app/schemas/chat.py`.
 *
 * Asking is the one call that does not answer with JSON: the answer arrives
 * as server-sent events while the model writes it (see `askAssistant`).
 */

/** Mirrors `QUESTION_MAX_CHARS`. The backend refuses longer with a 422. */
export const QUESTION_MAX_CHARS = 2000;

export interface ChatSession {
  id: string;
  course_id: string;
  /** The first question, cut to fit. Null until one has been answered. */
  title: string | null;
  created_at: string;
  /** When the last answer finished -- the list is sorted by it. */
  updated_at: string;
}

/** `[number]` in a stored answer is this lesson. */
export interface ChatCitation {
  number: number;
  lesson_id: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Cited lessons in order of first mention. Empty for a question. */
  cited_lesson_ids: string[];
  /** The same lessons keyed by the number the text uses for them. */
  citations: ChatCitation[];
  created_at: string;
}

/** A lesson the answer being written may cite as `[number]`. */
export interface ChatSource {
  number: number;
  lesson_id: string;
  lesson_title: string;
  section_title: string;
  /** Cosine similarity of its best passage to the question, 0..1. */
  score: number;
}

/**
 * One event of an answer, in the order they come: `sources` once, `delta`
 * any number of times, then exactly one of `done` or `error`.
 */
export type ChatStreamEvent =
  | { type: "sources"; sources: ChatSource[] }
  | { type: "delta"; text: string }
  | { type: "done"; message: ChatMessage; cited_numbers: number[] }
  | { type: "error"; code: string; message: string };

/**
 * What the page shows when the stream stops without saying how it ended --
 * the connection dropped, or a proxy gave up on it. The backend stores an
 * answer only once it is complete, so nothing was kept either way.
 */
export const STREAM_CUT_MESSAGE =
  "Mất kết nối giữa chừng nên câu trả lời chưa được lưu. Hỏi lại giúp mình nhé.";

export function createChatSession(
  accessToken: string,
  courseId: string,
): Promise<ChatSession> {
  return apiFetch<ChatSession>(`/api/v1/courses/${courseId}/chat-sessions`, {
    method: "POST",
    accessToken,
  });
}

export function listChatSessions(
  accessToken: string,
  courseId: string,
  page = 1,
  pageSize = 20,
): Promise<Page<ChatSession>> {
  return apiFetch<Page<ChatSession>>(
    `/api/v1/courses/${courseId}/chat-sessions?page=${page}&page_size=${pageSize}`,
    { accessToken },
  );
}

/**
 * A whole conversation, oldest message first.
 *
 * Read page by page until all of it is here. A chat is read as one scroll,
 * and the hourly question limit keeps even a long one to a few pages.
 */
export async function listAllChatMessages(
  accessToken: string,
  sessionId: string,
): Promise<ChatMessage[]> {
  const pageSize = 100;
  const messages: ChatMessage[] = [];

  for (let page = 1; ; page++) {
    const batch = await apiFetch<Page<ChatMessage>>(
      `/api/v1/chat-sessions/${sessionId}/messages?page=${page}&page_size=${pageSize}`,
      { accessToken },
    );
    messages.push(...batch.items);
    if (batch.items.length < pageSize || messages.length >= batch.total) {
      return messages;
    }
  }
}

export function deleteChatSession(accessToken: string, sessionId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/chat-sessions/${sessionId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * Ask, and receive the answer as it is written.
 *
 * Refusals that happen before the answer starts -- not enrolled, asking too
 * fast, the model unreachable -- throw `ApiError` like any other call. Once
 * the stream has begun, a failure is an `error` event instead, and a stream
 * that simply stops becomes one too, so the caller always sees an ending.
 *
 * Aborting `signal` stops the answer. The backend then stores nothing: a
 * question is only kept together with its complete answer.
 */
export async function* askAssistant(
  accessToken: string,
  sessionId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await apiResponse(`/api/v1/chat-sessions/${sessionId}/messages`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ content }),
    headers: { Accept: "text/event-stream" },
    signal,
  });

  if (response.body === null) {
    yield { type: "error", code: "STREAM_CUT", message: STREAM_CUT_MESSAGE };
    return;
  }

  for await (const frame of readServerSentEvents(response.body)) {
    const payload = JSON.parse(frame.data);

    switch (frame.event) {
      case "sources":
        yield { type: "sources", sources: payload.sources };
        break;
      case "delta":
        yield { type: "delta", text: payload.text };
        break;
      case "done":
        yield {
          type: "done",
          message: payload.message,
          cited_numbers: payload.cited_numbers,
        };
        return;
      case "error":
        yield { type: "error", code: payload.code, message: payload.message };
        return;
    }
  }

  yield { type: "error", code: "STREAM_CUT", message: STREAM_CUT_MESSAGE };
}
