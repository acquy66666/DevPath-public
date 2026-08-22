"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/ui/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, errorMessageForCode } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateEmail } from "@/lib/auth/validation";

/** `errorCode` carries a failure that happened before this page loaded --
 * today that means the Google callback redirecting back with `?loi=`. */
export function LoginForm({ errorCode = null }: { errorCode?: string | null }) {
  const router = useRouter();
  const { signIn } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});

  const mutation = useMutation({
    mutationFn: () => signIn({ email: email.trim(), password }),
    onSuccess: () => {
      router.push("/");
      // The header is a Client Component reading context, so it updates on its
      // own; refresh is for any Server Component that renders per-user content.
      router.refresh();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // Only the email is checked here. Password rules belong to registration --
    // telling someone their existing password is "too short" to sign in would
    // be both wrong and a hint about what the rules are.
    const errors = { email: validateEmail(email), password: password ? null : "Vui lòng nhập mật khẩu" };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
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
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        error={fieldErrors.email}
        autoComplete="email"
        placeholder="ban@example.com"
        disabled={mutation.isPending}
        autoFocus
      />

      <FormField
        label="Mật khẩu"
        type="password"
        value={password}
        onChange={setPassword}
        error={fieldErrors.password}
        autoComplete="current-password"
        disabled={mutation.isPending}
      />

      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang đăng nhập…
          </>
        ) : (
          "Đăng nhập"
        )}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Chưa có tài khoản?{" "}
        <Link href="/dang-ky" className="font-medium text-foreground underline-offset-4 hover:underline">
          Đăng ký
        </Link>
      </p>
    </form>
  );
}
