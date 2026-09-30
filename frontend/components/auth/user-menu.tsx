"use client";

import {
  BarChart3,
  BookOpen,
  GraduationCap,
  Heart,
  LayoutDashboard,
  LogOut,
  MessageCircleQuestion,
  ShieldCheck,
  Trophy,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
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
        <Button variant="ghost" size="sm" className="gap-2 px-2 text-[1.12rem] h-10">
          <UserAvatar user={user} className="size-10 text-sm" />
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
          <Link href="/khoa-hoc-cua-toi">
            <BookOpen aria-hidden />
            Khóa học của tôi
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/bang-xep-hang">
            <Trophy aria-hidden />
            Bảng xếp hạng
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/yeu-thich">
            <Heart aria-hidden />
            Yêu thích
          </Link>
        </DropdownMenuItem>
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
        {user.role === "instructor" ? (
          <DropdownMenuItem asChild>
            <Link href="/giang-day/hoi-dap">
              <MessageCircleQuestion aria-hidden />
              Hỏi đáp của học viên
            </Link>
          </DropdownMenuItem>
        ) : null}
        {user.role === "instructor" ? (
          <DropdownMenuItem asChild>
            <Link href="/giang-day/thong-ke">
              <BarChart3 aria-hidden />
              Thống kê giảng dạy
            </Link>
          </DropdownMenuItem>
        ) : null}
        {user.role === "admin" ? (
          <DropdownMenuItem asChild>
            <Link href="/quan-tri">
              <ShieldCheck aria-hidden />
              Quản trị
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
        <DropdownMenuItem onSelect={handleSignOut} disabled={signingOut}>
          <LogOut aria-hidden />
          {signingOut ? "Đang đăng xuất…" : "Đăng xuất"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
