"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { QA_KEY, QaThreadRow } from "@/components/qa/qa-shared";
import { QA_MESSAGES, QaThreadView } from "@/components/qa/qa-thread-view";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/empty-state";
import { useUnansweredCount } from "@/components/instructor/instructor-nav";
import { QaRowsSkeleton } from "@/components/instructor/instructor-skeletons";
import { listMyCourses } from "@/lib/api/courses";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listInstructorThreads } from "@/lib/api/qa";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * Questions from the learners of every course the instructor teaches.
 *
 * The instructor cannot enrol in their own course, so its learning page --
 * where the questions are asked -- is not theirs to open. This is where they
 * answer instead. It opens on what is waiting for them: no reply from the
 * instructor yet, and not marked solved by the asker.
 *
 * The open question lives in the URL (`?cau-hoi=`), like on the learning page,
 * so the back button closes it and a link can open straight onto it.
 */
export function QaInbox({ openThreadId }: { openThreadId: string | null }) {
  const { accessToken, user } = useAuth();
  const router = useRouter();
  const [courseId, setCourseId] = useState<string | null>(null);
  const [unanswered, setUnanswered] = useState(true);
  const [page, setPage] = useState(1);

  const courses = useQuery({
    queryKey: ["my-courses", "all"],
    queryFn: () => listMyCourses(accessToken as string, 1, 100),
    enabled: accessToken !== null,
  });

  const threads = useQuery({
    queryKey: [...QA_KEY, "inbox", courseId, unanswered, page],
    queryFn: () =>
      listInstructorThreads(accessToken as string, { courseId, unanswered, page }),
    enabled: accessToken !== null && openThreadId === null,
    placeholderData: keepPreviousData,
  });

  const unansweredCount = useUnansweredCount();

  function open(id: string | null) {
    router.push(id ? `/giang-day/hoi-dap?cau-hoi=${id}` : "/giang-day/hoi-dap", {
      scroll: false,
    });
  }

  if (openThreadId !== null && accessToken !== null) {
    return (
      <div className="mx-auto max-w-3xl">
        <QaThreadView
          key={openThreadId}
          threadId={openThreadId}
          accessToken={accessToken}
          currentUserId={user?.id ?? null}
          staff
          onBack={() => open(null)}
          backLabel="Hộp thư hỏi đáp"
        />
      </div>
    );
  }

  const waiting = unansweredCount.data;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="space-y-1.5">
        <h1 className="text-h2 sm:text-h1">Hỏi đáp của học viên</h1>
        <p className="text-body text-muted-foreground">
          Câu trả lời của bạn mang nhãn “Giảng viên” và người hỏi nhận được thông báo.
        </p>
      </div>

      <div className="flex flex-col gap-3 border-b sm:flex-row sm:items-end sm:justify-between">
        <Tabs
          value={unanswered ? "waiting" : "all"}
          onValueChange={(value) => {
            setUnanswered(value === "waiting");
            setPage(1);
          }}
          className="order-last gap-0 sm:order-none"
        >
          <TabsList variant="line" aria-label="Lọc câu hỏi" className="shadow-none">
            <TabsTrigger value="waiting" className="text-[0.9375rem]">
              Chờ trả lời{typeof waiting === "number" ? ` · ${waiting}` : ""}
            </TabsTrigger>
            <TabsTrigger value="all" className="text-[0.9375rem]">
              Tất cả
            </TabsTrigger>
          </TabsList>
          {/* The list below is the panel of both tabs. */}
          <TabsContent value="waiting" className="sr-only">
            Câu hỏi chưa có câu trả lời của bạn và chưa được đánh dấu đã giải quyết.
          </TabsContent>
          <TabsContent value="all" className="sr-only">
            Mọi câu hỏi trong các khóa bạn dạy.
          </TabsContent>
        </Tabs>
        <div className="flex items-center gap-2 sm:pb-2">
          <label htmlFor="qa-course" className="shrink-0 text-body-sm text-muted-foreground">
            Khóa học
          </label>
          <NativeSelect
            id="qa-course"
            className="w-full sm:w-auto sm:max-w-72"
            value={courseId ?? ""}
            onChange={(event) => {
              setCourseId(event.target.value || null);
              setPage(1);
            }}
          >
            <option value="">Tất cả khóa học</option>
            {courses.data?.items.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {threads.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(threads.error, QA_MESSAGES)}</AlertDescription>
        </Alert>
      ) : null}

      {threads.isPending ? <QaRowsSkeleton /> : null}

      {threads.data && threads.data.total === 0 ? (
        <EmptyState
          size="md"
          title={unanswered ? "Không còn câu hỏi nào chờ bạn" : "Chưa có câu hỏi nào"}
          description={
            unanswered
              ? "Mọi câu hỏi đã có câu trả lời của bạn hoặc được người hỏi đánh dấu đã giải quyết."
              : "Khi học viên đặt câu hỏi dưới một bài học, câu hỏi sẽ hiện ở đây."
          }
          action={
            unanswered ? (
              <Button
                variant="link"
                className="h-auto p-0"
                onClick={() => {
                  setUnanswered(false);
                  setPage(1);
                }}
              >
                Xem tất cả câu hỏi
              </Button>
            ) : null
          }
        />
      ) : null}

      {threads.data && threads.data.items.length > 0 ? (
        <ul
          className={threads.isPlaceholderData ? "space-y-3 opacity-60" : "space-y-3"}
          aria-busy={threads.isFetching}
        >
          {threads.data.items.map((thread) => (
            <QaThreadRow key={thread.id} thread={thread} showPlace onOpen={() => open(thread.id)} />
          ))}
        </ul>
      ) : null}

      {threads.data ? (
        <Pager
          page={threads.data.page}
          pageSize={threads.data.page_size}
          total={threads.data.total}
          onPage={setPage}
        />
      ) : null}
    </div>
  );
}
