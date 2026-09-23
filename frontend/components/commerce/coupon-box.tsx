"use client";

import { Loader2, TicketPercent, X } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CartDiscount } from "@/lib/api/commerce";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { formatAmount } from "@/lib/format";

/**
 * The "Mã giảm giá" box on the cart page.
 *
 * It owns the text being typed and nothing else. Which code is *applied* is
 * the cart's business, because the cart summary draws the result and because
 * the answer stops being true the moment a course is removed -- so the query
 * that asks the backend lives up there, next to the cart it is about, and this
 * component is handed its state.
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

  if (discount) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 rounded-lg border border-emerald-600/30 bg-emerald-600/5 p-3">
          <TicketPercent className="size-4 shrink-0 text-emerald-700" aria-hidden />
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium">{discount.coupon.code}</p>
            <p className="text-muted-foreground">{describe(discount)}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setCode("");
              onClear();
            }}
            aria-label={`Bỏ mã ${discount.coupon.code}`}
          >
            <X aria-hidden />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        const typed = code.trim();
        if (typed.length > 0) onApply(typed);
      }}
    >
      <div className="flex gap-2">
        <Input
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Mã giảm giá"
          aria-label="Mã giảm giá"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          className="uppercase"
        />
        <Button type="submit" variant="secondary" disabled={pending || code.trim() === ""}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Áp dụng
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}
    </form>
  );
}

/** "Giảm 50%", "Giảm 100.000 ₫ — cho 2 khóa học trong giỏ". */
function describe(discount: CartDiscount): string {
  const { coupon } = discount;
  const off =
    coupon.discount_type === "percent"
      ? `Giảm ${Number(coupon.value)}%`
      : `Giảm ${formatAmount(coupon.value)}`;

  if (coupon.scope === "site") return off;
  return `${off} cho ${discount.course_ids.length} khóa học trong giỏ`;
}
