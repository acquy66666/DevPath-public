"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import type { Banner } from "@/lib/api/banners";
import { cn } from "@/lib/utils";

const INTERVAL_MS = 6000;

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
      className="relative overflow-hidden rounded-2xl border bg-muted"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div
        className="flex transition-transform duration-500 ease-out motion-reduce:transition-none"
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

      {count > 1 ? (
        <>
          <button
            type="button"
            onClick={() => go(index - 1)}
            className="absolute top-1/2 left-2 -translate-y-1/2 rounded-full bg-background/80 p-1.5 shadow-sm backdrop-blur transition hover:bg-background focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            aria-label="Banner trước"
          >
            <ChevronLeft className="size-5" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => go(index + 1)}
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full bg-background/80 p-1.5 shadow-sm backdrop-blur transition hover:bg-background focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            aria-label="Banner sau"
          >
            <ChevronRight className="size-5" aria-hidden />
          </button>
          <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5">
            {banners.map((banner, position) => (
              <button
                key={banner.id}
                type="button"
                onClick={() => go(position)}
                aria-label={`Xem banner ${position + 1}`}
                aria-current={position === index ? "true" : undefined}
                className={cn(
                  "h-2 rounded-full bg-white/60 transition-all focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                  position === index ? "w-6 bg-white" : "w-2",
                )}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

function Slide({ banner, focusable }: { banner: Banner; focusable: boolean }) {
  const picture = (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- R2/MinIO URLs, not optimisable here */}
      <img src={banner.image_url} alt="" className="size-full object-cover" />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-5 pt-12 pb-8 sm:px-8">
        <p className="max-w-2xl text-lg font-semibold text-balance text-white drop-shadow sm:text-2xl">
          {banner.title}
        </p>
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
