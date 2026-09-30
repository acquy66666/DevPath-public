/** Same frame as the admin lists, so nothing jumps when the rows arrive. */
export default function Loading() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="h-9 w-80 max-w-full animate-pulse rounded-lg bg-muted/60" />
      {[0, 1, 2].map((row) => (
        <div key={row} className="h-24 animate-pulse rounded-xl border bg-muted/40" />
      ))}
    </div>
  );
}
