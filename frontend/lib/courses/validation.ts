/**
 * Client-side copies of the rules in `backend/app/schemas/courses.py` and
 * `backend/app/schemas/curriculum.py`.
 *
 * The backend stays the authority; these only save a round trip and let the
 * message land next to the field instead of in a banner.
 */

export const TITLE_MAX_LENGTH = 200;
export const SUBTITLE_MAX_LENGTH = 300;

/** `what` is a Vietnamese noun phrase: "tên khóa học", "tên chương"… */
function validateTitle(value: string, what: string): string | null {
  const title = value.trim();
  if (!title) return `Vui lòng nhập ${what}`;
  if (title.length > TITLE_MAX_LENGTH) {
    return `${what[0].toUpperCase()}${what.slice(1)} tối đa ${TITLE_MAX_LENGTH} ký tự`;
  }
  return null;
}

export function validateCourseTitle(value: string): string | null {
  return validateTitle(value, "tên khóa học");
}

export function validateSectionTitle(value: string): string | null {
  return validateTitle(value, "tên chương");
}

export function validateLessonTitle(value: string): string | null {
  return validateTitle(value, "tên bài học");
}

export function validateSubtitle(value: string): string | null {
  if (value.trim().length > SUBTITLE_MAX_LENGTH) {
    return `Mô tả ngắn tối đa ${SUBTITLE_MAX_LENGTH} ký tự`;
  }
  return null;
}

/**
 * The price is a text field so it can be typed and cleared freely; the column
 * behind it is NUMERIC(12,2) and the string is what gets sent, unparsed.
 */
export function validatePrice(value: string): string | null {
  const price = value.trim();
  if (!price) return "Vui lòng nhập giá (0 nếu miễn phí)";
  if (!/^\d+(\.\d{1,2})?$/.test(price)) {
    return "Giá chỉ gồm chữ số, tối đa 2 số lẻ. Ví dụ: 499000";
  }
  return null;
}
