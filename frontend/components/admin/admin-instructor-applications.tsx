"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { ADMIN_KEY, useAdminSummary } from "@/components/admin/admin-nav";
import { AdminTitle, EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { FilterChips } from "@/components/admin/filter-chips";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Pager } from "@/components/ui/pager";
import { Textarea } from "@/components/ui/textarea";
import {
  approveInstructorApplication,
  listInstructorApplications,
  rejectInstructorApplication,
  type AdminInstructorApplication,
  type ApplicationFilter,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { LONG_WAIT_DAYS, waitedDays, waitLabel } from "@/lib/admin/admin-view";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Same ceiling as `APPLICATION_REASON_MAX_LENGTH` on the server. */
const REASON_MAX_LENGTH = 1000;

const FILTERS: { value: ApplicationFilter; label: string }[] = [
  { value: "pending", label: "Chờ duyệt" },
  { value: "approved", label: "Đã duyệt" },
  { value: "rejected", label: "Bị từ chối" },
  { value: "all", label: "Tất cả" },
];

const STATUS_BADGE = {
  pending: { label: "Chờ duyệt", variant: "warning" },
  approved: { label: "Đã duyệt", variant: "success" },
  rejected: { label: "Bị từ chối", variant: "destructive" },
} as const;

/**
 * Learners asking to teach, longest waiting first. Approving makes the account
 * an instructor at once; rejecting needs a reason the learner reads, and they
 * may apply again.
 */
export function AdminInstructorApplications() {
  const { accessToken } = useAuth();
  const [status, setStatus] = useState<ApplicationFilter>("pending");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [done, setDone] = useState<string | null>(null);

  const summary = useAdminSummary();
  const applications = useQuery({
    queryKey: [...ADMIN_KEY, "instructor-applications", status, q, page],
    queryFn: () => listInstructorApplications(accessToken as string, { status, q, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-5" aria-labelledby="admin-applications-title">
      <AdminTitle
        id="admin-applications-title"
        title="Duyệt giảng viên"
        description="Học viên muốn tạo khóa học gửi yêu cầu ở đây. Duyệt xong, tài khoản thành giảng viên ngay; từ chối thì ghi lý do để họ bổ sung."
      />

      <div className="flex flex-wrap items-center gap-3">
        <FilterChips
          label="Lọc theo trạng thái"
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          options={FILTERS.map((filter) => ({
            ...filter,
            count:
              filter.value === "pending" ? summary.data?.pending_instructor_applications : undefined,
          }))}
        />
        <SearchBox
          id="admin-application-search"
          placeholder="Tên hoặc email người gửi"
          initial={q}
          onSearch={(value) => {
            setQ(value);
            setPage(1);
          }}
        />
      </div>

      <div role="status" aria-live="polite">
        {done ? (
          <Alert>
            <CheckCircle2 aria-hidden />
            <AlertDescription>{done}</AlertDescription>
          </Alert>
        ) : null}
      </div>

      {applications.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(applications.error)}</AlertDescription>
        </Alert>
      ) : null}

      {applications.isPending ? <ListSkeleton /> : null}

      {applications.data && applications.data.total === 0 ? (
        <EmptyState
          mood={q ? "empty-search" : "empty"}
          title={
            q
              ? "Không có yêu cầu nào khớp"
              : status === "pending"
                ? "Không còn yêu cầu nào chờ duyệt"
                : "Chưa có yêu cầu nào ở trạng thái này"
          }
          hint={
            status === "pending"
              ? "Khi học viên bấm “Gửi yêu cầu” ở trang Trở thành giảng viên, yêu cầu sẽ xếp hàng ở đây."
              : "Đổi bộ lọc trạng thái hoặc từ khóa tìm kiếm để xem yêu cầu khác."
          }
        />
      ) : null}

      {applications.data && applications.data.items.length > 0 ? (
        <ul
          className={applications.isPlaceholderData ? "space-y-3 opacity-60" : "space-y-3"}
          aria-busy={applications.isFetching}
        >
          {applications.data.items.map((application) => (
            <li key={application.id}>
              <ApplicationCard application={application} onDecided={setDone} />
            </li>
          ))}
        </ul>
      ) : null}

      {applications.data ? (
        <Pager
          page={applications.data.page}
          pageSize={applications.data.page_size}
          total={applications.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}

function ApplicationCard({
  application,
  onDecided,
}: {
  application: AdminInstructorApplication;
  onDecided: (message: string) => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const reasonId = useId();
  const [writing, setWriting] = useState(false);
  const [reason, setReason] = useState("");

  const { applicant } = application;
  const pending = application.status === "pending";
  const days = waitedDays(application.created_at, new Date());
  const badge = STATUS_BADGE[application.status];

  function settle(message: string) {
    queryClient.invalidateQueries({ queryKey: ADMIN_KEY });
    setWriting(false);
    setReason("");
    onDecided(message);
  }

  const approve = useMutation({
    mutationFn: () => approveInstructorApplication(accessToken as string, application.id),
    onSuccess: () =>
      settle(
        `Đã duyệt ${applicant.full_name}. Tài khoản này giờ là giảng viên và đã nhận được thông báo.`,
      ),
  });
  const reject = useMutation({
    mutationFn: (text: string) =>
      rejectInstructorApplication(accessToken as string, application.id, text),
    onSuccess: () =>
      settle(`Đã từ chối yêu cầu của ${applicant.full_name}. Họ nhận được lý do và có thể gửi lại.`),
  });

  const busy = approve.isPending || reject.isPending;
  const error = approve.error ?? reject.error;
  const trimmed = reason.trim();

  return (
    <article
      aria-label={`Yêu cầu của ${applicant.full_name}`}
      className="space-y-3 rounded-lg border bg-card p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start gap-3">
        <UserAvatar user={applicant} className="size-10 shrink-0" />
        <div className="min-w-0 flex-1 space-y-0.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h2 className="min-w-0 text-title break-words">{applicant.full_name}</h2>
            <Badge variant={badge.variant}>{badge.label}</Badge>
            {application.earlier_rejections > 0 ? (
              <Badge variant="muted">Từng bị từ chối {application.earlier_rejections} lần</Badge>
            ) : null}
            {applicant.locked_at ? <Badge variant="destructive">Tài khoản đang khóa</Badge> : null}
          </div>
          <p className="truncate text-body-sm text-muted-foreground">{applicant.email}</p>
          <p className="text-caption text-muted-foreground">
            Gửi {formatDate(application.created_at)}
            {pending ? (
              <>
                {" · "}
                <span className={cn(days >= LONG_WAIT_DAYS && "font-semibold text-warning-text")}>
                  {waitLabel(days)}
                </span>
              </>
            ) : application.decided_at ? (
              ` · quyết định ${formatDate(application.decided_at)}`
            ) : null}
            {" · "}tham gia {formatDate(applicant.created_at)} · {application.enrollments_count}{" "}
            khóa đã ghi danh
          </p>
        </div>
      </div>

      {application.motivation ? (
        <blockquote className="rounded-md bg-muted px-3 py-2 text-body whitespace-pre-line break-words">
          {application.motivation}
        </blockquote>
      ) : (
        <p className="text-body-sm text-muted-foreground">Không viết lời giới thiệu.</p>
      )}

      {application.status === "rejected" && application.rejection_reason ? (
        <p className="text-body-sm">
          <span className="font-semibold">Lý do đã gửi: </span>
          <span className="whitespace-pre-line">{application.rejection_reason}</span>
        </p>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      {pending && !writing ? (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => approve.mutate()}
            disabled={busy}
            aria-label={`Duyệt ${applicant.full_name} làm giảng viên`}
          >
            {approve.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Duyệt
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setWriting(true)}
            disabled={busy}
            aria-label={`Từ chối yêu cầu của ${applicant.full_name}`}
          >
            Từ chối…
          </Button>
        </div>
      ) : null}

      {pending && writing ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmed) reject.mutate(trimmed);
          }}
        >
          <Label htmlFor={reasonId}>Lý do từ chối</Label>
          <Textarea
            id={reasonId}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={REASON_MAX_LENGTH}
            rows={3}
            placeholder="Ví dụ: Bạn bổ sung kinh nghiệm dạy hoặc chủ đề định dạy rồi gửi lại nhé."
            autoFocus
          />
          <p className="text-caption text-muted-foreground">
            Người gửi đọc nguyên văn lý do này trong thông báo và trên trang Trở thành giảng viên.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" variant="destructive" disabled={busy || !trimmed}>
              {reject.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Từ chối yêu cầu
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setWriting(false);
                setReason("");
              }}
              disabled={busy}
            >
              Hủy
            </Button>
          </div>
        </form>
      ) : null}
    </article>
  );
}
