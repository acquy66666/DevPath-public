import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * A code that is not a certificate: mistyped, cut short, or made up.
 *
 * Says nothing more than that. Whether a code was malformed or merely unknown
 * is not something a verification page should help anybody tell apart.
 */
export default function CertificateNotFound() {
  return (
    <StatePanel
      mood="lost"
      code="404"
      title="Không tìm thấy chứng chỉ"
      actions={
        <Button asChild>
          <Link href="/">Về trang chủ</Link>
        </Button>
      }
    >
      Không có chứng chỉ nào mang mã này. Hãy kiểm tra lại mã in trên chứng chỉ, gồm 16 ký tự chữ và số.
    </StatePanel>
  );
}
