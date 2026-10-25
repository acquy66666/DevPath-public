import type { Curriculum, LessonSummary } from "@/lib/api/curriculum";

/**
 * Where a lesson sits in its course, worked out from the table of contents
 * already on the learning page: no request of its own.
 */
export interface LessonPlace {
  /** 1-based, as the page writes it: "Chương 3". */
  sectionNumber: number;
  sectionTitle: string;
  /** 1-based inside its section: "Bài 2/6". */
  lessonNumber: number;
  sectionLessonCount: number;
  /** The lesson before and after in reading order, across sections. */
  previous: LessonSummary | null;
  next: LessonSummary | null;
  /**
   * The first lesson of the section, where "Ôn lại chương N" after a weak
   * quiz goes; null when this lesson is the first.
   */
  sectionStart: LessonSummary | null;
}

export function locateLesson(curriculum: Curriculum, lessonId: string | null): LessonPlace | null {
  if (lessonId === null) return null;
  const order = curriculum.sections.flatMap((section) => section.lessons);
  const at = order.findIndex((lesson) => lesson.id === lessonId);
  if (at === -1) return null;

  const sectionIndex = curriculum.sections.findIndex((section) =>
    section.lessons.some((lesson) => lesson.id === lessonId),
  );
  const section = curriculum.sections[sectionIndex];
  return {
    sectionNumber: sectionIndex + 1,
    sectionTitle: section.title,
    lessonNumber: section.lessons.findIndex((lesson) => lesson.id === lessonId) + 1,
    sectionLessonCount: section.lessons.length,
    previous: order[at - 1] ?? null,
    next: order[at + 1] ?? null,
    sectionStart: section.lessons[0].id === lessonId ? null : section.lessons[0],
  };
}

/** How many lessons of one section are finished, for its row in the contents. */
export function sectionProgress(
  curriculum: Curriculum,
  completedIds: ReadonlySet<string>,
): Map<string, { done: number; total: number }> {
  return new Map(
    curriculum.sections.map((section) => [
      section.id,
      {
        done: section.lessons.filter((lesson) => completedIds.has(lesson.id)).length,
        total: section.lessons.length,
      },
    ]),
  );
}

/**
 * The sections the contents opens on: the one holding the lesson on screen.
 * A long course listed in full pushes the current lesson out of the sticky
 * column, and on a phone pushes everything under the lesson a long way down.
 * With nothing on screen yet, the first section.
 */
export function openSectionsFor(curriculum: Curriculum, lessonId: string | null): Set<string> {
  const holding = curriculum.sections.find((section) =>
    section.lessons.some((lesson) => lesson.id === lessonId),
  );
  const first = holding ?? curriculum.sections[0];
  return new Set(first ? [first.id] : []);
}

/**
 * Words a learner reads in a minute. Counted the way Vietnamese is written,
 * one syllable per space-separated token: about 250 a minute for study text
 * read with attention (a third slower than reading for pleasure).
 */
const SYLLABLES_PER_MINUTE = 250;

/**
 * Minutes to read an article lesson, at least one. Code blocks count like
 * the prose around them -- they are read, often twice -- but the markup
 * itself (fences, `#`, `*`, link targets) is not a word.
 */
export function readingMinutes(markdown: string): number {
  const words = markdown
    .replace(/```[^\n]*/g, " ")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[#*_>`|-]+/g, " ")
    .split(/\s+/)
    .filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
  return Math.max(1, Math.round(words / SYLLABLES_PER_MINUTE));
}

/**
 * Whether "Tiếp tục từ …" is worth saying: a few seconds in is someone who
 * pressed play and left, not a place to come back to; a finished video starts
 * again from the top.
 */
export function resumeAt(lastPositionS: number | undefined, durationS: number | null, finished: boolean): number | null {
  if (finished || !lastPositionS || lastPositionS < 10) return null;
  if (durationS !== null && lastPositionS >= durationS - 1) return null;
  return lastPositionS;
}
