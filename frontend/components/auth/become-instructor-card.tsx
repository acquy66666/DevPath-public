"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { LazyNaomiStill } from "@/components/mascot/lazy-still";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  applyToTeach,
  getMyInstructorApplication,
  type InstructorApplication,
} from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

/** Same ceiling as `APPLICATION_MOTIVATION_MAX_LENGTH` on the server. */
const MOTIVATION_MAX_LENGTH = 2000;

export const APPLICATION_KEY = ["instructor-application"] as const;

/** The card's frame, the same in every state so the column does not jump. */
function Frame({ children }: { children: ReactNode }) {
  return <div className="space-y-4 rounded-lg border bg-card p-6">{children}</div>;
}

function CardSkeleton() {
  return (
    <div aria-hidden>
      <Frame>
        <div className="flex items-center gap-3">
          <Skeleton className="size-18 shrink-0 rounded-full" />
          <div className="flex-1">
            <SkeletonText size="h3" className="w-2/3" />
            <SkeletonText size="body-sm" className="w-1/3" />
          </div>
        </div>
        <div>
          <SkeletonText />
          <SkeletonText className="w-4/5" />
        </div>
        <Skeleton className="h-11 w-full" />
      </Frame>
    </div>
  );
}

/**
 * The action beside "Trở thành giảng viên": what it says depends on who is
 * reading -- a visitor is asked to sign in, a learner sends an application
 * (or sees where it stands), an instructor is sent to the teaching area, an
 * admin is told why not.
 */
export function BecomeInstructorCard() {
  const { user, status } = useAuth();

  if (status === "loading") return <CardSkeleton />;

  if (user === null) {
    return (
      <Frame>
        <h2 className="text-h3">Đăng nhập để tiếp tục</h2>
        <p className="text-body text-foreground/80">
          Gửi yêu cầu cần biết bạn là ai. Đăng nhập rồi quay lại trang này nhé.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button size="lg" asChild>
            <Link href="/dang-nhap?next=/tro-thanh-giang-vien">Đăng nhập</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/dang-ky?next=/tro-thanh-giang-vien">Tạo tài khoản</Link>
          </Button>
        </div>
      </Frame>
    );
  }

  if (user.role === "instructor") {
    return (
      <Frame>
        <h2 className="text-h3">Bạn đã là giảng viên</h2>
        <p className="text-body text-foreground/80">
          Khóa học, thống kê và hỏi đáp của học viên nằm ở khu giảng dạy.
        </p>
        <Button size="lg" className="w-full" asChild>
          <Link href="/giang-day">Vào khu giảng dạy</Link>
        </Button>
      </Frame>
    );
  }

  if (user.role === "admin") {
    return (
      <Frame>
        <h2 className="text-h3">Tài khoản quản trị</h2>
        <p className="text-body text-foreground/80">
          Quản trị viên đã có mọi quyền của giảng viên, không cần gửi yêu cầu — và đổi sang giảng
          viên sẽ làm mất quyền quản trị.
        </p>
      </Frame>
    );
  }

  return <LearnerApplication name={user.full_name} />;
}

function LearnerApplication({ name }: { name: string }) {
  const { accessToken } = useAuth();
  const application = useQuery({
    queryKey: APPLICATION_KEY,
    queryFn: () => getMyInstructorApplication(accessToken as string),
    enabled: accessToken !== null,
  });

  if (application.isPending) return <CardSkeleton />;

  if (application.isError) {
    return (
      <Frame>
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(application.error)}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => application.refetch()}>
          Thử lại
        </Button>
      </Frame>
    );
  }

  const current = application.data;
  if (current?.status === "pending") return <Pending application={current} />;
  if (current?.status === "approved") return <Approved />;
  return <ApplyForm name={name} rejected={current?.status === "rejected" ? current : null} />;
}

