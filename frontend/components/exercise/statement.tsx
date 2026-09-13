"use client";

import ReactMarkdown from "react-markdown";

/**
 * The instructor's problem statement, rendered from markdown.
 *
 * `react-markdown` does not render raw HTML unless a plugin is added to make
 * it, and none is. That matters because this text is written by one user and
 * read by another: a statement containing a `<script>` is displayed as the
 * characters that were typed, which is the correct reading of it.
 *
 * The element styles are spelled out here rather than through a typography
 * plugin. The project's reset strips margins from headings and lists, so
 * without this a statement renders as one undifferentiated wall — and pulling
 * in a plugin to style six tags would be the larger change.
 */
export function Statement({ markdown }: { markdown: string }) {
  return (
    <div className="space-y-3 text-sm leading-relaxed text-pretty">
      <ReactMarkdown
        components={{
          h1: (props) => <h2 className="text-lg font-semibold" {...props} />,
          h2: (props) => <h3 className="text-base font-semibold" {...props} />,
          h3: (props) => <h4 className="font-semibold" {...props} />,
          p: (props) => <p className="whitespace-pre-line" {...props} />,
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
              className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs"
              {...props}
            />
          ),
          blockquote: (props) => (
            <blockquote
              className="border-l-2 pl-3 text-muted-foreground"
              {...props}
            />
          ),
          a: (props) => (
            <a
              className="underline underline-offset-4"
              target="_blank"
              rel="noreferrer noopener"
              {...props}
            />
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
