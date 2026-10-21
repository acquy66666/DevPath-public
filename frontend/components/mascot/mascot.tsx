"use client";

import {
  Component,
  Suspense,
  use,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { reactionFor, typing } from "@/lib/mascot/choreography";
import { MOOD_META, type Mood } from "@/lib/mascot/moods";
import { cn } from "@/lib/utils";

import { ART } from "./art";
import { animateTracks, play } from "./play";

export type MascotSize = "sm" | "md" | "lg";

const SIZE: Record<MascotSize, string> = { sm: "size-12", md: "size-32", lg: "size-50" };

export type MascotProps = {
  mood: Mood;
  /** 48 / 128 / 200 px. Default `md`. */
  size?: MascotSize;
  /**
   * The event this mood answers (a submission id, a quiz attempt id…), or
   * `true` for "the page just opened". Naomi reacts once per event, then goes
   * still. Leave it out for a still pose: an old result, a reopened history.
   */
  event?: string | number | true | null;
  /** `grading` only: share of tests done, 0…1. Lights the laptop's bar. */
  progress?: number;
  /**
   * Decorative by default (`aria-hidden`): the words next to her carry the
   * meaning. Give a label when she is the only one saying it; `true` uses the
   * mood's description.
   */
  label?: string | boolean;
  className?: string;
};

/**
 * Naomi, the DevPath gecko. The still pose is server-rendered markup, so it
 * shows before any script runs; the reaction is Web Animations, started once
 * she is on screen, skipped under `prefers-reduced-motion`. She never takes
 * clicks (`pointer-events: none`) and may spill outside her box when she jumps.
 */
export function Mascot({ mood, size = "md", event = null, progress, label, className }: MascotProps) {
  // A new mood renders in the background: the current drawing stays up until
  // the next one has loaded, instead of blinking out.
  const shown = useDeferredValue(JSON.stringify([mood, event]));
  const [shownMood, shownEvent] = JSON.parse(shown) as [Mood, string | number | true | null];
  const name = label === true ? MOOD_META[mood].label : label || undefined;
  return (
    <span
      data-mascot=""
      data-size={size}
      role={name ? "img" : undefined}
      aria-label={name}
      aria-hidden={name ? undefined : true}
      className={cn("pointer-events-none relative inline-block shrink-0 select-none", SIZE[size], className)}
    >
      <Quiet reset={shown}>
        <Suspense fallback={null}>
          <Stage key={shown} mood={shownMood} event={shownEvent} progress={progress} />
        </Suspense>
      </Quiet>
    </span>
  );
}

/** Start downloading drawings a page is about to need (e.g. the verdicts while grading). */
export function preloadMascot(...moods: Mood[]) {
  for (const mood of moods) void loadArt(mood).catch(() => undefined);
}

// ---------------------------------------------------------------- drawings

const loaded = new Map<Mood, Promise<string>>();

/**
 * One chunk per mood, cached. The promise records its own result the way
 * React's `use()` reads it (`status`, `value`), so a drawing that has loaded
 * renders synchronously instead of suspending again.
 */
function loadArt(mood: Mood): Promise<string> {
  let art = loaded.get(mood);
  if (!art) {
    const next: Promise<string> = ART[mood]().then(
      (m) => {
        Object.assign(next, { status: "fulfilled", value: m.default });
        return m.default;
      },
      (error: unknown) => {
        loaded.delete(mood); // let a later mount try again
        throw error;
      },
    );
    loaded.set(mood, next);
    art = next;
  }
  return art;
}

/**
 * The server reads every drawing synchronously, so server rendering never
 * waits on a chunk: the still pose is in the HTML from the first request after
 * a start. (React may still move a finished boundary to the end of the HTML
 * when the page before it is over 12,800 bytes; an inline script shows it
 * before hydration.) Next replaces `typeof window` at build time, so the
 * browser bundle drops this branch and never contains the module — capture.cjs
 * fails if a chunk holds more than one drawing.
 */
const SERVER_ART: Record<Mood, string> | null =
  typeof window === "undefined"
    ? // eslint-disable-next-line @typescript-eslint/no-require-imports
      (require("./art/server") as typeof import("./art/server")).ART_SYNC
    : null;

// ---------------------------------------------------------------- reduced motion

const REDUCE = "(prefers-reduced-motion: reduce)";
function subscribeReduce(onChange: () => void) {
  const query = window.matchMedia(REDUCE);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReduce, () => window.matchMedia(REDUCE).matches, () => false);
}

