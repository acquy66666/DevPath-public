import { BookOpen, CheckCircle2, CodeXml, History, ListChecks, PlayCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { LessonType } from "@/lib/api/curriculum";
import { LESSON_TYPE_LABELS } from "@/lib/courses/curriculum-summary";
import { formatTimestamp } from "@/lib/format";
import type { LessonPlace } from "@/lib/learn/position";

const TYPE_ICONS: Record<LessonType, LucideIcon> = {
  video: PlayCircle,
  article: BookOpen,
  quiz: ListChecks,
  code_exercise: CodeXml,
};

/**
 * The top of a lesson: where it sits ("Chương 3 · Rẽ nhánh và vòng lặp ·
 * Bài 2/6"), its title -- the page's h1 -- and a few facts as chips: the kind
 * of lesson with its length, where the video picks up, whether it is done.
 */
export function LessonHeading({
  place,
  title,
  type,
  length,
  resumeAt,
  finished,
}: {
  place: LessonPlace | null;
  title: string;
  type: LessonType;
  /** "08:18" for a video, "1 phút đọc" for an article; null when unknown. */
  length: string | null;
  /** Seconds the video resumes from, when that is worth saying. */
  resumeAt: number | null;
  finished: boolean;
}) {
  const Icon = TYPE_ICONS[type];

  return (
    <div className="flex flex-col gap-2">
      {place ? (
        <p className="text-eyebrow text-muted-foreground uppercase">
          Chương {place.sectionNumber}
          <span className="hidden sm:inline"> · {place.sectionTitle}</span> · Bài {place.lessonNumber}/
          {place.sectionLessonCount}
        </p>
      ) : null}
      <h1 className="text-h2 text-balance sm:text-h1">{title}</h1>
      <ul aria-label="Thông tin bài học" className="flex flex-wrap gap-1.5">
        <Chip icon={Icon}>
          {LESSON_TYPE_LABELS[type]}
          {length ? ` · ${length}` : null}
        </Chip>
        {resumeAt !== null ? <Chip icon={History}>Tiếp tục từ {formatTimestamp(resumeAt)}</Chip> : null}
        {finished ? (
          <Chip icon={CheckCircle2} tone="success">
            Đã hoàn thành
          </Chip>
        ) : null}
      </ul>
    </div>
  );
}

function Chip({
  icon: Icon,
  tone = "muted",
  children,
}: {
  icon: LucideIcon;
  tone?: "muted" | "success";
  children: ReactNode;
}) {
  return (
    <li
      className={
        tone === "success"
          ? "inline-flex h-6.5 items-center gap-1.5 rounded-full bg-success-soft px-2.5 text-caption text-success-text"
          : "inline-flex h-6.5 items-center gap-1.5 rounded-full bg-muted px-2.5 text-caption text-muted-foreground"
      }
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="tabular-nums">{children}</span>
    </li>
  );
}
