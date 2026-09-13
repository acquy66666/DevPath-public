/**
 * Client-side copies of the limits in `backend/app/models/grading.py`.
 *
 * The CHECK constraints in the database are the real ceiling and Pydantic is
 * the real gate; these exist so the message lands next to the field instead of
 * arriving as a 422 banner. When the backend's numbers change, these are the
 * ones that go stale -- they are duplicated deliberately, not derived.
 */

export const MIN_TIME_LIMIT_MS = 100;
export const MAX_TIME_LIMIT_MS = 10_000;
export const MIN_MEMORY_LIMIT_MB = 16;
export const MAX_MEMORY_LIMIT_MB = 512;

export const DEFAULT_TIME_LIMIT_MS = 2000;
export const DEFAULT_MEMORY_LIMIT_MB = 256;

export function validateStatement(value: string): string | null {
  if (!value.trim()) return "Vui lòng nhập đề bài";
  return null;
}

/** `what` is a Vietnamese noun phrase; the field is text so it can be cleared. */
function validateWholeNumber(
  value: string,
  what: string,
  min: number,
  max: number,
  unit: string,
): string | null {
  const raw = value.trim();
  if (!raw) return `Vui lòng nhập ${what}`;
  if (!/^\d+$/.test(raw)) return `${what} chỉ gồm chữ số`;

  const parsed = Number(raw);
  if (parsed < min || parsed > max) {
    return `${what} phải trong khoảng ${min}–${max} ${unit}`;
  }
  return null;
}

export function validateTimeLimit(value: string): string | null {
  return validateWholeNumber(
    value,
    "Giới hạn thời gian",
    MIN_TIME_LIMIT_MS,
    MAX_TIME_LIMIT_MS,
    "ms",
  );
}

export function validateMemoryLimit(value: string): string | null {
  return validateWholeNumber(
    value,
    "Giới hạn bộ nhớ",
    MIN_MEMORY_LIMIT_MB,
    MAX_MEMORY_LIMIT_MB,
    "MB",
  );
}

/** No upper bound in the schema; the constraint is simply `> 0`. */
export function validateScoreWeight(value: string): string | null {
  const raw = value.trim();
  if (!raw) return "Vui lòng nhập trọng số";
  if (!/^\d+$/.test(raw) || Number(raw) < 1) {
    return "Trọng số là số nguyên từ 1 trở lên";
  }
  return null;
}
