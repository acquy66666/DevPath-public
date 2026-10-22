import { connection } from "next/server";

import { Skeleton } from "@/components/ui/skeleton";
import { listBanners, type Banner } from "@/lib/api/banners";

import { BannerCarousel } from "./banner-carousel";

/**
 * Server Component: the banners live right now, or nothing.
 *
 * `connection()` defers it to request time -- a banner scheduled to come down
 * on Sunday must not stay baked into a page built on Saturday. A failed fetch
 * draws nothing rather than an error: the homepage is fine without banners.
 */
export async function HomeBanners() {
  await connection();

  let banners: Banner[] = [];
  try {
    banners = await listBanners();
  } catch {
    banners = [];
  }

  return banners.length > 0 ? <BannerCarousel banners={banners} /> : null;
}

/**
 * The carousel's frame while the banners stream in, at the slides' own
 * aspect: the hero below starts where it will stay. With no live banner the
 * frame goes away and the hero moves up once -- the rarer case, and the cost
 * of not knowing before the request.
 */
export function HomeBannersSkeleton() {
  return <Skeleton className="aspect-[16/9] w-full rounded-xl sm:aspect-[21/8]" />;
}
