import { connection } from "next/server";

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
