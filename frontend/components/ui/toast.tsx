"use client"

import * as React from "react"
import { Toast as ToastPrimitive } from "radix-ui"
import { XIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import {
  createToastStore,
  TOAST_DURATION_MS,
  type ToastInput,
} from "@/lib/design/toast-store"

// Design system, toast. Radix Toast underneath: it reads the title to a screen
// reader, pauses while the pointer or focus is on it, closes on Esc or a
// swipe to the right, and F8 jumps to it.
//
// When: something just left the screen because of a click (a course taken
// out of the cart or the wishlist), with "Hoàn tác" when undoing is one
// request. Not for errors (an Alert next to the thing that failed) and not
// for "Đã lưu" next to a form.
//
// Where: top right, under the header, so it never sits on the cart's sticky
// pay bar at the bottom of a phone screen.
//
// Motion (components/Motion): in over duration-slow on ease-enter, sliding
// 1rem from the right; out about 70% as long on ease-exit. With reduced
// motion only the fade is left.

const store = createToastStore()

/** Shows a toast from anywhere on the client. */
export function toast(input: ToastInput): number {
  return store.show(input)
}

export function Toaster() {
  const toasts = React.useSyncExternalStore(store.subscribe, store.snapshot, () => EMPTY)
  const viewport = React.useRef<HTMLOListElement>(null)
  const openCount = toasts.filter((t) => t.open).length

  // Radix 1.2 pauses every timer while the pointer or focus is on a toast, but
  // only listens for "left again" while some toast is on screen. Close the
  // last one with the pointer on it -- "Hoàn tác" does exactly that -- and the
  // pause outlives it: the next toast never closes by itself (measured: still
  // open after 10 s). So each time one opens, tell Radix the pointer has left,
  // unless it really is over the stack. Radix keeps the pause when focus is
  // inside, so a keyboard reader on a toast keeps theirs.
  React.useEffect(() => {
    if (openCount === 0) return
    const frame = requestAnimationFrame(() => {
      const wrapper = viewport.current?.parentElement
      if (wrapper && !wrapper.matches(":hover")) {
        wrapper.dispatchEvent(new PointerEvent("pointerleave"))
      }
    })
    return () => cancelAnimationFrame(frame)
  }, [openCount, toasts])

  return (
    <ToastPrimitive.Provider
      duration={TOAST_DURATION_MS}
      swipeDirection="right"
      label="Thông báo"
    >
      {toasts.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          open={t.open}
          onOpenChange={(open) => (open ? undefined : store.close(t.id))}
          // Radix unmounts once the exit animation ends; the store follows.
          onAnimationEnd={() => (t.open ? undefined : store.remove(t.id))}
          data-slot="toast"
          className={cn(
            "pointer-events-auto relative flex w-full items-start gap-3 rounded-lg border bg-popover p-4 pr-10 text-popover-foreground shadow-md",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-slow data-[state=open]:ease-enter motion-safe:data-[state=open]:slide-in-from-right-4",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-base data-[state=closed]:ease-exit motion-safe:data-[state=closed]:slide-out-to-right-4",
            // Swipe: follows the finger, springs back on cancel.
            "motion-safe:data-[swipe=move]:translate-x-(--radix-toast-swipe-move-x) data-[swipe=cancel]:translate-x-0 motion-safe:data-[swipe=cancel]:transition-transform motion-safe:data-[swipe=cancel]:duration-base",
            "motion-safe:data-[swipe=end]:slide-out-to-right-full data-[swipe=end]:animate-out data-[swipe=end]:fade-out-0 data-[swipe=end]:duration-base data-[swipe=end]:ease-exit"
          )}
        >
          <div className="grid min-w-0 flex-1 gap-1">
            <ToastPrimitive.Title className="text-body-sm font-semibold text-foreground">
              {t.title}
            </ToastPrimitive.Title>
            {t.description ? (
              <ToastPrimitive.Description className="text-body-sm text-muted-foreground">
                {t.description}
              </ToastPrimitive.Description>
            ) : null}
          </div>
          {t.action ? (
            <ToastPrimitive.Action
              altText={t.action.altText}
              onClick={t.action.onSelect}
              className="inline-flex h-8 shrink-0 items-center rounded-md border border-input bg-card px-3 text-[0.8125rem] font-semibold text-foreground shadow-xs transition-colors hover:bg-accent"
            >
              {t.action.label}
            </ToastPrimitive.Action>
          ) : null}
          <ToastPrimitive.Close
            aria-label="Đóng thông báo"
            className="absolute top-3 right-3 inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <XIcon className="size-4" aria-hidden />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport ref={viewport} className="pointer-events-none fixed top-18 right-0 z-[60] flex w-full max-w-sm flex-col gap-2 px-4 sm:right-4 sm:px-0" />
    </ToastPrimitive.Provider>
  )
}

const EMPTY: readonly never[] = []
