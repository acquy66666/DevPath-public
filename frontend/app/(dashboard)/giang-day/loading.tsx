export default function Loading() {
  return (
    <div className="mx-auto max-w-4xl space-y-4 px-4 py-12">
      <div className="h-9 w-64 animate-pulse rounded-md bg-muted" />
      {[0, 1, 2].map((row) => (
        <div key={row} className="h-24 animate-pulse rounded-lg border bg-muted/40" />
      ))}
    </div>
  );
}
