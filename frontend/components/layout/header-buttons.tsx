"use client";

import { Bell, Menu } from "lucide-react";
import type { ComponentProps } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/auth";

/**
 * The three header buttons that open a menu, without the menu.
 *
 * The menus (Radix Menu with its positioning engine, ~23 KB gzip) load after
 * the page is up -- the phone menu once the page hydrates, the bell and the
 * account menu once the session says who is signed in -- so a visitor's first
 * screen does not wait for code it may never use. Until then these stand in,
 * pixel for pixel: the real menu puts the same button inside its trigger.
 */

type ButtonProps = Omit<ComponentProps<typeof Button>, "children">;

export function MobileNavButton(props: ButtonProps) {
  return (
    <Button variant="ghost" size="icon" className="md:hidden" aria-label="Mở menu điều hướng" {...props}>
      <Menu className="size-5" aria-hidden />
    </Button>
  );
}

export function BellButton({ unread = 0, ...props }: ButtonProps & { unread?: number }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="relative h-10 px-2 sm:px-3"
      aria-label={unread > 0 ? `Thông báo, ${unread} chưa đọc` : "Thông báo"}
      {...props}
    >
      <Bell className="size-5" aria-hidden />
      {unread > 0 ? (
        <span
          className="absolute -top-0.5 right-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[0.7rem] font-semibold text-destructive-foreground tabular-nums"
          aria-hidden
        >
          {unread > 9 ? "9+" : unread}
        </span>
      ) : null}
    </Button>
  );
}

export function AccountButton({ user, ...props }: ButtonProps & { user: User }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-10 gap-2 px-1 text-base sm:px-2"
      aria-label={`Tài khoản: ${user.full_name}`}
      {...props}
    >
      <UserAvatar user={user} className="size-8 text-sm" />
      <span className="hidden max-w-32 truncate sm:inline">{user.full_name}</span>
    </Button>
  );
}
