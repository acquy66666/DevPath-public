"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { StarRating, StarRatingInput } from "@/components/courses/star-rating";
import { ReportButton } from "@/components/reports/report-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import type { CourseDetail } from "@/lib/api/courses";
import { getMyEnrollment } from "@/lib/api/enrollments";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  deleteMyReview,
  getMyReview,
  listCourseReviews,
  upsertMyReview,
  type CourseReviews as CourseReviewsPage,
  type Review,
} from "@/lib/api/reviews";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

const COMMENT_MAX_LENGTH = 2000;

function ReviewCard({ review }: { review: Review }) {
  const edited = review.updated_at !== review.created_at;

  return (
    <li className="flex gap-3 border-t py-4 first:border-t-0 first:pt-0">
      <UserAvatar user={review.author} className="size-9 shrink-0 text-xs" />

      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="font-medium">{review.author.full_name}</p>
          <StarRating value={review.rating} starClassName="size-3.5" />
          <p className="text-xs text-muted-foreground">
            {formatDate(review.created_at)}
            {edited ? " · đã sửa" : ""}
          </p>
          <ReportButton
            targetType="review"
            targetId={review.id}
            authorId={review.author.id}
            className="ml-auto"
          />
        </div>

        {review.comment ? (
          <p className="whitespace-pre-line text-pretty text-sm text-muted-foreground">
            {review.comment}
          </p>
        ) : null}
      </div>
    </li>
  );
}

/**
 * The form for the caller's own review — write, rewrite, or withdraw.
 *
 * Shown only to someone enrolled, because that is who the backend lets write.
 * Drawing it for everyone and letting the 403 explain afterwards would be a
 * form that exists to fail.
 */
function MyReviewForm({
  course,
  existing,
  onWritten,
}: {
  course: CourseDetail;
  existing: Review | null;
  onWritten: () => void;
}) {
  const { accessToken } = useAuth();
  // Seeded from the existing review and then owned by the form: re-syncing on
  // every render would undo what the person is in the middle of typing.
  const [rating, setRating] = useState(existing?.rating ?? 0);
  const [comment, setComment] = useState(existing?.comment ?? "");

  const save = useMutation({
    mutationFn: () =>
      upsertMyReview(accessToken as string, course.id, {
        rating,
        comment: comment.trim() || null,
      }),
    onSuccess: onWritten,
  });

  const remove = useMutation({
    mutationFn: () => deleteMyReview(accessToken as string, course.id),
    onSuccess: () => {
      setRating(0);
      setComment("");
      onWritten();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rating === 0) return;
    save.mutate();
  }

  const busy = save.isPending || remove.isPending;

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-medium">
          {existing ? "Đánh giá của bạn" : "Viết đánh giá"}
        </h3>

        {existing ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Trash2 aria-hidden />
            )}
            Xóa đánh giá
          </Button>
        ) : null}
      </div>

      <StarRatingInput value={rating} onChange={setRating} disabled={busy} />

      <Textarea
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        placeholder="Điều gì khiến bạn chấm mức điểm này? (không bắt buộc)"
        rows={3}
        maxLength={COMMENT_MAX_LENGTH}
        disabled={busy}
      />

      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      {remove.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" size="sm" disabled={busy || rating === 0}>
        {save.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang lưu…
          </>
        ) : existing ? (
          "Cập nhật đánh giá"
        ) : (
          "Gửi đánh giá"
        )}
      </Button>
    </form>
  );
}

/**
 * The reviews section of the course page.
 *
 * The first page arrives server-rendered — a crawler and a reader on a slow
 * connection both see the reviews in the first response — and this component
 * takes over from there for paging and for the caller's own review, neither of
 * which the server can answer: the access token lives in the browser.
 */
export function CourseReviews({
  course,
  initial,
}: {
  course: CourseDetail;
  initial: CourseReviewsPage;
}) {
  const { user, accessToken, status } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);

  const owns = user?.id === course.instructor.id;
  const signedIn = status === "authenticated" && accessToken !== null;

  const reviews = useQuery({
    queryKey: ["reviews", course.id, page],
    queryFn: () => listCourseReviews(course.id, page),
    initialData: page === 1 ? initial : undefined,
    placeholderData: keepPreviousData,
  });

  // The same key the enrol button uses, so this is a cache hit rather than a
  // second request for the same answer.
  const enrollment = useQuery({
    queryKey: ["enrollment", course.id],
    queryFn: () => getMyEnrollment(accessToken as string, course.id),
    enabled: signedIn && !owns,
    // A 404 here means "not enrolled", which is an answer, not a failure.
    retry: false,
  });

  const myReview = useQuery({
    queryKey: ["my-review", course.id],
    queryFn: () => getMyReview(accessToken as string, course.id),
    enabled: signedIn && !owns,
    retry: false,
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["reviews", course.id] });
    queryClient.invalidateQueries({ queryKey: ["my-review", course.id] });
  }

  const current = reviews.data ?? initial;
  const pageCount = Math.max(1, Math.ceil(current.total / current.page_size));
  const rated = current.rating_count > 0;

  // A 404 is how "you have not written one" comes back; anything else is a
  // real failure and the form should not pretend it knows the answer.
  const missing =
    myReview.error instanceof ApiError && myReview.error.status === 404;
  const settled = myReview.isSuccess || missing;
  // `getMyEnrollment` answers null for "not enrolled"; only a row means yes.
  const enrolled = enrollment.data != null;

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-xl font-semibold tracking-tight">Đánh giá</h2>

        {rated ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <StarRating value={Number(current.rating_avg)} />
            <span>
              {current.rating_avg} · {current.rating_count} đánh giá
            </span>
          </p>
        ) : null}
      </div>

      {status === "loading" ? (
        <div className="h-24 animate-pulse rounded-lg bg-muted" aria-hidden />
      ) : user === null ? (
        <p className="text-sm text-muted-foreground">
          <Link
            href={`/dang-nhap?next=/khoa-hoc/${course.slug}`}
            className="underline underline-offset-4"
          >
            Đăng nhập
          </Link>{" "}
          để viết đánh giá cho khóa học này.
        </p>
      ) : owns ? null : enrollment.isLoading ? (
        <div className="h-24 animate-pulse rounded-lg bg-muted" aria-hidden />
      ) : !enrolled ? (
        <p className="text-sm text-muted-foreground">
          Đăng ký khóa học để viết đánh giá.
        </p>
      ) : settled ? (
        <MyReviewForm
          // Remounts when the review appears or is withdrawn, so the fields
          // start from whatever is now stored rather than from the last edit.
          key={myReview.data?.id ?? "new"}
          course={course}
          existing={myReview.data ?? null}
          onWritten={refresh}
        />
      ) : (
        <div className="h-24 animate-pulse rounded-lg bg-muted" aria-hidden />
      )}

      {current.items.length === 0 ? (
        <p className="rounded-lg border border-dashed px-5 py-8 text-center text-sm text-muted-foreground">
          Chưa có đánh giá nào. Học xong rồi, bạn viết đánh giá đầu tiên nhé.
        </p>
      ) : (
        <ul className={reviews.isPlaceholderData ? "opacity-60" : undefined}>
          {current.items.map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </ul>
      )}

      {pageCount > 1 ? (
        <nav
          aria-label="Phân trang đánh giá"
          className="flex items-center justify-center gap-3"
        >
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Trang trước
          </Button>
          <span className="text-sm text-muted-foreground">
            Trang {page} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setPage((value) => value + 1)}
          >
            Trang sau
          </Button>
        </nav>
      ) : null}
    </section>
  );
}
