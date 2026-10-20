import { apiFetch } from "./client";
import type { Page } from "./courses";

/**
 * The admin's money pages. Types mirror `backend/app/schemas/finance.py`.
 *
 * Money arrives as strings ("280000.00"), rates as numbers in 0..1, dates as
 * Vietnamese calendar days ("2026-10-20"), bucket starts as Vietnamese wall
 * clock with no zone ("2026-10-20T09:00:00").
 */

export type FinanceGranularity = "hour" | "day" | "week" | "month" | "quarter" | "year";

export const GRANULARITIES: { value: FinanceGranularity; label: string; maxDays: number }[] = [
  { value: "hour", label: "Giờ", maxDays: 7 },
  { value: "day", label: "Ngày", maxDays: 366 },
  { value: "week", label: "Tuần", maxDays: 1100 },
  { value: "month", label: "Tháng", maxDays: 3660 },
  { value: "quarter", label: "Quý", maxDays: 3660 },
  { value: "year", label: "Năm", maxDays: 3660 },
];

export interface Person {
  id: string;
  full_name: string;
  email: string;
}

export interface TierBrief {
  id: string;
  code: string;
  name: string;
  rank: number;
  share_rate: string;
}

export interface Money {
  orders: number;
  lines: number;
  buyers: number;
  list_amount: string;
  discount: string;
  paid: string;
  instructor_share: string;
  platform_share: string;
}

export interface MoneyPoint extends Money {
  bucket: string;
}

export interface Revenue {
  start: string;
  end: string;
  granularity: FinanceGranularity;
  previous_start: string;
  previous_end: string;
  instructor: Person | null;
  totals: Money;
  previous: Money;
  series: MoneyPoint[];
}

export interface InstructorMoney extends Money {
  instructor: Person;
  tier: TierBrief;
  courses_sold: number;
  share_of_paid: number | null;
}

export interface CourseMoney extends Money {
  course_id: string;
  course_title: string;
  course_slug: string;
  instructor: Person;
}

export interface RevenueBreakdown {
  start: string;
  end: string;
  instructors: InstructorMoney[];
  courses: CourseMoney[];
}

export interface RangeParams {
  start?: string;
  end?: string;
}

