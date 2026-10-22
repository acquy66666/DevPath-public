"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUp,
  History,
  Loader2,
  RotateCcw,
  Sparkles,
  Square,
  SquarePen,
} from "lucide-react";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { ChatHistory } from "@/components/chat/chat-history";
import {
  ChatMarkdown,
  SourceList,
  type CitedLesson,
} from "@/components/chat/chat-markdown";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  askAssistant,
  createChatSession,
  deleteChatSession,
  listAllChatMessages,
  listChatSessions,
  QUESTION_MAX_CHARS,
  type ChatMessage,
  type ChatSource,
} from "@/lib/api/chat";
import { ApiError } from "@/lib/api/client";
import type { Curriculum } from "@/lib/api/curriculum";
import { apiErrorMessage, CHAT_MESSAGES } from "@/lib/api/error-messages";
import { formatRelativeTime } from "@/lib/format";

/**
 * A question still on its way: asked, not yet stored.
 *
 * The backend keeps a question only together with its finished answer, so
 * until `done` arrives this exists nowhere but here. `failed` and `stopped`
 * are the two ways it can end without being kept -- the page says so and
 * offers to ask again, rather than leaving half an answer that looks saved.
 */
interface LiveTurn {
  question: string;
  phase: "searching" | "writing" | "failed" | "stopped";
  /** The lessons this answer may cite. Null until the stream says. */
  sources: ChatSource[] | null;
  text: string;
  error: string | null;
}

type LessonIndex = Map<string, { title: string; sectionTitle: string }>;

const sessionsKey = (courseId: string) => ["chat-sessions", courseId] as const;
const messagesKey = (sessionId: string) => ["chat-messages", sessionId] as const;

function indexLessons(curriculum: Curriculum): LessonIndex {
  const index: LessonIndex = new Map();
  for (const section of curriculum.sections) {
    for (const lesson of section.lessons) {
      index.set(lesson.id, { title: lesson.title, sectionTitle: section.title });
    }
  }
  return index;
}

/** A stored answer's citations, named from the table of contents already on the page. */
function citedOf(message: ChatMessage, lessons: LessonIndex): CitedLesson[] {
  return message.citations.map(({ number, lesson_id }) => {
    const lesson = lessons.get(lesson_id);
    return {
      number,
      lessonId: lesson_id,
      title: lesson?.title ?? null,
      sectionTitle: lesson?.sectionTitle ?? null,
    };
  });
}

function citedFromSources(sources: ChatSource[]): CitedLesson[] {
  return sources.map((source) => ({
    number: source.number,
    lessonId: source.lesson_id,
    title: source.lesson_title,
    sectionTitle: source.section_title,
  }));
}

/**
 * The course assistant, beside the lesson.
 *
 * One conversation at a time, a new one by default: a question about this
 * lesson rarely belongs to yesterday's thread, and the old threads are one
 * click away. A conversation is only created on the server when its first
 * question is sent, so opening the panel costs nothing.
 *
 * Answers stream in. While one is being written the panel stays on it --
 * switching conversation is disabled rather than silently stopping the
 * answer; "Dừng" is the explicit way out. Following a source only changes
 * the lesson beside the panel, so it never interrupts anything.
 */
