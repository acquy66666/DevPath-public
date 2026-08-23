"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/ui/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  PASSWORD_MIN_LENGTH,
  validateEmail,
  validateFullName,
  validatePassword,
} from "@/lib/auth/validation";

export function RegisterForm({ next = "/" }: { next?: string }) {
  const router = useRouter();
  const { signUp } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});

  const mutation = useMutation({
    mutationFn: () =>
      signUp({ email: email.trim(), password, full_name: fullName.trim() }),
    onSuccess: () => {
      router.push(next);
      router.refresh();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const errors = {
      full_name: validateFullName(fullName),
      email: validateEmail(email),
      password: validatePassword(password),
    };
    setFieldErrors(errors);
    if (errors.full_name || errors.email || errors.password) return;

    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {mutation.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      ) : null}

      <FormField
        label="Họ và tên"
        type="text"
        value={fullName}
        onChange={setFullName}
        error={fieldErrors.full_name}
        autoComplete="name"
        placeholder="Nguyễn Văn A"
        disabled={mutation.isPending}
        autoFocus
      />

      <FormField
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        error={fieldErrors.email}
        autoComplete="email"
        placeholder="ban@example.com"
        disabled={mutation.isPending}
      />

      <FormField
        label="Mật khẩu"
        type="password"
        value={password}
        onChange={setPassword}
        error={fieldErrors.password}
        hint={`Tối thiểu ${PASSWORD_MIN_LENGTH} ký tự`}
        autoComplete="new-password"
        disabled={mutation.isPending}
      />

      <Button type="submit" className="w-full" disabled={mutation.isPending}>
        {mutation.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang tạo tài khoản…
          </>
        ) : (
          "Tạo tài khoản"
        )}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Đã có tài khoản?{" "}
        <Link
          href="/dang-nhap"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Đăng nhập
        </Link>
      </p>
    </form>
  );
}
