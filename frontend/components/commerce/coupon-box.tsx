"use client";

import { Loader2, TicketPercent, X } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CartDiscount } from "@/lib/api/commerce";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { formatAmount, formatDate } from "@/lib/format";

/**
 * The "Mã giảm giá" box on the cart page.
 *
 * It owns the text being typed and nothing else. Which code is *applied* is
 * the cart's business, because the cart summary draws the result and because
 * the answer stops being true the moment a course is removed -- so the query
 * that asks the backend lives up there, next to the cart it is about, and this
 * component is handed its state.
 *
 * A refused code keeps what was typed and says why right under the field,
 * tied to it with `aria-describedby`, so it can be fixed in place.
 *
 * Nothing is remembered between visits. A coupon is checked again at checkout
 * anyway, so a code restored from storage would only be a promise this page
 * cannot keep.
 */
export function CouponBox({
  discount,
  pending,
  error,
  onApply,
  onClear,
}: {
  /** The applied code's effect, or null when none is applied. */
  discount: CartDiscount | null;
  pending: boolean;
  error: unknown;
  onApply: (code: string) => void;
  onClear: () => void;
}) {
  const [code, setCode] = useState("");
  const id = useId();
  const errorId = `${id}-error`;

  if (discount) {
    return (
      <div className="flex items-center gap-3 rounded-md bg-secondary py-2.5 pr-2 pl-3">
        <TicketPercent className="size-5 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1 text-body-sm">
          <p className="font-semibold text-secondary-foreground">{discount.coupon.code}</p>
          <p className="text-muted-foreground">{describe(discount)}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setCode("");
            onClear();
          }}
          aria-label={`Bỏ mã ${discount.coupon.code}`}
        >
          <X aria-hidden />
        </Button>
      </div>
    );
  }

  const refused = Boolean(error) && !pending;

  return (
    <form
      className="flex flex-col gap-1.5"
      onSubmit={(event) => {
        event.preventDefault();
        const typed = code.trim();
        if (typed.length > 0) onApply(typed);
      }}
    >
      <label htmlFor={id} className="text-body-sm font-medium">
        Mã giảm giá
      </label>
      <div className="flex gap-2">
        <Input
          id={id}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          className="uppercase"
          aria-invalid={refused || undefined}
          aria-describedby={refused ? errorId : undefined}
        />
        <Button type="submit" variant="secondary" className="h-10" disabled={pending || code.trim() === ""}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Áp dụng
        </Button>
      </div>

      {refused ? (
        <p id={errorId} role="alert" className="text-body-sm text-destructive-text">
          {apiErrorMessage(error)}
        </p>
      ) : null}
    </form>
  );
}

/** "Giảm 50% · hết hạn 05/11/2026", "Giảm 100.000 ₫ cho 2 khóa học trong giỏ". */
function describe(discount: CartDiscount): string {
  const { coupon } = discount;
  const off =
    coupon.discount_type === "percent"
      ? `Giảm ${Number(coupon.value)}%`
      : `Giảm ${formatAmount(coupon.value)}`;
  const scope = coupon.scope === "site" ? off : `${off} cho ${discount.course_ids.length} khóa học trong giỏ`;
  return coupon.valid_to ? `${scope} · hết hạn ${formatDate(coupon.valid_to)}` : scope;
}