export function ChatPanel({
  courseId,
  accessToken,
  curriculum,
  currentLesson,
  onOpenLesson,
}: {
  courseId: string;
  accessToken: string;
  curriculum: Curriculum;
  currentLesson: { id: string; title: string } | null;
  onOpenLesson: (lessonId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [view, setView] = useState<"chat" | "history">("chat");
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<LiveTurn | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  // Whether the reader is at the bottom. Kept there as text arrives -- unless
  // they scrolled up to reread something, which the stream must not undo.
  const pinned = useRef(true);

  const busy = live !== null && (live.phase === "searching" || live.phase === "writing");
  const lessons = useMemo(() => indexLessons(curriculum), [curriculum]);

  const sessions = useInfiniteQuery({
    queryKey: sessionsKey(courseId),
    queryFn: ({ pageParam }) => listChatSessions(accessToken, courseId, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
  const allSessions = sessions.data?.pages.flatMap((page) => page.items) ?? [];

  // Never stale: every change to a conversation is made from this panel and
  // written into the cache as it happens. A refetch racing a finished answer
  // could otherwise land after it and wipe it off the screen.
  const messages = useQuery({
    queryKey: messagesKey(sessionId ?? ""),
    queryFn: () => listAllChatMessages(accessToken, sessionId as string),
    enabled: sessionId !== null,
    staleTime: Infinity,
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteChatSession(accessToken, id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: messagesKey(id) });
      if (id === sessionId) {
        setSessionId(null);
        setLive(null);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: sessionsKey(courseId) }),
  });

  // Leaving the page stops the answer: nobody is left to read it, and the
  // backend keeps nothing unfinished.
  useEffect(() => () => abort.current?.abort(), []);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && pinned.current) element.scrollTop = element.scrollHeight;
  }, [messages.data, live, view, sessionId]);

  function onScroll() {
    const element = scroller.current;
    if (!element) return;
    pinned.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
  }

  function openSession(id: string | null) {
    pinned.current = true;
    setSessionId(id);
    setLive(null);
    setView("chat");
  }

  async function send(question: string) {
    const text = question.trim();
    // The ref, not `busy`: two clicks inside one frame both see the same
    // render, and only the ref is already set by the time the second runs.
    if (text === "" || abort.current !== null) return;

    const controller = new AbortController();
    abort.current = controller;
    pinned.current = true;
    setDraft("");
    setLive({ question: text, phase: "searching", sources: null, text: "", error: null });
    setAnnouncement("Trợ giảng đang trả lời…");

    const end = (phase: "failed" | "stopped", error: string | null) => {
      setLive((turn) => turn && { ...turn, phase, error });
      setAnnouncement(error ?? "Đã dừng câu trả lời.");
    };

    let id = sessionId;
    try {
      if (id === null) {
        const created = await createChatSession(accessToken, courseId);
        id = created.id;
        queryClient.setQueryData<ChatMessage[]>(messagesKey(id), []);
        setSessionId(id);
      }
      const target = id;

      for await (const event of askAssistant(accessToken, target, text, controller.signal)) {
        switch (event.type) {
          case "sources":
            setLive((turn) => turn && { ...turn, sources: event.sources, phase: "writing" });
            break;
          case "delta":
            setLive((turn) => turn && { ...turn, text: turn.text + event.text });
            break;
          case "done": {
            // The stored pair takes the live turn's place. The question is
            // written here rather than fetched: `done` carries the answer
            // only, and the question's text is exactly what was sent.
            const asked: ChatMessage = {
              id: `asked-${event.message.id}`,
              role: "user",
              content: text,
              cited_lesson_ids: [],
              citations: [],
              created_at: event.message.created_at,
            };
            queryClient.setQueryData<ChatMessage[]>(messagesKey(target), (old) => [
              ...(old ?? []),
              asked,
              event.message,
            ]);
            setLive(null);
            setAnnouncement("Trợ giảng đã trả lời xong.");
            queryClient.invalidateQueries({ queryKey: sessionsKey(courseId) });
            break;
          }
          case "error":
            end("failed", event.message);
            break;
        }
      }
    } catch (error) {
      if (controller.signal.aborted) {
        end("stopped", null);
      } else {
        end("failed", apiErrorMessage(error, CHAT_MESSAGES));
        // Deleted from another tab: asking again should start a new one.
        if (error instanceof ApiError && error.code === "CHAT_SESSION_NOT_FOUND") {
          setSessionId(null);
          queryClient.invalidateQueries({ queryKey: sessionsKey(courseId) });
        }
      }
    } finally {
      if (abort.current === controller) abort.current = null;
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // `isComposing`: Enter also confirms a word in an input method, and that
    // Enter must not send a half-typed Vietnamese sentence.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(draft);
    }
  }

  const stored = sessionId === null ? [] : (messages.data ?? []);
  const loadingMessages = sessionId !== null && messages.isPending;
  const empty = !loadingMessages && !messages.isError && stored.length === 0 && live === null;
  const current = allSessions.find((session) => session.id === sessionId);
  const heading =
    view === "history"
      ? "Lịch sử trò chuyện"
      : sessionId === null
        ? "Cuộc trò chuyện mới"
        : (current?.title ?? live?.question ?? "Cuộc trò chuyện");

  return (
    // Sized for where the panel first appears -- about 13rem down, below the
    // site header, the course title and the tabs -- not for where it sits once
    // stuck to the top. Sized for the stuck position, the question box opened
    // below the fold, and the first thing a reader had to do was scroll.
    <section
      aria-label="Trợ giảng AI"
      className="flex h-[34rem] flex-col overflow-hidden rounded-lg border lg:h-[calc(100dvh-14rem)] lg:min-h-[28rem]"
    >
      <header className="flex items-center gap-1 border-b px-2 py-1.5">
        {view === "history" ? (
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Quay lại cuộc trò chuyện"
            onClick={() => setView("chat")}
          >
            <ArrowLeft aria-hidden />
          </Button>
        ) : (
          <Sparkles className="mx-1.5 size-4 shrink-0 text-primary" aria-hidden />
        )}
        <p className="min-w-0 flex-1 truncate text-sm font-medium" title={heading}>
          {heading}
        </p>
        <Button
          size="icon-sm"
          variant={view === "history" ? "secondary" : "ghost"}
          aria-label="Lịch sử trò chuyện"
          aria-pressed={view === "history"}
          title={busy ? "Đợi câu trả lời xong, hoặc bấm Dừng" : "Lịch sử trò chuyện"}
          disabled={busy}
          onClick={() => setView(view === "history" ? "chat" : "history")}
        >
          <History aria-hidden />
        </Button>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Cuộc trò chuyện mới"
          title={busy ? "Đợi câu trả lời xong, hoặc bấm Dừng" : "Cuộc trò chuyện mới"}
          disabled={busy || (sessionId === null && live === null && view === "chat")}
          onClick={() => openSession(null)}
        >
          <SquarePen aria-hidden />
        </Button>
      </header>

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      {view === "history" ? (
        <div className="flex-1 overflow-y-auto">
          {remove.isError ? (
            <Alert variant="destructive" className="m-2 w-auto">
              <AlertDescription>{apiErrorMessage(remove.error, CHAT_MESSAGES)}</AlertDescription>
            </Alert>
          ) : null}
          {sessions.isPending ? (
            <HistorySkeleton />
          ) : sessions.isError ? (
            <Alert variant="destructive" className="m-2 w-auto">
              <AlertDescription>{apiErrorMessage(sessions.error, CHAT_MESSAGES)}</AlertDescription>
            </Alert>
          ) : (
            <ChatHistory
              sessions={allSessions}
              currentId={sessionId}
              hasMore={sessions.hasNextPage}
              loadingMore={sessions.isFetchingNextPage}
              deletingId={remove.isPending ? (remove.variables ?? null) : null}
              onLoadMore={() => sessions.fetchNextPage()}
              onOpen={openSession}
              onDelete={(id) => remove.mutate(id)}
            />
          )}
        </div>
      ) : (
        <>
          <div ref={scroller} onScroll={onScroll} className="flex-1 overflow-y-auto px-3 py-4">
            {loadingMessages ? (
              <ConversationSkeleton />
            ) : messages.isError && sessionId !== null ? (
              <Alert variant="destructive">
                <AlertDescription className="space-y-2">
                  <p>{apiErrorMessage(messages.error, CHAT_MESSAGES)}</p>
                  <Button size="sm" variant="outline" onClick={() => openSession(null)}>
                    Cuộc trò chuyện mới
                  </Button>
                </AlertDescription>
              </Alert>
            ) : empty ? (
              <EmptyState
                currentLesson={currentLesson}
                recent={allSessions.filter((session) => session.title !== null).slice(0, 3)}
                total={sessions.data?.pages[0]?.total ?? 0}
                onAsk={(question) => void send(question)}
                onOpen={openSession}
                onShowAll={() => setView("history")}
              />
            ) : (
              <ol className="space-y-5">
                {stored.map((message) =>
                  message.role === "user" ? (
                    <Question key={message.id} text={message.content} />
                  ) : (
                    <li key={message.id}>
                      <Answer>
                        <ChatMarkdown
                          content={message.content}
                          cited={citedOf(message, lessons)}
                          onOpenLesson={onOpenLesson}
                        />
                        <SourceList
                          cited={citedOf(message, lessons)}
                          currentLessonId={currentLesson?.id ?? null}
                          onOpenLesson={onOpenLesson}
                        />
                      </Answer>
                    </li>
                  ),
                )}

                {live ? (
                  <>
                    <Question text={live.question} />
                    <li>
                      <Answer>
                        <LiveAnswer
                          turn={live}
                          onOpenLesson={onOpenLesson}
                          onRetry={() => void send(live.question)}
                        />
                      </Answer>
                    </li>
                  </>
                ) : null}
              </ol>
            )}
          </div>

          <form onSubmit={submit} className="space-y-1.5 border-t p-2">
            <div className="relative">
              <Textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Hỏi về nội dung khóa học…"
                aria-label="Câu hỏi cho trợ giảng AI"
                rows={2}
                maxLength={QUESTION_MAX_CHARS}
                className="max-h-40 min-h-16 resize-none pr-11 text-sm"
              />
              {busy ? (
                <Button
                  type="button"
                  size="icon-sm"
                  variant="secondary"
                  className="absolute right-2 bottom-2"
                  aria-label="Dừng câu trả lời"
                  title="Dừng — câu trả lời dở sẽ không được lưu"
                  onClick={() => abort.current?.abort()}
                >
                  <Square className="fill-current" aria-hidden />
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="icon-sm"
                  className="absolute right-2 bottom-2"
                  aria-label="Gửi câu hỏi"
                  disabled={draft.trim() === ""}
                >
                  <ArrowUp aria-hidden />
                </Button>
              )}
            </div>
            <p className="flex justify-between gap-2 px-1 text-[11px] text-muted-foreground">
              <span>AI có thể nhầm — bấm vào nguồn để đối chiếu với bài học.</span>
              {draft.length > QUESTION_MAX_CHARS - 200 ? (
                <span className="shrink-0 tabular-nums">
                  {draft.length}/{QUESTION_MAX_CHARS}
                </span>
              ) : null}
            </p>
          </form>
        </>
      )}
    </section>
  );
}

