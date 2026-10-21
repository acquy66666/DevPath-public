import type { Ref } from "react";

// The same DOM for every variant: the celebrate drawing, and the rest drawing
// stacked on top of it at opacity 0, to cross-fade into once the reaction ends.
// No hooks, so a server component can render it (static and CSS variants) and
// a client component can hand it a scope ref (the two Motion variants).
export function NaomiFrame({
  celebrate,
  rest,
  playing,
  scope,
}: {
  celebrate: string;
  rest: string;
  playing: boolean;
  scope?: Ref<HTMLDivElement>;
}) {
  return (
    <div
      ref={scope}
      className="naomi"
      data-playing={playing ? "" : undefined}
      aria-hidden="true"
      style={{ position: "relative", width: 200, height: 200, pointerEvents: "none" }}
    >
      <div data-part="celebrate" style={{ position: "absolute", inset: 0 }} dangerouslySetInnerHTML={{ __html: celebrate }} />
      <div data-part="rest" style={{ position: "absolute", inset: 0 }} dangerouslySetInnerHTML={{ __html: rest }} />
    </div>
  );
}
