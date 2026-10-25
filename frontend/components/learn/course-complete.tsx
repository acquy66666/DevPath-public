"use client";

import { useQuery } from "@tanstack/react-query";
import { Award, ChevronDown } from "lucide-react";
import Link from "next/link";

import { Mascot } from "@/components/mascot/mascot";
import { buttonVariants } from "@/components/ui/button";
import { getNextCourses } from "@/lib/api/recommendations";
import { cn } from "@/lib/utils";

/** Where "Học tiếp theo" sits under the lesson, for the banner to jump to. */
export const NEXT_COURSES_ID = "hoc-tiep-theo";

/**
 * The course is finished: Naomi in her graduation cap, the certificate, and
 * the courses to take next (reaction map, design doc §5: `graduate`).
 *
 * A certificate is a reward, so this is the one card on the page in the
 * reward tint. Naomi reacts once, and only when the last lesson was ticked
 * while the page was open (`reactTo`); a finished course opened again is a
 * still picture.
 *
 * "Học tiếp theo" asks the same query the block under the lesson does -- one
 * request between the two -- and is left out when there is nothing to show.
 */
export function CourseComplete({
  courseId,
  courseTitle,
  accessToken,
  certificateCode,
  reactTo,
}: {
  courseId: string;
  courseTitle: string;
  accessToken: string;
  certificateCode: string | null;
  reactTo: string | null;
}) {
  const next = useQuery({
    queryKey: ["next-courses", courseId],
    queryFn: () => getNextCourses(accessToken, courseId, 3),
  });
  const hasNext = (next.data?.items.length ?? 0) > 0;

  return (
    <section
      aria-labelledby="hoan-thanh-khoa"
      className="@container rounded-lg bg-reward-soft"
    >
      <div className="flex flex-col items-center gap-4 p-5 text-center @xl:flex-row @xl:gap-7 @xl:py-5 @xl:pr-7 @xl:pl-5 @xl:text-left">
        <Mascot mood="graduate" event={reactTo} className="size-24 @xl:size-28" />
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <h2 id="hoan-thanh-khoa" className="text-h3 text-reward-foreground">
            Bạn đã hoàn thành khóa học
          </h2>
          <p className="text-body text-reward-foreground">
            {certificateCode
              ? `Chứng chỉ “${courseTitle}” mang tên bạn đã được cấp. Gửi đường dẫn cho bất kỳ ai, họ mở ra là kiểm tra được.`
              : `Bạn đã xong mọi bài của “${courseTitle}”.`}
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {certificateCode ? (
            <Link href={`/cert/${certificateCode}`} className={cn(buttonVariants(), "h-10")}>
              <Award aria-hidden />
              Xem chứng chỉ
            </Link>
          ) : null}
          {hasNext ? (
            <a href={`#${NEXT_COURSES_ID}`} className={cn(buttonVariants({ variant: "outline" }), "h-10")}>
              Học tiếp theo
              <ChevronDown aria-hidden />
            </a>
          ) : null}
        </div>
      </div>
    </section>
  );
}
