/**
 * The word mark: "Dev" in `foreground`, "Path" in `primary`. DevPath has no
 * logo image yet; size and weight come from the caller.
 */
export function BrandMark() {
  return (
    <>
      Dev<span className="text-primary">Path</span>
    </>
  );
}
