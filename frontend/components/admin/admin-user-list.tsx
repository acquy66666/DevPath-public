"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Lock, LockOpen } from "lucide-react";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { AdminTitle, EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { UserAvatar } from "@/components/auth/user-avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { cn } from "@/lib/utils";

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
  const [locking, setLocking] = useState<AdminUser | null>(null);

  const users = useQuery({
    queryKey: [...ADMIN_KEY, "users", q, role, lock, page],
    queryFn: () => listAdminUsers(accessToken as string, { q, role, lock, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-5" aria-labelledby="admin-users-title">
      <AdminTitle
        id="admin-users-title"
        title="Người dùng"
        description="Khóa một tài khoản là đăng xuất họ khỏi mọi thiết bị; bài viết và khóa học của họ giữ nguyên."
      />

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
          className="w-auto"
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
          className="w-auto"
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
          <p className="text-body-sm text-muted-foreground">{users.data.total} tài khoản</p>
          {/* A phone gets cards: a five-column table there hid the lock button off the side. */}
          <ul
            className={cn("space-y-2 md:hidden", users.isPlaceholderData && "opacity-60")}
            aria-busy={users.isFetching}
          >
            {users.data.items.map((user) => (
              <li key={user.id}>
                <UserCard user={user} onLock={() => setLocking(user)} />
              </li>
            ))}
          </ul>
          {/* `relative` keeps the sr-only header cell inside the scrolling box. */}
          <div className="relative hidden overflow-x-auto rounded-lg border bg-card md:block">
            <table
              className={cn("w-full min-w-[44rem] text-body-sm", users.isPlaceholderData && "opacity-60")}
              aria-busy={users.isFetching}
            >
              <thead>
                <tr className="border-b bg-muted text-left text-muted-foreground">
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Tài khoản
                  </th>
                  <th scope="col" className="px-3 py-2.5 font-medium">
                    Vai trò
                  </th>
                  <th scope="col" className="px-3 py-2.5 font-medium">
                    Tham gia
                  </th>
                  <th scope="col" className="px-3 py-2.5 font-medium">
                    Đăng nhập gần nhất
                  </th>
                  <th scope="col" className="px-4 py-2.5">
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((user) => (
                  <UserRow key={user.id} user={user} onLock={() => setLocking(user)} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <LockDialog user={locking} onClose={() => setLocking(null)} />

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

/** Unlocking gives access back, so it needs no question first. */
function useUnlock(user: AdminUser) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unlockUser(accessToken as string, user.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_KEY }),
  });
}

function RoleBadges({ user }: { user: AdminUser }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant={ROLE_VARIANTS[user.role]}>{ROLE_LABELS[user.role]}</Badge>
      {user.locked_at ? <Badge variant="destructive">Đã khóa {formatDate(user.locked_at)}</Badge> : null}
    </div>
  );
}

function holdings(user: AdminUser): string {
  return user.role === "instructor"
    ? `${user.courses_count} khóa đang dạy`
    : `${user.enrollments_count} khóa đã ghi danh`;
}

function LockAction({ user, onLock }: { user: AdminUser; onLock: () => void }) {
  const unlock = useUnlock(user);
  if (user.role === "admin") {
    return <span className="text-caption text-muted-foreground">Không khóa được</span>;
  }
  return (
    <>
      {user.locked_at ? (
        <Button variant="outline" size="sm" onClick={() => unlock.mutate()} disabled={unlock.isPending}>
          {unlock.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <LockOpen aria-hidden />}
          Mở khóa
          <span className="sr-only"> {user.full_name}</span>
        </Button>
      ) : (
        <Button variant="outline" size="sm" onClick={onLock}>
          <Lock aria-hidden />
          Khóa
          <span className="sr-only"> {user.full_name}</span>
        </Button>
      )}
      {unlock.isError ? (
        <p className="mt-1 text-caption text-destructive-text">{apiErrorMessage(unlock.error)}</p>
      ) : null}
    </>
  );
}

function UserCard({ user, onLock }: { user: AdminUser; onLock: () => void }) {
  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border p-3",
        user.locked_at ? "bg-destructive-soft" : "bg-card",
      )}
    >
      <div className="flex items-start gap-2.5">
        <UserAvatar user={user} className="size-8 shrink-0 text-xs" />
        <div className="min-w-0 flex-1">
          <p className="font-medium break-words">{user.full_name}</p>
          <p className="truncate text-caption text-muted-foreground">
            {user.email}
            {user.oauth_provider ? " · Google" : ""}
          </p>
        </div>
      </div>
      <RoleBadges user={user} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-caption text-muted-foreground">
          {holdings(user)} · tham gia {formatDate(user.created_at)} · đăng nhập{" "}
          {user.last_login_at ? formatRelativeTime(user.last_login_at) : "chưa lần nào"}
        </p>
        <div>
          <LockAction user={user} onLock={onLock} />
        </div>
      </div>
    </div>
  );
}

function UserRow({ user, onLock }: { user: AdminUser; onLock: () => void }) {
  const locked = user.locked_at !== null;

  return (
    <tr className={cn("border-b last:border-b-0", locked && "bg-destructive-soft")}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2.5">
          <UserAvatar user={user} className="size-8 shrink-0 text-xs" />
          <div className="min-w-0">
            <p className="font-medium break-words">{user.full_name}</p>
            <p className="truncate text-caption text-muted-foreground">
              {user.email}
              {user.oauth_provider ? " · Google" : ""}
            </p>
          </div>
        </div>
      </td>
      <td className="px-3 py-3">
        <RoleBadges user={user} />
        <p className="mt-1 text-caption text-muted-foreground">{holdings(user)}</p>
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-muted-foreground">{formatDate(user.created_at)}</td>
      <td className="px-3 py-3 whitespace-nowrap text-muted-foreground">
        {user.last_login_at ? formatRelativeTime(user.last_login_at) : "chưa lần nào"}
      </td>
      <td className="px-4 py-3 text-right">
        <LockAction user={user} onLock={onLock} />
      </td>
    </tr>
  );
}

const ROLE_VARIANTS = { student: "muted", instructor: "secondary", admin: "default" } as const;

/** Locking someone out asks first, and says what stays as it is. */
function LockDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const lock = useMutation({
    mutationFn: (target: AdminUser) => lockUser(accessToken as string, target.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_KEY });
      onClose();
    },
  });

  return (
    <Dialog
      open={user !== null}
      onOpenChange={(open) => {
        if (!open && !lock.isPending) {
          lock.reset();
          onClose();
        }
      }}
    >
      <DialogContent>
        {user ? (
          <>
            <DialogHeader>
              <DialogTitle>Khóa tài khoản {user.full_name}?</DialogTitle>
              <DialogDescription>
                Họ bị đăng xuất khỏi mọi thiết bị và không đăng nhập lại được tới khi bạn mở khóa.
                {user.role === "instructor" && user.courses_count > 0
                  ? ` ${user.courses_count} khóa học đang bán của họ vẫn giữ nguyên.`
                  : ""}
              </DialogDescription>
            </DialogHeader>
            {lock.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{apiErrorMessage(lock.error)}</AlertDescription>
              </Alert>
            ) : null}
            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={lock.isPending}>
                Hủy
              </Button>
              <Button variant="destructive" onClick={() => lock.mutate(user)} disabled={lock.isPending}>
                {lock.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
                Khóa tài khoản
              </Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
