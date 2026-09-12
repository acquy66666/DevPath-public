"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck, Check, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef } from "react";

import { ExerciseWorkspace } from "@/components/exercise/exercise-workspace";
import { LessonList } from "@/components/learn/lesson-list";
import { NotesPanel } from "@/components/learn/notes-panel";
import {
  VideoPlayer,
  type PlayerHandle,
} from "@/components/learn/video-player";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { getCourseBySlug } from "@/lib/api/courses";
import { getCurriculum, getLesson } from "@/lib/api/curriculum";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getCourseProgress, saveProgress } from "@/lib/api/progress";
import { listBookmarks, setBookmark } from "@/lib/api/study";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The learning page: a player on the left, the table of contents on the right.
 *
 * Entirely a Client Component, unlike the course page it follows: every call
 * here needs the access token, which lives in memory in the browser. Nothing
 * on this page is for a crawler anyway.
 */
export function LearnView({
  slug,
  lessonId,
}: {
  slug: string;
  /** From `?bai=`. Null means "wherever I left off". */
  lessonId: string | null;
}) {
  const { accessToken, status } = useAuth();
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

  if (status === "loading") {
    return <div className="h-96 animate-pulse rounded-xl bg-muted/50" aria-hidden />;
  }

  if (!signedIn) {
    return (
      <Alert>
        <AlertDescription className="flex flex-wrap items-center gap-3">
          Đăng nhập để tiếp tục khóa học của bạn.
          <Button size="sm" asChild>
            <Link href={`/dang-nhap?next=/hoc/${slug}`}>Đăng nhập</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (progress.isError) {
    const notEnrolled =
      progress.error instanceof ApiError && progress.error.code === "NOT_ENROLLED";

    return (
      <Alert variant={notEnrolled ? "default" : "destructive"}>
        <AlertDescription className="flex flex-wrap items-center gap-3">
          {notEnrolled
            ? "Bạn chưa đăng ký khóa học này."
            : apiErrorMessage(progress.error)}
          <Button size="sm" variant="outline" asChild>
            <Link href={`/khoa-hoc/${slug}`}>Xem khóa học</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!course.data || !curriculum.data || !progress.data) {
    return <div className="h-96 animate-pulse rounded-xl bg-muted/50" aria-hidden />;
  }

  const completedIds = new Set(
    progress.data.lessons
      .filter((row) => row.completed_at !== null)
      .map((row) => row.lesson_id),
  );
  const percent =
    progress.data.lesson_count === 0
      ? 0
      : Math.round((progress.data.completed_count / progress.data.lesson_count) * 100);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link
          href={`/khoa-hoc/${slug}`}
          className="text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          ← {course.data.title}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <div className="h-2 w-48 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary transition-[width]" style={{ width: `${percent}%` }} />
          </div>
          <p className="text-sm text-muted-foreground">
            {progress.data.completed_count}/{progress.data.lesson_count} bài · {percent}%
            {progress.data.completed_at ? " · đã hoàn thành khóa học 🎉" : null}
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          {lesson.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(lesson.error)}</AlertDescription>
            </Alert>
          ) : null}

          {lesson.data ? (
            <>
              <h1 className="text-xl font-semibold tracking-tight">{lesson.data.title}</h1>

              {lesson.data.type === "video" ? (
                lesson.data.video?.hls_url ? (
                  <VideoPlayer
                    key={lesson.data.id}
                    ref={player}
                    src={lesson.data.video.hls_url}
                    startAt={current?.last_position_s ?? 0}
                    onProgress={handleProgress}
                    onEnded={() => setCompleted.mutate(true)}
                  />
                ) : (
                  <Alert>
                    <AlertDescription>
                      {lesson.data.video?.status === "processing"
                        ? "Video đang được xử lý, vài phút nữa quay lại nhé."
                        : "Bài học này chưa có video."}
                    </AlertDescription>
                  </Alert>
                )
              ) : lesson.data.type === "code_exercise" ? (
                <ExerciseWorkspace
                  // Keyed by lesson: moving to another exercise must start a
                  // fresh editor rather than carry the previous answer over.
                  key={lesson.data.id}
                  lessonId={lesson.data.id}
                  accessToken={accessToken as string}
                />
              ) : (
                <article className="whitespace-pre-line text-pretty">
                  {lesson.data.article_content ?? "Bài học này chưa có nội dung."}
                </article>
              )}

              <div className="flex items-center gap-3">
                <Button
                  variant={finished ? "outline" : "default"}
                  onClick={() => setCompleted.mutate(!finished)}
                  disabled={setCompleted.isPending}
                >
                  {setCompleted.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden />
                      Đang lưu…
                    </>
                  ) : finished ? (
                    "Bỏ đánh dấu hoàn thành"
                  ) : (
                    <>
                      <Check aria-hidden />
                      Đánh dấu hoàn thành
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={() => toggleBookmark.mutate(!flagged)}
                  disabled={toggleBookmark.isPending}
                  aria-pressed={flagged}
                >
                  {flagged ? (
                    <>
                      <BookmarkCheck aria-hidden />
                      Bỏ đánh dấu
                    </>
                  ) : (
                    <>
                      <Bookmark aria-hidden />
                      Đánh dấu để xem lại
                    </>
                  )}
                </Button>

                {setCompleted.isError ? (
                  <p className="text-sm text-destructive">
                    {apiErrorMessage(setCompleted.error)}
                  </p>
                ) : null}
              </div>

              <NotesPanel
                lessonId={lesson.data.id}
                timed={lesson.data.type === "video"}
                currentTime={() => player.current?.currentTime() ?? 0}
                onSeek={(seconds) => player.current?.seekTo(seconds)}
              />
            </>
          ) : (
            <div className="h-96 animate-pulse rounded-xl bg-muted/50" aria-hidden />
          )}
        </div>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <LessonList
            curriculum={curriculum.data}
            currentLessonId={currentId}
            completedLessonIds={completedIds}
            bookmarkedLessonIds={bookmarkedIds}
            onSelect={selectLesson}
          />
        </aside>
      </div>
    </div>
  );
}
