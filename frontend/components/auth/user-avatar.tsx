import type { User } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

/** First letters of the name, for when there is no picture. Falls back to the email. */
function initials(user: User): string {
  const source = user.full_name.trim() || user.email;
  const words = source.split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? [words[0], words[words.length - 1]] : [words[0]];
  return letters
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

/**
 * The circle that stands for a person: their picture, or their initials.
 *
 * `alt` is empty on purpose. This never appears on its own — the name is beside
 * it in the header and above it on the profile page — so describing it again
 * would only make a screen reader say the name twice.
 *
 * Size comes from the caller through `className` (`size-7`, `size-20`), because
 * the header and the profile page want very different ones.
 */
export function UserAvatar({ user, className }: { user: User; className?: string }) {
  const shared = cn(
    "flex shrink-0 items-center justify-center overflow-hidden rounded-full",
    className,
  );

  if (user.avatar_url) {
    // A plain `<img>`: the host is an environment variable (our R2 bucket, or
    // Google for an account that signed in there), and `next/image` would need
    // every such host pinned in next.config at build time.
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={user.avatar_url}
        alt=""
        className={cn(shared, "bg-muted object-cover")}
      />
    );
  }

  return (
    <span
      aria-hidden
      className={cn(shared, "bg-primary font-medium text-primary-foreground")}
    >
      {initials(user)}
    </span>
  );
}