function Question({ text }: { text: string }) {
  return (
    <li className="flex justify-end">
      <p className="ml-8 rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm break-words whitespace-pre-wrap text-primary-foreground">
        {text}
      </p>
    </li>
  );
}

function Answer({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-2">{children}</div>
    </div>
  );
}

function LiveAnswer({
  turn,
  onOpenLesson,
  onRetry,
}: {
  turn: LiveTurn;
  onOpenLesson: (lessonId: string) => void;
  onRetry: () => void;
}) {
  const sources = turn.sources ?? [];

  return (
    <>
      {turn.phase === "searching" ? <Working label="Đang tra cứu tài liệu khóa học…" /> : null}
      {turn.phase === "writing" && turn.text === "" ? (
        <Working label="Đang soạn câu trả lời…" />
      ) : null}

      {turn.text !== "" ? (
        <ChatMarkdown
          content={turn.text}
          cited={citedFromSources(sources)}
          onOpenLesson={onOpenLesson}
        />
      ) : null}

      {turn.phase === "writing" && sources.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Đang đọc {sources.length} bài:{" "}
          {sources.map((source) => `“${source.lesson_title}”`).join(", ")}
        </p>
      ) : null}

      {turn.phase === "failed" || turn.phase === "stopped" ? (
        <div className="space-y-2 rounded-md border border-dashed p-2.5 text-sm">
          <p className={turn.phase === "failed" ? "text-destructive" : "text-muted-foreground"}>
            {turn.phase === "failed"
              ? turn.error
              : "Đã dừng. Câu hỏi và phần trả lời dở này không được lưu."}
          </p>
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RotateCcw aria-hidden />
            Hỏi lại
          </Button>
        </div>
      ) : null}
    </>
  );
}

