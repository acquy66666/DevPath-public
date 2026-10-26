"use client";

import { Check, Circle, CircleAlert, Eye, EyeOff } from "lucide-react";
import { useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { passwordProgress } from "@/lib/auth/validation";
import { cn } from "@/lib/utils";

interface PasswordFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  autoComplete: "current-password" | "new-password";
  /** Say the password rule under the field, ticking it off while typing (new passwords). */
  rule?: boolean;
  disabled?: boolean;
  autoFocus?: boolean;
  ref?: React.Ref<HTMLInputElement>;
}

/**
 * A password input with a "Hiện" / "Ẩn" button inside it, and for a new
 * password the rule as a line that counts down and turns into a tick.
 *
 * The button's name never says "mật khẩu": the field's label already does,
 * and `getByLabel("Mật khẩu")` (E2E, capture scripts) must find one element.
 * Its name starts with the word on it ("Hiện…"), so voice control finds it by
 * what it shows. No `name` on the input either: a click before hydration
 * submits the form as a GET, and nothing must ride along in the URL.
 */
export function PasswordField({
  label,
  value,
  onChange,
  error,
  autoComplete,
  rule = false,
  disabled,
  autoFocus,
  ref,
}: PasswordFieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const [shown, setShown] = useState(false);
  const progress = rule ? passwordProgress(value) : null;
  const hasMessage = Boolean(error) || progress !== null;

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          ref={ref}
          id={id}
          type={shown ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={hasMessage ? messageId : undefined}
          autoComplete={autoComplete}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          disabled={disabled}
          autoFocus={autoFocus}
          className="pr-20"
        />
        <button
          type="button"
          onClick={() => setShown((value) => !value)}
          aria-controls={id}
          aria-label={shown ? "Ẩn ký tự đã gõ" : "Hiện ký tự đã gõ"}
          disabled={disabled}
          className={cn(
            "absolute inset-y-1 right-1 inline-flex items-center gap-1.5 rounded-sm px-2.5 text-body-sm font-medium text-link transition-colors hover:bg-secondary disabled:pointer-events-none disabled:opacity-50",
            shown && "bg-secondary",
          )}
        >
          {shown ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
          {shown ? "Ẩn" : "Hiện"}
        </button>
      </div>
      {error ? (
        <p id={messageId} className="flex items-start gap-1.5 text-sm text-destructive-text">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : progress ? (
        <p
          id={messageId}
          data-met={progress.met || undefined}
          className={cn(
            "flex items-start gap-1.5 text-sm",
            progress.met ? "text-success-text" : progress.tooLong ? "text-destructive-text" : "text-muted-foreground",
          )}
        >
          {progress.met ? (
            <Check className="mt-0.5 size-4 shrink-0 text-success" strokeWidth={2.5} aria-hidden />
          ) : progress.tooLong ? (
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          ) : (
            <Circle className="mt-0.5 size-4 shrink-0" aria-hidden />
          )}
          <span>{progress.text}</span>
        </p>
      ) : null}
    </div>
  );
}
