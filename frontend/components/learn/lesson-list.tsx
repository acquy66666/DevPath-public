"use client";

import {
  Bookmark,
  Check,
  ChevronDown,
  ChevronRight,
  CodeXml,
  FileText,
  ListChecks,
  PlayCircle,
} from "lucide-react";
import { useState } from "react";

import type { Curriculum, LessonType } from "@/lib/api/curriculum";
import { LESSON_TYPE_LABELS } from "@/lib/courses/curriculum-summary";
import { openSectionsFor, sectionProgress } from "@/lib/learn/position";
import { cn } from "@/lib/utils";

const TYPE_ICONS: Record<LessonType, typeof PlayCircle> = {
  video: PlayCircle,
  article: FileText,
  quiz: ListChecks,
  code_exercise: CodeXml,
};

/**
 * The table of contents while studying: one card, a row per section that
 * folds, and in each open section a row per lesson saying what it is and
 * whether it is done -- in words ("Video · Đã xong"), not only in a tick.
 *
 * It opens on the section of the lesson on screen and keeps whatever else
 * the reader opens. Moving to a lesson in a closed section opens that one
 * too, so the highlighted row is never hidden: the set is adjusted during
 * render when the lesson changes, not in an effect, so there is no frame of
 * the old state first.
 *
 * Long courses scroll inside the card on a laptop, where the column is
 * sticky; on a phone the card is as long as what is open.
 */
export function LessonList({
  curriculum,
  currentLessonId,
  completedLessonIds,
  bookmarkedLessonIds,
  onSelect,
}: {
  curriculum: Curriculum;
  currentLessonId: string | null;
  completedLessonIds: Set<string>;
  bookmarkedLessonIds: Set<string>;
  onSelect: (lessonId: string) => void;
}) {
  const [open, setOpen] = useState(() => openSectionsFor(curriculum, currentLessonId));
  const [seenLessonId, setSeenLessonId] = useState(currentLessonId);
  if (currentLessonId !== seenLessonId) {
    setSeenLessonId(currentLessonId);
    const holding = openSectionsFor(curriculum, currentLessonId);
    if ([...holding].some((id) => !open.has(id))) setOpen(new Set([...open, ...holding]));
  }

  const progress = sectionProgress(curriculum, completedLessonIds);
  const lessonCount = curriculum.sections.reduce((sum, section) => sum + section.lessons.length, 0);

  function toggle(sectionId: string) {
    const next = new Set(open);
    if (next.has(sectionId)) next.delete(sectionId);
    else next.add(sectionId);
    setOpen(next);
  }

  return (
    <nav aria-label="Nội dung khóa học" className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-baseline justify-between gap-3 px-4 py-3.5">
        <h2 className="text-title">Nội dung khóa học</h2>
        {/* "18 bài", never "x/18 bài": the page's progress says that once,
            and the golden-flow test reads it as the one place it is written. */}
        <p className="text-caption text-muted-foreground">
          {curriculum.sections.length} chương · {lessonCount} bài
        </p>
      </div>

      <div className="lg:max-h-[calc(100dvh-13rem)] lg:overflow-y-auto">
        {curriculum.sections.map((section, index) => {
          const expanded = open.has(section.id);
          const count = progress.get(section.id) ?? { done: 0, total: 0 };
          const finished = count.total > 0 && count.done === count.total;
          const panelId = `muc-luc-${section.id}`;

          return (
            <div key={section.id} className="border-t">
              <button
                type="button"
                onClick={() => toggle(section.id)}
                aria-expanded={expanded}
                aria-controls={panelId}
                className="flex min-h-14 w-full items-center gap-2.5 bg-background px-4 py-2.5 text-left transition-colors duration-fast hover:bg-accent"
              >
                {expanded ? (
                  <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                ) : (
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                )}
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-eyebrow text-muted-foreground uppercase">Chương {index + 1}</span>
                  <span className="text-body-sm font-semibold text-foreground">{section.title}</span>
                </span>
                <span
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1 text-caption tabular-nums",
                    finished ? "font-semibold text-success-text" : "text-muted-foreground",
                  )}
                >
                  {finished ? <Check className="size-3.5" strokeWidth={2.5} aria-hidden /> : null}
                  {/* "Đã xong 3/3", never "3/3 bài": that is the course's
                      count, written once at the top. */}
                  <span className="sr-only">Đã xong </span>
                  {count.done}/{count.total}
                </span>
              </button>

              {expanded ? (
                <ul id={panelId}>
                  {section.lessons.map((lesson) => (
                    <LessonRow
                      key={lesson.id}
                      title={lesson.title}
                      type={lesson.type}
                      done={completedLessonIds.has(lesson.id)}
                      current={lesson.id === currentLessonId}
                      bookmarked={bookmarkedLessonIds.has(lesson.id)}
                      onSelect={() => onSelect(lesson.id)}
                    />
                  ))}
                  {section.lessons.length === 0 ? (
                    <li className="border-t border-muted px-4 py-3 text-body-sm text-muted-foreground">
                      Chương này chưa có bài học.
                    </li>
                  ) : null}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function LessonRow({
  title,
  type,
  done,
  current,
  bookmarked,
  onSelect,
}: {
  title: string;
  type: LessonType;
  done: boolean;
  current: boolean;
  bookmarked: boolean;
  onSelect: () => void;
}) {
  const Icon = TYPE_ICONS[type] ?? FileText;
  const state = current ? "Đang học" : done ? "Đã xong" : null;

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={current ? "true" : undefined}
        className={cn(
          "flex min-h-14 w-full items-start gap-3 border-t px-4 py-2.5 text-left transition-colors duration-fast",
          current
            ? "border-secondary-hover bg-secondary text-secondary-foreground"
            : "border-muted bg-card text-foreground hover:bg-accent",
        )}
      >
        {current ? (
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border-2 border-primary">
            <span className="size-2 rounded-full bg-primary" />
          </span>
        ) : done ? (
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Check className="size-3" strokeWidth={3} aria-hidden />
          </span>
        ) : (
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center text-muted-foreground">
            <Icon className="size-4" aria-hidden />
          </span>
        )}
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className={cn("text-body-sm", current && "font-semibold")}>{title}</span>
          <span className={cn("text-caption", current ? "text-link" : "text-muted-foreground")}>
            {LESSON_TYPE_LABELS[type]}
            {state ? ` · ${state}` : null}
          </span>
        </span>
        {bookmarked ? (
          <Bookmark className="mt-1 size-3.5 shrink-0 fill-current text-link" aria-label="Đã đánh dấu" />
        ) : null}
      </button>
    </li>
  );
}
