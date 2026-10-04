"""One line per run: did the answer arrive piece by piece, or in one go?

    python sse_summary.py RESULTS.jsonl

`spread` is last delta minus first delta, as read off the client's socket.
Streaming: about as long as the model took to write. Buffered by a proxy:
close to zero, every delta landing in the same read at the very end.
"""

import json
import sys

print(
    f"{'path':<8}{'q':>2} {'st':>4} {'reads':>6} {'deltas':>7} {'chars':>6} "
    f"{'sources':>8} {'1st d':>6} {'last d':>7} {'spread':>7} {'gaps<5ms':>9} {'done':>6}  enc / te / X-Accel"
)
for line in open(sys.argv[1], encoding="utf-8"):
    row = json.loads(line)
    result = row["r"]
    events = result["events"]
    if result["status"] != 200 or not events:
        print(f"{row['path']:<8}{row['q']:>2} {result['status']:>4}  (no stream)")
        continue
    deltas = [event for event in events if event[1] == "delta"]
    times = [event[0] for event in deltas]
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    headers = result["headers"]
    print(
        f"{row['path']:<8}{row['q']:>2} {result['status']:>4} {result['socket_reads']:>6} "
        f"{len(deltas):>7} {sum(e[2] for e in deltas):>6} {events[0][0]:>8} {times[0]:>6} "
        f"{times[-1]:>7} {times[-1] - times[0]:>7} {sum(g < 5 for g in gaps):>9} {events[-1][0]:>6}  "
        f"{headers['Content-Encoding']} / {headers['Transfer-Encoding']} / {headers['X-Accel-Buffering']}"
    )
