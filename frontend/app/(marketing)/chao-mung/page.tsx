import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { WelcomeHero } from "@/components/account/welcome-hero";
import { CourseCard } from "@/components/courses/course-card";
import { HomeTopics, HomeTopicsSkeleton } from "@/components/home/home-topics";
import { CourseBlock, CourseBlockSkeleton } from "@/components/recommendations/course-block";
import { courseTitleFor } from "@/lib/account/course-title";
import { welcomeAction } from "@/lib/account/welcome";
import { listCourses, type CourseCard as Course } from "@/lib/api/courses";
import { safeNextPath } from "@/lib/auth/next-path";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Chào mừng — DevPath",
  description: "Bắt đầu học trên DevPath: chọn khóa, học và nộp bài, giữ nhịp học.",
  robots: { index: false },
};

const STEPS = [
  {
    title: "Chọn một khóa",
    text: "Khóa nào cũng có bài xem trước để học thử. Khóa miễn phí thì đăng ký là học được ngay.",
  },
  {
    title: "Học và nộp bài",
    text: "Bài code được chấm trong sandbox, kết quả từng test hiện ngay. Kẹt chỗ nào thì hỏi trợ giảng AI.",
  },
  {
    title: "Giữ nhịp học",
    text: "Mỗi bài xong được XP. Học mỗi ngày để giữ chuỗi; học hết khóa thì nhận chứng chỉ.",
  },
];

const TOPICS = "Bắt đầu với một chủ đề";
const FREE = "Khóa miễn phí để bắt đầu";
const FREE_HREF = "/khoa-hoc?price_max=0";

/**
 * Where sign-up lands (`/chao-mung?next=…`): Naomi says hello, how learning
 * here works in three steps, and two ways to start -- a topic or a free
 * course. The main button goes back to where the visitor was before signing
 * up, so this page never stands between them and the course they chose.
 */
export default async function WelcomePage({ searchParams }: PageProps<"/chao-mung">) {
  const next = safeNextPath((await searchParams).next);
  const action = welcomeAction(next, await courseTitleFor(next));

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 pt-6 pb-16 md:gap-14 md:pt-12 md:pb-24">
      <WelcomeHero action={action} next={next} />

      <section aria-labelledby="welcome-steps" className="space-y-5">
        <h2 id="welcome-steps" className="text-h2">
          Học trên DevPath thế nào
        </h2>
        <ol className="grid gap-3 md:grid-cols-3 md:gap-5">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3.5 gap-y-1 rounded-lg border bg-card p-4.5 md:flex md:flex-col md:gap-2.5 md:p-6"
            >
              <span
                aria-hidden
                className={cn(
                  "row-span-2 inline-flex size-9 items-center justify-center rounded-full font-bold",
                  index === STEPS.length - 1 ? "bg-reward-soft text-reward-foreground" : "bg-secondary text-secondary-foreground",
                )}
              >
                {index + 1}
              </span>
              <h3 className="text-title">
                <span className="sr-only">Bước {index + 1}: </span>
                {step.title}
              </h3>
              <p className="text-body text-muted-foreground">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <Suspense fallback={<HomeTopicsSkeleton title={TOPICS} />}>
        <HomeTopics title={TOPICS} id="welcome-topics" />
      </Suspense>

      <Suspense fallback={<CourseBlockSkeleton title={FREE} count={3} columns={3} action={<FreeLink />} />}>
        <FreeCourses />
      </Suspense>
    </div>
  );
}

/** Up to three free courses; nothing at all when there are none or the API is down. */
async function FreeCourses() {
  await connection();

  let items: Course[] = [];
  try {
    items = (await listCourses({ price_max: "0", sort: "rating", page_size: 3 })).items;
  } catch {
    return null;
  }
  if (items.length === 0) return null;

  return (
    <CourseBlock title={FREE} columns={3} action={<FreeLink />}>
      {items.map((course) => (
        <CourseCard key={course.id} course={course} />
      ))}
    </CourseBlock>
  );
}

function FreeLink() {
  return (
    <Link href={FREE_HREF} className="text-link underline-offset-4 hover:underline">
      Xem tất cả khóa miễn phí
    </Link>
  );
}
