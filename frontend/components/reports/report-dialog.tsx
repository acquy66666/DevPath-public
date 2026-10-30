"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  REPORT_DETAILS_MAX_LENGTH,
  REPORT_REASONS,
  createReport,
  type ReportReason,
  type ReportTargetType,
} from "@/lib/api/reports";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

const WHAT: Record<ReportTargetType, string> = {
  course: "khóa học này",
  review: "đánh giá này",
  qa_thread: "câu hỏi này",
  qa_reply: "câu trả lời này",
};

/**
 * The dialog behind "Báo cáo", in a chunk of its own: it opens on a click
 * that most visits never make, and Radix Dialog with its focus trap and
 * scroll lock is ~26 KB gzip a course page need not carry up front
 * (Phase 7 performance). `report-button.tsx` mounts it on the first click.
 *
 * Mounted already open; closing tells the button, which unmounts it. Radix
 * hands focus back to the element that had it when the dialog opened --
 * the button that was clicked.
 */
export function ReportDialog({
  targetType,
  targetId,
  onClose,
}: {
  targetType: ReportTargetType;
  targetId: string;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent size="form">
        <ReportForm targetType={targetType} targetId={targetId} />
      </DialogContent>
    </Dialog>
  );
}

function ReportForm({
  targetType,
  targetId,
}: {
  targetType: ReportTargetType;
  targetId: string;
}) {
  const { user, accessToken } = useAuth();
  const pathname = usePathname();
  const detailsId = useId();
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState("");

  const submit = useMutation({
    mutationFn: () =>
      createReport(accessToken as string, {
        target_type: targetType,
        target_id: targetId,
        reason: reason as ReportReason,
        details: details.trim() || null,
      }),
  });

  if (user === null || accessToken === null) {
    return (
      <>
        <DialogHeader>
          <DialogTitle>Đăng nhập để báo cáo</DialogTitle>
          <DialogDescription>
            Mỗi báo cáo gắn với một tài khoản, để quản trị viên liên hệ được khi cần và
            để hàng đợi không bị spam.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button asChild>
            <Link href={`/dang-nhap?next=${encodeURIComponent(pathname)}`}>Đăng nhập</Link>
          </Button>
        </DialogFooter>
      </>
    );
  }

  // "Already reported" is a success from where the reader stands: the admin
  // has their complaint either way.
  const alreadyReported =
    submit.error instanceof ApiError && submit.error.code === "ALREADY_REPORTED";

  if (submit.isSuccess || alreadyReported) {
    return (
      <>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-primary" aria-hidden />
            {alreadyReported ? "Bạn đã báo cáo nội dung này" : "Đã gửi báo cáo"}
          </DialogTitle>
          <DialogDescription>
            Quản trị viên sẽ xem xét và xử lý. Cảm ơn bạn đã giúp cộng đồng học tập sạch hơn.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button>Đóng</Button>
          </DialogClose>
        </DialogFooter>
      </>
    );
  }

  const needsDetails = reason === "other" && details.trim().length === 0;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (reason === null || needsDetails) return;
    submit.mutate();
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>Báo cáo {WHAT[targetType]}</DialogTitle>
        <DialogDescription>
          Chọn lý do phù hợp nhất. Người viết không biết ai đã báo cáo.
        </DialogDescription>
      </DialogHeader>

      <fieldset className="grid gap-2">
        <legend className="sr-only">Lý do báo cáo</legend>
        {REPORT_REASONS.map((option) => (
          <label
            key={option.value}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm transition-colors hover:bg-muted/50 has-focus-visible:ring-3 has-focus-visible:ring-ring/50",
              reason === option.value && "border-primary bg-primary/5",
            )}
          >
            <input
              type="radio"
              name="report-reason"
              value={option.value}
              checked={reason === option.value}
              onChange={() => setReason(option.value)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              <span className="block font-medium">{option.label}</span>
              <span className="block text-xs text-muted-foreground">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div className="grid gap-1.5">
        <label htmlFor={detailsId} className="text-sm font-medium">
          Mô tả thêm{reason === "other" ? "" : " (không bắt buộc)"}
        </label>
        <Textarea
          id={detailsId}
          value={details}
          onChange={(event) => setDetails(event.target.value)}
          maxLength={REPORT_DETAILS_MAX_LENGTH}
          rows={3}
          placeholder="Điều gì ở nội dung này vi phạm?"
          required={reason === "other"}
        />
      </div>

      {submit.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(submit.error)}</AlertDescription>
        </Alert>
      ) : null}

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            Hủy
          </Button>
        </DialogClose>
        <Button type="submit" disabled={reason === null || needsDetails || submit.isPending}>
          {submit.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Gửi báo cáo
        </Button>
      </DialogFooter>
    </form>
  );
}
