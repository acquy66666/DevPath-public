"use client";

import { CircleAlert } from "lucide-react";
import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface FormFieldProps {
  label: string;
  type: React.HTMLInputTypeAttribute;
  value: string;
  onChange: (value: string) => void;
  /** Message shown under the field, once the field has been touched. */
  error?: string | null;
  autoComplete?: string;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  /** For a form that moves focus to the first field it rejects. */
  ref?: React.Ref<HTMLInputElement>;
}

/**
 * One labelled input with its hint or error line: label, field and message
 * 6px apart (design system, component FormField).
 *
 * `aria-describedby` and `aria-invalid` are what make the error reach a screen
 * reader -- red text alone only reaches people who can see it, which is also
 * why the error carries an icon.
 */
export function FormField({
  label,
  type,
  value,
  onChange,
  error,
  autoComplete,
  placeholder,
  hint,
  disabled,
  autoFocus,
  ref,
}: FormFieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const message = error ?? hint;

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        ref={ref}
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={message ? messageId : undefined}
        autoComplete={autoComplete}
        placeholder={placeholder}
        disabled={disabled}
        autoFocus={autoFocus}
      />
      {error ? (
        <p id={messageId} className="flex items-start gap-1.5 text-sm text-destructive-text">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p id={messageId} className="text-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
