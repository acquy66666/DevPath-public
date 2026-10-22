import type { Curriculum, LessonType } from "@/lib/api/curriculum";

/** Lesson types in the order a course page lists them. */
export const LESSON_TYPE_ORDER: readonly LessonType[] = ["video", "article", "quiz", "code_exercise"];

export const LESSON_TYPE_LABELS: Record<LessonType, string> = {
  video: "Video",
  article: "Bài đọc",
  quiz: "Quiz",
  code_exercise: "Bài tập code",
};

export interface CurriculumSummary {
  sections: number;
  lessons: number;
  /** Only the types the course has, in `LESSON_TYPE_ORDER`. */
  byType: { type: LessonType; count: number }[];
}

/**
 * What the course is made of, counted from the public table of contents: no
 * request of its own, and nothing the curriculum does not already say.
 */
export function summarizeCurriculum(curriculum: Curriculum): CurriculumSummary {
  const counts = new Map<LessonType, number>();
  let lessons = 0;
  for (const section of curriculum.sections) {
    for (const lesson of section.lessons) {
      counts.set(lesson.type, (counts.get(lesson.type) ?? 0) + 1);
      lessons += 1;
    }
  }
  return {
    sections: curriculum.sections.length,
    lessons,
    byType: LESSON_TYPE_ORDER.filter((type) => counts.has(type)).map((type) => ({
      type,
      count: counts.get(type) as number,
    })),
  };
}
