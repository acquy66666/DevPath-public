"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Award, CheckCircle2, Circle, Lock } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatRate } from "@/components/instructor/stats/format";
import { TierBodySkeleton } from "@/components/instructor/instructor-skeletons";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getMyTier } from "@/lib/api/instructor-stats";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * The instructor's tier: where they stand, what each step pays, and how far
 * the next one is.
 *
 * Criteria about money -- paid students and revenue -- show only whether they
 * are met: an instructor never sees a money figure (20/10/2026). The rate of
 * each step is shown, as every marketplace surveyed does: a reward nobody can
 * see rewards nobody. Promotion is an admin's decision; meeting every
 * criterion puts the instructor on the admin's review list.
 */
export function MyTier() {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["instructor-tier"],
    queryFn: () => getMyTier(accessToken as string),
    enabled: accessToken !== null,
  });

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/giang-day/thong-ke"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Thống kê giảng dạy
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Cấp giảng viên</h1>
        <p className="text-sm text-muted-foreground">
          Cấp càng cao, phần bạn nhận trên mỗi lượt bán càng lớn. Quản trị viên xét lên cấp dựa
          trên các tiêu chí dưới đây.
        </p>
      </div>

      {query.isPending ? (
        <TierBodySkeleton />
      ) : query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-4">
                <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Award className="size-6" aria-hidden />
                </span>
                <div>
                  <CardDescription>Cấp hiện tại</CardDescription>
                  <CardTitle className="text-xl">
                    {query.data.current.name} · nhận {formatRate(Number(query.data.current.share_rate))}{" "}
                    mỗi lượt bán
                  </CardTitle>
                  {query.data.current.description ? (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {query.data.current.description}
                    </p>
                  ) : null}
                </div>
              </div>
            </CardHeader>
          </Card>

          <ol className="grid gap-2 sm:grid-cols-5" aria-label="Bậc thang cấp giảng viên">
            {query.data.ladder.map((tier) => {
              const here = tier.id === query.data.current.id;
              const passed = tier.rank < query.data.current.rank;
              return (
                <li
                  key={tier.id}
                  aria-current={here ? "step" : undefined}
                  className={cn(
                    "rounded-lg border p-3 text-sm",
                    here && "border-primary bg-primary/5",
                    passed && "bg-muted/40",
                  )}
                >
                  <span className="text-xs text-muted-foreground">Cấp {tier.rank}</span>
                  <span className="block font-semibold">{tier.name}</span>
                  <span className="block tabular-nums">{formatRate(Number(tier.share_rate))}</span>
                </li>
              );
            })}
          </ol>

          {query.data.next ? (
            <Card>
              <CardHeader>
                <CardTitle>Lên “{query.data.next.tier.name}”</CardTitle>
                <CardDescription>
                  {query.data.eligible
                    ? "Bạn đã đạt mọi tiêu chí — quản trị viên sẽ thấy bạn trong danh sách xét lên cấp."
                    : `Đã đạt ${query.data.next.criteria.filter((c) => c.met).length}/${query.data.next.criteria.length} tiêu chí.`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {query.data.next.criteria.map((criterion) => (
                    <li key={criterion.key} className="flex items-start gap-3 py-3 text-sm">
                      {criterion.met ? (
                        <CheckCircle2
                          className="mt-0.5 size-4 shrink-0 text-emerald-600"
                          aria-label="Đạt"
                        />
                      ) : (
                        <Circle
                          className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                          aria-label="Chưa đạt"
                        />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium">{criterion.label}</span>
                        {criterion.value === null ? (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Lock className="size-3" aria-hidden />
                            Tiêu chí về doanh số do quản trị viên đánh giá — chỉ hiện đạt hay chưa.
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            Của bạn: {criterion.value} · Cần: {criterion.threshold}
                          </span>
                        )}
                      </span>
                      <Badge variant={criterion.met ? "default" : "outline"}>
                        {criterion.met ? "Đạt" : "Chưa đạt"}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : (
            <Alert>
              <AlertDescription>Bạn đang ở cấp cao nhất của DevPath.</AlertDescription>
            </Alert>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Lịch sử cấp</CardTitle>
              <CardDescription>
                Mỗi lần đổi cấp kèm lý do của quản trị viên. Lượt bán đã có giữ nguyên tỉ lệ lúc
                bán.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.history.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Chưa có thay đổi nào — mọi giảng viên bắt đầu ở cấp “{query.data.ladder[0].name}”.
                </p>
              ) : (
                <ul className="space-y-3">
                  {query.data.history.map((change) => (
                    <li key={change.created_at} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">
                        {change.from_tier ?? query.data.ladder[0].name} → {change.to_tier}
                        <span className="ml-2 text-xs font-normal text-muted-foreground">
                          {formatDate(change.created_at)}
                        </span>
                      </p>
                      <p className="mt-1 text-muted-foreground">{change.note}</p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