function search(params: Record<string, string | number | undefined | null>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function revenuePath(
  params: RangeParams & { granularity: FinanceGranularity; instructorId?: string | null },
  suffix = "",
): string {
  return `/api/v1/admin/finance/revenue${suffix}${search({
    start: params.start,
    end: params.end,
    granularity: params.granularity,
    instructor_id: params.instructorId,
  })}`;
}

export function getRevenue(
  accessToken: string,
  params: RangeParams & { granularity: FinanceGranularity; instructorId?: string | null },
): Promise<Revenue> {
  return apiFetch<Revenue>(revenuePath(params), { accessToken });
}

export function getRevenueBreakdown(
  accessToken: string,
  params: RangeParams & { instructorId?: string | null },
): Promise<RevenueBreakdown> {
  return apiFetch<RevenueBreakdown>(
    `/api/v1/admin/finance/revenue/breakdown${search({
      start: params.start,
      end: params.end,
      instructor_id: params.instructorId,
    })}`,
    { accessToken },
  );
}

// --- Rankings -----------------------------------------------------------------

export type RankUnit = "money" | "count" | "rating" | "rate" | "hours";

export interface RankEntry {
  rank: number;
  key: string;
  label: string;
  detail: string | null;
  value: string | number;
  previous: string | number | null;
}

export interface Ranking {
  code: string;
  group: "instructors" | "courses" | "coupons" | "categories";
  title: string;
  unit: RankUnit;
  ascending: boolean;
  note: string | null;
  total_entries: number;
  entries: RankEntry[];
}

export interface Leaderboards {
  start: string;
  end: string;
  previous_start: string;
  previous_end: string;
  rankings: Ranking[];
  concentration: { top1: number | null; top5: number | null; top10: number | null; instructors: number };
}

export const rankingsPath = (params: RangeParams, suffix = "") =>
  `/api/v1/admin/finance/rankings${suffix}${search({ start: params.start, end: params.end })}`;

export function getRankings(accessToken: string, params: RangeParams): Promise<Leaderboards> {
  return apiFetch<Leaderboards>(rankingsPath(params), { accessToken });
}

// --- Tiers --------------------------------------------------------------------

export interface TierAdmin extends TierBrief {
  description: string | null;
  min_paid_students: number;
  min_revenue_12m: string;
  min_rating: string | null;
  min_reviews: number;
  min_completion_rate: string | null;
  min_qa_answer_rate: string | null;
  min_published_courses: number;
  min_months_active: number;
  instructors: number;
}

export type TierUpdate = Partial<
  Pick<
    TierAdmin,
    | "name"
    | "description"
    | "share_rate"
    | "min_paid_students"
    | "min_revenue_12m"
    | "min_rating"
    | "min_reviews"
    | "min_completion_rate"
    | "min_qa_answer_rate"
    | "min_published_courses"
    | "min_months_active"
  >
>;

export interface Criterion {
  key: string;
  label: string;
  value: string;
  threshold: string;
  met: boolean;
  admin_only: boolean;
}

export interface TierMetrics {
  paid_students: number;
  revenue_12m: string;
  reviews: number;
  rating_raw: number | null;
  rating: number | null;
  completion_rate: number | null;
  completion_base: number;
  qa_questions: number;
  qa_answer_rate: number | null;
  published_courses: number;
  first_published_at: string | null;
  months_active: number;
  removed_courses_90d: number;
  locked: boolean;
}

export interface TierChange {
  id: string;
  from_tier: TierBrief | null;
  to_tier: TierBrief;
  decided_by: Person | null;
  note: string;
  metrics: Record<string, unknown>;
  created_at: string;
}

export type TierFlag = "eligible" | "below_maintenance" | "recently_changed" | "top_tier_skips_a_step";

export interface Evaluation {
  instructor: Person;
  current: TierBrief;
  suggested: TierBrief;
  keeps_current: boolean;
  flags: TierFlag[];
  metrics: TierMetrics;
  checks: { tier: TierBrief; met: boolean; criteria: Criterion[] }[];
  last_change: TierChange | null;
}

export const listTiers = (accessToken: string) =>
  apiFetch<TierAdmin[]>("/api/v1/admin/tiers", { accessToken });

export const updateTier = (accessToken: string, tierId: string, body: TierUpdate) =>
  apiFetch<TierAdmin>(`/api/v1/admin/tiers/${tierId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(body),
  });

export const listEvaluations = (accessToken: string) =>
  apiFetch<Evaluation[]>("/api/v1/admin/instructor-tiers", { accessToken });

export const tierHistory = (accessToken: string, instructorId: string) =>
  apiFetch<TierChange[]>(`/api/v1/admin/instructor-tiers/${instructorId}/history`, {
    accessToken,
  });

export const setInstructorTier = (
  accessToken: string,
  instructorId: string,
  body: { tier_id: string; note: string },
) =>
  apiFetch<Evaluation>(`/api/v1/admin/instructor-tiers/${instructorId}`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });

export const TIER_REVIEW_EXPORT = "/api/v1/admin/instructor-tiers/export.xlsx";

// --- Payouts ------------------------------------------------------------------

export type PayoutStatus = "draft" | "confirmed" | "paid" | "void";

export const PAYOUT_STATUS_LABELS: Record<PayoutStatus, string> = {
  draft: "Nháp",
  confirmed: "Đã chốt",
  paid: "Đã chi trả",
  void: "Đã hủy",
};

export interface Balance {
  instructor: Person;
  earned_all_time: string;
  unbilled: string;
  unbilled_lines: number;
  oldest_unbilled: string | null;
  in_draft: string;
  confirmed_unpaid: string;
  paid_out: string;
  tax_withheld: string;
}

export interface Balances {
  settings: { minimum: string; pit_rate: string; pit_threshold: string };
  items: Balance[];
}

export interface Statement {
  id: string;
  code: string;
  instructor_id: string;
  instructor_name: string;
  instructor_email: string;
  period_start: string;
  period_end: string;
  status: PayoutStatus;
  line_count: number;
  gross_amount: string;
  instructor_amount: string;
  platform_amount: string;
  tax_withheld: string;
  payable_amount: string;
  note: string | null;
  created_at: string;
  confirmed_at: string | null;
  paid_at: string | null;
  payment_reference: string | null;
  voided_at: string | null;
  void_reason: string | null;
}

export interface StatementLine {
  id: string;
  order_code: string;
  course_id: string;
  course_title: string;
  paid_at: string;
  unit_price: string;
  discount: string;
  net_amount: string;
  share_rate: string;
  instructor_amount: string;
}

export interface StatementDetail extends Statement {
  carried_lines: number;
  lines: StatementLine[];
}

export interface StatementBatch {
  period_start: string;
  period_end: string;
  created: Statement[];
  skipped: { instructor: Person; amount: string; lines: number }[];
}

export const getBalances = (accessToken: string) =>
  apiFetch<Balances>("/api/v1/admin/payouts/balances", { accessToken });

export const listStatements = (
  accessToken: string,
  params: { status?: PayoutStatus | ""; month?: string; page?: number },
) =>
  apiFetch<Page<Statement>>(
    `/api/v1/admin/payouts/statements${search({
      status: params.status,
      month: params.month,
      page: params.page ?? 1,
    })}`,
    { accessToken },
  );

export const createStatements = (accessToken: string, month: string, instructorIds: string[] = []) =>
  apiFetch<StatementBatch>("/api/v1/admin/payouts/statements", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ month, instructor_ids: instructorIds }),
  });

export const getStatement = (accessToken: string, id: string) =>
  apiFetch<StatementDetail>(`/api/v1/admin/payouts/statements/${id}`, { accessToken });

export const setWithholding = (accessToken: string, id: string, withhold: boolean, note?: string) =>
  apiFetch<StatementDetail>(`/api/v1/admin/payouts/statements/${id}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify({ withhold, ...(note !== undefined ? { note } : {}) }),
  });

