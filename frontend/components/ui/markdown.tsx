import ReactMarkdown, { type Components, type ExtraProps } from "react-markdown";

import { cn } from "@/lib/utils";

/**
 * Markdown one user wrote for another to read: an exercise statement, an
 * article lesson. One renderer for both, so the two cannot drift apart.
 *
 * `react-markdown` does not render raw HTML unless a plugin is added to make
 * it, and none is. That matters because the author and the reader are
 * different people: a `<script>` in the text is displayed as the characters
 * that were typed, which is the correct reading of it.
 *
 * The element styles are spelled out here rather than through a typography
 * plugin. The project's reset strips margins from headings and lists, so
 * without this the text renders as one undifferentiated wall -- and pulling in
 * a plugin to style a dozen tags would be the larger change.
 *
 * Code is sized in `em`, so the same styles serve a compact statement
 * (`className="text-sm"`) and an article at body size.
 */
export function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3 leading-relaxed text-pretty break-words", className)}>
      <ReactMarkdown components={components}>{children}</ReactMarkdown>
    </div>
  );
}

/**
 * react-markdown hands every component the hast `node` it came from. Spread
 * onto a DOM element, that object comes out as `node="[object Object]"`.
 */
function withoutNode<Props extends ExtraProps>(props: Props): Omit<Props, "node"> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

// Headings sit one level down: the page's own h1 is the lesson title.
const heading = "font-semibold not-first:pt-2";

const components: Components = {
  h1: (props) => <h2 {...withoutNode(props)} className={cn(heading, "text-lg")} />,
  h2: (props) => <h3 {...withoutNode(props)} className={cn(heading, "text-base")} />,
  h3: (props) => <h4 {...withoutNode(props)} className={heading} />,
  h4: (props) => <h5 {...withoutNode(props)} className={heading} />,
  h5: (props) => <h6 {...withoutNode(props)} className={heading} />,
  h6: (props) => <h6 {...withoutNode(props)} className={heading} />,
  // Authors break lines inside a paragraph and expect to see them broken.
  p: (props) => <p {...withoutNode(props)} className="whitespace-pre-line" />,
  ul: (props) => (
    <ul
      {...withoutNode(props)}
      className="list-disc space-y-1 pl-5 marker:text-muted-foreground"
    />
  ),
  ol: (props) => (
    <ol
      {...withoutNode(props)}
      className="list-decimal space-y-1 pl-5 marker:text-muted-foreground"
    />
  ),
  strong: (props) => <strong {...withoutNode(props)} className="font-semibold" />,
  // Keeps the `language-*` class of a fenced block: it names the language.
  code: ({ className, ...props }) => (
    <code
      {...withoutNode(props)}
      className={cn("rounded-xs bg-muted px-1 py-0.5 font-mono text-[0.85em]", className)}
    />
  ),
  // A block's `<code>` is the same component as inline code; inside `<pre>`
  // it drops the chip look instead of drawing a box inside the box.
  pre: (props) => (
    <pre
      {...withoutNode(props)}
      className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-[0.85em] leading-normal [&>code]:rounded-none [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-[1em]"
    />
  ),
  blockquote: (props) => (
    <blockquote
      {...withoutNode(props)}
      className="border-l-2 border-border-strong pl-3 text-muted-foreground"
    />
  ),
  a: (props) => (
    <a
      {...withoutNode(props)}
      className="text-link underline underline-offset-4 hover:decoration-2"
      target="_blank"
      rel="noreferrer noopener"
    />
  ),
};
