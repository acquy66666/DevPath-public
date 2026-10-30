"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";

import { AuthProvider } from "@/lib/auth/auth-provider";
import { useAfterLoad } from "@/lib/design/use-after-load";

// Loaded once the page has loaded and gone quiet: a toast only ever follows
// a click, and Radix Toast has no business in the first screen's JavaScript.
// A toast raised before that waits in the store and shows when it mounts. The pages that call
// `toast()` import the same module, so both ends share one store.
const Toaster = dynamic(() => import("@/components/ui/toast").then((m) => m.Toaster), { ssr: false });

/**
 * Client-side providers for the whole app.
 *
 * The QueryClient is created in state, not at module scope: on the server a
 * module-level client would be shared by every request, and one visitor's
 * cached data would be handed to the next.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Long enough that moving between pages does not refetch what was
            // just shown; short enough that a course list is never stale news.
            staleTime: 60_000,
            retry: 1,
          },
        },
      }),
  );

  const { ready } = useAfterLoad();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      {ready ? <Toaster /> : null}
    </QueryClientProvider>
  );
}
