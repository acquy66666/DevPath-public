import { ShieldCheck, Sparkles, MessageSquareText } from "lucide-react";
import { Suspense } from "react";

import { HomeBanners, HomeBannersSkeleton } from "@/components/banners/home-banners";
import { NewestCourses } from "@/components/courses/newest-courses";
import { GradingShowcase } from "@/components/home/grading-showcase";
import { HeroActions } from "@/components/home/hero-actions";
import { HomeRecommendations } from "@/components/home/home-recommendations";
import { HomeTopics } from "@/components/home/home-topics";
import { CodeFontPreload } from "@/components/layout/code-font-preload";

/** The three things DevPath does that a plain video course does not. */
const PROMISES = [
  { icon: ShieldCheck, text: "Chấm trong sandbox Docker" },
  { icon: Sparkles, text: "Gợi ý theo tiến độ" },
  { icon: MessageSquareText, text: "Trợ giảng AI trích nguồn bài giảng" },
];

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 pt-10 pb-16 md:gap-16 md:pt-14 md:pb-24">
      <CodeFontPreload />
      {/* The promise on the left, one graded submission on the right: the
          page opens on what the site is for, not on a promotion. */}
      <section className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:gap-12">
        <div className="min-w-0 space-y-5">
          <p className="text-eyebrow text-link uppercase">Học lập trình bằng tiếng Việt</p>
          <h1 className="text-display text-balance">Học lập trình bằng cách viết code</h1>
          <p className="max-w-[34em] text-body-lg text-foreground/80">
            Bài tập được chấm tự động trong môi trường cô lập, gợi ý khóa học theo tiến độ của bạn, và
            trợ giảng AI trả lời trong phạm vi bài giảng.
          </p>
          <HeroActions />
          <ul className="flex flex-wrap gap-x-6 gap-y-3 pt-1 text-body-sm text-foreground/80">
            {PROMISES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-2">
                <Icon className="size-4 shrink-0 text-primary" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <GradingShowcase />
      </section>

      {/* Streamed behind a frame of the carousel's size; nothing at all once
          it turns out there are no live banners. */}
      <Suspense fallback={<HomeBannersSkeleton />}>
        <HomeBanners />
      </Suspense>

      {/* Draws nothing for a signed-out visitor: a recommendation is one
          person's history, and there is no anonymous version of it. */}
      <HomeRecommendations />

      {/* Rendered with the page rather than streamed behind skeletons. The
          catalogue answers in milliseconds, so the skeletons were never seen
          -- yet both they and the real blocks went down in the HTML and the
          RSC payload, and those ~2 KB put the home page's HTML and CSS one
          round trip over on a slow phone (first paint 1.21 s against the
          course page's 0.96 s; Phase 7 performance,
          docs/report/assets/phase-7/performance.md). Like the course page,
          the response now waits for the API; both blocks draw nothing when
          it fails. `connection()` inside them keeps them out of the
          build-time prerender. */}
      <HomeTopics />
      <NewestCourses />
    </div>
  );
}
