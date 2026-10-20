# docs/ui-ux — Phase 7 (nâng cấp UI/UX)

- [thiet-ke-nang-cap-ui-ux.md](thiet-ke-nang-cap-ui-ux.md): làm gì và vì sao. Đọc trước mọi task Phase 7.
- Kế hoạch có checkbox: [`docs/plan/phase-7-ui-ux-upgrade.md`](../plan/phase-7-ui-ux-upgrade.md).
- [design-system/](design-system/README.md): design system DevPath (artifact Claude Design + bản trong repo). Mọi token sinh từ `design-system/palette.py`.

## Skill đã cài cho Phase 7 (18/10/2026)

Cài **từng skill**, không cài cả repo, và không chạy CLI cài đặt của bên thứ ba. Mỗi skill đi qua bốn bước:

1. Kiểm audit trên skills.sh: `https://skills.sh/api/v1/skills/audit/<owner>/<repo>/<skill>`. JSON gốc lưu ở [`docs/report/assets/phase-7/skills-audit/`](../report/assets/phase-7/skills-audit/).
2. Tải đúng thư mục của skill, ghim theo commit, vào một thư mục tạm.
3. Đọc mọi SKILL.md và mọi script; quét phần còn lại tìm gọi mạng, chạy lệnh và câu chữ kiểu chèn chỉ dẫn.
4. Chép vào chỗ cài. Mỗi thư mục có `_source.json` ghi repo, đường dẫn, commit và các bản vá cục bộ.

Cột audit: Gen Agent Trust Hub · Socket · Snyk · Runlayer · ZeroLeaks; "–" là nhà đó chưa audit skill này.

| Skill | Nguồn @ commit | Cấp | Giấy phép | Audit | Vá cục bộ |
|---|---|---|---|---|---|
| frontend-design | `anthropics/skills` @ `dbd4588f9e10` | dự án | Apache-2.0 (`LICENSE.txt`) | pass ×5 | — |
| theme-factory | `anthropics/skills` @ `dbd4588f9e10` | dự án | Apache-2.0 (`LICENSE.txt`) | pass ×5 | — |
| canvas-design | `anthropics/skills` @ `dbd4588f9e10` | **người dùng** (`~/.claude/skills/`) | Apache-2.0; font kèm theo OFL | pass ×5 | — |
| web-design-guidelines | `vercel-labs/agent-skills` @ `063bee94c3f4` | dự án | MIT (README của repo, `_LICENSE-NOTE.md`) | pass, Socket **warn** (gptAnomaly) | **có** |
| react-best-practices (`vercel-react-best-practices`) | `vercel-labs/agent-skills` @ `063bee94c3f4` | dự án | MIT | pass ×4 | — |
| shadcn | `shadcn/ui` @ `d2fba50ee5b9` | dự án | MIT | pass, Socket **warn** (gptAnomaly) | **có** |
| ui-ux-pro-max | `nextlevelbuilder/ui-ux-pro-max-skill` @ `56ea9cf174ed` | dự án | MIT | pass ×5 | **có** |
| motion-react | `bm629/agent-skills` @ `6f1504cfc0e3` | dự án | MIT | pass ×3 (Runlayer, ZeroLeaks –) | — |
| character-appeal | `dylantarre/animation-principles` @ `83597134ba8f` | dự án | MIT | pass, Runlayer **warn MEDIUM** | — |
| education-learning | `dylantarre/animation-principles` @ `83597134ba8f` | dự án | MIT | pass, Runlayer **warn MEDIUM** | — |
| accessible-motion | `dylantarre/animation-principles` @ `83597134ba8f` | dự án | MIT | pass, Runlayer **warn MEDIUM** | — |
| visual-testing | `petrkindlmann/qa-skills` @ `b3bb61bd268b` | dự án | MIT | pass ×3 (Runlayer, ZeroLeaks –) | — |

**Vì sao `canvas-design` ở cấp người dùng:** nó nặng 5,6 MB, phần lớn là 54 tệp font, và chỉ dùng một lần để vẽ poster hay model sheet tĩnh. Mọi skill còn lại nằm trong `.claude/skills/` của repo (4,3 MB), để session ở máy khác hay trên cloud cũng có.

### Các cảnh báo, đã đọc

