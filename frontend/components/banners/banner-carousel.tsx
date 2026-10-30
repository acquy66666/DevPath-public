"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import type { Banner } from "@/lib/api/banners";

const INTERVAL_MS = 6000;

/** A round white button over the picture; 36px, the size of a button. */
const ARROW =
  "flex size-9 items-center justify-center rounded-full bg-card text-foreground shadow-sm transition-colors duration-fast hover:bg-accent";

/**
 * The homepage banners, one at a time.
 *
 * It turns by itself every few seconds -- but not while a pointer or the
 * keyboard is on it (nobody wants the slide they are reading to leave), and
 * not at all for someone who asked their system for reduced motion. The
 * arrows and dots work either way, and every slide is in the markup, so
 * nothing depends on the timer.
 */
export function BannerCarousel({ banners }: { banners: Banner[] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const count = banners.length;

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (count < 2 || paused || reducedMotion) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % count), INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [count, paused, reducedMotion]);

  if (count === 0) return null;
  const go = (next: number) => setIndex((next + count) % count);

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Tin nổi bật"
      className="relative overflow-hidden rounded-xl border bg-muted"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div
        className="flex transition-transform duration-slow ease-standard motion-reduce:transition-none"
        style={{ transform: `translateX(-${index * 100}%)` }}
      >
        {banners.map((banner, position) => (
          <div
            key={banner.id}
            role="group"
            aria-roledescription="slide"
            aria-label={`${position + 1} / ${count}: ${banner.title}`}
            aria-hidden={position !== index}
            className="relative aspect-[16/9] w-full shrink-0 sm:aspect-[21/8]"
          >
            <Slide banner={banner} focusable={position === index} />
          </div>
        ))}
      </div>

      {/* Both arrows and the count sit together in a corner, off the title:
          over the middle of the picture they covered its words on a phone. */}
      {count > 1 ? (
        <div className="absolute right-3 bottom-3 flex items-center gap-1.5 sm:right-5 sm:bottom-5">
          <button
            type="button"
            onClick={() => go(index - 1)}
            className={ARROW}
            aria-label="Banner trước"
          >
            <ChevronLeft className="size-4.5" aria-hidden />
          </button>
          <span className="min-w-10 text-center text-body-sm font-semibold text-slate-0 tabular-nums">
            <span className="sr-only">Banner </span>
            {index + 1} / {count}
          </span>
          <button
            type="button"
            onClick={() => go(index + 1)}
            className={ARROW}
            aria-label="Banner sau"
          >
            <ChevronRight className="size-4.5" aria-hidden />
          </button>
        </div>
      ) : null}
    </section>
  );
}

function Slide({ banner, focusable }: { banner: Banner; focusable: boolean }) {
  const picture = (
    <>
      {/* Lazy: the carousel sits under the hero since Phase 7, and its three
          pictures (~63 KB) were fetched before the hero's text had painted. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- R2/MinIO URLs, not optimisable here */}
      <img src={banner.image_url} alt="" loading="lazy" decoding="async" className="size-full object-cover" />
      {/* A scrim under the words: the picture is whatever an admin uploaded,
          and white text has to stay readable on any of it. Right padding
          leaves room for the controls in the corner. */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/75 to-transparent px-5 pt-14 pb-5 pr-36 sm:px-8 sm:pb-7 sm:pr-44">
        <p className="max-w-2xl text-title text-balance text-slate-0 sm:text-h2">{banner.title}</p>
      </div>
    </>
  );

  if (!banner.link_url) return picture;

  const className =
    "block size-full focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset";
  const tabIndex = focusable ? undefined : -1;
  return banner.link_url.startsWith("/") ? (
    <Link href={banner.link_url} className={className} tabIndex={tabIndex}>
      {picture}
    </Link>
  ) : (
    <a
      href={banner.link_url}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      tabIndex={tabIndex}
    >
      {picture}
    </a>
  );
}
