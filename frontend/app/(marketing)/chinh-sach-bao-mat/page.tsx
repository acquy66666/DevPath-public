import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Chính sách bảo mật — DevPath",
  description:
    "DevPath thu thập dữ liệu gì, dùng vào việc gì, chia sẻ với ai và bạn có những quyền gì với dữ liệu của mình.",
};

// Google's OAuth consent screen links here: an app open to every Google
// account must publish a privacy policy on its own domain. Keep it true to
// what the code does -- change the data the app keeps, change this page.
const UPDATED_ON = "18/10/2026";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 leading-7">{children}</div>
    </section>
  );
}

function Bullets({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-2 pl-6">{children}</ul>;
}

function External({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">
      {children}
    </a>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Chính sách bảo mật</h1>
      <p className="mt-2 text-muted-foreground">Cập nhật lần cuối: {UPDATED_ON}</p>

      <p className="mt-6 leading-7">
        DevPath là nền tảng học lập trình trực tuyến, được xây dựng trong một khóa luận tốt nghiệp.
        Trang này nói rõ DevPath thu thập dữ liệu gì về bạn, dùng vào việc gì, chia sẻ với ai, và bạn
        có những quyền gì với dữ liệu đó.
      </p>

      <Section title="1. Dữ liệu DevPath thu thập">
        <Bullets>
          <li>
            <strong>Tài khoản:</strong> email, họ tên, ảnh đại diện, vai trò (học viên, giảng viên,
            quản trị viên). Nếu bạn đăng ký bằng mật khẩu, DevPath chỉ lưu bản băm của mật khẩu, không
            lưu mật khẩu gốc.
          </li>
          <li>
            <strong>Khi đăng nhập bằng Google:</strong> DevPath chỉ xin ba quyền cơ bản{" "}
            <code>openid</code>, <code>email</code>, <code>profile</code>. Google gửi lại mã định
            danh tài khoản Google, địa chỉ email, việc email đã được xác minh hay chưa, tên và ảnh đại
            diện. DevPath không đọc Gmail, Drive, danh bạ hay bất kỳ dữ liệu Google nào khác.
          </li>
          <li>
            <strong>Hoạt động học tập:</strong> khóa học đã ghi danh, tiến độ từng bài, ghi chú và
            đánh dấu, bài trắc nghiệm, mã nguồn bạn nộp cùng kết quả chấm, điểm kinh nghiệm (XP), chuỗi
            ngày học, chứng chỉ, đánh giá khóa học, câu hỏi và trả lời trong mục Hỏi đáp, báo cáo vi
            phạm.
          </li>
          <li>
            <strong>Trợ giảng AI:</strong> các câu bạn hỏi và câu trả lời, lưu theo từng phiên trò
            chuyện.
          </li>
          <li>
            <strong>Nội dung giảng viên đăng:</strong> thông tin khóa học, bài đọc cùng ảnh chèn
            trong bài, video, transcript, bài tập và câu hỏi trắc nghiệm.
          </li>
          <li>
            <strong>Mua khóa học:</strong> đơn hàng, số tiền, mã giảm giá đã dùng, và thông báo kết
            quả mà VNPay gửi về. Số thẻ hay tài khoản ngân hàng được nhập trên trang của VNPay; DevPath
            không nhận và không lưu các thông tin đó.
          </li>
          <li>
            <strong>Dữ liệu kỹ thuật:</strong> địa chỉ IP và tên trình duyệt của mỗi phiên đăng nhập,
            số lần đăng nhập gần đây (để chặn dò mật khẩu), và nhật ký truy cập của máy chủ.
          </li>
        </Bullets>
      </Section>

      <Section title="2. DevPath dùng dữ liệu vào việc gì">
        <Bullets>
          <li>Cho bạn đăng nhập, học, nộp bài, được chấm điểm và nhận chứng chỉ.</li>
          <li>
            Gợi ý khóa học phù hợp, dựa trên khóa bạn đã ghi danh và nội dung khóa học.
          </li>
          <li>Giữ an toàn cho tài khoản và hệ thống: giới hạn số lần đăng nhập, phát hiện lạm dụng.</li>
          <li>Cho giảng viên thấy số liệu tổng hợp về khóa học của họ (học viên, tiến độ, doanh thu).</li>
        </Bullets>
        <p>
          DevPath không bán dữ liệu của bạn, không hiển thị quảng cáo, và không gắn công cụ theo dõi
          hay phân tích của bên thứ ba. Ảnh trong bài đọc, đề bài và Hỏi đáp chỉ được tải từ kho lưu
          trữ của DevPath; ảnh trỏ tới trang khác hiện thành liên kết, để trang đó không biết ai
          đang đọc.
        </p>
      </Section>

      <Section title="3. Ai nhìn thấy gì về bạn">
        <Bullets>
          <li>
            Người dùng đã đăng nhập khác thấy tên, ảnh đại diện và XP của bạn trên bảng xếp hạng, cùng
            tên của bạn bên cạnh đánh giá và câu hỏi bạn viết.
          </li>
          <li>
            Mỗi chứng chỉ có một trang công khai ghi tên bạn và tên khóa học, để người khác kiểm tra
            được. Ai có mã chứng chỉ đều mở được trang đó.
          </li>
          <li>
            Giảng viên của khóa bạn học thấy câu hỏi bạn gửi trong khóa đó. Quản trị viên xem được dữ
            liệu khi cần xử lý báo cáo vi phạm hoặc sự cố.
          </li>
        </Bullets>
      </Section>

      <Section title="4. Bên thứ ba xử lý dữ liệu">
        <Bullets>
          <li>
            <strong>Google:</strong> xác thực khi bạn chọn đăng nhập bằng Google. Câu hỏi bạn gửi trợ
            giảng AI, kèm các đoạn nội dung khóa học liên quan, được gửi tới Google Gemini API để soạn
            câu trả lời. Giảng viên dùng tính năng sinh câu hỏi trắc nghiệm thì nội dung bài học cũng
            được gửi tới Gemini.
          </li>
          <li>
            <strong>VNPay:</strong> nhận mã đơn và số tiền khi bạn thanh toán.
          </li>
          <li>
            <strong>Cloudflare:</strong> mọi kết nối tới DevPath đi qua mạng của Cloudflare, nơi cấp
            chứng chỉ HTTPS và chuyển tiếp yêu cầu tới máy chủ.
          </li>
        </Bullets>
      </Section>

      <Section title="5. Cookie và bộ nhớ trình duyệt">
        <Bullets>
          <li>
            Cookie <code>devpath_refresh</code> giữ cho bạn đăng nhập, tối đa 30 ngày. Cookie này có cờ
            HttpOnly, nên mã JavaScript trên trang không đọc được.
          </li>
          <li>
            Một cookie tạm, sống 10 phút, được đặt khi bạn bấm đăng nhập bằng Google, để chống giả mạo
            yêu cầu đăng nhập.
          </li>
          <li>
            Bộ nhớ của trình duyệt (localStorage) giữ bản nháp mã nguồn bạn đang viết và tốc độ phát
            video bạn chọn. Dữ liệu này nằm trên máy bạn, không gửi về máy chủ.
          </li>
        </Bullets>
        <p>DevPath không dùng cookie quảng cáo hay cookie phân tích.</p>
      </Section>

      <Section title="6. Lưu trữ và bảo vệ dữ liệu">
        <p>
          Dữ liệu nằm trên máy chủ do DevPath vận hành, và mọi kết nối đều đi qua HTTPS. Mã nguồn bạn
          nộp được chạy trong một môi trường cô lập, không có mạng, có giới hạn thời gian và bộ nhớ.
          Dữ liệu được giữ tới khi tài khoản bị xóa.
        </p>
      </Section>

      <Section title="7. Quyền của bạn">
        <Bullets>
          <li>
            Xem và sửa họ tên, ảnh đại diện, đổi mật khẩu tại trang{" "}
            <Link href="/ho-so" className="underline underline-offset-4">
              Hồ sơ
            </Link>
            .
          </li>
          <li>Xóa ghi chú, đánh dấu và các phiên trò chuyện với trợ giảng AI ngay trong trang học.</li>
          <li>
            Gỡ quyền truy cập của DevPath vào tài khoản Google bất cứ lúc nào tại{" "}
            <External href="https://myaccount.google.com/connections">
              myaccount.google.com/connections
            </External>
            .
          </li>
          <li>Yêu cầu xuất hoặc xóa toàn bộ dữ liệu tài khoản, theo cách liên hệ ở mục 9.</li>
        </Bullets>
      </Section>

      <Section title="8. Thay đổi chính sách">
        <p>
          Khi DevPath thay đổi cách thu thập hay sử dụng dữ liệu, trang này sẽ được cập nhật, kèm ngày
          cập nhật ở đầu trang.
        </p>
      </Section>

      <Section title="9. Liên hệ">
        <p>
          Mọi câu hỏi hay yêu cầu về dữ liệu cá nhân, xin gửi tới email hỗ trợ của DevPath. Địa chỉ này
          hiện trên màn hình đăng nhập bằng Google: bấm vào tên DevPath ở màn hình đó để xem.
        </p>
      </Section>
    </article>
  );
}
