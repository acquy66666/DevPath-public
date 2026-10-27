import { Mascot } from "@/components/mascot/mascot";

/**
 * "Chào …" at the top of the instructor overview: the one place in the work
 * areas where Naomi appears outside an empty state (design doc §4, "Trẻ con
 * hóa khu làm việc"). She stands still -- opening the overview is not an
 * event -- and she is decorative: the heading says it all.
 */
export function InstructorGreeting({ name, line }: { name: string | null; line: string }) {
  return (
    <section className="flex items-center gap-4 rounded-xl bg-secondary p-5 sm:gap-6 sm:px-8 sm:py-7">
      <Mascot mood="wave" className="size-18 sm:size-28" />
      <div className="min-w-0 space-y-1.5">
        <h1 className="text-h2 sm:text-h1">{name ? `Chào ${name}` : "Chào bạn"}</h1>
        <p className="text-body-sm text-muted-foreground sm:text-body">{line}</p>
      </div>
    </section>
  );
}
