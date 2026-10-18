"""The old ffmpeg command line against the new one, on the real worker image.

Run inside the dev `worker` container (the one that transcodes):

    docker compose exec -T worker python - < docs/report/assets/phase-6/ffmpeg-hardening/worker_drill.py

The attack: an "upload" that is an HLS playlist, pointing at a `.ts` file that
sits on the worker's own disk. The old command line transcodes it -- the local
file becomes the published lecture. The new one (`run_ffmpeg`, with
INPUT_GUARDS) refuses to parse it. A real clip is run through both too, to
show the guards cost an honest upload nothing.
"""

import subprocess
import tempfile
from pathlib import Path

from app.workers import video

work = Path(tempfile.mkdtemp(prefix="ffmpeg-drill-"))
print(subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0])


def sh(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, check=False)


sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
   "testsrc=size=320x240:rate=10:duration=4", "-f", "lavfi", "-i", "sine=duration=4",
   "-c:v", "libx264", "-c:a", "aac", str(work / "clip.mp4"))
# Stands for any media file that happens to be on the worker's disk.
secret = work / "on-the-worker.ts"
sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "clip.mp4"), "-c", "copy",
   "-f", "mpegts", str(secret))
playlist = work / "original.m3u8"
playlist.write_text(
    f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:4.0,\n{secret}\n#EXT-X-ENDLIST\n",
    encoding="utf-8",
)


def old_command(source: Path, out: Path) -> subprocess.CompletedProcess:
    """`run_ffmpeg` as it was before INPUT_GUARDS, flag for flag."""
    out.mkdir(parents=True, exist_ok=True)
    return sh(
        "ffmpeg", "-y", "-i", str(source),
        "-vf", f"scale=w=-2:h=min({video.MAX_HEIGHT}\\,ih)",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-profile:v", "main", "-c:a", "aac", "-b:a", "128k",
        "-force_key_frames", f"expr:gte(t,n_forced*{video.SEGMENT_SECONDS})",
        "-hls_time", str(video.SEGMENT_SECONDS), "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(out / "segment_%04d.ts"), str(out / video.MANIFEST_NAME),
    )


for label, source in (("playlist posing as an upload", playlist), ("real 4 s clip", work / "clip.mp4")):
    old = old_command(source, work / f"old-{source.stem}")
    made = sorted(p.name for p in (work / f"old-{source.stem}").glob("segment_*.ts"))
    print(f"\n{label}:")
    print(f"  old command line : exit {old.returncode}, {len(made)} segment(s) written"
          + (", the file on the worker's disk is now a lecture" if old.returncode == 0 and source == playlist else ""))
    try:
        manifest = video.run_ffmpeg(source, work / f"new-{source.stem}")
        segments = len(list(manifest.parent.glob("segment_*.ts")))
        print(f"  run_ffmpeg (new) : ok, {segments} segment(s), duration "
              f"{video.probe_duration_seconds(source)} s")
    except video.TranscodeError as error:
        print(f"  run_ffmpeg (new) : refused -- {str(error).splitlines()[-1]}")
        print(f"  probe_duration_seconds (new): {video.probe_duration_seconds(source)}")

subprocess.run(["rm", "-rf", str(work)], check=False)
