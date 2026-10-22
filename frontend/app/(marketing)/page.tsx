import Link from "next/link";
import { Suspense } from "react";

import { HomeBanners, HomeBannersSkeleton } from "@/components/banners/home-banners";
import { NewestCourses, NewestCoursesSkeleton } from "@/components/courses/newest-courses";
import { RecommendedForYou } from "@/components/recommendations/recommended-for-you";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-16">
      {/* Streamed, like the newest courses below, behind a frame of the
          carousel's size. Nothing at all once it turns out there are no live
          banners: the hero below already opens the page. */}
      <Suspense fallback={<HomeBannersSkeleton />}>
        <HomeBanners />
      </Suspense>

      <section className="max-w-2xl">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Học lập trình bằng cách viết code
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Bài tập được chấm tự động trong môi trường cô lập, gợi ý khóa học theo tiến độ của bạn, và
          trợ giảng AI trả lời trong phạm vi bài giảng.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/khoa-hoc">Khám phá khóa học</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dang-ky">Tạo tài khoản miễn phí</Link>
          </Button>
        </div>
      </section>

      {/* Draws nothing for a signed-out visitor: a recommendation is one
          person's history, and there is no anonymous version of it. */}
      <RecommendedForYou />

      {/* Suspense giữ phần tĩnh của trang được prerender, còn khối gọi API
          thì stream tại thời điểm request — nếu không, danh sách bị nướng
          cứng vào HTML lúc build. */}
      <Suspense fallback={<NewestCoursesSkeleton />}>
        <NewestCourses />
      </Suspense>
    </div>
  );
}