// ---------------------------------------------------------------- one drawing, one event

type Phase = "still" | "playing" | "settled";

function Stage({ mood, event, progress }: { mood: Mood; event: string | number | true | null; progress?: number }) {
  const art = SERVER_ART ? SERVER_ART[mood] : use(loadArt(mood));
  const reaction = useMemo(() => reactionFor(mood, MOOD_META[mood]), [mood]);
  const toRest = reaction.settle === "rest";
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<Phase>("still");
  const [restArt, setRestArt] = useState<string | null>(null);
  const box = useRef<HTMLSpanElement>(null);
  const drawing = useRef<HTMLSpanElement>(null);
  const rest = useRef<HTMLSpanElement>(null);
  const started = useRef(false);
  // Reduced motion wins at any moment, even halfway through a reaction.
  const playing = phase === "playing" && !reduced;

  // Wait until she is on screen (and, if she goes back to rest, until that
  // drawing has loaded), then react — once for this event.
  useEffect(() => {
    const el = box.current;
    if (event === null || reduced || started.current || !el) return;
    let live = true;
    const seen = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        seen.disconnect();
        const ready = toRest ? loadArt("rest") : Promise.resolve(null);
        ready.then(
          (restMarkup) => {
            if (!live || started.current) return;
            started.current = true;
            setRestArt(restMarkup);
            setPhase("playing");
          },
          () => undefined, // no resting drawing: she simply stays still
        );
      },
      { threshold: 0.25 },
    );
    seen.observe(el);
    return () => {
      live = false;
      seen.disconnect();
    };
  }, [event, reduced, toRest]);

  useLayoutEffect(() => {
    if (!playing || !drawing.current) return;
    const run = play(drawing.current, reaction, toRest ? (rest.current ?? undefined) : undefined);
    let live = true;
    const done = () => {
      if (!live) return;
      live = false;
      setPhase(toRest ? "settled" : "still");
    };
    run.finished.then(done, () => undefined); // rejected = cancelled by the cleanup below
    // Animations paused or cancelled from outside (dev tools, a test seeking
    // past the end) never report back: do not stay mid-reaction for good.
    const guard = window.setTimeout(done, run.endsAt + 1000);
    return () => {
      live = false;
      window.clearTimeout(guard);
      run.cancel();
    };
  }, [playing, reaction, toRest]);

  // `grading`: light the laptop's bar from the test count, and tap the keys
  // each time a test finishes.
  useLayoutEffect(() => {
    if (mood !== "grading" || progress === undefined || !drawing.current) return;
    const p = Math.min(1, Math.max(0, progress));
    const lit = p >= 1 ? 5 : Math.min(4, Math.ceil(p * 5));
    // The two colours build.cjs draws the bar with.
    drawing.current.querySelectorAll("[data-seg]").forEach((seg, i) => {
      seg.setAttribute("fill", i < lit ? "var(--color-green-600)" : "var(--color-slate-300)");
    });
  }, [mood, progress]);
  const lastProgress = useRef(progress);
  useEffect(() => {
    const moved = progress !== lastProgress.current;
    lastProgress.current = progress;
    if (mood !== "grading" || !moved || reduced || playing || !drawing.current) return;
    const taps = animateTracks(drawing.current, typing());
    return () => taps.forEach((a) => a.cancel());
  }, [mood, progress, reduced, playing]);

  const settled = phase === "settled" && restArt !== null;
  return (
    <span ref={box} data-phase={playing ? "playing" : settled ? "settled" : "still"} data-mood={mood} className="absolute inset-0">
      {settled ? null : <span key="mood" ref={drawing} className="absolute inset-0" dangerouslySetInnerHTML={{ __html: art }} />}
      {restArt !== null && phase !== "still" ? (
        <span
          key="rest"
          ref={rest}
          className="absolute inset-0"
          style={settled ? undefined : { opacity: 0 }}
          dangerouslySetInnerHTML={{ __html: restArt }}
        />
      ) : null}
    </span>
  );
}

/** A drawing that fails to load takes Naomi off the page, never the page itself. */
class Quiet extends Component<{ reset: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(previous: { reset: string }) {
    if (this.state.failed && previous.reset !== this.props.reset) this.setState({ failed: false });
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
