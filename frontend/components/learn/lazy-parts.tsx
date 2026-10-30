"use client";

import dynamic from "next/dynamic";

import { QuizSkeleton } from "@/components/quiz/quiz-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The parts of the learning page that only some lessons, or some clicks, need
 * -- each in a chunk of its own, so a video lesson's first load carries the
 * player and the contents and not the editor, the quiz, the Markdown
 * renderer, the assistant or the class's questions. Each stands in with the
 * frame its own loading state draws, so nothing moves when the code lands.
 */

/** Started early by the page as soon as the contents say the lesson is an article. */
export const loadMarkdown = () => import("@/components/ui/markdown");

export const Markdown = dynamic(() => loadMarkdown().then((m) => m.Markdown), {
  loading: () => <Skeleton className="h-64 w-full max-w-[68ch]" />,
});

export const ExerciseWorkspace = dynamic(
  () => import("@/components/exercise/exercise-workspace").then((m) => m.ExerciseWorkspace),
  { loading: () => <Skeleton className="h-96 rounded-lg" /> },
);

export const QuizWorkspace = dynamic(
  () => import("@/components/quiz/quiz-workspace").then((m) => m.QuizWorkspace),
  { loading: () => <QuizSkeleton /> },
);

export const QaPanel = dynamic(() => import("@/components/qa/qa-panel").then((m) => m.QaPanel), {
  loading: () => (
    <div className="flex flex-col gap-2.5" aria-hidden>
      <Skeleton className="h-28 rounded-lg" />
      <Skeleton className="h-28 rounded-lg" />
    </div>
  ),
});

/** Built the first time its tab is opened; most visits never open it. */
export const ChatPanel = dynamic(() => import("@/components/chat/chat-panel").then((m) => m.ChatPanel), {
  loading: () => <Skeleton className="h-96 rounded-lg" />,
});

/** Under a finished course only. */
export const NextCourses = dynamic(
  () => import("@/components/recommendations/next-courses").then((m) => m.NextCourses),
);
