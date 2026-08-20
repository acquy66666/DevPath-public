import { connection } from "next/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth, type Health } from "@/lib/api/health";

/**
 * Server Component. Proves the frontend can reach the FastAPI backend.
 *
 * Awaiting happens inside try/catch, rendering happens outside it: JSX built
 * inside a try block would swallow render errors thrown by children.
 *
 * connection() defers this component to request time. Without it the card is
 * prerendered at build time, freezing whatever the backend answered then --
 * which is a stale "offline" badge on every page load.
 */
export async function BackendStatus() {
  await connection();

  let health: Health | null = null;
  let reason = "";

  try {
    health = await getHealth();
  } catch (error) {
    reason = error instanceof Error ? error.message : "Lỗi không xác định";
  }

  if (health === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Kết nối backend
            <Badge variant="destructive">Không kết nối được</Badge>
          </CardTitle>
          <CardDescription>
            Kiểm tra backend đã chạy chưa:{" "}
            <code className="font-mono">uvicorn app.main:app --reload</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">{reason}</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Kết nối backend
          <Badge>{health.status === "ok" ? "Hoạt động" : health.status}</Badge>
        </CardTitle>
        <CardDescription>Frontend gọi được API của {health.app}.</CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        Môi trường: <code className="font-mono">{health.env}</code>
      </CardContent>
    </Card>
  );
}

export function BackendStatusSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Kết nối backend</CardTitle>
        <CardDescription>Đang kiểm tra…</CardDescription>
      </CardHeader>
      <CardContent className="h-5 w-32 animate-pulse rounded bg-muted" />
    </Card>
  );
}