function Working({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-3.5 animate-spin" aria-hidden />
      {label}
    </p>
  );
}

function EmptyState({
  currentLesson,
  recent,
  total,
  onAsk,
  onOpen,
  onShowAll,
}: {
  currentLesson: { id: string; title: string } | null;
  recent: { id: string; title: string | null; updated_at: string }[];
  total: number;
  onAsk: (question: string) => void;
  onOpen: (sessionId: string) => void;
  onShowAll: () => void;
}) {
  // Named after the lesson on screen: the assistant does not know which
  // lesson is open, so "bài này" would give the search nothing to go on.
  const suggestions = currentLesson
    ? [
        `Tóm tắt ý chính của bài “${currentLesson.title}”.`,
        `Giải thích lại bài “${currentLesson.title}” kèm một ví dụ đơn giản.`,
      ]
    : [];

  return (
    <div className="flex min-h-full flex-col justify-center gap-5">
      <div className="space-y-2 text-center">
        <span className="mx-auto flex size-10 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="size-5" aria-hidden />
        </span>
        <p className="font-medium">Hỏi trợ giảng AI về khóa học</p>
        <p className="text-sm text-pretty text-muted-foreground">
          Trợ giảng trả lời từ bài viết và lời giảng của chính khóa học này, kèm nguồn để
          bạn mở lại đúng bài. Câu hỏi ngoài phạm vi khóa học sẽ được từ chối.
        </p>
      </div>

      {suggestions.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Thử hỏi</p>
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onAsk(suggestion)}
              className="block w-full rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Tiếp tục trò chuyện</p>
          <ul className="space-y-1">
            {recent.map((session) => (
              <li key={session.id}>
                <button
                  type="button"
                  onClick={() => onOpen(session.id)}
                  className="flex w-full items-baseline gap-2 rounded-md px-3 py-1.5 text-left text-sm transition-colors hover:bg-muted"
                >
                  <span className="min-w-0 flex-1 truncate">{session.title}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(session.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {total > recent.length ? (
            <Button variant="link" size="sm" className="px-3" onClick={onShowAll}>
              Xem tất cả {total} cuộc trò chuyện
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ConversationSkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      <div className="ml-auto h-9 w-2/3 animate-pulse rounded-xl bg-muted" />
      <div className="space-y-2">
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-2 p-3" aria-hidden>
      {[0, 1, 2].map((row) => (
        <div key={row} className="h-10 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}
