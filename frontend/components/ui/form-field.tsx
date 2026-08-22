"use client";

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
}

/**
 * One labelled input with its error line.
 *
 * `aria-describedby` and `aria-invalid` are what make the error reach a screen
 * reader -- red text alone only reaches people who can see it.
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
}: FormFieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const message = error ?? hint;

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
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
      {message ? (
        <p
          id={messageId}
          className={error ? "text-sm text-destructive" : "text-sm text-muted-foreground"}
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}
