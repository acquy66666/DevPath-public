"use client";

import { Check, FileText, PlayCircle } from "lucide-react";

import type { Curriculum, LessonType } from "@/lib/api/curriculum";
import { cn } from "@/lib/utils";

const TYPE_ICONS: Record<LessonType, typeof PlayCircle> = {
  video: PlayCircle,
  article: FileText,
  quiz: FileText,
  code_exercise: FileText,
};

/** The table of contents while studying: what is done, and what is open now. */
export function LessonList({
  curriculum,
  currentLessonId,
  completedLessonIds,
  onSelect,
}: {
  curriculum: Curriculum;
  currentLessonId: string | null;
  completedLessonIds: Set<string>;
  onSelect: (lessonId: string) => void;
}) {
  return (
    <nav aria-label="Nội dung khóa học" className="overflow-hidden rounded-xl border">
      {curriculum.sections.map((section) => (
        <div key={section.id} className="border-b last:border-b-0">
          <p className="bg-muted/40 px-4 py-2.5 text-sm font-medium">{section.title}</p>

          <ul>
            {section.lessons.map((lesson) => {
              const Icon = TYPE_ICONS[lesson.type] ?? FileText;
              const done = completedLessonIds.has(lesson.id);
              const current = lesson.id === currentLessonId;

              return (
                <li key={lesson.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(lesson.id)}
                    aria-current={current ? "true" : undefined}
                    className={cn(
                      "flex w-full items-center gap-3 border-t px-4 py-2.5 text-left text-sm transition-colors hover:bg-muted/50",
                      current && "bg-muted font-medium",
                    )}
                  >
                    {done ? (
                      <Check className="size-4 shrink-0 text-primary" aria-label="Đã hoàn thành" />
                    ) : (
                      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                    )}
                    <span className="min-w-0 flex-1 truncate">{lesson.title}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
