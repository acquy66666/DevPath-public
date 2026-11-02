import { BarChart3, Code2, Layers, Sparkles } from "lucide-react";
import type { Metadata } from "next";

import { BecomeInstructorCard } from "@/components/auth/become-instructor-card";

export const metadata: Metadata = {
  title: "Trở thành giảng viên — DevPath",
  description:
    "Gửi yêu cầu trở thành giảng viên DevPath để tạo khóa học, ra bài tập code được chấm tự động và theo dõi học viên.",
};

/** What the instructor area holds, said as what you can do with it. */
const TOOLS = [
  { icon: Layers, title: "Soạn khóa học", text: "Chương, bài giảng video và bài đọc, sắp xếp bằng kéo-thả." },
  { icon: Code2, title: "Bài tập code", text: "Test mẫu và test ẩn, chấm tự động trong sandbox Docker." },
  { icon: Sparkles, title: "Sinh quiz bằng AI", text: "Câu hỏi nháp từ nội dung bài giảng, bạn duyệt từng câu." },
  { icon: BarChart3, title: "Thống kê và hỏi đáp", text: "Học viên mới, tỉ lệ hoàn thành, câu hỏi chưa trả lời." },
];

/** The road from this page to a course on sale -- both admin reviews included. */
const STEPS = [
  { title: "Gửi yêu cầu", text: "Kèm vài dòng giới thiệu về bạn." },
  { title: "Được duyệt", text: "Quản trị viên mở khu giảng dạy cho bạn." },
  { title: "Soạn và gửi duyệt", text: "Khóa học nháp được xem lại nội dung." },
  { title: "Lên sàn", text: "Học viên tìm thấy và ghi danh." },
];

export default function BecomeInstructorPage() {
  return (
    <div className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] items-start gap-12 px-4 pt-10 pb-16 md:pt-14 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="min-w-0 space-y-10">
        <header className="space-y-4">
          <p className="text-eyebrow text-link uppercase">Dành cho người dạy</p>
          <h1 className="text-display text-balance">Dạy lập trình bằng bài tập được chấm tự động</h1>
          <p className="max-w-[34em] text-body-lg text-foreground/80">
            Soạn khóa học, ra bài tập có bộ test, để hệ thống chấm từng bài nộp trong sandbox. Bạn dành
            thời gian cho bài giảng, không cho việc chấm tay.
          </p>
        </header>

        <section aria-labelledby="cong-cu" className="space-y-4">
          <h2 id="cong-cu" className="text-h2">
            Bạn có những gì
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {TOOLS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3 rounded-lg border bg-card p-4">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                  <Icon className="size-4.5" aria-hidden />
                </span>
                <span className="min-w-0 space-y-0.5">
                  <span className="block text-title">{title}</span>
                  <span className="block text-body-sm text-muted-foreground">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="cac-buoc" className="space-y-4">
          <h2 id="cac-buoc" className="text-h2">
            Từ tài khoản tới khóa học trên sàn
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title} className={index === 0 ? "border-t-2 border-primary pt-3" : "border-t-2 border-border-strong pt-3"}>
                <span className="block font-mono text-code-sm font-semibold text-link">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="mt-1 block text-title">{step.title}</span>
                <span className="block text-body-sm text-muted-foreground">{step.text}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      {/* After the explanation on a phone, beside it from lg: the reader has
          seen what the button does before reaching it. */}
      <aside aria-label="Yêu cầu trở thành giảng viên" className="lg:sticky lg:top-8">
        <BecomeInstructorCard />
      </aside>
    </div>
  );
}
