"use client";

import { ArrowRight } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { citationNumber, remarkCitations } from "@/lib/chat/citations";
import { cn } from "@/lib/utils";

/** A lesson an answer cites as `[number]`. */
export interface CitedLesson {
  number: number;
  lessonId: string;
  /** Null when the lesson is no longer in the course. */
  title: string | null;
  sectionTitle: string | null;
}

/**
 * An answer from the assistant: markdown, with each `[n]` drawn as a small
 * button that opens lesson n.
 *
 * No raw HTML, for the reason `Markdown` gives: this is a model's output
 * over text other people wrote, and a `<script>` in either must read as the
 * characters it is. Ordinary links open in a new tab so the chat -- and the
 * video beside it -- stay where they are.
 */
export function ChatMarkdown({
  content,
  cited,
  onOpenLesson,
}: {
  content: string;
  cited: CitedLesson[];
  onOpenLesson: (lessonId: string) => void;
}) {
  const byNumber = new Map(cited.map((lesson) => [lesson.number, lesson]));
  const known = new Set(byNumber.keys());

  return (
    <div className="space-y-2 text-body-sm leading-[1.375rem] text-pretty break-words">
      <ReactMarkdown
        remarkPlugins={[[remarkCitations, { known }]]}
        components={{
          // A heading in a chat bubble is emphasis, not structure: one size.
          h1: (props) => <h4 className="font-semibold" {...props} />,
          h2: (props) => <h4 className="font-semibold" {...props} />,
          h3: (props) => <h4 className="font-semibold" {...props} />,
          ul: (props) => <ul className="list-disc space-y-1 pl-5" {...props} />,
          ol: (props) => <ol className="list-decimal space-y-1 pl-5" {...props} />,
          strong: (props) => <strong className="font-semibold" {...props} />,
          code: (props) => (
            <code
              className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
              {...props}
            />
          ),
          pre: (props) => (
            <pre
              className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs [&_code]:bg-transparent [&_code]:p-0"
              {...props}
            />
          ),
          blockquote: (props) => (
            <blockquote className="border-l-2 pl-3 text-muted-foreground" {...props} />
          ),
          a: ({ href, children }) => {
            const number = citationNumber(href);
            if (number === null) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="underline underline-offset-4"
                >
                  {children}
                </a>
              );
            }

            const lesson = byNumber.get(number);
            return (
              <CitationChip
                number={number}
                lesson={lesson}
                onOpen={() => lesson && onOpenLesson(lesson.lessonId)}
              />
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/**
 * The lessons an answer cited, by number, each opening its lesson. What the
 * chips in the text point at, readable without hunting for the chips.
 */
export function SourceList({
  cited,
  currentLessonId,
  onOpenLesson,
}: {
  cited: CitedLesson[];
  currentLessonId: string | null;
  onOpenLesson: (lessonId: string) => void;
}) {
  if (cited.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-eyebrow text-muted-foreground uppercase">Nguồn trong khóa học</p>
      <ul className="flex flex-col gap-1.5">
        {[...cited]
          .sort((a, b) => a.number - b.number)
          .map((lesson) => {
            const here = lesson.lessonId === currentLessonId;
            return (
              <li key={lesson.number}>
                <button
                  type="button"
                  onClick={() => onOpenLesson(lesson.lessonId)}
                  disabled={lesson.title === null}
                  className="flex w-full items-center gap-2.5 rounded-md border bg-background px-2.5 py-2 text-left transition-colors duration-fast hover:not-disabled:bg-accent disabled:cursor-not-allowed"
                >
                  <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-sm bg-secondary px-1 font-mono text-[0.6875rem] font-semibold text-secondary-foreground">
                    {lesson.number}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span
                      className={cn(
                        "truncate text-[0.8125rem] leading-[1.125rem] font-semibold",
                        lesson.title === null && "font-normal text-muted-foreground italic",
                      )}
                    >
                      {lesson.title ?? "Bài học không còn trong khóa"}
                    </span>
                    {lesson.sectionTitle ? (
                      <span className="truncate text-caption text-muted-foreground">
                        {lesson.sectionTitle}
                      </span>
                    ) : null}
                  </span>
                  {lesson.title === null ? null : here ? (
                    <span className="shrink-0 text-caption text-muted-foreground">Đang xem</span>
                  ) : (
                    <span className="inline-flex shrink-0 items-center gap-1 text-caption font-semibold text-link">
                      Mở bài
                      <ArrowRight className="size-3.5" aria-hidden />
                    </span>
                  )}
                </button>
              </li>
            );
          })}
      </ul>
    </div>
  );
}

export function CitationChip({
  number,
  lesson,
  onOpen,
  className,
}: {
  number: number;
  lesson: CitedLesson | undefined;
  onOpen: () => void;
  className?: string;
}) {
  const gone = !lesson || lesson.title === null;
  const label = gone
    ? `Nguồn ${number}: bài học không còn trong khóa`
    : `Nguồn ${number}: mở bài “${lesson.title}”`;

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={gone}
      title={label}
      aria-label={label}
      className={cn(
        "mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-sm bg-secondary px-1 align-[1px] font-mono text-[0.6875rem] leading-5 font-semibold text-secondary-foreground transition-colors duration-fast hover:not-disabled:bg-secondary-hover disabled:bg-muted disabled:text-muted-foreground",
        className,
      )}
    >
      {number}
    </button>
  );
}
