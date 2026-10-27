"use client";

import { useQuery } from "@tanstack/react-query";

import { SkeletonText } from "@/components/ui/skeleton";
import { getCurriculum } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { curriculumCounts } from "@/lib/instructor/teaching-view";

const ROWS = [
  ["sections", "Chương"],
  ["video", "Video"],
  ["article", "Bài đọc"],
  ["code_exercise", "Bài tập code"],
  ["quiz", "Trắc nghiệm"],
  ["preview", "Bài cho học thử"],
] as const;

/** The curriculum in numbers, beside the editor: the same query the builder reads. */
export function CourseOutlineCard({ courseId }: { courseId: string }) {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["curriculum", courseId],
    queryFn: () => getCurriculum(courseId, accessToken),
    enabled: accessToken !== null,
  });
  const counts = query.data ? curriculumCounts(query.data.sections) : null;

  return (
    <section aria-labelledby="course-outline" className="rounded-lg border bg-card p-5">
      <h2 id="course-outline" className="text-title">
        Mục lục
      </h2>
      <dl className="mt-2.5 grid grid-cols-[1fr_auto] gap-y-2 text-body-sm">
        {ROWS.map(([key, label]) => (
          <div key={key} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right font-semibold tabular-nums">
              {counts ? counts[key] : <SkeletonText size="body-sm" className="w-4" />}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
