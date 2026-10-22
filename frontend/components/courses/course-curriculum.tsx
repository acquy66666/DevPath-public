import { ChevronRight, Code2, FileText, ListChecks, Lock, PlayCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Curriculum, LessonSummary, LessonType } from "@/lib/api/curriculum";
import { LESSON_TYPE_LABELS } from "@/lib/courses/curriculum-summary";

const TYPE_ICONS: Record<LessonType, typeof PlayCircle> = {
  video: PlayCircle,
  article: FileText,
  quiz: ListChecks,
  code_exercise: Code2,
};

function LessonRow({ lesson }: { lesson: LessonSummary }) {
  const Icon = TYPE_ICONS[lesson.type] ?? FileText;
  const label = LESSON_TYPE_LABELS[lesson.type] ?? "Bài học";

  return (
    <li className="flex items-center gap-3 border-t px-4 py-2.5 text-body-sm sm:pl-11">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      {/* The type in words from sm: an icon alone does not say "quiz". */}
      <span className="w-24 shrink-0 text-caption text-muted-foreground max-sm:sr-only">{label}</span>
      <span className="min-w-0 flex-1 truncate">{lesson.title}</span>

      {lesson.is_preview ? (
        <Badge variant="secondary" className="shrink-0">
          Học thử
        </Badge>
      ) : (
        <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label="Cần ghi danh để xem" />
      )}
    </li>
  );
}

/**
 * The table of contents, as a visitor sees it before paying.
 *
 * Built on `<details>` rather than a state hook so the whole page stays a
 * Server Component: a crawler reads every lesson title in the HTML even though
 * a reader sees them folded, and opening a section costs no JavaScript. The
 * chapter and lesson count is the page's own line above this.
 */
export function CourseCurriculum({ curriculum }: { curriculum: Curriculum }) {
  const lessonCount = curriculum.sections.reduce((total, section) => total + section.lessons.length, 0);

  if (lessonCount === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-body-sm text-muted-foreground">
        Giảng viên đang xây dựng nội dung cho khóa học này.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      {curriculum.sections.map((section, index) => (
        <details
          key={section.id}
          open={index === 0}
          className="group border-b last:border-b-0 [&_summary::-webkit-details-marker]:hidden"
        >
          <summary className="flex cursor-pointer items-center gap-3 bg-muted px-4 py-3.5 transition-colors duration-fast hover:bg-accent">
            <ChevronRight
              className="size-4 shrink-0 text-muted-foreground transition-transform duration-fast group-open:rotate-90 motion-reduce:transition-none"
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-title">{section.title}</span>
            <span className="shrink-0 text-caption text-muted-foreground">{section.lessons.length} bài</span>
          </summary>

          {section.lessons.length > 0 ? (
            <ul>
              {section.lessons.map((lesson) => (
                <LessonRow key={lesson.id} lesson={lesson} />
              ))}
            </ul>
          ) : (
            <p className="border-t px-4 py-3 text-body-sm text-muted-foreground sm:pl-11">
              Chương này chưa có bài học.
            </p>
          )}
        </details>
      ))}
    </div>
  );
}
