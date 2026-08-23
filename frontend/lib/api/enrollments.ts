import { apiFetch, ApiError } from "./client";
import type { CourseCard, Page } from "./courses";

/** Mirrors `EnrollmentOut`. No user id: it always describes the caller. */
export interface Enrollment {
  id: string;
  course_id: string;
  source: "free" | "purchase";
  completed_at: string | null;
  created_at: string;
}

/** A row of "Khóa học của tôi". */
export interface EnrolledCourse {
  course: CourseCard;
  enrolled_at: string;
  completed_at: string | null;
}

/**
 * Enrol in a free course.
 *
 * Answers 201 the first time and 200 afterwards; both come back here as the
 * same enrolment, because asking twice is not an error.
 */
export function enrolInCourse(
  accessToken: string,
  courseId: string,
): Promise<Enrollment> {
  return apiFetch<Enrollment>(`/api/v1/courses/${courseId}/enroll`, {
    method: "POST",
    accessToken,
  });
}

/**
 * The caller's enrolment in one course, or null when there is none.
 *
 * A 404 here is an answer, not a failure — "you are not enrolled" is exactly
 * what the button needs to know — so it is turned into null rather than thrown.
 */
export async function getMyEnrollment(
  accessToken: string,
  courseId: string,
): Promise<Enrollment | null> {
  try {
    return await apiFetch<Enrollment>(`/api/v1/courses/${courseId}/enrollment`, {
      accessToken,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function listMyEnrollments(
  accessToken: string,
  page = 1,
): Promise<Page<EnrolledCourse>> {
  return apiFetch<Page<EnrolledCourse>>(`/api/v1/enrollments/me?page=${page}`, {
    accessToken,
  });
}
