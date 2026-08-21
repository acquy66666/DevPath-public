"use client";

import { GraduationCap, LayoutDashboard, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { User } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/auth-provider";
import { ROLE_LABELS } from "@/lib/auth/roles";

/** First letters of the name, for the avatar circle. Falls back to the email. */
function initials(user: User): string {
  const source = user.full_name.trim() || user.email;
  const words = source.split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? [words[0], words[words.length - 1]] : [words[0]];
  return letters
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export function UserMenu({ user }: { user: User }) {
  const router = useRouter();
  const { signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await signOut();
      router.push("/");
      router.refresh();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 px-2">
          <span
            aria-hidden
            className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground"
          >
            {initials(user)}
          </span>
          <span className="hidden max-w-32 truncate sm:inline">{user.full_name}</span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate font-medium">{user.full_name}</span>
          <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
          <span className="mt-1 block text-xs text-muted-foreground">
            {ROLE_LABELS[user.role]}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/ho-so">
            <UserRound aria-hidden />
            Hồ sơ của tôi
          </Link>
        </DropdownMenuItem>
        {user.role === "instructor" ? (
          <DropdownMenuItem asChild>
            <Link href="/giang-day">
              <LayoutDashboard aria-hidden />
              Khóa học tôi dạy
            </Link>
          </DropdownMenuItem>
        ) : null}
        {/* Chỉ học viên mới thấy: giảng viên đã nâng cấp rồi, admin nâng cấp là
            mất quyền. */}
        {user.role === "student" ? (
          <DropdownMenuItem asChild>
            <Link href="/tro-thanh-giang-vien">
              <GraduationCap aria-hidden />
              Trở thành giảng viên
            </Link>
          </DropdownMenuItem>
        ) : null}
        {/* Khóa học của tôi... thêm khi trang đó tồn tại. */}
        <DropdownMenuItem onSelect={handleSignOut} disabled={signingOut}>
          <LogOut aria-hidden />
          {signingOut ? "Đang đăng xuất…" : "Đăng xuất"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
