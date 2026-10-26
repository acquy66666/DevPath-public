import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api/client";

/**
 * Starts the Google flow.
 *
 * A plain link, not a fetch: OAuth is a top-level navigation to Google and
 * back, and the state cookie the backend sets only rides along on one.
 *
 * Hidden unless `NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED` is "true" -- a deployment
 * without an OAuth client would otherwise offer a button that can only fail.
 */
export function GoogleButton({ label }: { label: string }) {
  if (process.env.NEXT_PUBLIC_GOOGLE_LOGIN_ENABLED !== "true") return null;

  return (
    <div className="flex flex-col gap-4">
      <Button variant="outline" size="lg" className="w-full" asChild>
        <a href={apiUrl("/api/v1/auth/google/authorize")}>
          <GoogleMark />
          {label}
        </a>
      </Button>

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-caption text-muted-foreground">hoặc dùng email</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}

/** Google's four-colour G. Inline so the page pulls in no external asset. */
export function GoogleMark({ className = "size-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden focusable="false">
      <path
        fill="#4285F4"
        d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5a5.6 5.6 0 0 1-2.4 3.7v3h3.9c2.3-2.1 3.5-5.2 3.5-8.9z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.2 0 5.9-1.1 7.9-2.9l-3.9-3c-1.1.7-2.4 1.2-4 1.2-3.1 0-5.7-2.1-6.6-4.9H1.4v3.1A12 12 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.4 14.3a7.2 7.2 0 0 1 0-4.6V6.6H1.4a12 12 0 0 0 0 10.8l4-3.1z"
      />
      <path
        fill="#EA4335"
        d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.4 6.6l4 3.1C6.3 6.9 8.9 4.8 12 4.8z"
      />
    </svg>
  );
}
