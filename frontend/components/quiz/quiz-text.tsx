import { Fragment } from "react";

import { splitInlineCode } from "@/lib/quiz/inline-code";
import { cn } from "@/lib/utils";

/**
 * A question, an option or an explanation, with `code` in backticks drawn as
 * code. `codeClassName` gives the code its background when the text sits on
 * `muted` already (the explanation box), where the usual `muted` would vanish.
 */
export function QuizText({ text, codeClassName }: { text: string; codeClassName?: string }) {
  return (
    <>
      {splitInlineCode(text).map((piece, index) =>
        piece.code ? (
          <code
            key={index}
            className={cn("rounded-xs bg-muted px-1.5 py-px font-mono text-[0.9em] font-medium", codeClassName)}
          >
            {piece.text}
          </code>
        ) : (
          <Fragment key={index}>{piece.text}</Fragment>
        ),
      )}
    </>
  );
}

/** "A", "B", "C"…: how an option is called out loud and on the paper. */
export function optionLetter(index: number): string {
  return String.fromCharCode(65 + index);
}
