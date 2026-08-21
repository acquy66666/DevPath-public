"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as authApi from "@/lib/api/auth";
import type { LoginInput, RegisterInput, Session, User } from "@/lib/api/auth";

/**
 * Session state for the whole app.
 *
 * The access token is kept in React state and nowhere else -- not in
 * localStorage, not in a readable cookie. A script injected into the page has
 * no store to read it out of, and it dies with the tab. What survives a reload
 * is the HttpOnly refresh cookie, which the mount effect below trades for a
 * new token; that is the brief "đang tải" state on first paint.
 */
export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  status: AuthStatus;
  signIn: (input: LoginInput) => Promise<User>;
  signUp: (input: RegisterInput) => Promise<User>;
  signOut: () => Promise<void>;
  /** Re-read the session from the server, e.g. after the role changed. */
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Renew this long before the token expires. A minute of slack covers a slow
 * request without ever letting a call go out with a token that expired on the
 * way.
 */
const RENEW_MARGIN_MS = 60_000;
const MIN_RENEW_DELAY_MS = 5_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const startSession = useCallback((next: Session): User => {
    setSession(next);
    setStatus("authenticated");
    return next.user;
  }, []);

  const endSession = useCallback(() => {
    setSession(null);
    setStatus("anonymous");
  }, []);

  // Restore the session on first mount: the cookie outlived the page, the
  // access token did not.
  useEffect(() => {
    let cancelled = false;

    authApi
      .refresh()
      .then((restored) => {
        if (cancelled) return;
        setSession(restored);
        setStatus("authenticated");
      })
      .catch(() => {
        // No cookie, or it is no longer valid — an ordinary signed-out visit.
        if (!cancelled) setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Keep the token fresh. Re-runs on every new session, so each renewal
  // schedules the next one and signing out cancels the pending timer.
  useEffect(() => {
    if (session === null) return;

    const delay = Math.max(
      session.expires_in * 1000 - RENEW_MARGIN_MS,
      MIN_RENEW_DELAY_MS,
    );

    const timer = setTimeout(() => {
      authApi
        .refresh()
        .then((renewed) => {
          setSession(renewed);
          setStatus("authenticated");
        })
        .catch(() => {
          // Refresh cookie gone, expired, or revoked: the session is over.
          setSession(null);
          setStatus("anonymous");
        });
    }, delay);

    return () => clearTimeout(timer);
  }, [session]);

  const signIn = useCallback(
    async (input: LoginInput) => startSession(await authApi.login(input)),
    [startSession],
  );

  const signUp = useCallback(
    async (input: RegisterInput) => startSession(await authApi.register(input)),
    [startSession],
  );

  const refreshSession = useCallback(async () => {
    // Anything that changes the user server-side (a promotion to instructor,
    // say) is picked up here rather than by patching local state, so the UI
    // can never disagree with the row.
    startSession(await authApi.refresh());
  }, [startSession]);

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Whatever the server said, this browser is signed out. Leaving the UI
      // signed in because a request failed would be the worse answer.
      endSession();
    }
  }, [endSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      accessToken: session?.access_token ?? null,
      status,
      signIn,
      signUp,
      signOut,
      refreshSession,
    }),
    [session, status, signIn, signUp, signOut, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth phải nằm trong <AuthProvider>");
  }
  return context;
}
