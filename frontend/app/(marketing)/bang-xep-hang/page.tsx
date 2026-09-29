import type { Metadata } from "next";

import { LeaderboardView } from "@/components/gamification/leaderboard-view";

export const metadata: Metadata = {
  title: "Bảng xếp hạng — DevPath",
  description: "Ai đã học chăm nhất tuần này, tháng này và từ trước tới nay trên DevPath.",
  // A list of learners' names, shown only to learners who are signed in.
  robots: { index: false },
};

export default function LeaderboardPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Bảng xếp hạng</h1>
      <p className="mt-2 mb-6 text-muted-foreground">
        Xếp theo XP: hoàn thành bài học, vượt qua bài trắc nghiệm và giải bài tập code.
      </p>
      <LeaderboardView />
    </div>
  );
}
