import { apiFetch } from "./client";

/** Matches HealthOut in backend/app/schemas/health.py. */
export interface Health {
  status: string;
  app: string;
  env: string;
}

export function getHealth(): Promise<Health> {
  return apiFetch<Health>("/api/v1/health");
}
