"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUp,
  Check,
  History,
  Info,
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
import { Mascot } from "@/components/mascot/mascot";
import { Skeleton } from "@/components/ui/skeleton";
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
import { assistantHeader, isRefusal, readingChips } from "@/lib/chat/assistant-state";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

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
  // What Naomi in the header last reacted to: the question being asked, then
  // the answer that came back. Cleared when a conversation is opened from
  // the history, where an old answer is a still picture.
  const [reaction, setReaction] = useState<string | null>(null);
  const questionCount = useRef(0);

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
    setReaction(null);
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
    questionCount.current += 1;
    setReaction(`asked-${questionCount.current}`);

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
            setReaction(event.message.id);
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
  const lastAnswer = [...stored].reverse().find((message) => message.role === "assistant") ?? null;
  const header = assistantHeader({
    live: live && { phase: live.phase, sources: live.sources?.length ?? 0 },
    lastAnswer: lastAnswer && {
      id: lastAnswer.id,
      content: lastAnswer.content,
      citations: lastAnswer.citations.length,
    },
  });

  return (
    // Sized for where the panel first appears -- below the site header, the
    // course strip and the tabs -- not for where it sits once stuck to the
    // top. Sized for the stuck position, the question box opened below the
    // fold, and the first thing a reader had to do was scroll.
    <section
      aria-label="Trợ giảng AI"
      className="flex h-[36rem] flex-col overflow-hidden rounded-lg border bg-card lg:h-[calc(100dvh-16rem)] lg:min-h-[30rem]"
    >
      {view === "history" ? (
        <header className="flex min-h-16 items-center gap-2 border-b p-2">
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Quay lại cuộc trò chuyện"
            onClick={() => setView("chat")}
          >
            <ArrowLeft aria-hidden />
          </Button>
          <p className="min-w-0 flex-1 text-title">Lịch sử trò chuyện</p>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Cuộc trò chuyện mới"
            title="Cuộc trò chuyện mới"
            onClick={() => openSession(null)}
          >
            <SquarePen aria-hidden />
          </Button>
        </header>
      ) : (
        <header className="flex items-center gap-3 border-b py-2 pr-2 pl-3">
          {/* The assistant's face: thinking while it looks things up and
              writes, holding its book once the answer cites the course. */}
          <Mascot mood={header.mood} size="sm" event={reaction} />
          <div className="flex min-w-0 flex-1 flex-col">
            <p className="text-title">Trợ giảng AI</p>
            <p className="truncate text-caption text-muted-foreground">{header.status}</p>
          </div>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Lịch sử trò chuyện"
            title={busy ? "Đợi câu trả lời xong, hoặc bấm Dừng" : "Lịch sử trò chuyện"}
            disabled={busy}
            onClick={() => setView("history")}
          >
            <History aria-hidden />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Cuộc trò chuyện mới"
            title={busy ? "Đợi câu trả lời xong, hoặc bấm Dừng" : "Cuộc trò chuyện mới"}
            disabled={busy || (sessionId === null && live === null)}
            onClick={() => openSession(null)}
          >
            <SquarePen aria-hidden />
          </Button>
        </header>
      )}

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
          <div ref={scroller} onScroll={onScroll} className="flex-1 overflow-y-auto p-4">
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
              <ol className="flex flex-col gap-4">
                {stored.map((message) =>
                  message.role === "user" ? (
                    <Question key={message.id} text={message.content} />
                  ) : (
                    <li key={message.id} className="flex flex-col gap-3">
                      {message.citations.length === 0 && isRefusal(message.content) ? <OutOfScope /> : null}
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
                    </li>
                  ),
                )}

                {live ? (
                  <>
                    <Question text={live.question} />
                    <li className="flex flex-col gap-3">
                      <LiveAnswer
                        turn={live}
                        onOpenLesson={onOpenLesson}
                        onRetry={() => void send(live.question)}
                      />
                    </li>
                  </>
                ) : null}
              </ol>
            )}
          </div>

          <form onSubmit={submit} className="flex flex-col gap-1.5 border-t p-2">
            <div className="relative">
              <Textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Hỏi về nội dung khóa học…"
                aria-label="Câu hỏi cho trợ giảng AI"
                rows={2}
                maxLength={QUESTION_MAX_CHARS}
                className="max-h-40 min-h-16 resize-none pr-12 text-body-sm"
              />
              {busy ? (
                <Button
                  type="button"
                  size="icon-sm"
                  variant="secondary"
                  className="absolute right-2 bottom-2.5"
                  aria-label="Dừng câu trả lời"
                  title="Dừng — câu trả lời dở sẽ không được lưu"
                  onClick={() => abort.current?.abort()}
                >
                  <Square className="size-3.5 fill-current" aria-hidden />
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="icon-sm"
                  className="absolute right-2 bottom-2.5"
                  aria-label="Gửi câu hỏi"
                  disabled={draft.trim() === ""}
                >
                  <ArrowUp aria-hidden />
                </Button>
              )}
            </div>
            <p className="flex justify-between gap-2 px-1 text-caption text-muted-foreground">
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
      <p className="ml-8 rounded-xl rounded-br-[0.375rem] bg-primary px-3 py-2 text-body-sm break-words whitespace-pre-wrap text-primary-foreground">
        {text}
      </p>
    </li>
  );
}

