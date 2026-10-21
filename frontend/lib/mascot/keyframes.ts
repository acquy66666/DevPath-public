// Choreography → Web Animations keyframes. Pure, so it is tested without a
// browser (lib/mascot/mascot.test.ts); components/mascot/play.ts applies it.
//
// Each transform goes through its own CSS property (`translate`, `rotate`,
// `scale`), which browsers apply to SVG elements and compose in a fixed order,
// so a jump and a lean on the same piece do not overwrite each other.
import type { Ease, Origin, Track } from "./choreography";

/** Resolved CSS easing per design-system curve, e.g. `cubic-bezier(…)`. */
export type Easing = Record<Ease, string>;

export const PROPERTIES = ["x", "y", "scale", "scaleX", "scaleY", "rotate", "opacity"] as const;
export type Property = (typeof PROPERTIES)[number];

/** Where each property comes back to: the drawing itself. */
const IDENTITY: Record<Property, number> = { x: 0, y: 0, scale: 1, scaleX: 1, scaleY: 1, rotate: 0, opacity: 1 };

export function animated(t: Track): Property[] {
  return PROPERTIES.filter((p) => t[p] !== undefined);
}

export function frameCount(t: Track): number {
  const lengths = new Set(animated(t).map((p) => t[p]!.length));
  if (lengths.size !== 1) throw new Error(`track ${t.target.join(",")}: keyframe lists differ in length or are missing`);
  return [...lengths][0];
}

export function offsets(t: Track): number[] {
  const n = frameCount(t);
  return t.times ? [...t.times] : Array.from({ length: n }, (_, i) => i / (n - 1));
}

export function eases(t: Track): Ease[] {
  const n = frameCount(t);
  if (t.ease === undefined || typeof t.ease === "string") return Array(n - 1).fill(t.ease ?? "standard");
  return [...t.ease];
}

export function toKeyframes(t: Track, easing: Easing): Keyframe[] {
  const at = offsets(t);
  const curve = eases(t);
  return at.map((offset, i) => {
    const k: Keyframe = { offset };
    if (t.x || t.y) k.translate = `${t.x?.[i] ?? 0}px ${t.y?.[i] ?? 0}px`;
    if (t.scale) k.scale = `${t.scale[i]}`;
    else if (t.scaleX || t.scaleY) k.scale = `${t.scaleX?.[i] ?? 1} ${t.scaleY?.[i] ?? 1}`;
    if (t.rotate) k.rotate = `${t.rotate[i]}deg`;
    if (t.opacity) k.opacity = t.opacity[i];
    if (i < at.length - 1) k.easing = easing[curve[i]];
    return k;
  });
}

/** Does the first keyframe differ from the drawing? Then it must hold through the delay. */
export function startsAway(t: Track): boolean {
  return animated(t).some((p) => t[p]![0] !== IDENTITY[p]);
}

/** Does the last keyframe leave the piece where the drawing has it? */
export function endsHome(t: Track): boolean {
  return animated(t).every((p) => {
    const last = t[p]![t[p]!.length - 1];
    return p === "rotate" ? last % 360 === 0 : last === IDENTITY[p];
  });
}

/** When the last of `count` matched pieces finishes, in ms. */
export function trackEnd(t: Track, count: number): number {
  return t.at + (t.stagger ?? 0) * Math.max(0, count - 1) + t.duration;
}

/** CSS for the pivot: drawing coordinates, or a point of the piece's own box. */
export function originStyle(o: Origin): { transformBox: string; transformOrigin: string } {
  if (o === "center") return { transformBox: "fill-box", transformOrigin: "50% 50%" };
  if (o === "base") return { transformBox: "fill-box", transformOrigin: "50% 100%" };
  return { transformBox: "view-box", transformOrigin: `${o[0]}px ${o[1]}px` };
}
