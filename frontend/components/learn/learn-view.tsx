"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListTree, MessageCircleQuestion, NotebookPen, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { ExerciseWorkspace } from "@/components/exercise/exercise-workspace";
import { CourseBar } from "@/components/learn/course-bar";
import { CourseComplete, NEXT_COURSES_ID } from "@/components/learn/course-complete";
import { LearnSkeleton } from "@/components/learn/learn-skeleton";
import { LessonActions } from "@/components/learn/lesson-actions";
import { LessonHeading } from "@/components/learn/lesson-heading";
import { LessonList } from "@/components/learn/lesson-list";
import { NotesPanel } from "@/components/learn/notes-panel";
import { VideoPlayer, type PlayerHandle } from "@/components/learn/video-player";
import { Mascot } from "@/components/mascot/mascot";
import { QaPanel } from "@/components/qa/qa-panel";
import { QuizWorkspace } from "@/components/quiz/quiz-workspace";
import { NextCourses } from "@/components/recommendations/next-courses";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/client";
import { getCourseBySlug } from "@/lib/api/courses";
import { getCurriculum, getLesson } from "@/lib/api/curriculum";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getCourseProgress, saveProgress } from "@/lib/api/progress";
import { listBookmarks, setBookmark } from "@/lib/api/study";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatTimestamp } from "@/lib/format";
import { locateLesson, readingMinutes, resumeAt } from "@/lib/learn/position";

/**
 * The learning page: the lesson on the left, the table of contents and the
 * course assistant on the right; on a phone, one column in that order.
 *
 * Entirely a Client Component, unlike the course page it follows: every call
 * here needs the access token, which lives in memory in the browser. Nothing
 * on this page is for a crawler anyway.
 */
