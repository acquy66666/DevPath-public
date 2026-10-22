/** Same frame as the dashboard, so nothing jumps when the numbers arrive. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-12">
      <div className="h-9 w-64 animate-pulse rounded-md bg-muted" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((tile) => (
          <div key={tile} className="h-24 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1].map((chart) => (
          <div key={chart} className="h-72 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
    </div>
  );
}
