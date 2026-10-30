import {
  Award,
  CalendarDays,
  Clock,
  Code2,
  FileText,
  ListChecks,
  MessageSquareText,
  PlayCircle,
  Star,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache, type ReactNode } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { CourseCover } from "@/components/courses/course-cover";
import { CourseCurriculum } from "@/components/courses/course-curriculum";
import { CourseReviews } from "@/components/courses/course-reviews";
import { EnrollButton } from "@/components/courses/enroll-button";
import { SimilarCourses } from "@/components/recommendations/similar-courses";
import { ReportButton } from "@/components/reports/report-button";
import { Markdown } from "@/components/ui/markdown";
import { ApiError } from "@/lib/api/client";
import { getCourseBySlug, type CourseDetail } from "@/lib/api/courses";
import { getCurriculum, type LessonType } from "@/lib/api/curriculum";
import { getSimilarCourses, type SimilarCourse } from "@/lib/api/recommendations";
import { listCourseReviews } from "@/lib/api/reviews";
import { summarizeCurriculum } from "@/lib/courses/curriculum-summary";
import { LEVEL_LABELS, languageLabel } from "@/lib/courses/labels";
import { formatDate, formatDuration, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CodeFontPreload } from "@/components/layout/code-font-preload";

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
  const summary = summarizeCurriculum(curriculum);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16">
      <CodeFontPreload />
      {/* Three grid items, not two columns: on a phone the price card has to
          come straight after the title -- below the curriculum and the reviews
          nobody finds the button -- while on a wide screen it is the sticky
          right-hand column beside both. */}
      <div className="grid gap-x-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* The head sits on a band of `card` that runs the full width of the
            window: a spread shadow paints it, clipped top and bottom to the
            header itself, so the band needs no wrapper outside this grid and
            the price card can still overlap it. */}
        <header className="min-w-0 space-y-4 bg-card py-8 shadow-[0_0_0_100vmax_var(--card),0_1px_0_100vmax_var(--border)] [clip-path:inset(0_-100vmax_-1px)] lg:col-start-1 lg:row-start-1 lg:pb-10">
          <nav aria-label="Đường dẫn" className="text-body-sm text-muted-foreground">
            <Link href="/khoa-hoc" className="hover:text-foreground hover:underline hover:underline-offset-4">
              Khóa học
            </Link>
            <span className="mx-2" aria-hidden>
              /
            </span>
            <Link
              href={`/khoa-hoc?category_id=${encodeURIComponent(course.category.id)}`}
              className="hover:text-foreground hover:underline hover:underline-offset-4"
            >
              {course.category.name}
            </Link>
          </nav>

          <p className="text-eyebrow text-link uppercase">
            {LEVEL_LABELS[course.level]} · {languageLabel(course.language)}
          </p>

          <h1 className="text-h1 text-balance">{course.title}</h1>

          {course.subtitle ? (
            <p className="max-w-[40em] text-body-lg text-pretty text-foreground/80">{course.subtitle}</p>
          ) : null}

          <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 text-body-sm text-foreground/80">
            <Fact label="Đánh giá" icon={Star} iconClassName={rated ? "fill-reward-mark text-reward-mark" : undefined}>
              {rated ? `${formatRating(course.rating_avg)} (${course.rating_count} đánh giá)` : "Chưa có đánh giá"}
            </Fact>
            <Fact label="Học viên" icon={Users}>
              {course.students_count} học viên
            </Fact>
            {duration ? (
              <Fact label="Thời lượng" icon={Clock}>
                {duration}
              </Fact>
            ) : null}
            {course.published_at ? (
              <Fact label="Xuất bản" icon={CalendarDays}>
                Xuất bản {formatDate(course.published_at)}
              </Fact>
            ) : null}
          </dl>

          <div className="flex items-center gap-3 pt-1">
            <UserAvatar user={course.instructor} className="size-10 text-body-sm" />
            <div className="min-w-0">
              <p className="truncate text-title">{course.instructor.full_name}</p>
              <p className="text-caption text-muted-foreground">Giảng viên</p>
            </div>
          </div>
        </header>

        <aside
          aria-label="Ghi danh khóa học"
          className="mt-6 lg:sticky lg:top-8 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-8 lg:self-start"
        >
          <div className="overflow-hidden rounded-lg border bg-card">
            <CourseCover thumbnailUrl={course.thumbnail_url} colorKey={course.id} size="lg" />

            <div className="space-y-4 p-5">
              <p className="text-h1 tabular-nums">{formatPrice(course.price)}</p>

              <EnrollButton course={course} />

              <div className="space-y-2.5 border-t pt-4">
                <p className="text-body-sm font-semibold">Khóa học gồm</p>
                <ul className="space-y-2 text-body-sm text-foreground/80">
                  {summary.byType.map(({ type, count }) => {
                    const Icon = TYPE_ICONS[type];
                    return (
                      <li key={type} className="flex items-center gap-2.5">
                        <Icon className="size-4 shrink-0 text-primary" aria-hidden />
                        {includes(type, count, duration)}
                      </li>
                    );
                  })}
                  <li className="flex items-center gap-2.5">
                    <MessageSquareText className="size-4 shrink-0 text-primary" aria-hidden />
                    Trợ giảng AI trả lời theo bài giảng
                  </li>
                  <li className="flex items-center gap-2.5">
                    <Award className="size-4 shrink-0 text-primary" aria-hidden />
                    Chứng chỉ khi hoàn thành
                  </li>
                </ul>
              </div>

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

        <div className="min-w-0 space-y-12 pt-10 lg:col-start-1 lg:row-start-2">
          {course.description ? (
            <section aria-labelledby="gioi-thieu" className="space-y-3">
              <h2 id="gioi-thieu" className="text-h2">
                Giới thiệu
              </h2>
              {/* Markdown, as the course builder tells the instructor it is --
                  through the same renderer as the lessons, which shows raw
                  HTML as the characters typed. */}
              <Markdown className="max-w-[40em] text-body-lg text-foreground/85">{course.description}</Markdown>
            </section>
          ) : null}

          <section aria-labelledby="noi-dung" className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 id="noi-dung" className="text-h2">
                Nội dung khóa học
              </h2>
              {summary.lessons > 0 ? (
                <p className="text-body-sm text-muted-foreground">
                  {summary.sections} chương · {summary.lessons} bài học
                </p>
              ) : null}
            </div>
            <CourseCurriculum curriculum={curriculum} />
          </section>

          {/* Server-rendered first page, then a Client Component takes over:
              the reviews are worth crawling, the form behind them needs a
              token the server never sees. */}
          <CourseReviews course={course} initial={reviews} />
        </div>
      </div>

      {similar.length > 0 ? (
        <div className="mt-16">
          <SimilarCourses items={similar} />
        </div>
      ) : null}
    </div>
  );
}

const TYPE_ICONS: Record<LessonType, LucideIcon> = {
  video: PlayCircle,
  article: FileText,
  quiz: ListChecks,
  code_exercise: Code2,
};

/** One line of "Khóa học gồm", counted from the curriculum. */
function includes(type: LessonType, count: number, duration: string | null): string {
  switch (type) {
    case "video":
      return duration ? `${count} video · ${duration}` : `${count} video`;
    case "article":
      return `${count} bài đọc`;
    case "quiz":
      return `${count} quiz`;
    case "code_exercise":
      return `${count} bài tập code chấm tự động`;
  }
}

/** Comma decimals, as the design system writes numbers: 4,6. */
function formatRating(value: string): string {
  return Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

/** One fact of the meta line: a hidden term, an icon, the value. */
function Fact({
  label,
  icon: Icon,
  iconClassName,
  children,
}: {
  label: string;
  icon: LucideIcon;
  iconClassName?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <dt className="sr-only">{label}</dt>
      <Icon className={cn("size-4 text-muted-foreground", iconClassName)} aria-hidden />
      <dd>{children}</dd>
    </div>
  );
}
