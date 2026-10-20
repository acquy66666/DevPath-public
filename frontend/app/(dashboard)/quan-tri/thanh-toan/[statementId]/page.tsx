import { StatementDetail } from "@/components/admin/finance/statement-detail";

export default async function AdminStatementPage({
  params,
}: {
  params: Promise<{ statementId: string }>;
}) {
  const { statementId } = await params;
  return <StatementDetail id={statementId} />;
}
