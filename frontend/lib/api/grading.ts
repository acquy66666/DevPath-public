import { apiFetch } from "./client";

/**
 * Code exercises and their test cases, from the instructor's side.
 *
 * The backend answers `GET /code-exercises/{id}/test-cases` with two different
 * models depending on who asks: `TestCaseOut` -- what is typed below -- for the
 * instructor who wrote the answer key, and a sample-only model for everyone
 * else. This file is used by the authoring UI, so it types the first one. The
 * student's view arrives with the submission page and must not reuse this type:
 * an `expected_output` that is always present in TypeScript is exactly the
 * assumption that turns a hidden case into a visible one.
 */

export interface CodeExercise {
  id: string;
  lesson_id: string;
  statement_md: string;
  language: string;
  starter_code: string | null;
  time_limit_ms: number;
  memory_limit_mb: number;
  created_at: string;
  updated_at: string;
}

export interface TestCase {
  id: string;
  exercise_id: string;
  input: string;
  expected_output: string;
  is_hidden: boolean;
  position: number;
  score_weight: number;
}

export interface CodeExerciseCreate {
  statement_md: string;
  starter_code?: string | null;
  time_limit_ms?: number;
  memory_limit_mb?: number;
}

export type CodeExerciseUpdate = Partial<CodeExerciseCreate>;

export interface TestCaseCreate {
  input: string;
  expected_output: string;
  is_hidden: boolean;
  score_weight: number;
}

export type TestCaseUpdate = Partial<TestCaseCreate>;

// --- Exercises -------------------------------------------------------------

/** 404 `EXERCISE_NOT_FOUND` when the lesson has no exercise attached yet. */
export function getExerciseOfLesson(
  lessonId: string,
  accessToken?: string | null,
): Promise<CodeExercise> {
  return apiFetch<CodeExercise>(`/api/v1/lessons/${lessonId}/code-exercise`, {
    accessToken,
  });
}

export function createExercise(
  accessToken: string,
  lessonId: string,
  input: CodeExerciseCreate,
): Promise<CodeExercise> {
  return apiFetch<CodeExercise>(`/api/v1/lessons/${lessonId}/code-exercise`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateExercise(
  accessToken: string,
  exerciseId: string,
  input: CodeExerciseUpdate,
): Promise<CodeExercise> {
  return apiFetch<CodeExercise>(`/api/v1/code-exercises/${exerciseId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

// --- Test cases ------------------------------------------------------------

export function listTestCases(
  accessToken: string,
  exerciseId: string,
): Promise<TestCase[]> {
  return apiFetch<TestCase[]>(`/api/v1/code-exercises/${exerciseId}/test-cases`, {
    accessToken,
  });
}

export function createTestCase(
  accessToken: string,
  exerciseId: string,
  input: TestCaseCreate,
): Promise<TestCase> {
  return apiFetch<TestCase>(`/api/v1/code-exercises/${exerciseId}/test-cases`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateTestCase(
  accessToken: string,
  testCaseId: string,
  input: TestCaseUpdate,
): Promise<TestCase> {
  return apiFetch<TestCase>(`/api/v1/test-cases/${testCaseId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteTestCase(
  accessToken: string,
  testCaseId: string,
): Promise<void> {
  return apiFetch<void>(`/api/v1/test-cases/${testCaseId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * The order of every case at once, as it looks after the move.
 *
 * Same shape as the curriculum's reorder calls, and for the same reason: the
 * browser already knows what the list became, and one request cannot leave it
 * half-applied. Positions are what "test case 3 failed" refers to, so they are
 * worth a round trip.
 */
export function reorderTestCases(
  accessToken: string,
  exerciseId: string,
  testCaseIds: string[],
): Promise<TestCase[]> {
  return apiFetch<TestCase[]>(
    `/api/v1/code-exercises/${exerciseId}/test-cases/order`,
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify({ test_case_ids: testCaseIds }),
    },
  );
}
