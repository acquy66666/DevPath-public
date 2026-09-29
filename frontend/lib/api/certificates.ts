import { apiFetch, apiUrl } from "./client";

/** Mirrors `CertificateOut`: what is printed on the paper, nothing about the account. */
export interface Certificate {
  code: string;
  /** ABCD-EFGH-JKLM-NPQR, as printed. */
  display_code: string;
  recipient_name: string;
  course_title: string;
  instructor_name: string;
  issued_at: string;
  /** The course page while the course is still on sale; null after that. */
  course_slug: string | null;
  /** False until the worker has drawn the PDF. */
  pdf_ready: boolean;
  verify_url: string;
}

/** Public: holding the code is the permission. */
export function getCertificate(code: string): Promise<Certificate> {
  return apiFetch<Certificate>(`/api/v1/certificates/${encodeURIComponent(code)}`);
}

/** Where the browser downloads the PDF from -- a plain link, no token needed. */
export function certificatePdfUrl(code: string): string {
  return apiUrl(`/api/v1/certificates/${encodeURIComponent(code)}/pdf`);
}
