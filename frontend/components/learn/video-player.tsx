"use client";

import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type Ref,
} from "react";

import { NativeSelect } from "@/components/ui/native-select";

/** What the player offers. 1 is first because it is the answer for most people. */
const SPEEDS = [1, 0.75, 1.25, 1.5, 1.75, 2];

/** Remembered across lessons: someone who watches at 1.5× means it every time. */
const SPEED_KEY = "devpath:playback-rate";

/** How often the position is reported while the video is playing. */
const HEARTBEAT_MS = 10_000;

function storedSpeed(): number {
  if (typeof window === "undefined") return 1;
  const saved = Number(window.localStorage.getItem(SPEED_KEY));
  return SPEEDS.includes(saved) ? saved : 1;
}

/**
 * An HLS video that reports where it has got to.
 *
 * The player itself decides nothing: it reports a position and an ending, and
 * the page above it decides what to save. That keeps hls.js -- and the
 * difference between Safari and everything else -- inside this one file.
 *
 * hls.js is imported inside the effect rather than at the top of the module so
 * it is fetched only by a page that actually plays a video, and never on the
 * server, where `window` does not exist.
 */
/** What the page around the player is allowed to ask of it. */
export interface PlayerHandle {
  /** Where the video is right now, in seconds. */
  currentTime: () => number;
  /** Jump to a moment — what clicking the timestamp on a note does. */
  seekTo: (seconds: number) => void;
}

export function VideoPlayer({
  src,
  startAt,
  onProgress,
  onEnded,
  ref,
}: {
  src: string;
  /** Seconds to resume from. Applied once, when the video is ready. */
  startAt: number;
  onProgress: (seconds: number) => void;
  onEnded: () => void;
  ref?: Ref<PlayerHandle>;
}) {
  const video = useRef<HTMLVideoElement>(null);
  // Lazy initialiser, not an effect: this component is only ever mounted after
  // the lesson has been fetched in the browser, so it never renders on the
  // server and there is no hydration to mismatch.
  const [speed, setSpeed] = useState(storedSpeed);
  const [error, setError] = useState<string | null>(null);

  // Held in a ref so the heartbeat effect can call the latest callback without
  // tearing the player down every time the page re-renders.
  const report = useRef(onProgress);
  useEffect(() => {
    report.current = onProgress;
  }, [onProgress]);

  useEffect(() => {
    const element = video.current;
    if (element === null) return;

    let destroy = () => {};
    let cancelled = false;

    // Safari plays HLS by itself, and does it better than any library can --
    // hardware decoding, picture-in-picture, AirPlay. Only the browsers that
    // cannot get the polyfill.
    if (element.canPlayType("application/vnd.apple.mpegurl")) {
      element.src = src;
    } else {
      import("hls.js")
        .then(({ default: Hls }) => {
          if (cancelled || !Hls.isSupported()) {
            if (!cancelled) setError("Trình duyệt này không phát được video HLS.");
            return;
          }
          const hls = new Hls({ enableWorker: true });
          hls.loadSource(src);
          hls.attachMedia(element);
          hls.on(Hls.Events.ERROR, (_event, data) => {
            // Only fatal errors reach the reader: hls.js recovers from most
            // network hiccups by itself, and a message per dropped segment
            // would be noise over a video that is still playing.
            if (data.fatal) setError("Không tải được video. Thử tải lại trang.");
          });
          destroy = () => hls.destroy();
        })
        .catch(() => setError("Không tải được trình phát video."));
    }

    return () => {
      cancelled = true;
      destroy();
    };
  }, [src]);

  // Resume, once the browser knows how long the video is. `startAt` is not in
  // the dependencies on purpose: it changes as the position is saved, and
  // re-seeking to it would fight the person dragging the scrub bar.
  useEffect(() => {
    const element = video.current;
    if (element === null || startAt <= 0) return;

    const seek = () => {
      // Right at the end means "finished", not "resume half a second before
      // the credits" -- start again instead.
      if (element.duration && startAt < element.duration - 1) {
        element.currentTime = startAt;
      }
    };

    element.addEventListener("loadedmetadata", seek, { once: true });
    return () => element.removeEventListener("loadedmetadata", seek);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  useEffect(() => {
    const element = video.current;
    if (element !== null) element.playbackRate = speed;
  }, [speed, src]);

  // The heartbeat, plus the two moments worth saving exactly: pausing, and
  // the tab going away. A hard close can still lose up to one interval, which
  // is the trade for not writing a row every second.
  useEffect(() => {
    const element = video.current;
    if (element === null) return;

    const save = () => {
      if (element.currentTime > 0) report.current(Math.floor(element.currentTime));
    };

    const timer = window.setInterval(() => {
      if (!element.paused && !element.ended) save();
    }, HEARTBEAT_MS);

    const onHidden = () => {
      if (document.visibilityState === "hidden") save();
    };

    element.addEventListener("pause", save);
    document.addEventListener("visibilitychange", onHidden);

    return () => {
      window.clearInterval(timer);
      element.removeEventListener("pause", save);
      document.removeEventListener("visibilitychange", onHidden);
      save();
    };
  }, [src]);

  // Two verbs, no state: the page asks the element directly rather than
  // mirroring a number that changes thirty times a second into React.
  useImperativeHandle(ref, () => ({
    currentTime: () => Math.floor(video.current?.currentTime ?? 0),
    seekTo: (seconds: number) => {
      const element = video.current;
      if (element === null) return;
      element.currentTime = seconds;
      // Jumping to a moment means wanting to watch it.
      void element.play().catch(() => {});
    },
  }), []);

  function changeSpeed(value: number) {
    setSpeed(value);
    window.localStorage.setItem(SPEED_KEY, String(value));
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border bg-black">
        <video
          ref={video}
          controls
          playsInline
          onEnded={onEnded}
          className="aspect-video w-full"
        />
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="flex items-center justify-end gap-2">
        <label htmlFor="playback-rate" className="text-sm text-muted-foreground">
          Tốc độ phát
        </label>
        <NativeSelect
          id="playback-rate"
          value={speed}
          onChange={(event) => changeSpeed(Number(event.target.value))}
          className="w-24"
        >
          {SPEEDS.map((value) => (
            <option key={value} value={value}>
              {value}×
            </option>
          ))}
        </NativeSelect>
      </div>
    </div>
  );
}
