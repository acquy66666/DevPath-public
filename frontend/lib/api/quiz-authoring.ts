/**
 * The instructor's side of a quiz: writing the questions and the answers.
 *
 * Deliberately not in `quiz.ts`. That file is what a student's page imports,
 * and its `QuestionForAttempt` has no `correct_index` on it — which is the
 * property the whole feature rests on. A type that always carries the answer
 * key belongs on this side of the line, where every call is made by somebody
 * who wrote it.
 */

import { apiFetch } from "./client";
import type { Quiz } from "./quiz";

export type { Quiz } from "./quiz";

/** A question as its author sees it: answer and explanation included. */
export interface Question {
  id: string;
  quiz_id: string;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string | null;
  position: number;
}

export interface QuestionInput {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string | null;
}

export interface QuizSettings {
  /** Seconds, or null for a quiz with no clock. */
  time_limit_s?: number | null;
  pass_score?: number;
  is_published?: boolean;
}

export function createQuiz(
  accessToken: string,
  lessonId: string,
  settings: QuizSettings,
): Promise<Quiz> {
  return apiFetch<Quiz>(`/api/v1/lessons/${lessonId}/quiz`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(settings),
  });
}

/**
 * Change the clock, the pass mark, or whether students can see it.
 *
 * Sending `time_limit_s: null` removes the clock; leaving the key out leaves
 * it alone. The backend tells those apart by which keys arrive, so callers
 * must not "helpfully" fill in the fields they are not changing.
 */
export function updateQuiz(
  accessToken: string,
  quizId: string,
  settings: QuizSettings,
): Promise<Quiz> {
  return apiFetch<Quiz>(`/api/v1/quizzes/${quizId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(settings),
  });
}

export function listQuestions(accessToken: string, quizId: string): Promise<Question[]> {
  return apiFetch<Question[]>(`/api/v1/quizzes/${quizId}/questions`, { accessToken });
}

export function addQuestion(
  accessToken: string,
  quizId: string,
  input: QuestionInput,
): Promise<Question> {
  return apiFetch<Question>(`/api/v1/quizzes/${quizId}/questions`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateQuestion(
  accessToken: string,
  questionId: string,
  input: Partial<QuestionInput>,
): Promise<Question> {
  return apiFetch<Question>(`/api/v1/quiz-questions/${questionId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteQuestion(accessToken: string, questionId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/quiz-questions/${questionId}`, {
    method: "DELETE",
    accessToken,
  });
}
