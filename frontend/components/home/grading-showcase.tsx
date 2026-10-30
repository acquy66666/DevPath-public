import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { LazyNaomiStill } from "@/components/mascot/lazy-still";

/** The tests of the example, as the submission page lists them. */
const TESTS = [
  { name: "Test 1", time: "18 ms" },
  { name: "Test 2", time: "21 ms" },
  { name: "Test 3 (ẩn)", time: "19 ms" },
];

/*
 * Syntax colours of the example. Illustration, so the palette rather than the
 * semantic layer -- the same steps the code editor theme would use. Each one
 * is at least 4.5:1 on `card`.
 */
const kw = "text-jade-700";
const fn = "text-blue-700";
const num = "text-rose-700";

/**
 * The home page's picture: one submission, graded. A few lines of Python,
 * three tests passed, the AC verdict -- and Naomi, who just caught the bug.
 *
 * Drawn with the site's own type and tokens instead of a screenshot, so it
 * stays sharp, follows the design system and costs no image request. Naomi
 * is the still pose: the home page has no event to react to.
 */
export function GradingShowcase() {
  return (
    <figure className="min-w-0">
      <figcaption className="sr-only">
        Ví dụ một bài nộp được chấm tự động: cả 3 test đều đúng, 100/100 điểm.
      </figcaption>
      <div aria-hidden className="overflow-hidden rounded-lg border bg-card">
        <div className="flex items-center justify-between gap-3 border-b bg-muted px-4 py-2.5">
          <span className="truncate font-mono text-code-sm text-foreground/80">tong_so_chan.py</span>
          <span className="shrink-0 text-caption text-muted-foreground">Python 3.12</span>
        </div>

        <pre className="overflow-x-auto px-4 py-4 font-mono text-code">
          <Line n={1}>
            <span className={kw}>def</span> <span className={fn}>tong_so_chan</span>(ds):
          </Line>
          <Line n={2}>
            {"    "}
            <span className={kw}>return</span> <span className={fn}>sum</span>(x <span className={kw}>for</span> x{" "}
            <span className={kw}>in</span> ds <span className={kw}>if</span> x % <span className={num}>2</span> =={" "}
            <span className={num}>0</span>)
          </Line>
          <Line n={3} />
          <Line n={4}>
            ds = <span className={fn}>map</span>(<span className={fn}>int</span>, <span className={fn}>input</span>().split())
          </Line>
          <Line n={5}>
            <span className={fn}>print</span>(tong_so_chan(ds))
          </Line>
        </pre>

        <div className="flex items-end gap-3 border-t px-4 pt-3.5 pb-4">
          <div className="min-w-0 flex-1 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-body-sm font-semibold">Kết quả chấm</span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-verdict-ac-soft px-2.5 text-body-sm leading-6 font-semibold text-verdict-ac">
                <Check className="size-3.5 text-verdict-ac-solid" strokeWidth={2.5} />
                <span className="font-mono">AC</span> Đúng · 100/100
              </span>
            </div>
            <ol className="space-y-1.5 text-body-sm text-foreground/80">
              {TESTS.map((test) => (
                <li key={test.name} className="flex items-center gap-2">
                  <Check className="size-3.5 shrink-0 text-verdict-ac-solid" strokeWidth={2.5} />
                  <span className="min-w-0 flex-1 truncate">{test.name} · Đúng</span>
                  <span className="font-mono text-code-sm text-muted-foreground tabular-nums">{test.time}</span>
                </li>
              ))}
            </ol>
          </div>
          <LazyNaomiStill mood="celebrate" className="-mb-2 size-24 shrink-0 sm:size-28" />
        </div>
      </div>
    </figure>
  );
}

/** One line of the listing, numbered in the gutter. */
function Line({ n, children }: { n: number; children?: ReactNode }) {
  return (
    <span className="block whitespace-pre">
      <span className="mr-3 inline-block w-4 text-right text-muted-foreground/70 select-none">{n}</span>
      {children}
    </span>
  );
}