- **Runlayer MEDIUM ở ba skill `dylantarre`**: audit chỉ ghi "1/1 file flagged". Mỗi skill là đúng một SKILL.md hướng dẫn hoạt hình (12 nguyên lý Disney), không có lệnh, URL hay script. Đã đọc toàn văn, không thấy gì đáng ngại.
- **Socket gptAnomaly ở `web-design-guidelines`**: skill gốc tải bộ luật từ `raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` **ở mỗi lần chạy** và làm theo nội dung tải về. Trust Hub cũng gắn nhãn `EXTERNAL_DOWNLOADS`, `INDIRECT_PROMPT_INJECTION`. Đã vá (dưới).
- **Socket gptAnomaly ở `shadcn`**: skill gốc tự cấp quyền chạy `npx shadcn@latest *`, và tự chạy `npx shadcn@latest info --json` khi được nạp. Đã vá (dưới).

### Vá cục bộ

Mỗi skill bị vá có một khối "DevPath local patch" ở đầu, và danh sách bản vá trong `_source.json`.

- **shadcn**: bỏ `allowed-tools` (tự cấp quyền `npx shadcn@latest *`, `pnpm dlx …`, `bunx …`). Đổi dòng tự chạy khi nạp ``!`npx shadcn@latest info --json` `` thành chỉ dẫn thường. Thêm ghi chú của repo: chạy CLI trong `frontend/`; luôn `add --dry-run` / `--diff` trước, vì `shadcn add dialog` từng ghi đè `button.tsx` và thêm gói npm `cn`; không dùng registry cộng đồng khi chưa xem; CSP chặn script/font/style từ host khác.
- **web-design-guidelines**: bộ luật được ghim vào `references/command.md` ở commit `434b7f913646` của `vercel-labs/web-interface-guidelines` (MIT, 192 dòng, đã đọc), thay vì tải lại mỗi lần. Muốn làm mới thì tải lại, đọc diff, rồi commit.
- **ui-ux-pro-max**: đường dẫn script `${CLAUDE_PLUGIN_ROOT}/.claude/skills/…` (11 chỗ, dành cho bản cài dạng plugin) đổi thành `.claude/skills/…`, chạy từ gốc repo. Thư mục `scripts/tests/` không chép. Script chỉ dùng thư viện chuẩn của Python, không gọi mạng. Thử: `python .claude/skills/ui-ux-pro-max/scripts/search.py "educational" --domain product -n 1` ra "Educational App".

### Không cài, hoặc cài thứ khác

- **`pedronauck/skills/motion`** (tên trong tài liệu thiết kế): repo không còn skill này, kể cả `motion-react` — cây 979 tệp ở HEAD không có thư mục nào chứa "motion" ngoài một tệp tham chiếu của skill khác. skills.sh vẫn giữ bản audit cũ. Thay bằng **`bm629/agent-skills/motion-react`**: cùng phạm vi (Motion v12, `motion/react`, `motion/react-client` cho App Router), đặt `prefers-reduced-motion` và sự tiết chế lên hàng đầu, khớp phản mục tiêu "nhân vật làm phiền". Repo nhỏ (4 sao, MIT), nên đã đọc cả 6 tệp.
- **`dylantarre/animation-principles`**: repo có 144 skill. Chỉ lấy 3 skill sát việc nhất: `character-appeal` (nhân vật), `education-learning` (bối cảnh học tập), `accessible-motion` (giảm chuyển động).
- **`manutej/luxor-claude-marketplace/playwright-visual-testing`**: không cài, như plan dặn. Audit 18/10: Snyk warn MEDIUM (1 issue), Runlayer warn MEDIUM (5/5 file); catalog từng ghi HIGH.
- **`brand-guidelines`** (`anthropics/skills`): chưa cài. Nó là khuôn để viết skill `devpath-ui` ở cuối Phase 7; đọc thẳng từ repo lúc làm task đó.
- **Skill Rive** (`stevysmith/rive-skills`, `bowtiedswan/rive-skills`): chỉ cài nếu spike hoạt ảnh chọn Rive.

### Cập nhật hay gỡ

Không có lệnh cập nhật tự động; mỗi lần cập nhật đi lại đủ bốn bước ở trên và giữ các bản vá. Gỡ = xóa thư mục skill (cấp dự án thì commit việc xóa). Script tải dùng một lần (đã bỏ): đọc cây Git ở `HEAD`, ghim SHA, tải từng tệp qua `gh api … contents/<path>?ref=<sha>`, không chạy gì đã tải.
