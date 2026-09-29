/** Same frame as the inbox, so nothing jumps when the questions arrive. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-12">
      <div className="h-9 w-72 animate-pulse rounded-lg bg-muted" />
      <div className="h-8 w-96 max-w-full animate-pulse rounded-lg bg-muted/60" />
      <div className="space-y-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-24 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
    </div>
  );
}
