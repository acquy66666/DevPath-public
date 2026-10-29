// The site's toasts, as plain data: who says what, in which order. The
// component (components/ui/toast.tsx) draws them; this file only keeps the
// list, so `npm test` can check it under bare Node (no imports here).
//
// A toast is for something that just left the screen because of a click: a
// course taken out of the cart or the wishlist. A message that belongs next to
// a form ("Đã lưu thay đổi.") stays next to the form.

export type ToastAction = {
  /** Button text, short: "Hoàn tác". */
  label: string;
  /** What the button says to a screen reader that cannot see the toast. */
  altText: string;
  onSelect: () => void;
};

export type ToastInput = {
  title: string;
  description?: string;
  action?: ToastAction;
};

export type Toast = ToastInput & {
  id: number;
  /** false once it has been closed; it stays in the list while it fades out. */
  open: boolean;
};

/** More than this and the oldest one goes: a stack of toasts is noise. */
export const MAX_TOASTS = 3;
/** How long a toast stays: long enough to read a title and reach "Hoàn tác". */
export const TOAST_DURATION_MS = 6000;

type Listener = () => void;

export function createToastStore() {
  let toasts: readonly Toast[] = [];
  let nextId = 1;
  const listeners = new Set<Listener>();

  const emit = (next: readonly Toast[]) => {
    toasts = next;
    for (const listener of listeners) listener();
  };

  return {
    show(input: ToastInput): number {
      const id = nextId++;
      const shown = toasts.filter((t) => t.open);
      // The oldest open ones close (and fade) to make room.
      const overflow = new Set(shown.slice(0, Math.max(0, shown.length - MAX_TOASTS + 1)).map((t) => t.id));
      emit([
        ...toasts.map((t) => (overflow.has(t.id) ? { ...t, open: false } : t)),
        { ...input, id, open: true },
      ]);
      return id;
    },
    /** Starts the fade-out. */
    close(id: number) {
      if (!toasts.some((t) => t.id === id && t.open)) return;
      emit(toasts.map((t) => (t.id === id ? { ...t, open: false } : t)));
    },
    /** Takes it out of the list, once its fade-out has run. */
    remove(id: number) {
      if (!toasts.some((t) => t.id === id)) return;
      emit(toasts.filter((t) => t.id !== id));
    },
    snapshot(): readonly Toast[] {
      return toasts;
    },
    subscribe(listener: Listener): () => void {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export type ToastStore = ReturnType<typeof createToastStore>;
