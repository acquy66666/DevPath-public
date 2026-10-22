import { FileText, ListChecks, Lock, PlayCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Curriculum, LessonSummary, LessonType } from "@/lib/api/curriculum";

const TYPE_ICONS: Record<LessonType, typeof PlayCircle> = {
  video: PlayCircle,
  article: FileText,
  quiz: ListChecks,
  code_exercise: FileText,
};

function countLessons(curriculum: Curriculum): number {
  return curriculum.sections.reduce(
    (total, section) => total + section.lessons.length,
    0,
  );
}

function LessonRow({ lesson }: { lesson: LessonSummary }) {
  const Icon = TYPE_ICONS[lesson.type] ?? FileText;

  return (
    <li className="flex items-center gap-3 border-t px-4 py-2.5 text-sm">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{lesson.title}</span>

      {lesson.is_preview ? (
        <Badge variant="outline" className="shrink-0">
          Học thử
        </Badge>
      ) : (
        <Lock
          className="size-3.5 shrink-0 text-muted-foreground"
          aria-label="Cần ghi danh để xem"
        />
      )}
    </li>
  );
}

/**
 * The table of contents, as a visitor sees it before paying.
 *
 * Built on `<details>` rather than a state hook so the whole page stays a
 * Server Component: a crawler reads every lesson title in the HTML even though
 * a reader sees them folded, and opening a section costs no JavaScript.
 */
export function CourseCurriculum({ curriculum }: { curriculum: Curriculum }) {
  const lessonCount = countLessons(curriculum);

  if (lessonCount === 0) {
    return (
      <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        Giảng viên đang xây dựng nội dung cho khóa học này.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {curriculum.sections.length} chương · {lessonCount} bài học
      </p>

      <div className="overflow-hidden rounded-md border">
        {curriculum.sections.map((section, index) => (
          <details
            key={section.id}
            open={index === 0}
            className="border-b last:border-b-0 [&_summary::-webkit-details-marker]:hidden"
          >
            <summary className="flex cursor-pointer items-center justify-between gap-3 bg-muted/40 px-4 py-3 text-sm font-medium hover:bg-muted/70">
              <span className="min-w-0 truncate">{section.title}</span>
              <span className="shrink-0 text-xs font-normal text-muted-foreground">
                {section.lessons.length} bài
              </span>
            </summary>

            {section.lessons.length > 0 ? (
              <ul>
                {section.lessons.map((lesson) => (
                  <LessonRow key={lesson.id} lesson={lesson} />
                ))}
              </ul>
            ) : (
              <p className="border-t px-4 py-3 text-sm text-muted-foreground">
                Chương này chưa có bài học.
              </p>
            )}
          </details>
        ))}
      </div>
    </div>
  );
}
