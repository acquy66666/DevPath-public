import type { CourseLevel } from "@/lib/api/courses";

/** Shown wherever a level appears: the instructor's form, the public page. */
export const LEVEL_LABELS: Record<CourseLevel, string> = {
  beginner: "Người mới bắt đầu",
  intermediate: "Trung cấp",
  advanced: "Nâng cao",
};

/** Spelled out rather than derived from the object: a `<select>` has an order. */
export const LEVEL_ORDER: CourseLevel[] = ["beginner", "intermediate", "advanced"];

const LANGUAGE_NAMES = new Intl.DisplayNames(["vi"], { type: "language" });

/**
 * "vi" → "Tiếng Việt". Falls back to the code itself for anything the runtime
 * does not recognise, which is better than an empty line on the page.
 */
export function languageLabel(code: string): string {
  try {
    return LANGUAGE_NAMES.of(code) ?? code;
  } catch {
    return code;
  }
}
