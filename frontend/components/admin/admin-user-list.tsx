"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Lock, LockOpen } from "lucide-react";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { UserAvatar } from "@/components/auth/user-avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import {
  listAdminUsers,
  lockUser,
  unlockUser,
  type AdminUser,
  type LockFilter,
  type RoleFilter,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { formatDate, formatRelativeTime } from "@/lib/format";

/**
 * Every account, newest first, and the one lever an admin has on it: lock.
 *
 * Locking signs the account out everywhere at once and blocks sign-in; nothing
 * it wrote is removed and an instructor's courses stay on sale. Admin accounts
 * have no lock button -- the backend refuses them anyway.
 */
export function AdminUserList() {
  const { accessToken } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [lock, setLock] = useState<LockFilter>("all");
  const [page, setPage] = useState(1);

  const users = useQuery({
    queryKey: [...ADMIN_KEY, "users", q, role, lock, page],
    queryFn: () => listAdminUsers(accessToken as string, { q, role, lock, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-4" aria-labelledby="admin-users-title">
      <h2 id="admin-users-title" className="sr-only">
        Người dùng
      </h2>

      <div className="flex flex-wrap items-center gap-3">
        <SearchBox
          id="admin-user-search"
          placeholder="Tên hoặc email"
          initial={q}
          onSearch={(value) => {
            setQ(value);
            setPage(1);
          }}
        />
        <label htmlFor="admin-user-role" className="sr-only">
          Vai trò
        </label>
        <NativeSelect
          id="admin-user-role"
          className="h-9 w-auto"
          value={role}
          onChange={(event) => {
            setRole(event.target.value as RoleFilter);
            setPage(1);
          }}
        >
          <option value="all">Mọi vai trò</option>
          <option value="student">Học viên</option>
          <option value="instructor">Giảng viên</option>
          <option value="admin">Quản trị viên</option>
        </NativeSelect>
        <label htmlFor="admin-user-lock" className="sr-only">
          Trạng thái tài khoản
        </label>
        <NativeSelect
          id="admin-user-lock"
          className="h-9 w-auto"
          value={lock}
          onChange={(event) => {
            setLock(event.target.value as LockFilter);
            setPage(1);
          }}
        >
          <option value="all">Mọi trạng thái</option>
          <option value="active">Đang hoạt động</option>
          <option value="locked">Đã khóa</option>
        </NativeSelect>
      </div>

      {users.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(users.error)}</AlertDescription>
        </Alert>
      ) : null}

      {users.isPending ? <ListSkeleton height="h-20" fill /> : null}

      {users.data && users.data.total === 0 ? (
        <EmptyState
          mood="empty-search"
          title="Không có tài khoản nào khớp"
          hint="Đổi từ khóa tìm kiếm hoặc bộ lọc vai trò, trạng thái."
        />
      ) : null}

      {users.data && users.data.items.length > 0 ? (
        <>
          <p className="text-sm text-muted-foreground">{users.data.total} tài khoản</p>
          <ul
            className={users.isPlaceholderData ? "space-y-2 opacity-60" : "space-y-2"}
            aria-busy={users.isFetching}
          >
            {users.data.items.map((user) => (
              <li key={user.id}>
                <UserRow user={user} />
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {users.data ? (
        <Pager
          page={users.data.page}
          pageSize={users.data.page_size}
          total={users.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}

function UserRow({ user }: { user: AdminUser }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  const toggle = useMutation({
    mutationFn: () =>
      user.locked_at
        ? unlockUser(accessToken as string, user.id)
        : lockUser(accessToken as string, user.id),
    onSuccess: () => {
      setConfirming(false);
      queryClient.invalidateQueries({ queryKey: ADMIN_KEY });
    },
  });

  const locked = user.locked_at !== null;

  return (
    <div className="space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-3">
        <UserAvatar user={user} className="size-10 shrink-0 text-sm" />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium break-words">{user.full_name}</span>
            <Badge variant={user.role === "admin" ? "default" : "secondary"}>
              {ROLE_LABELS[user.role]}
            </Badge>
            {locked ? <Badge variant="destructive">Đã khóa</Badge> : null}
          </p>
          <p className="truncate text-sm text-muted-foreground">{user.email}</p>
          <p className="text-xs text-muted-foreground">
            Tham gia {formatDate(user.created_at)} · đăng nhập{" "}
            {user.last_login_at ? formatRelativeTime(user.last_login_at) : "chưa lần nào"}
            {user.oauth_provider ? " · Google" : ""}
            {user.role === "instructor" ? ` · ${user.courses_count} khóa đang dạy` : ""}
            {` · ${user.enrollments_count} khóa đã ghi danh`}
            {locked && user.locked_at ? ` · khóa từ ${formatDate(user.locked_at)}` : ""}
          </p>
        </div>
        {user.role !== "admin" && !confirming ? (
          <Button
            variant={locked ? "outline" : "ghost"}
            size="sm"
            onClick={() => (locked ? toggle.mutate() : setConfirming(true))}
            disabled={toggle.isPending}
          >
            {toggle.isPending ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : locked ? (
              <LockOpen aria-hidden />
            ) : (
              <Lock aria-hidden />
            )}
            {locked ? "Mở khóa" : "Khóa"}
          </Button>
        ) : null}
      </div>

      {confirming ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md bg-destructive/5 p-3 text-sm">
          <span className="min-w-0 flex-1">
            Khóa <span className="font-medium">{user.full_name}</span>? Tài khoản bị đăng xuất
            khỏi mọi thiết bị ngay và không đăng nhập lại được cho tới khi mở khóa.
            {user.role === "instructor" && user.courses_count > 0
              ? " Khóa học đang bán của họ vẫn giữ nguyên."
              : ""}
          </span>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => toggle.mutate()}
            disabled={toggle.isPending}
          >
            {toggle.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Khóa tài khoản
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(false)}
            disabled={toggle.isPending}
          >
            Hủy
          </Button>
        </div>
      ) : null}

      {toggle.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(toggle.error)}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