function Pending({ application }: { application: InstructorApplication }) {
  return (
    <Frame>
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-warning-soft text-warning-text">
          <Clock className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="text-h3">Yêu cầu đang chờ duyệt</h2>
          <p className="text-body-sm text-muted-foreground">
            Gửi ngày {formatDate(application.created_at)}
          </p>
        </div>
      </div>
      <p className="text-body text-foreground/80">
        Quản trị viên sẽ xem yêu cầu của bạn. Có kết quả, bạn nhận được thông báo ở chuông trên đầu
        trang. Trong lúc chờ, bạn vẫn học bình thường.
      </p>
      {application.motivation ? (
        <div className="space-y-1">
          <p className="text-body-sm font-semibold">Lời giới thiệu bạn đã gửi</p>
          <blockquote className="rounded-md bg-muted px-3 py-2 text-body-sm whitespace-pre-line break-words">
            {application.motivation}
          </blockquote>
        </div>
      ) : null}
    </Frame>
  );
}

/**
 * Approved, but this session still says "student" (the role was changed by
 * an admin, elsewhere). Re-read the session once so the header and the
 * teaching area see the new role.
 */
function Approved() {
  const router = useRouter();
  const { refreshSession } = useAuth();
  const asked = useRef(false);

  useEffect(() => {
    if (asked.current) return;
    asked.current = true;
    void refreshSession().then(() => router.refresh());
  }, [refreshSession, router]);

  return (
    <Frame>
      <h2 className="text-h3">Yêu cầu đã được duyệt</h2>
      <p className="text-body text-foreground/80">
        Tài khoản của bạn giờ là giảng viên. Khóa học đang học, tiến độ và ghi chú đều giữ nguyên.
      </p>
      <Button size="lg" className="w-full" asChild>
        <Link href="/giang-day">Vào khu giảng dạy</Link>
      </Button>
    </Frame>
  );
}

function ApplyForm({ name, rejected }: { name: string; rejected: InstructorApplication | null }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fieldId = useId();
  const hintId = `${fieldId}-hint`;
  const [motivation, setMotivation] = useState(rejected?.motivation ?? "");

  const mutation = useMutation({
    mutationFn: () => applyToTeach(accessToken as string, motivation),
    onSuccess: (sent) => queryClient.setQueryData(APPLICATION_KEY, sent),
  });

  return (
    <Frame>
      <div className="flex items-center gap-3">
        <LazyNaomiStill mood="wave" size="sm" className="size-18" />
        <div className="min-w-0">
          <h2 className="truncate text-h3">Chào {name}</h2>
          <p className="text-body-sm text-muted-foreground">Tài khoản học viên</p>
        </div>
      </div>

      {rejected?.rejection_reason ? (
        <Alert variant="destructive">
          <AlertTitle>Yêu cầu trước chưa được duyệt</AlertTitle>
          <AlertDescription className="whitespace-pre-line">
            {rejected.rejection_reason}
          </AlertDescription>
        </Alert>
      ) : null}

      <p className="text-body text-foreground/80">
        {rejected
          ? "Bổ sung theo góp ý rồi gửi lại. Quản trị viên sẽ xem lại từ đầu."
          : "Gửi yêu cầu để quản trị viên duyệt. Miễn phí, và khóa học đang học, tiến độ, ghi chú của bạn đều giữ nguyên."}
      </p>

      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={fieldId}>Giới thiệu ngắn về bạn (không bắt buộc)</Label>
          <Textarea
            id={fieldId}
            value={motivation}
            onChange={(event) => setMotivation(event.target.value)}
            maxLength={MOTIVATION_MAX_LENGTH}
            rows={4}
            aria-describedby={hintId}
            placeholder="Ví dụ: Mình dạy Python ở trung tâm 3 năm, muốn mở khóa cho người mới bắt đầu."
          />
          <p id={hintId} className="text-caption text-muted-foreground">
            Kinh nghiệm, chủ đề định dạy, đường dẫn tới bài viết hay dự án của bạn.
          </p>
        </div>

        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
          </Alert>
        ) : null}

        <Button type="submit" size="lg" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang gửi…
            </>
          ) : rejected ? (
            "Gửi lại yêu cầu"
          ) : (
            "Gửi yêu cầu"
          )}
        </Button>
      </form>

      <p className="text-caption text-muted-foreground">
        Được duyệt rồi, khóa học bạn tạo vẫn ở trạng thái nháp và phải qua quản trị viên duyệt trước
        khi hiện công khai.
      </p>
    </Frame>
  );
}