/** Above an answer that declines: said in words, not left to the reader to infer. */
function OutOfScope() {
  return (
    <span className="inline-flex h-6 items-center gap-1.5 self-start rounded-full bg-muted px-2.5 text-caption font-semibold text-muted-foreground">
      <Info className="size-3.5" aria-hidden />
      Ngoài phạm vi khóa học
    </span>
  );
}

/**
 * An answer on its way, as the three things the assistant does: look the
 * question up in the course, read the lessons it found, write. Each step is
 * ticked off as the stream reaches it, so the retrieval behind the answer is
 * visible while it happens -- not just a spinner.
 */
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
  const running = turn.phase === "searching" || turn.phase === "writing";
  const chips = readingChips(sources.map((source) => source.lesson_title));

  return (
    <>
      {running ? (
        <ol
          aria-label="Các bước trả lời"
          className="flex flex-col gap-2.5 rounded-md border bg-background p-3"
        >
          <Step state={turn.phase === "searching" ? "active" : "done"}>Tra cứu tài liệu khóa học</Step>
          {turn.phase === "writing" ? (
            <>
              <Step state="done">
                {sources.length > 0 ? `Đọc ${sources.length} bài liên quan` : "Không có bài nào khớp câu hỏi"}
                {sources.length > 0 ? (
                  <span className="mt-1.5 flex flex-wrap gap-1">
                    {chips.titles.map((title) => (
                      <span
                        key={title}
                        className="max-w-full truncate rounded-full border bg-card px-2 py-0.5 text-caption text-muted-foreground"
                      >
                        {title}
                      </span>
                    ))}
                    {chips.more > 0 ? (
                      <span className="px-2 py-0.5 text-caption text-muted-foreground">+{chips.more} bài</span>
                    ) : null}
                  </span>
                ) : null}
              </Step>
              <Step state="active">Đang soạn câu trả lời</Step>
            </>
          ) : null}
        </ol>
      ) : null}

      {turn.text !== "" ? (
        <ChatMarkdown
          content={turn.text}
          cited={citedFromSources(sources)}
          onOpenLesson={onOpenLesson}
        />
      ) : null}

      {turn.phase === "failed" || turn.phase === "stopped" ? (
        <div className="flex flex-col gap-2 rounded-md border border-dashed border-border-strong p-3 text-body-sm">
          <p className={turn.phase === "failed" ? "text-destructive-text" : "text-muted-foreground"}>
            {turn.phase === "failed"
              ? turn.error
              : "Đã dừng. Câu hỏi và phần trả lời dở này không được lưu."}
          </p>
          <Button size="sm" variant="outline" className="self-start" onClick={onRetry}>
            <RotateCcw aria-hidden />
            Hỏi lại
          </Button>
        </div>
      ) : null}
    </>
  );
}

function Step({ state, children }: { state: "done" | "active"; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5">
      {state === "done" ? (
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Check className="size-3" strokeWidth={3} aria-hidden />
        </span>
      ) : (
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full border-2 border-primary">
          <span className="size-2 rounded-full bg-primary" />
        </span>
      )}
      <span
        className={cn(
          "flex min-w-0 flex-col text-[0.8125rem] leading-5",
          state === "active" ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {children}
        <span className="sr-only">{state === "done" ? " — xong" : " — đang làm"}</span>
      </span>
    </li>
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

  // No Naomi here: she is already in the header, waiting for the question.
  return (
    <div className="flex min-h-full flex-col justify-center gap-5">
      <div className="flex flex-col gap-1.5">
        <p className="text-title">Hỏi về bất cứ bài nào trong khóa</p>
        <p className="text-body-sm text-pretty text-muted-foreground">
          Trợ giảng trả lời từ bài viết và lời giảng của chính khóa học này, kèm nguồn để
          bạn mở lại đúng bài. Câu hỏi ngoài phạm vi khóa học sẽ được từ chối.
        </p>
      </div>

      {suggestions.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-eyebrow text-muted-foreground uppercase">Thử hỏi</p>
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onAsk(suggestion)}
              className="flex w-full items-start gap-2 rounded-md border bg-card px-3 py-2.5 text-left text-body-sm transition-colors duration-fast hover:bg-accent"
            >
              <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div className="flex flex-col gap-1">
          <p className="mb-0.5 text-eyebrow text-muted-foreground uppercase">Tiếp tục trò chuyện</p>
          <ul className="flex flex-col">
            {recent.map((session) => (
              <li key={session.id}>
                <button
                  type="button"
                  onClick={() => onOpen(session.id)}
                  className="flex w-full items-baseline gap-2 rounded-md px-3 py-2 text-left text-body-sm transition-colors duration-fast hover:bg-accent"
                >
                  <span className="min-w-0 flex-1 truncate">{session.title}</span>
                  <span className="shrink-0 text-caption text-muted-foreground">
                    {formatRelativeTime(session.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {total > recent.length ? (
            <Button variant="link" size="sm" className="self-start px-3" onClick={onShowAll}>
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
    <div className="flex flex-col gap-5" aria-hidden>
      <Skeleton className="ml-auto h-9 w-2/3 rounded-xl" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3 w-full rounded-xs" />
        <Skeleton className="h-3 w-5/6 rounded-xs" />
        <Skeleton className="h-3 w-2/3 rounded-xs" />
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="flex flex-col gap-2 p-3" aria-hidden>
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-12" />
      ))}
    </div>
  );
}
