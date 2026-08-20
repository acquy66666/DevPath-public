/** Skeleton in the shape of the card that is about to arrive. */
export default function AuthLoading() {
  return (
    <div className="space-y-4 rounded-xl border p-6">
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="h-4 w-52 animate-pulse rounded bg-muted" />
      <div className="h-10 w-full animate-pulse rounded bg-muted" />
      <div className="h-10 w-full animate-pulse rounded bg-muted" />
      <div className="h-10 w-full animate-pulse rounded bg-muted" />
    </div>
  );
}
