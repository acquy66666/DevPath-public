"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Flag, Loader2, Lock, Star } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton, PersonLine } from "@/components/admin/admin-shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import { Textarea } from "@/components/ui/textarea";
import {
  dismissReport,
  listAdminReports,
  lockUser,
  resolveReport,
  startReportReview,
  type AdminReport,
  type ReportQueue,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { REPORT_REASON_LABELS, type ReportTargetType } from "@/lib/api/reports";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const TARGET_LABELS: Record<ReportTargetType, string> = {
  course: "Khóa học",
  review: "Đánh giá",
  qa_thread: "Câu hỏi Hỏi đáp",
  qa_reply: "Câu trả lời Hỏi đáp",
};

const REMOVE_LABELS: Record<ReportTargetType, string> = {
  course: "Gỡ khóa học khỏi sàn",
  review: "Xóa đánh giá",
  qa_thread: "Xóa câu hỏi",
  qa_reply: "Xóa câu trả lời",
};

const STATUS_LABELS: Record<AdminReport["status"], string> = {
  open: "Mới",
  reviewing: "Đang xem xét",
  resolved: "Đã xử lý",
  dismissed: "Không vi phạm",
};

const NOTE_MAX_LENGTH = 1000;

/**
 * Reports learners filed, oldest first -- the order that is fair to whoever
 * reported first.
 *
 * A decision is about the content, so it closes every pending report on the
 * same thing; the card says how many that is before the admin clicks.
 */
export function AdminReportQueue() {
  const { accessToken } = useAuth();
  const [queue, setQueue] = useState<ReportQueue>("pending");
  const [targetType, setTargetType] = useState<ReportTargetType | null>(null);
  const [page, setPage] = useState(1);

  const reports = useQuery({
    queryKey: [...ADMIN_KEY, "reports", queue, targetType, page],
    queryFn: () => listAdminReports(accessToken as string, { status: queue, targetType, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-4" aria-labelledby="admin-reports-title">
      <h2 id="admin-reports-title" className="sr-only">
        Báo cáo vi phạm
      </h2>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border p-0.5" role="group" aria-label="Hàng đợi">
          {(
            [
              ["pending", "Chờ xử lý"],
              ["closed", "Đã xử lý"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={queue === value}
              onClick={() => {
                setQueue(value);
                setPage(1);
              }}
              className={cn(
                "rounded-md px-3 py-1 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                queue === value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <label htmlFor="admin-report-type" className="sr-only">
          Loại nội dung
        </label>
        <NativeSelect
          id="admin-report-type"
          className="h-9 w-auto"
          value={targetType ?? ""}
          onChange={(event) => {
            setTargetType((event.target.value || null) as ReportTargetType | null);
            setPage(1);
          }}
        >
          <option value="">Mọi loại nội dung</option>
          {Object.entries(TARGET_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </NativeSelect>
      </div>

      {reports.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(reports.error)}</AlertDescription>
        </Alert>
      ) : null}

      {reports.isPending ? <ListSkeleton height="h-40" /> : null}

      {reports.data && reports.data.total === 0 ? (
        <EmptyState
          icon={Flag}
          title={queue === "pending" ? "Không có báo cáo nào đang chờ" : "Chưa xử lý báo cáo nào"}
          hint={
            queue === "pending"
              ? "Học viên báo cáo khóa học, đánh giá hoặc nội dung hỏi đáp bằng nút “Báo cáo”; báo cáo sẽ xếp hàng ở đây."
              : "Báo cáo đã xử lý hoặc bỏ qua sẽ được lưu lại ở đây."
          }
        />
      ) : null}

      {reports.data && reports.data.items.length > 0 ? (
        <ul
          className={reports.isPlaceholderData ? "space-y-3 opacity-60" : "space-y-3"}
          aria-busy={reports.isFetching}
        >
          {reports.data.items.map((report) => (
            <li key={report.id}>
              <ReportCard report={report} />
            </li>
          ))}
        </ul>
      ) : null}

      {reports.data ? (
        <Pager
          page={reports.data.page}
          pageSize={reports.data.page_size}
          total={reports.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}

/** Where the admin can see the reported thing in its own page, if anywhere. */
function targetHref(report: AdminReport): string | null {
  const { target } = report;
  if (!target.exists || !target.course) return null;
  if (report.target_type === "course") return `/quan-tri/khoa-hoc/${target.course.id}`;
  if (report.target_type === "review") {
    return target.course.status === "published" ? `/khoa-hoc/${target.course.slug}` : null;
  }
  // Q&A lives on the learning page, which opens for enrolled learners; the
  // excerpt on the card is what the admin judges.
  return null;
}

function ReportCard({ report }: { report: AdminReport }) {
  const { target } = report;
  const pending = report.status === "open" || report.status === "reviewing";
  const href = targetHref(report);

  return (
    <article className="space-y-3 rounded-xl border p-4">
      <header className="flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="destructive">{REPORT_REASON_LABELS[report.reason]}</Badge>
        <Badge variant="outline">{TARGET_LABELS[report.target_type]}</Badge>
        <Badge variant={pending ? "secondary" : "outline"}>{STATUS_LABELS[report.status]}</Badge>
        <span className="text-muted-foreground">{formatRelativeTime(report.created_at)}</span>
        {pending && report.pending_on_target > 1 ? (
          <span className="font-medium text-destructive">
            {report.pending_on_target} báo cáo cho cùng nội dung
          </span>
        ) : null}
      </header>

      <div className="space-y-2 rounded-lg bg-muted/40 p-3 text-sm">
        {target.exists ? (
          <>
            {target.course && report.target_type !== "course" ? (
              <p className="text-xs text-muted-foreground">Trong khóa: {target.course.title}</p>
            ) : null}
            {target.title ? <p className="font-medium break-words">{target.title}</p> : null}
            {target.rating !== null ? (
              <p className="flex items-center gap-1 text-xs" aria-label={`${target.rating} sao`}>
                {Array.from({ length: 5 }, (_, index) => (
                  <Star
                    key={index}
                    className={cn(
                      "size-3.5",
                      index < (target.rating ?? 0)
                        ? "fill-amber-400 text-amber-400"
                        : "text-muted-foreground/40",
                    )}
                    aria-hidden
                  />
                ))}
              </p>
            ) : null}
            {target.excerpt ? (
              <p className="whitespace-pre-line break-words text-muted-foreground">
                {target.excerpt}
              </p>
            ) : null}
            {target.author ? (
              <AuthorLine report={report} />
            ) : null}
            {href ? (
              <Link
                href={href}
                target={href.startsWith("/quan-tri") ? undefined : "_blank"}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <ExternalLink className="size-3" aria-hidden />
                {report.target_type === "course" ? "Mở trang duyệt khóa học" : "Mở trang khóa học"}
              </Link>
            ) : null}
          </>
        ) : (
          <p className="text-muted-foreground italic">
            Nội dung này không còn nữa — tác giả hoặc quản trị viên đã xóa nó.
          </p>
        )}
      </div>

      <div className="space-y-1 text-sm">
        <PersonLine person={report.reporter} label="Người báo cáo:" />
        {report.details ? (
          <p className="border-l-2 pl-3 whitespace-pre-line break-words text-muted-foreground">
            {report.details}
          </p>
        ) : null}
      </div>

      {pending ? (
        <Decision report={report} />
      ) : (
        <p className="text-sm text-muted-foreground">
          {report.status === "resolved" ? "Xác nhận vi phạm" : "Bỏ qua, không vi phạm"}
          {report.resolved_by ? ` bởi ${report.resolved_by.full_name}` : ""}
          {report.resolved_at ? `, ${formatRelativeTime(report.resolved_at)}` : ""}
          {report.content_removed ? " · đã gỡ nội dung" : ""}
          {report.resolution_note ? ` — “${report.resolution_note}”` : ""}
        </p>
      )}
    </article>
  );
}

/** The author of the reported thing, with a way to lock them from here. */
function AuthorLine({ report }: { report: AdminReport }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const author = report.target.author;

  const lock = useMutation({
    mutationFn: () => lockUser(accessToken as string, author!.id),
    onSuccess: () => {
      setConfirming(false);
      queryClient.invalidateQueries({ queryKey: ADMIN_KEY });
    },
  });

  if (!author) return null;
  const lockable = author.role !== "admin" && author.locked_at === null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <PersonLine person={author} label="Tác giả:" />
        {lockable && !confirming ? (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            <Lock aria-hidden />
            Khóa tác giả
          </Button>
        ) : null}
      </div>
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-destructive/5 p-2">
          <span className="min-w-0 flex-1 text-xs">
            Khóa {author.full_name}: đăng xuất khỏi mọi thiết bị và không đăng nhập được nữa.
          </span>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => lock.mutate()}
            disabled={lock.isPending}
          >
            {lock.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Khóa tài khoản
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
            Hủy
          </Button>
        </div>
      ) : null}
      {lock.isError ? (
        <p className="text-xs text-destructive">{apiErrorMessage(lock.error)}</p>
      ) : null}
    </div>
  );
}

function Decision({ report }: { report: AdminReport }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const settled = {
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_KEY }),
  };
  const review = useMutation({
    mutationFn: () => startReportReview(accessToken as string, report.id),
    ...settled,
  });
  const resolve = useMutation({
    mutationFn: (removeContent: boolean) =>
      resolveReport(accessToken as string, report.id, {
        note: note.trim() || null,
        remove_content: removeContent,
      }),
    ...settled,
  });
  const dismiss = useMutation({
    mutationFn: () => dismissReport(accessToken as string, report.id, note.trim() || null),
    ...settled,
  });

  const busy = review.isPending || resolve.isPending || dismiss.isPending;
  const error = review.error ?? resolve.error ?? dismiss.error;
  const { target } = report;
  const removable =
    target.exists && (report.target_type !== "course" || target.course?.status === "published");

  return (
    <div className="space-y-2 border-t pt-3">
      <label htmlFor={`note-${report.id}`} className="sr-only">
        Ghi chú xử lý
      </label>
      <Textarea
        id={`note-${report.id}`}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        maxLength={NOTE_MAX_LENGTH}
        rows={2}
        placeholder={
          report.target_type === "course"
            ? "Ghi chú xử lý (không bắt buộc) — nếu gỡ khóa học, giảng viên đọc được câu này"
            : "Ghi chú xử lý (không bắt buộc)"
        }
      />
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {removable ? (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => resolve.mutate(true)}
            disabled={busy}
          >
            {resolve.isPending && resolve.variables === true ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : null}
            {REMOVE_LABELS[report.target_type]}
          </Button>
        ) : null}
        <Button variant="outline" size="sm" onClick={() => resolve.mutate(false)} disabled={busy}>
          {resolve.isPending && resolve.variables === false ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : null}
          Vi phạm, giữ nội dung
        </Button>
        <Button variant="outline" size="sm" onClick={() => dismiss.mutate()} disabled={busy}>
          {dismiss.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Không vi phạm
        </Button>
        {report.status === "open" ? (
          <Button variant="ghost" size="sm" onClick={() => review.mutate()} disabled={busy}>
            Đánh dấu đang xem xét
          </Button>
        ) : null}
      </div>
    </div>
  );
}
