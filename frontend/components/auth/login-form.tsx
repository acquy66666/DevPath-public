"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { PasswordField } from "@/components/auth/password-field";
import { FormField } from "@/components/ui/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { authHref } from "@/lib/account/welcome";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage, errorMessageForCode } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateEmail } from "@/lib/auth/validation";

/**
 * `errorCode` carries a failure that happened before this page loaded -- today
 * that means the Google callback redirecting back with `?loi=`. `next` is where
 * to go afterwards, already checked to be a path on this site. `initialEmail`
 * comes from sign-up's "this email already has an account".
 */
export function LoginForm({
  errorCode = null,
  next = "/",
  initialEmail = "",
}: {
  errorCode?: string | null;
  next?: string;
  initialEmail?: string;
}) {
  const router = useRouter();
  const { signIn } = useAuth();

  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});
  const emailInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: () => signIn({ email: email.trim(), password }),
    onSuccess: () => {
      router.push(next);
      // The header is a Client Component reading context, so it updates on its
      // own; refresh is for any Server Component that renders per-user content.
      router.refresh();
    },
    onError: (error) => {
      // A wrong password is retyped, not edited: empty the field and put the
      // cursor in it. The email stays -- it is usually right.
      if (error instanceof ApiError && error.code === "INVALID_CREDENTIALS") {
        setPassword("");
        requestAnimationFrame(() => passwordInput.current?.focus());
      }
    },
  });

  /** Typing in a field takes back what was said about it. */
  function edit(key: string, set: (value: string) => void) {
    return (value: string) => {
      set(value);
      setFieldErrors((errors) => (errors[key] ? { ...errors, [key]: null } : errors));
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // Only the email is checked here. Password rules belong to registration --
    // telling someone their existing password is "too short" to sign in would
    // be both wrong and a hint about what the rules are.
    const errors = { email: validateEmail(email), password: password ? null : "Vui lòng nhập mật khẩu" };
    setFieldErrors(errors);
    if (errors.email) return emailInput.current?.focus();
    if (errors.password) return passwordInput.current?.focus();

    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      {mutation.isError || errorCode ? (
        <Alert variant="destructive">
          <AlertDescription>
            {mutation.isError
              ? apiErrorMessage(mutation.error)
              : errorMessageForCode(errorCode as string)}
          </AlertDescription>
        </Alert>
      ) : null}

      <FormField
        ref={emailInput}
        label="Email"
        type="email"
        value={email}
        onChange={edit("email", setEmail)}
        error={fieldErrors.email}
        autoComplete="email"
        placeholder="ban@example.com"
        disabled={mutation.isPending}
        autoFocus={!initialEmail}
      />

      <PasswordField
        ref={passwordInput}
        label="Mật khẩu"
        value={password}
        onChange={edit("password", setPassword)}
        error={fieldErrors.password}
        autoComplete="current-password"
        disabled={mutation.isPending}
        autoFocus={Boolean(initialEmail)}
      />

      <Button type="submit" size="lg" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang đăng nhập…
          </>
        ) : (
          "Đăng nhập"
        )}
      </Button>

      <p className="text-center text-body-sm text-muted-foreground">
        Chưa có tài khoản?{" "}
        <Link href={authHref("/dang-ky", next)} className="font-semibold text-link underline-offset-4 hover:underline">
          Đăng ký miễn phí
        </Link>
      </p>
    </form>
  );
}