export const confirmStatement = (accessToken: string, id: string) =>
  apiFetch<StatementDetail>(`/api/v1/admin/payouts/statements/${id}/confirm`, {
    method: "POST",
    accessToken,
  });

export const payStatement = (accessToken: string, id: string, reference: string) =>
  apiFetch<StatementDetail>(`/api/v1/admin/payouts/statements/${id}/pay`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ reference }),
  });

export const voidStatement = (accessToken: string, id: string, reason: string) =>
  apiFetch<StatementDetail>(`/api/v1/admin/payouts/statements/${id}/void`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ reason }),
  });

export const deleteStatement = (accessToken: string, id: string) =>
  apiFetch<void>(`/api/v1/admin/payouts/statements/${id}`, { method: "DELETE", accessToken });

export const statementExportPath = (id: string) =>
  `/api/v1/admin/payouts/statements/${id}/export.xlsx`;

export const payoutsExportPath = (params: { status?: PayoutStatus | ""; month?: string }) =>
  `/api/v1/admin/payouts/export.xlsx${search({ status: params.status, month: params.month })}`;

// --- Profit -------------------------------------------------------------------

export type ExpenseCategory =
  | "infrastructure"
  | "ai_api"
  | "payment_fee"
  | "marketing"
  | "staff"
  | "tax"
  | "other";

export interface ProfitColumn {
  start: string;
  end: string;
  list_amount: string;
  discount: string;
  collected: string;
  instructor_share: string;
  platform_revenue: string;
  gateway_orders: number;
  gateway_fee: string;
  expenses: Record<ExpenseCategory, string>;
  operating_expenses: string;
  profit_before_tax: string;
  tax: string;
  retained: string;
  take_rate: number | null;
  gross_margin: number | null;
  net_margin: number | null;
}

export interface Profit {
  year: number;
  granularity: "month" | "quarter";
  columns: ProfitColumn[];
  total: ProfitColumn;
  fee_rate: string;
  fee_source: string;
  category_labels: Record<ExpenseCategory, string>;
}

export interface Expense {
  id: string;
  incurred_on: string;
  category: ExpenseCategory;
  description: string;
  amount: string;
  created_by: Person | null;
  created_at: string;
}

export interface ExpenseInput {
  incurred_on: string;
  category: ExpenseCategory;
  description: string;
  amount: string;
}

export interface ExpensePage extends Page<Expense> {
  amount: string;
}

export const profitPath = (year: number, granularity: "month" | "quarter", suffix = "") =>
  `/api/v1/admin/finance/profit${suffix}${search({ year, granularity })}`;

export const getProfit = (accessToken: string, year: number, granularity: "month" | "quarter") =>
  apiFetch<Profit>(profitPath(year, granularity), { accessToken });

export const expensesPath = (
  params: { year?: number; month?: number | null; category?: ExpenseCategory | ""; page?: number },
  suffix = "",
) =>
  `/api/v1/admin/expenses${suffix}${search({
    year: params.year,
    month: params.month,
    category: params.category,
    page: suffix ? undefined : params.page,
  })}`;

export const listExpenses = (
  accessToken: string,
  params: { year?: number; month?: number | null; category?: ExpenseCategory | ""; page?: number },
) => apiFetch<ExpensePage>(expensesPath(params), { accessToken });

export const createExpense = (accessToken: string, body: ExpenseInput) =>
  apiFetch<Expense>("/api/v1/admin/expenses", {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });

export const updateExpense = (accessToken: string, id: string, body: Partial<ExpenseInput>) =>
  apiFetch<Expense>(`/api/v1/admin/expenses/${id}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(body),
  });

export const deleteExpense = (accessToken: string, id: string) =>
  apiFetch<void>(`/api/v1/admin/expenses/${id}`, { method: "DELETE", accessToken });

export const overviewExportPath = (period: string) =>
  `/api/v1/admin/stats/export.xlsx?period=${period}`;
