"use client";

import { useEffect, useRef, useState } from "react";

import { Mascot, preloadMascot, type MascotSize } from "@/components/mascot/mascot";
import { Button } from "@/components/ui/button";
import { reactionFor } from "@/lib/mascot/choreography";
import { MOODS, MOOD_META, type Mood } from "@/lib/mascot/moods";

const SIZES: MascotSize[] = ["sm", "md", "lg"];
const TESTS = 5;

/** Each "Phát" is a new event: a new id, so the reaction plays once more. */
function useRounds() {
  const [rounds, setRounds] = useState<Partial<Record<Mood, number>>>({});
  const next = (moods: readonly Mood[]) =>
    setRounds((r) => Object.fromEntries([...Object.entries(r), ...moods.map((m) => [m, (r[m] ?? 0) + 1])]));
  return [rounds, next] as const;
}

export function NaomiPreview() {
  const [size, setSize] = useState<MascotSize>("md");
  const [rounds, play] = useRounds();
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <h1 className="text-xl font-semibold tracking-tight">Naomi — mọi mood</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
        Trang chỉ có ở môi trường dev. Mỗi lần bấm “Phát” là một sự kiện mới: Naomi phản ứng một lần rồi đứng yên
        (mood <code>hold</code>) hoặc về tư thế nghỉ (mood <code>rest</code>). Giảm chuyển động đang{" "}
        <strong data-testid="reduced">{reduced ? "bật" : "tắt"}</strong>.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {SIZES.map((s) => (
          <Button key={s} size="sm" variant={s === size ? "default" : "outline"} onClick={() => setSize(s)}>
            {s}
          </Button>
        ))}
        <Button size="sm" variant="secondary" data-testid="play-all" onClick={() => play(MOODS)}>
          Phát tất cả
        </Button>
      </div>

      <GradingFlow />

      <ul className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-4">
        {MOODS.map((mood) => {
          const { settle } = reactionFor(mood, MOOD_META[mood]);
          return (
            <li key={mood} data-testid={`mood-${mood}`} className="flex flex-col items-center gap-2 rounded-lg border p-3">
              {/* Room above her for a jump at size lg. */}
              <div className="flex h-64 w-full items-end justify-center">
                <Mascot mood={mood} size={size} event={rounds[mood] ?? null} />
              </div>
              <p className="font-mono text-sm">{mood}</p>
              <p className="text-center text-xs text-muted-foreground">{MOOD_META[mood].label}</p>
              <p className="text-xs text-muted-foreground">sau phản ứng: {settle === "rest" ? "về nghỉ" : "giữ dáng"}</p>
              <Button size="xs" variant="outline" data-testid={`play-${mood}`} onClick={() => play([mood])}>
                Phát
              </Button>
            </li>
          );
        })}
      </ul>

      <section className="mt-8">
        <h2 className="font-medium">Không chặn thao tác</h2>
        <p className="text-sm text-muted-foreground">Naomi nằm đè lên nút; nút vẫn bấm được.</p>
        <ClickThrough />
      </section>
    </main>
  );
}

/** The submission page in miniature: grading k/n, then the verdict for the same submission. */
function GradingFlow() {
  const [done, setDone] = useState(0);
  const [mood, setMood] = useState<Mood>("grading");
  const [submission, setSubmission] = useState<number | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearInterval(timer.current), []);

  const start = (verdict: Mood) => {
    window.clearInterval(timer.current);
    preloadMascot(verdict);
    setSubmission((s) => (s ?? 0) + 1);
    setMood("grading");
    setDone(0);
    let k = 0;
    timer.current = window.setInterval(() => {
      k += 1;
      setDone(k);
      if (k === TESTS) {
        window.clearInterval(timer.current);
        window.setTimeout(() => setMood(verdict), 400);
      }
    }, 700);
  };

  return (
    <section className="mt-6 flex flex-wrap items-center gap-4 rounded-lg border p-4" data-testid="flow">
      <Mascot mood={mood} size="md" event={submission} progress={done / TESTS} label />
      <div className="space-y-2">
        <p className="text-sm">
          Nộp bài thử: chấm {done}/{TESTS} test rồi ra verdict, cùng một mã bài nộp.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" data-testid="flow-ac" onClick={() => start("celebrate")}>
            Nộp (AC)
          </Button>
          <Button size="sm" variant="outline" data-testid="flow-wa" onClick={() => start("partial")}>
            Nộp (WA)
          </Button>
          <Button size="sm" variant="outline" data-testid="flow-tle" onClick={() => start("sleepy")}>
            Nộp (TLE)
          </Button>
        </div>
      </div>
    </section>
  );
}

function ClickThrough() {
  const [clicks, setClicks] = useState(0);
  return (
    <div className="relative mt-3 inline-block">
      <Button data-testid="under" className="h-32 w-56" onClick={() => setClicks((c) => c + 1)}>
        Đã bấm {clicks} lần
      </Button>
      <Mascot mood="wave" size="md" event={clicks || true} className="absolute top-0 left-12" />
    </div>
  );
}
