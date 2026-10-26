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
import { afterSignUpPath, authHref, welcomeMarker } from "@/lib/account/welcome";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateEmail, validateFullName, validatePassword } from "@/lib/auth/validation";
import { writeItem } from "@/lib/gamification/seen";

export function RegisterForm({ next = "/" }: { next?: string }) {
  const router = useRouter();
  const { signUp } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});
  const nameInput = useRef<HTMLInputElement>(null);
  const emailInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: () =>
      signUp({ email: email.trim(), password, full_name: fullName.trim() }),
    onSuccess: (user) => {
      // The welcome page waves for this account, once, in this tab.
      writeItem("session", welcomeMarker.key, user.id);
      router.push(afterSignUpPath(next));
      router.refresh();
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

    const errors = {
      full_name: validateFullName(fullName),
      email: validateEmail(email),
      password: validatePassword(password),
    };
    setFieldErrors(errors);
    // The cursor goes to the first field that needs fixing.
    if (errors.full_name) return nameInput.current?.focus();
    if (errors.email) return emailInput.current?.focus();
    if (errors.password) return passwordInput.current?.focus();

    mutation.mutate();
  }

  const taken =
    mutation.error instanceof ApiError && mutation.error.code === "EMAIL_ALREADY_REGISTERED";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      {mutation.isError ? (
        <Alert variant="destructive">
          <AlertDescription>
            <p>{apiErrorMessage(mutation.error)}</p>
            {taken ? (
              <Link
                href={authHref("/dang-nhap", next, { email: email.trim() })}
                className="mt-1 inline-block font-semibold text-destructive-text underline underline-offset-4"
              >
                Đăng nhập với email này
              </Link>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <FormField
        ref={nameInput}
        label="Họ và tên"
        type="text"
        value={fullName}
        onChange={edit("full_name", setFullName)}
        error={fieldErrors.full_name}
        autoComplete="name"
        placeholder="Nguyễn Văn A"
        disabled={mutation.isPending}
        autoFocus
      />

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
      />

      <PasswordField
        ref={passwordInput}
        label="Mật khẩu"
        value={password}
        onChange={edit("password", setPassword)}
        error={fieldErrors.password}
        autoComplete="new-password"
        rule
        disabled={mutation.isPending}
      />

      <Button type="submit" size="lg" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang tạo tài khoản…
          </>
        ) : (
          "Tạo tài khoản"
        )}
      </Button>

      <p className="text-caption text-muted-foreground">
        Khi tạo tài khoản, bạn đồng ý với{" "}
        <Link href="/chinh-sach-bao-mat" className="text-link underline underline-offset-4">
          chính sách bảo mật
        </Link>{" "}
        của DevPath.
      </p>

      <p className="text-center text-body-sm text-muted-foreground">
        Đã có tài khoản?{" "}
        <Link href={authHref("/dang-nhap", next)} className="font-semibold text-link underline-offset-4 hover:underline">
          Đăng nhập
        </Link>
      </p>
    </form>
  );
}
