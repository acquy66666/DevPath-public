"""The lecture transcripts the seed gives its videos.

They are the chatbot's corpus: its evaluation (scripts/eval_chatbot.py) is run
on them, so a file that stops parsing, or that lands on the wrong lesson after
someone reorders a course, changes the numbers in the thesis without failing
anything. These run without a database or a bucket.
"""

import pytest

from app.services.transcripts import transcript_format, transcript_text
from scripts.seed_courses import COURSES
from scripts.seed_transcripts import TRANSCRIPTS, transcript_files

COURSES_BY_SLUG = {course.slug: course for course in COURSES}
FOLDERS = sorted(path for path in TRANSCRIPTS.iterdir() if path.is_dir())


def test_there_is_a_transcript_folder_to_seed():
    assert FOLDERS


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda folder: folder.name)
def test_every_folder_is_a_seed_course(folder):
    assert folder.name in COURSES_BY_SLUG


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda folder: folder.name)
def test_every_file_names_a_video_lesson_and_reads_like_an_upload(folder):
    course = COURSES_BY_SLUG[folder.name]

    for file in transcript_files(folder):
        lesson = course.sections[file.section].lessons[file.lesson]
        assert lesson.type == "video", f"{file.path.name} là bài {lesson.type}"

        # The same two calls PUT /lessons/{id}/transcript makes before it
        # stores anything: an .srt with no timings, or a file that is not
        # UTF-8, fails here rather than in front of the seed script.
        fmt = transcript_format(file.path.name)
        assert fmt is not None
        assert transcript_text(file.path.read_bytes().decode("utf-8"), fmt)


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda folder: folder.name)
def test_a_course_with_transcripts_has_one_for_every_video(folder):
    """A gap would leave one lesson unsearchable, and the evaluation would
    report a retrieval miss that is really a missing file."""
    course = COURSES_BY_SLUG[folder.name]
    videos = {
        (section_position, lesson_position)
        for section_position, section in enumerate(course.sections)
        for lesson_position, lesson in enumerate(section.lessons)
        if lesson.type == "video"
    }
    seeded = [(file.section, file.lesson) for file in transcript_files(folder)]

    assert sorted(seeded) == sorted(videos)


def test_a_misnamed_file_is_refused(tmp_path):
    (tmp_path / "1-0.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nA\n", "utf-8")
    (tmp_path / "bai-hai.txt").write_text("B", "utf-8")

    with pytest.raises(SystemExit, match="bai-hai.txt"):
        transcript_files(tmp_path)
