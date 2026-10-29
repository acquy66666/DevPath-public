"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { Toaster } from "@/components/ui/toast";
import { AuthProvider } from "@/lib/auth/auth-provider";

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

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      <Toaster />
    </QueryClientProvider>
  );
}
