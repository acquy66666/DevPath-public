import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * A code that is not a certificate: mistyped, cut short, or made up.
 *
 * Says nothing more than that. Whether a code was malformed or merely unknown
 * is not something a verification page should help anybody tell apart.
 */
export default function CertificateNotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <h1 className="text-xl font-semibold tracking-tight">Không tìm thấy chứng chỉ</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Không có chứng chỉ nào mang mã này. Hãy kiểm tra lại mã in trên chứng chỉ, gồm 16 ký
        tự chữ và số.
      </p>
      <div className="mt-6">
        <Button asChild>
          <Link href="/">Về trang chủ</Link>
        </Button>
      </div>
    </div>
  );
}
