import { apiFetch } from "./client";

/** Mirrors `BannerOut`: what the homepage draws. */
export interface Banner {
  id: string;
  title: string;
  image_url: string;
  /** A path on this site or an http(s) address; null when the banner is only a picture. */
  link_url: string | null;
}

/** Switched on and inside their window right now, in order, at most five. */
export function listBanners(): Promise<Banner[]> {
  return apiFetch<Banner[]>("/api/v1/banners");
}
