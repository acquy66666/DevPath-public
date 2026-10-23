import { ImageIcon } from "lucide-react";
import ReactMarkdown, { type Components, type ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";

import { classifyImage, mediaOrigins } from "@/lib/markdown/images";
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
 *
 * GitHub's extensions are on (`remark-gfm`): tables, ~~strikethrough~~, task
 * lists and bare links -- an instructor pasting a table from any Markdown
 * editor expects a table, not a row of pipes.
 *
 * Pictures are drawn only from this platform's own media storage
 * (`lib/markdown/images.ts`); an image anywhere else is shown as a link, so
 * an author cannot learn who reads their text by hiding a picture in it.
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
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
        {children}
      </ReactMarkdown>
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

/** Read once: both are build-time values. */
const MEDIA_ORIGINS = mediaOrigins();

/**
 * Inside a paragraph, so spans only: a `<figure>` in a `<p>` is invalid HTML
 * and a hydration error. The description shows under the picture for
 * sighted readers; screen readers already hear it as the alt text.
 */
function Picture({ src, alt }: { src?: string; alt?: string }) {
  const source = classifyImage(src, MEDIA_ORIGINS);
  const description = alt?.trim() ?? "";

  if (source.kind === "uploading") {
    return (
      <span className="flex items-center gap-2 rounded-md border border-dashed border-border-strong p-4 text-sm text-muted-foreground">
        <ImageIcon className="size-4 shrink-0" aria-hidden />
        Đang tải ảnh lên…
      </span>
    );
  }

  if (source.kind === "external") {
    const label = `Ảnh ngoài: ${description || "không có mô tả"}`;
    return source.href ? (
      <a
        href={source.href}
        target="_blank"
        rel="noreferrer noopener"
        className="inline-flex items-center gap-1 text-link underline underline-offset-4 hover:decoration-2"
      >
        <ImageIcon className="size-4 shrink-0" aria-hidden />
        {label}
      </a>
    ) : (
      <span className="text-muted-foreground">[{label}]</span>
    );
  }

  return (
    <span className="block py-1">
      {/* eslint-disable-next-line @next/next/no-img-element -- bucket URLs of any size, not optimisable here */}
      <img
        src={source.src}
        alt={description}
        loading="lazy"
        decoding="async"
        className="mx-auto block h-auto max-h-[36rem] w-auto max-w-full rounded-md border border-border"
      />
      {description && description !== "Ảnh" ? (
        <span aria-hidden className="mt-1.5 block text-center text-sm text-muted-foreground">
          {description}
        </span>
      ) : null}
    </span>
  );
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
  // A task list (`- [x] …`) carries its own checkbox instead of a bullet.
  ul: ({ className, ...props }) => (
    <ul
      {...withoutNode(props)}
      className={
        className?.includes("contains-task-list")
          ? "space-y-1"
          : "list-disc space-y-1 pl-5 marker:text-muted-foreground"
      }
    />
  ),
  ol: (props) => (
    <ol
      {...withoutNode(props)}
      className="list-decimal space-y-1 pl-5 marker:text-muted-foreground"
    />
  ),
  strong: (props) => <strong {...withoutNode(props)} className="font-semibold" />,
  del: (props) => <del {...withoutNode(props)} className="text-muted-foreground" />,
  hr: (props) => <hr {...withoutNode(props)} className="my-2 border-border" />,
  input: (props) => (
    <input {...withoutNode(props)} className="mr-2 size-4 translate-y-0.5 accent-primary" />
  ),
  img: ({ src, alt }) => <Picture src={typeof src === "string" ? src : undefined} alt={alt} />,
  // `relative`: an `sr-only` inside an `overflow-x-auto` box widens the page
  // unless the box positions it.
  table: (props) => (
    <div className="relative max-w-full overflow-x-auto rounded-md border border-border">
      <table {...withoutNode(props)} className="w-full border-collapse text-[0.95em]" />
    </div>
  ),
  th: (props) => (
    <th
      {...withoutNode(props)}
      className="border-b border-border bg-muted px-3 py-2 text-left font-semibold"
    />
  ),
  td: (props) => (
    <td {...withoutNode(props)} className="border-t border-border px-3 py-2 align-top" />
  ),
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