export function LearnView({
  slug,
  lessonId,
  threadId,
}: {
  slug: string;
  /** From `?bai=`. Null means "wherever I left off". */
  lessonId: string | null;
  /** From `?hoi-dap=`: a question under this lesson to open straight onto. */
  threadId: string | null;
}) {
  const { accessToken, status, user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const signedIn = status === "authenticated" && accessToken !== null;

  const course = useQuery({
    queryKey: ["course", slug],
    queryFn: () => getCourseBySlug(slug, accessToken),
    enabled: signedIn,
  });
  const courseId = course.data?.id ?? null;

  const progress = useQuery({
    queryKey: ["progress", courseId],
    queryFn: () => getCourseProgress(accessToken as string, courseId as string),
    enabled: signedIn && courseId !== null,
    retry: false,
  });

  const curriculum = useQuery({
    queryKey: ["curriculum", courseId],
    queryFn: () => getCurriculum(courseId as string, accessToken),
    enabled: signedIn && courseId !== null,
  });

  const bookmarks = useQuery({
    queryKey: ["bookmarks", courseId],
    queryFn: () => listBookmarks(accessToken as string, courseId as string),
    enabled: signedIn && courseId !== null,
  });

  // The player is asked things rather than mirrored into state: its position
  // changes thirty times a second and nothing here needs to re-render for it.
  const player = useRef<PlayerHandle>(null);
  // "Ghi chú tại …" under the player puts the cursor in the note box.
  const composer = useRef<HTMLTextAreaElement>(null);

  // The assistant is built the first time its tab is opened, then kept: most
  // visits never open it, and the ones that do must not lose an answer to a
  // glance at the table of contents.
  const [chatOpened, setChatOpened] = useState(false);

  // Under the lesson: the reader's own notes, or the class's questions. A link
  // that names a question opens on the questions.
  const [belowTab, setBelowTab] = useState(threadId ? "qa" : "notes");
  // The same for a link followed while the page is already open: adjusting
  // state during render rather than in an effect, so there is no frame of the
  // wrong tab first.
  const [seenThreadId, setSeenThreadId] = useState(threadId);
  if (threadId !== seenThreadId) {
    setSeenThreadId(threadId);
    if (threadId) setBelowTab("qa");
  }

  // Naomi graduates only for a course finished while the page is open: the
  // page must have seen it unfinished first. Reopening a finished course
  // shows her still.
  const [sawUnfinished, setSawUnfinished] = useState(false);
  if (progress.data && progress.data.completed_at === null && !sawUnfinished) {
    setSawUnfinished(true);
  }

  // `?bai=` wins; without it, carry on where this reader stopped.
  const currentId = lessonId ?? progress.data?.resume_lesson_id ?? null;

  const lesson = useQuery({
    queryKey: ["lesson", currentId],
    queryFn: () => getLesson(currentId as string, accessToken),
    enabled: signedIn && currentId !== null,
  });

  const current = progress.data?.lessons.find((row) => row.lesson_id === currentId);
  const finished = current?.completed_at != null;
  const bookmarkedIds = new Set(bookmarks.data?.lesson_ids ?? []);
  const flagged = currentId !== null && bookmarkedIds.has(currentId);

  const toggleBookmark = useMutation({
    mutationFn: (next: boolean) =>
      setBookmark(accessToken as string, currentId as string, next),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bookmarks", courseId] });
    },
  });

  // The heartbeat writes constantly and must not make the page flicker, so it
  // invalidates nothing. Only a change of completion refreshes the ticks.
  const lastSaved = useRef(0);
  const heartbeat = useMutation({
    mutationFn: (seconds: number) =>
      saveProgress(accessToken as string, currentId as string, {
        last_position_s: seconds,
      }),
  });

  const setCompleted = useMutation({
    mutationFn: (completed: boolean) =>
      saveProgress(accessToken as string, currentId as string, {
        last_position_s: lastSaved.current,
        completed,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["progress", courseId] });
      queryClient.invalidateQueries({ queryKey: ["my-enrollments"] });
      queryClient.invalidateQueries({ queryKey: ["gamification"] });
    },
  });

  const handleProgress = useCallback(
    (seconds: number) => {
      lastSaved.current = seconds;
      if (currentId !== null) heartbeat.mutate(seconds);
    },
    // `heartbeat` is stable enough for this: the mutation is recreated per
    // render but calling the latest one is exactly what we want.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [currentId],
  );

  function selectLesson(id: string) {
    router.push(`/hoc/${slug}?bai=${id}`, { scroll: false });
  }

  function openThread(id: string | null) {
    if (currentId === null) return;
    const lessonQuery = `?bai=${currentId}`;
    router.push(`/hoc/${slug}${lessonQuery}${id ? `&hoi-dap=${id}` : ""}`, { scroll: false });
  }

  function noteHere() {
    setBelowTab("notes");
    // The notes tab may only mount with this change: wait a frame for it.
    requestAnimationFrame(() => composer.current?.focus());
  }

  if (status === "loading") return <LearnSkeleton />;

  if (!signedIn) {
    return (
      <LearnGate
        mood="wave"
        title="Đăng nhập để vào học"
        hint="Tiến độ, ghi chú và bài đã nộp được lưu theo tài khoản của bạn."
        href={`/dang-nhap?next=/hoc/${slug}`}
        action="Đăng nhập"
      />
    );
  }

  if (progress.isError) {
    const notEnrolled =
      progress.error instanceof ApiError && progress.error.code === "NOT_ENROLLED";

    if (notEnrolled) {
      return (
        <LearnGate
          mood="empty-courses"
          title="Bạn chưa đăng ký khóa học này"
          hint={
            course.data
              ? `Đăng ký “${course.data.title}” ở trang khóa học, rồi quay lại đây để học.`
              : "Đăng ký ở trang khóa học, rồi quay lại đây để học."
          }
          href={`/khoa-hoc/${slug}`}
          action="Xem khóa học"
        />
      );
    }

    return (
      <Alert variant="destructive">
        <AlertDescription className="flex flex-wrap items-center gap-3">
          {apiErrorMessage(progress.error)}
          <Button size="sm" variant="outline" asChild>
            <Link href={`/khoa-hoc/${slug}`}>Xem khóa học</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!course.data || !curriculum.data || !progress.data) return <LearnSkeleton />;

  const completedIds = new Set(
    progress.data.lessons
      .filter((row) => row.completed_at !== null)
      .map((row) => row.lesson_id),
  );
  const place = locateLesson(curriculum.data, currentId);
  const courseFinished = progress.data.completed_at !== null;
  const graduateEvent = sawUnfinished && courseFinished ? progress.data.completed_at : null;

  const data = lesson.data;
  const length =
    data?.type === "video" && data.video?.duration_s
      ? formatTimestamp(data.video.duration_s)
      : data?.type === "article" && data.article_content?.trim()
        ? `${readingMinutes(data.article_content)} phút đọc`
        : null;

  return (
    <div className="flex flex-col gap-6">
      <CourseBar
        slug={slug}
        courseId={course.data.id}
        title={course.data.title}
        thumbnailUrl={course.data.thumbnail_url}
        completed={progress.data.completed_count}
        total={progress.data.lesson_count}
        certificateCode={courseFinished ? null : progress.data.certificate_code}
      />

      {courseFinished ? (
        <CourseComplete
          courseId={course.data.id}
          courseTitle={course.data.title}
          accessToken={accessToken as string}
          certificateCode={progress.data.certificate_code}
          reactTo={graduateEvent}
        />
      ) : null}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_24rem]">
        {/* `min-w-0` for the same reason as the aside below: on a phone the
            lesson column must not set the width of the whole grid. */}
        <div className="flex min-w-0 flex-col gap-5">
          {lesson.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(lesson.error)}</AlertDescription>
            </Alert>
          ) : null}

          {data ? (
            <>
              <LessonHeading
                place={place}
                title={data.title}
                type={data.type}
                length={length}
                resumeAt={
                  data.type === "video"
                    ? resumeAt(current?.last_position_s, data.video?.duration_s ?? null, finished)
                    : null
                }
                finished={finished}
              />

              {data.type === "video" ? (
                data.video?.hls_url ? (
                  <VideoPlayer
                    key={data.id}
                    ref={player}
                    src={data.video.hls_url}
                    startAt={current?.last_position_s ?? 0}
                    onProgress={handleProgress}
                    onEnded={() => setCompleted.mutate(true)}
                    onNoteHere={noteHere}
                  />
                ) : (
                  <Alert>
                    <AlertDescription>
                      {data.video?.status === "processing"
                        ? "Video đang được xử lý, vài phút nữa quay lại nhé."
                        : "Bài học này chưa có video."}
                    </AlertDescription>
                  </Alert>
                )
              ) : data.type === "code_exercise" ? (
                <ExerciseWorkspace
                  // Keyed by lesson: moving to another exercise must start a
                  // fresh editor rather than carry the previous answer over.
                  key={data.id}
                  lessonId={data.id}
                  accessToken={accessToken as string}
                  title={data.title}
                  context={course.data.title}
                  // Solving it finishes the lesson, and the worker wrote that
                  // down in the same transaction as the verdict. The page only
                  // has to go and look: the tick, the "x/y bài" counter and the
                  // course card all read from these two.
                  onSolved={() => {
                    queryClient.invalidateQueries({ queryKey: ["progress", courseId] });
                    queryClient.invalidateQueries({ queryKey: ["my-enrollments"] });
                  }}
                />
              ) : data.type === "quiz" ? (
                <QuizWorkspace
                  // Keyed by lesson for the same reason the exercise is:
                  // moving to another quiz must not carry the previous
                  // attempt's answers into a fresh paper.
                  key={data.id}
                  lessonId={data.id}
                  accessToken={accessToken as string}
                  // Passing finishes the lesson, written in the same
                  // transaction as the score. The page only has to go and
                  // look -- exactly as it does after an accepted submission.
                  onPassed={() => {
                    queryClient.invalidateQueries({ queryKey: ["progress", courseId] });
                    queryClient.invalidateQueries({ queryKey: ["my-enrollments"] });
                  }}
                />
              ) : data.article_content?.trim() ? (
                <article className="rounded-lg border bg-card px-5 py-6 sm:px-10 sm:py-8">
                  <Markdown className="max-w-[68ch] text-body-lg">{data.article_content}</Markdown>
                </article>
              ) : (
                // No Naomi: the empty notes under it already have her, and a
                // screen has one.
                <p className="rounded-lg border border-dashed border-border-strong px-5 py-8 text-center text-body text-muted-foreground">
                  Bài học này chưa có nội dung.
                </p>
              )}

              <LessonActions
                slug={slug}
                type={data.type}
                finished={finished}
                saving={setCompleted.isPending}
                onToggleComplete={() => setCompleted.mutate(!finished)}
                flagged={flagged}
                flagging={toggleBookmark.isPending}
                onToggleFlag={() => toggleBookmark.mutate(!flagged)}
                previous={place?.previous ?? null}
                next={place?.next ?? null}
                error={setCompleted.isError ? apiErrorMessage(setCompleted.error) : null}
              />

              <Tabs value={belowTab} onValueChange={setBelowTab} className="gap-5 pt-2">
                <TabsList variant="line" aria-label="Dưới bài học">
                  <TabsTrigger value="notes" className="text-[0.9375rem]">
                    <NotebookPen aria-hidden />
                    Ghi chú
                  </TabsTrigger>
                  <TabsTrigger value="qa" className="text-[0.9375rem]">
                    <MessageCircleQuestion aria-hidden />
                    Hỏi đáp
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="notes">
                  <NotesPanel
                    lessonId={data.id}
                    timed={data.type === "video"}
                    currentTime={() => player.current?.currentTime() ?? 0}
                    onSeek={(seconds) => player.current?.seekTo(seconds)}
                    composerRef={composer}
                  />
                </TabsContent>

                <TabsContent value="qa">
                  <QaPanel
                    // A fresh board per lesson: sort, page and a half-written
                    // question belong to the lesson they were started on.
                    key={data.id}
                    lessonId={data.id}
                    lessonTitle={data.title}
                    accessToken={accessToken as string}
                    currentUserId={user?.id ?? null}
                    openThreadId={threadId}
                    onOpenThread={openThread}
                  />
                </TabsContent>
              </Tabs>
            </>
          ) : (
            <div className="flex flex-col gap-5" aria-hidden>
              <Skeleton className="h-24 w-full max-w-md" />
              <Skeleton className="aspect-video w-full rounded-lg" />
            </div>
          )}
        </div>

        {/* `min-w-0`: a grid item is at least as wide as its longest
            unbreakable line, and on a phone the table of contents' was wider
            than the screen -- the whole column spilled into the right gutter. */}
        <aside className="min-w-0 lg:sticky lg:top-6 lg:self-start">
          <Tabs
            defaultValue="lessons"
            onValueChange={(value) => value === "assistant" && setChatOpened(true)}
          >
            <TabsList className="h-11 w-full sm:h-10" aria-label="Bên cạnh bài học">
              <TabsTrigger value="lessons" className="h-9 sm:h-8">
                <ListTree aria-hidden />
                Nội dung
              </TabsTrigger>
              <TabsTrigger value="assistant" className="h-9 sm:h-8">
                <Sparkles aria-hidden />
                Trợ giảng AI
              </TabsTrigger>
            </TabsList>

            <TabsContent value="lessons">
              <LessonList
                curriculum={curriculum.data}
                currentLessonId={currentId}
                completedLessonIds={completedIds}
                bookmarkedLessonIds={bookmarkedIds}
                onSelect={selectLesson}
              />
            </TabsContent>

            {/* Mounted even while hidden: switching back to the contents
                must not cut off an answer that is still being written. */}
            <TabsContent value="assistant" forceMount className="data-[state=inactive]:hidden">
              {chatOpened ? (
                <ChatPanel
                  courseId={course.data.id}
                  accessToken={accessToken as string}
                  curriculum={curriculum.data}
                  currentLesson={data ? { id: data.id, title: data.title } : null}
                  // A source opens its lesson beside the chat, which stays
                  // put: reading a lesson and asking about it are one activity.
                  onOpenLesson={selectLesson}
                />
              ) : null}
            </TabsContent>
          </Tabs>
        </aside>
      </div>

      {/* Appears the moment the last lesson is ticked: finishing it
          invalidates the progress query, which is what sets this. */}
      {courseFinished ? (
        <div id={NEXT_COURSES_ID} className="scroll-mt-6">
          <NextCourses courseId={course.data.id} accessToken={accessToken as string} />
        </div>
      ) : null}
    </div>
  );
}

/**
 * Why there is no lesson to show, and the one thing to do about it. Naomi
 * stands beside it still -- waving the reader in to sign in, next to a
 * closed book for a course not yet joined -- because nothing just happened:
 * the page simply cannot open yet.
 */
function LearnGate({
  mood,
  title,
  hint,
  href,
  action,
}: {
  mood: "wave" | "empty-courses";
  title: string;
  hint: string;
  href: string;
  action: string;
}) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-2 rounded-lg border bg-card px-6 py-8 text-center sm:py-10">
      <Mascot mood={mood} className="size-28 sm:size-32" />
      <h1 className="text-h3 text-balance">{title}</h1>
      <p className="max-w-[40ch] text-body text-pretty text-muted-foreground">{hint}</p>
      <Button className="mt-2 h-11 sm:h-10" asChild>
        <Link href={href}>{action}</Link>
      </Button>
    </div>
  );
}
