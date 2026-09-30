import { redirect } from "next/navigation";

/** Until the admin dashboard exists, the review queue is the front door. */
export default function AdminIndexPage() {
  redirect("/quan-tri/khoa-hoc");
}
