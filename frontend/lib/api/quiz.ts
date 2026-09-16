/**
 * Sitting a quiz, from the student's side.
 *
 * Two types describe the same question and the difference between them is the
 * feature: `QuestionForAttempt` is what arrives while the clock is running and
 * has no correct answer on it; `QuestionReview` is what arrives after
 * submitting and does. They are separate types for the same reason the backend
 * has separate response models -- code that renders a running attempt cannot
 * print an answer key, because the value it would print does not exist.
 *
 * The clock is the server's. `seconds_remaining` is computed per response
 * against the server's clock, and the countdown here only ticks that number
 * down between responses; nothing in this file sends a time to the backend,
 * because no endpoint accepts one.
 */

import { apiFetch } from "./client";

/** Matches QuizOut. `question_count` is how a page decides what to offer. */
export interface Quiz {
  id: string;
  lesson_id: string;
  time_limit_s: number | null;
  pass_score: number;
  ai_generated: boolean;
  is_published: boolean;
  question_count: number;
  created_at: string;
  updated_at: string;
}

/** A question as it arrives during an attempt: no answer, no explanation. */
export interface QuestionForAttempt {
  id: string;
  position: number;
  question: string;
  options: string[];
}

/** The same question once the attempt is over, where the key is the point. */
export interface QuestionReview {
  id: string;
  position: number;
  question: string;
  options: string[];
  your_answer: number | null;
  correct_index: number;
  explanation: string | null;
  is_correct: boolean;
}

/**
 * One attempt. Which fields are filled says which state it is in: `review` is
 * null while it runs, and `seconds_remaining` is null once it is over (or when
 * the quiz has no time limit at all -- `deadline_at` tells those two apart).
 */
export interface Attempt {
  id: string;
  quiz_id: string;
  pass_score: number;
  time_limit_s: number | null;
  started_at: string;
  deadline_at: string | null;
  seconds_remaining: number | null;
  submitted_at: string | null;
  score: number | null;
  passed: boolean | null;
  /** Submitted too late, and scored zero because of it. */
  expired: boolean;
  questions: QuestionForAttempt[];
  review: QuestionReview[] | null;
}

/** One row of the history panel. */
export interface AttemptSummary {
  id: string;
  quiz_id: string;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  passed: boolean | null;
}

export interface AttemptPage {
  items: AttemptSummary[];
  total: number;
  page: number;
  page_size: number;
}

export function getQuizOfLesson(lessonId: string, accessToken: string): Promise<Quiz> {
  return apiFetch<Quiz>(`/api/v1/lessons/${lessonId}/quiz`, { accessToken });
}

/**
 * Start the quiz -- or pick up the attempt already running.
 *
 * Idempotent on the server, which is what lets the page call it on mount
 * without asking first: a refresh resumes the same attempt with the same
 * deadline rather than starting a second clock.
 */
export function startAttempt(accessToken: string, quizId: string): Promise<Attempt> {
  return apiFetch<Attempt>(`/api/v1/quizzes/${quizId}/attempts`, {
    method: "POST",
    accessToken,
  });
}

export function getAttempt(accessToken: string, attemptId: string): Promise<Attempt> {
  return apiFetch<Attempt>(`/api/v1/quiz-attempts/${attemptId}`, { accessToken });
}

/**
 * Hand the answers in. One entry per question, in question order; null for
 * a question left blank.
 *
 * An answer that arrives after the deadline is not an error -- the attempt
 * comes back `expired` with a score of zero, so the page can say what happened
 * instead of showing a failed request.
 */
export function submitAttempt(
  accessToken: string,
  attemptId: string,
  answers: (number | null)[],
): Promise<Attempt> {
  return apiFetch<Attempt>(`/api/v1/quiz-attempts/${attemptId}/submit`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ answers }),
  });
}

export function listAttempts(accessToken: string, quizId: string): Promise<AttemptPage> {
  return apiFetch<AttemptPage>(`/api/v1/quizzes/${quizId}/attempts`, { accessToken });
}
