import { GraduationCap, Star, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { CourseCurriculum } from "@/components/courses/course-curriculum";
import { CourseReviews } from "@/components/courses/course-reviews";
import { EnrollButton } from "@/components/courses/enroll-button";
import { SimilarCourses } from "@/components/recommendations/similar-courses";
import { ReportButton } from "@/components/reports/report-button";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api/client";
import { getCourseBySlug, type CourseDetail } from "@/lib/api/courses";
import { getCurriculum } from "@/lib/api/curriculum";
import { getSimilarCourses, type SimilarCourse } from "@/lib/api/recommendations";
import { listCourseReviews } from "@/lib/api/reviews";
import { LEVEL_LABELS, languageLabel } from "@/lib/courses/labels";
import { formatDate, formatDuration, formatPrice } from "@/lib/format";

/**
 * The public page for one course, server-rendered so a crawler reads the whole
 * thing — title, description and every lesson name — in the first response.
 *
 * There is deliberately no `loading.tsx` beside this file, nor in `khoa-hoc/`
 * above it (a loading file wraps every segment below it — the catalogue's
 * skeleton sits in the `(danh-sach)` group for that reason). A Suspense fallback
 * starts the response streaming, and once headers are out the status is fixed
 * at 200; a course that does not exist, or one still waiting for an admin,
 * would then answer 200 with a `noindex` tag instead of a real 404. Checking
 * before anything streams is what buys the honest status code, and on a page
 * whose whole purpose is search visibility that is worth more than a skeleton.
 * Both were added once (13/09/2026) and taken out again at the Phase 5 gate.
 */

/** Roughly what a search result shows before it cuts the description off. */
const META_DESCRIPTION_LIMIT = 160;

/**
 * The course behind this URL, or null when there is none to show.
 *
 * `cache` because both `generateMetadata` and the page itself need it, and
 * without it the same course would be fetched twice per render.
 *
 * The request carries no token: a Server Component cannot reach the refresh
 * cookie, which lives on the backend's origin. So this is always the anonymous
 * view -- exactly what a crawler gets, and the only view this page promises.
 * An instructor's own draft is reachable through the dashboard instead.
 */
const loadCourse = cache(async (slug: string): Promise<CourseDetail | null> => {
  try {
    return await getCourseBySlug(slug);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

/** One row of three beside a `max-w-5xl` page. */
const SIMILAR_LIMIT = 3;

/**
 * The "Khóa học tương tự" row, or none. A failure here is swallowed on
 * purpose: it is a suggestion under the page, and letting it throw would put
 * the whole course page behind `error.tsx` for the sake of a sidebar.
 */
async function loadSimilar(courseId: string): Promise<SimilarCourse[]> {
  try {
    return (await getSimilarCourses(courseId, SIMILAR_LIMIT)).items;
  } catch (error) {
    console.error("similar courses unavailable", error);
    return [];
  }
}

function metaDescription(course: CourseDetail): string {
  const source = course.subtitle ?? course.description ?? "";
  const text = source.replace(/\s+/g, " ").trim();

  if (text.length === 0) {
    return `Khóa học ${course.title} trên DevPath.`;
  }
  if (text.length <= META_DESCRIPTION_LIMIT) return text;
  return `${text.slice(0, META_DESCRIPTION_LIMIT - 1).trimEnd()}…`;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const course = await loadCourse(slug);

  if (course === null) {
    return { title: "Không tìm thấy khóa học — DevPath", robots: { index: false } };
  }

  const description = metaDescription(course);
  const path = `/khoa-hoc/${course.slug}`;

  return {
    title: `${course.title} — DevPath`,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      title: course.title,
      description,
      url: path,
      siteName: "DevPath",
      locale: "vi_VN",
      images: course.thumbnail_url ? [course.thumbnail_url] : undefined,
    },
    twitter: {
      card: course.thumbnail_url ? "summary_large_image" : "summary",
      title: course.title,
      description,
    },
  };
}

export default async function CourseDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const course = await loadCourse(slug);
  if (course === null) notFound();

  // All in one round trip rather than one after the other: none needs
  // another's answer, and the page cannot paint until it has them all.
  const [curriculum, reviews, similar] = await Promise.all([
    getCurriculum(course.id),
    listCourseReviews(course.id),
    loadSimilar(course.id),
  ]);
  const duration = formatDuration(course.duration_total_s);
  const rated = course.rating_count > 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <nav aria-label="Đường dẫn" className="mb-6 text-sm text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          Trang chủ
        </Link>
        <span className="mx-2" aria-hidden>
          /
        </span>
        <span>{course.category.name}</span>
      </nav>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-10">
          <header className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{course.category.name}</Badge>
              <Badge variant="outline">{LEVEL_LABELS[course.level]}</Badge>
              <Badge variant="outline">{languageLabel(course.language)}</Badge>
            </div>

            <h1 className="text-3xl font-semibold tracking-tight text-balance">
              {course.title}
            </h1>

            {course.subtitle ? (
              <p className="text-lg text-muted-foreground text-pretty">
                {course.subtitle}
              </p>
            ) : null}

            <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <dt className="sr-only">Đánh giá</dt>
                <Star className="size-4" aria-hidden />
                <dd>
                  {rated
                    ? `${course.rating_avg} (${course.rating_count} đánh giá)`
                    : "Chưa có đánh giá"}
                </dd>
              </div>

              <div className="flex items-center gap-1.5">
                <dt className="sr-only">Học viên</dt>
                <Users className="size-4" aria-hidden />
                <dd>{course.students_count} học viên</dd>
              </div>

              {duration ? (
                <div className="flex items-center gap-1.5">
                  <dt className="sr-only">Thời lượng</dt>
                  <GraduationCap className="size-4" aria-hidden />
                  <dd>{duration}</dd>
                </div>
              ) : null}
            </dl>

            <div className="flex items-center gap-3 pt-2">
              <UserAvatar user={course.instructor} className="size-10 text-sm" />
              <div className="text-sm">
                <p className="font-medium">{course.instructor.full_name}</p>
                <p className="text-muted-foreground">Giảng viên</p>
              </div>
            </div>
          </header>

          {course.description ? (
            <section className="space-y-3">
              <h2 className="text-xl font-semibold tracking-tight">Giới thiệu</h2>
              {/* Plain text for now: a rich-text editor would decide the markup,
                  and the builder writes into a textarea. */}
              <p className="whitespace-pre-line text-pretty text-muted-foreground">
                {course.description}
              </p>
            </section>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-xl font-semibold tracking-tight">Nội dung khóa học</h2>
            <CourseCurriculum curriculum={curriculum} />
          </section>

          {/* Server-rendered first page, then a Client Component takes over:
              the reviews are worth crawling, the form behind them needs a
              token the server never sees. */}
          <CourseReviews course={course} initial={reviews} />
        </div>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <div className="overflow-hidden rounded-xl border">
            {course.thumbnail_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={course.thumbnail_url}
                alt=""
                className="aspect-video w-full bg-muted object-cover"
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center bg-muted">
                <GraduationCap className="size-10 text-muted-foreground" aria-hidden />
              </div>
            )}

            <div className="space-y-4 p-5">
              <p className="text-2xl font-semibold">{formatPrice(course.price)}</p>

              <EnrollButton course={course} />

              <dl className="space-y-1.5 border-t pt-4 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Trình độ</dt>
                  <dd>{LEVEL_LABELS[course.level]}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Ngôn ngữ</dt>
                  <dd>{languageLabel(course.language)}</dd>
                </div>
                {duration ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Thời lượng</dt>
                    <dd>{duration}</dd>
                  </div>
                ) : null}
                {course.published_at ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Xuất bản</dt>
                    <dd>{formatDate(course.published_at)}</dd>
                  </div>
                ) : null}
              </dl>

              <div className="border-t pt-2">
                <ReportButton
                  targetType="course"
                  targetId={course.id}
                  authorId={course.instructor.id}
                  label="Báo cáo khóa học"
                  className="-ml-2"
                />
              </div>
            </div>
          </div>
        </aside>
      </div>

      {similar.length > 0 ? (
        <div className="mt-14">
          <SimilarCourses items={similar} />
        </div>
      ) : null}
    </div>
  );
}
