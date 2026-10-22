"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { QA_KEY, QaThreadRow } from "@/components/qa/qa-shared";
import { QA_MESSAGES, QaThreadView } from "@/components/qa/qa-thread-view";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/empty-state";
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

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link
          href="/giang-day"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Khóa học của tôi
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Hỏi đáp của học viên</h1>
        <p className="text-sm text-muted-foreground">
          Câu hỏi học viên đặt dưới các bài học trong khóa bạn dạy. Câu trả lời của bạn
          được gắn nhãn “Giảng viên” và người hỏi nhận được thông báo.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="qa-course" className="text-sm text-muted-foreground">
            Khóa học
          </label>
          <NativeSelect
            id="qa-course"
            className="w-auto max-w-72"
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={unanswered}
            onChange={(event) => {
              setUnanswered(event.target.checked);
              setPage(1);
            }}
          />
          Chỉ câu chưa trả lời
        </label>
      </div>

      {threads.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(threads.error, QA_MESSAGES)}</AlertDescription>
        </Alert>
      ) : null}

      {threads.isPending ? (
        <QaRowsSkeleton />
      ) : null}

      {threads.data && threads.data.total === 0 ? (
        <EmptyState
          size="md"
          title={unanswered ? "Không còn câu hỏi nào chờ bạn trả lời" : "Chưa có câu hỏi nào"}
          description={
            unanswered
              ? "Bỏ chọn “Chỉ câu chưa trả lời” để xem lại những câu đã trả lời."
              : "Khi học viên đặt câu hỏi dưới một bài học, câu hỏi sẽ hiện ở đây."
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
