import { Suspense } from "react";

import { BackendStatus, BackendStatusSkeleton } from "@/components/backend-status";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-16">
      <section className="max-w-2xl">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Học lập trình bằng cách viết code
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Bài tập được chấm tự động trong môi trường cô lập, gợi ý khóa học theo tiến độ của bạn, và
          trợ giảng AI trả lời trong phạm vi bài giảng.
        </p>
        <div className="mt-8 flex gap-3">
          <Button disabled>Khám phá khóa học</Button>
          <Button variant="outline" disabled>
            Tìm hiểu thêm
          </Button>
        </div>
      </section>

      <section className="max-w-md">
        {/* Suspense giữ phần tĩnh của trang được prerender, còn khối gọi API
            thì stream tại thời điểm request — nếu không, trạng thái backend bị
            nướng cứng vào HTML lúc build. */}
        <Suspense fallback={<BackendStatusSkeleton />}>
          <BackendStatus />
        </Suspense>
      </section>
    </div>
  );
}
