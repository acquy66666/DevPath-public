"""What the monitor decides on its own, every minute, with nobody watching:
which container state is a problem, when a problem is real enough to wake
someone, when to say it is over, and that a notification which could not be
sent is not lost. Talking to a real Docker daemon, nginx and ntfy is proven by
the drill on a production stack (docs/report/assets/phase-6/monitoring.txt).

    python -m pytest infra/monitor
"""

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import devpath_monitor as m
import pytest


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


T0 = utc(2026, 10, 2, 7, 0)  # 14:00 in Vietnam
MINUTE = timedelta(minutes=1)


def container(service: str, **kw) -> m.Container:
    fields = {
        "id": f"id-{service}",
        "service": service,
        "status": "running",
        "health": "healthy",
        "exit_code": 0,
        "oom_killed": False,
        "restart_count": 0,
    }
    return m.Container(**{**fields, **kw})


# --- configuration -------------------------------------------------------------


def test_the_env_file_is_read_the_way_compose_writes_it(tmp_path: Path) -> None:
    env = tmp_path / ".env.prod"
    env.write_text(
        "# a comment\n\nDOMAIN=devpath.example.com\nMONITOR_NTFY_URL='https://ntfy.sh/x'\n"
        'POSTGRES_PASSWORD="p=a=s"\nBROKEN LINE\n',
        encoding="utf-8",
    )
    assert m.read_env_file(env) == {
        "DOMAIN": "devpath.example.com",
        "MONITOR_NTFY_URL": "https://ntfy.sh/x",
        "POSTGRES_PASSWORD": "p=a=s",
    }


def _config(file_env: dict, process_env: dict | None = None) -> m.Config:
    return m.config_from(
        file_env,
        process_env or {},
        env_file=Path(".env.prod"),
        compose_file=Path("docker-compose.prod.yml"),
        state_dir=Path("state"),
        project="devpath",
    )


def test_a_monitor_without_a_domain_refuses_to_start() -> None:
    with pytest.raises(m.ConfigError, match="DOMAIN"):
        _config({"DOMAIN": ""})


def test_the_process_environment_overrides_monitor_settings_and_nothing_else() -> None:
    config = _config(
        {"DOMAIN": "devpath.example.com", "MONITOR_CERT_MIN_DAYS": "14"},
        {"MONITOR_CERT_MIN_DAYS": "3", "MONITOR_HTTPS_ADDRESS": "127.0.0.1:8443", "PATH": "/bin"},
    )
    assert config.cert_min_days == 3
    assert config.https_address == ("127.0.0.1", 8443)
    assert config.ntfy_url == ""


def test_a_bad_ntfy_url_is_refused_at_start_not_at_the_first_incident() -> None:
    with pytest.raises(m.ConfigError, match="MONITOR_NTFY_URL"):
        _config({"DOMAIN": "d.example", "MONITOR_NTFY_URL": "ntfy.sh/topic"})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MONITOR_CONFIRM_RUNS", "0"),
        ("MONITOR_CERT_MIN_DAYS", "two"),
        ("MONITOR_HTTPS_ADDRESS", "443"),
    ],
)
def test_nonsense_numbers_are_refused(name: str, value: str) -> None:
    with pytest.raises(m.ConfigError, match=name):
        _config({"DOMAIN": "d.example", name: value})


# --- containers ----------------------------------------------------------------


def test_inspect_output_is_parsed_and_one_off_containers_are_left_out() -> None:
    output = (
        "aaa\tbackend\tFalse\t2\trunning\thealthy\t0\tfalse\n"
        "bbb\tbackend\tTrue\t0\texited\t\t0\tfalse\n"  # compose run --rm alembic
        "ccc\tbeat\tFalse\t0\trunning\t\t0\tfalse\n"  # no healthcheck
        "ddd\tworker\tFalse\t5\trestarting\t\t137\ttrue\n"
    )
    assert m.parse_inspect(output) == [
        container("backend", id="aaa", restart_count=2),
        container("beat", id="ccc", health=""),
        container(
            "worker",
            id="ddd",
            status="restarting",
            health="",
            exit_code=137,
            oom_killed=True,
            restart_count=5,
        ),
    ]


def test_the_inspect_template_survives_a_container_without_a_healthcheck() -> None:
    # `.State.Health` on a container with no healthcheck fails the template,
    # and with it the whole `docker inspect` -- every service unreadable
    # because beat has no healthcheck. Only the map lookup is safe.
    assert ".State.Health" not in m.INSPECT_FORMAT
    assert 'index .State "Health"' in m.INSPECT_FORMAT


def test_the_compose_file_is_the_list_of_what_should_be_running() -> None:
    config = {
        "services": {
            "backend": {"restart": "unless-stopped"},
            "grading-workspace": {"restart": "no"},
            "certbot": {"restart": "always"},
            "oneshot": {},
        }
    }
    assert m.expected_services(config) == {
        "backend": True,
        "grading-workspace": False,
        "certbot": True,
        "oneshot": False,
    }


def test_a_healthy_stack_has_nothing_to_say() -> None:
    expected = {"backend": True, "beat": True, "grading-workspace": False}
    containers = [
        container("backend"),
        container("beat", health=""),
        container("grading-workspace", status="exited", health=""),
    ]
    assert m.service_findings(expected, containers) == {}


@pytest.mark.parametrize(
    ("state", "detail"),
    [
        ({"status": "exited", "exit_code": 1, "health": ""}, "đã dừng (mã thoát 1)"),
        (
            {"status": "restarting", "exit_code": 137, "oom_killed": True, "health": ""},
            "khởi động lại liên tục (mã thoát 137, hết bộ nhớ (OOM))",
        ),
        ({"status": "paused"}, "không chạy (paused)"),
        ({"health": "unhealthy"}, "healthcheck báo unhealthy"),
    ],
)
def test_each_way_a_service_can_be_down_is_named(state: dict, detail: str) -> None:
    findings = m.service_findings({"worker": True}, [container("worker", **state)])
    assert findings == {"service:worker": detail}


def test_a_service_with_no_container_at_all_is_missing() -> None:
    assert m.service_findings({"backup": True}, []) == {"service:backup": "không có container"}


def test_a_container_inside_its_start_period_is_not_a_problem_yet() -> None:
    assert m.service_findings({"backend": True}, [container("backend", health="starting")]) == {}


def test_a_one_shot_job_is_a_problem_only_when_it_failed() -> None:
    expected = {"grading-workspace": False}
    failed = container("grading-workspace", status="exited", exit_code=1, health="")
    assert m.service_findings(expected, []) == {}
    assert m.service_findings(expected, [failed]) == {
        "service:grading-workspace": "tác vụ một lần bị lỗi (mã thoát 1)"
    }


def test_a_restart_docker_already_recovered_from_is_reported_once() -> None:
    before = {"id-worker": 0, "id-backend": 3}
    now = [
        container("worker", restart_count=1, oom_killed=True),
        container("backend", restart_count=3),
    ]
    events, counts = m.restart_events(before, now)
    assert events == ["worker: Docker tự khởi động lại 1 lần (lần gần nhất vì hết bộ nhớ)"]
    assert counts == {"id-worker": 1, "id-backend": 3}

    events, _ = m.restart_events(counts, now)
    assert events == []


def test_a_container_recreated_by_a_deploy_is_not_a_restart() -> None:
    events, counts = m.restart_events({"old-id": 4}, [container("backend", id="new-id")])
    assert events == []
    assert counts == {"new-id": 0}


# --- the policy --------------------------------------------------------------------


def _round(
    state: m.State, findings: dict, at: datetime, events: list | None = None, confirm: int = 2
):
    return m.evaluate(state, findings, events or [], at, confirm_runs=confirm, domain="d.example")


def test_one_bad_round_is_not_an_incident() -> None:
    state, message = _round(m.State(), {"service:worker": "đã dừng (mã thoát 1)"}, T0)
    assert message is None
    assert state.problems["service:worker"].runs == 1


def test_a_problem_seen_twice_is_announced_once() -> None:
    down = {"service:worker": "đã dừng (mã thoát 1)"}
    state, _ = _round(m.State(), down, T0)
    state, message = _round(state, down, T0 + MINUTE)
    assert message is not None
    assert message.title == "DevPath: 1 sự cố mới"
    assert "✗ Service worker: đã dừng (mã thoát 1) (từ 14:00 02/10)" in message.body
    assert m.LOGS_HINT in message.body
    assert message.priority == m.HIGH

    state, message = _round(state, down, T0 + 2 * MINUTE)
    assert message is None


def test_the_site_being_unreachable_is_the_urgent_kind() -> None:
    state, message = _round(
        m.State(), {"site": "trả HTTP 502", "service:frontend": "x"}, T0, confirm=1
    )
    assert message is not None
    assert message.priority == m.URGENT
    assert message.title == "DevPath: 2 sự cố mới"


def test_a_problem_that_lasts_is_repeated_every_six_hours() -> None:
    down = {"disk": "đĩa trống 4%"}
    state, _ = _round(m.State(), down, T0, confirm=1)
    state, message = _round(state, down, T0 + timedelta(hours=5, minutes=59), confirm=1)
    assert message is None
    state, message = _round(state, down, T0 + timedelta(hours=6), confirm=1)
    assert message is not None
    assert message.title == "DevPath: vẫn còn 1 sự cố"
    assert "(từ 14:00 02/10)" in message.body


def test_the_end_of_an_announced_problem_is_announced_with_how_long_it_lasted() -> None:
    down = {"api": "trả HTTP 502"}
    state, _ = _round(m.State(), down, T0)
    state, _ = _round(state, down, T0 + MINUTE)
    state, message = _round(state, {}, T0 + timedelta(minutes=75))
    assert message is not None
    assert message.title == "DevPath: đã ổn lại"
    assert "✓ API /api/v1/health: ổn lại sau 1 giờ 15 phút" in message.body
    assert m.LOGS_HINT not in message.body
    assert state.problems == {}


def test_a_blip_is_never_announced_in_either_direction() -> None:
    state, _ = _round(m.State(), {"service:backend": "không có container"}, T0)
    state, message = _round(state, {}, T0 + MINUTE)
    assert message is None
    assert state.problems == {}


def test_a_recovery_does_not_read_as_all_clear_while_something_else_is_down() -> None:
    state, _ = _round(m.State(), {"api": "502", "service:worker": "đã dừng"}, T0, confirm=1)
    state, message = _round(state, {"service:worker": "đã dừng"}, T0 + MINUTE, confirm=1)
    assert message is not None
    assert message.title == "DevPath: đã ổn lại"
    assert message.body.splitlines()[1] == "Vẫn đang lỗi: Service worker"


def test_a_changed_detail_does_not_re_announce_the_same_problem() -> None:
    state, _ = _round(m.State(), {"service:worker": "đã dừng (mã thoát 1)"}, T0, confirm=1)
    state, message = _round(
        state, {"service:worker": "khởi động lại liên tục"}, T0 + MINUTE, confirm=1
    )
    assert message is None
    assert state.problems["service:worker"].detail == "khởi động lại liên tục"


def test_restarts_are_facts_and_go_out_without_confirmation() -> None:
    _, message = _round(m.State(), {}, T0, events=["worker: Docker tự khởi động lại 1 lần"])
    assert message is not None
    assert message.title == "DevPath: service tự khởi động lại"
    assert "↻ worker: Docker tự khởi động lại 1 lần" in message.body


@pytest.mark.parametrize(
    ("span", "text"),
    [
        (timedelta(seconds=20), "1 phút"),
        (timedelta(minutes=59), "59 phút"),
        (timedelta(hours=2), "2 giờ"),
        (timedelta(hours=50, minutes=5), "2 ngày 2 giờ"),
    ],
)
def test_durations_read_like_a_person_wrote_them(span: timedelta, text: str) -> None:
    assert m._duration(span) == text


def test_the_journal_line_says_ok_or_lists_every_problem() -> None:
    assert (
        m.summary({}, ["11 container chạy", "TLS hợp lệ"]) == "ổn — 11 container chạy, TLS hợp lệ"
    )
    assert m.summary({"tls": "còn 3 ngày", "api": "502"}, []) == (
        "2 vấn đề — API /api/v1/health: 502; Chứng chỉ TLS: còn 3 ngày"
    )


# --- notifications -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://ntfy.sh/devpath-x1y2", ("https://ntfy.sh/", "devpath-x1y2")),
        ("https://alerts.example/ntfy/devpath/", ("https://alerts.example/ntfy", "devpath")),
    ],
)
def test_the_topic_is_split_from_the_server_it_lives_on(url: str, expected: tuple) -> None:
    assert m.ntfy_endpoint(url) == expected


@pytest.mark.parametrize(
    "url", ["https://ntfy.sh", "https://ntfy.sh/", "ftp://ntfy.sh/x", "ntfy.sh/x"]
)
def test_a_url_without_a_topic_is_refused(url: str) -> None:
    with pytest.raises(m.ConfigError):
        m.ntfy_endpoint(url)


def test_a_vietnamese_title_reaches_ntfy_intact() -> None:
    received: list[tuple[str, dict]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 -- the stdlib's name
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, json.loads(body.decode("utf-8"))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    try:
        message = m.Message("DevPath: 1 sự cố mới", "✗ Ổ đĩa: đầy", m.HIGH, ("rotating_light",))
        m.send_ntfy(f"http://127.0.0.1:{server.server_port}/devpath-topic", message.to_json())
    finally:
        server.server_close()

    assert received == [
        (
            "/",
            {
                "topic": "devpath-topic",
                "title": "DevPath: 1 sự cố mới",
                "message": "✗ Ổ đĩa: đầy",
                "priority": 4,
                "tags": ["rotating_light"],
            },
        )
    ]


def test_a_notification_that_cannot_be_sent_waits_and_order_is_kept() -> None:
    sent: list[str] = []
    logs: list[str] = []

    def flaky(message: dict) -> None:
        if message["title"] == "b":
            raise OSError("network is unreachable")
        sent.append(message["title"])

    left = m.flush([{"title": "a"}, {"title": "b"}, {"title": "c"}], flaky, logs.append)
    assert sent == ["a"]
    assert left == [{"title": "b"}, {"title": "c"}]
    assert "còn 2 tin chờ lượt sau" in logs[0]


def test_an_outage_of_the_notifier_does_not_grow_the_outbox_without_end() -> None:
    def down(message: dict) -> None:
        raise OSError("down")

    left = m.flush([{"n": i} for i in range(30)], down, lambda _: None)
    assert len(left) == m.OUTBOX_LIMIT
    assert left[-1] == {"n": 29}


# --- disk and state ---------------------------------------------------------------------


def test_the_disk_is_a_problem_only_under_the_threshold(tmp_path: Path) -> None:
    problem, reading = m.disk_finding(str(tmp_path), 0)
    assert problem is None
    assert "đĩa trống" in reading
    problem, _ = m.disk_finding(str(tmp_path), 101)
    assert problem == f"{reading}, dưới ngưỡng 101%"


def test_a_missing_disk_path_falls_back_to_the_root_filesystem() -> None:
    problem, reading = m.disk_finding("/no/such/docker/root", 0)
    assert problem is None
    assert "/no/such" not in reading


def test_state_survives_a_round_trip_and_a_broken_file_starts_over(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state, _ = _round(m.State(), {"tls": "còn 3 ngày"}, T0, confirm=1)
    state.restarts = {"abc": 2}
    state.outbox = [{"title": "x"}]
    m.save_state(path, state)
    assert m.load_state(path, print) == state

    path.write_text("{not json", encoding="utf-8")
    logs: list[str] = []
    assert m.load_state(path, logs.append) == m.State()
    assert "bắt đầu lại" in logs[0]


# --- one round, wired together ------------------------------------------------------


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stands in for Docker and nginx; everything after them is real."""
    world = {
        "expected": {"backend": True, "worker": True},
        "containers": [container("backend"), container("worker")],
        "http": {},
        "sent": [],
        "ntfy_up": True,
    }
    monkeypatch.setattr(
        m, "read_containers", lambda config: (world["expected"], world["containers"])
    )
    monkeypatch.setattr(m, "tls_finding", lambda config, now: (None, True))
    monkeypatch.setattr(m, "http_findings", lambda config, verify: dict(world["http"]))

    def send(url: str, message: dict) -> None:
        if not world["ntfy_up"]:
            raise OSError("ntfy unreachable")
        world["sent"].append(message["title"])

    monkeypatch.setattr(m, "send_ntfy", send)
    return world


def _config_at(tmp_path: Path) -> m.Config:
    return m.Config(
        domain="d.example",
        state_dir=tmp_path,
        disk_path=str(tmp_path),
        disk_min_free_percent=0,
        ntfy_url="https://ntfy.sh/t",
    )


def test_a_worker_that_stops_is_announced_on_the_second_round_and_closed_later(
    stack: dict, tmp_path: Path
) -> None:
    config = _config_at(tmp_path)
    logs: list[str] = []
    m.run_check(config, logs.append)
    assert stack["sent"] == []
    assert logs[-1].startswith("ổn — 2 container chạy")

    stack["containers"] = [container("backend"), container("worker", status="exited", exit_code=1)]
    m.run_check(config, logs.append)
    m.run_check(config, logs.append)
    assert stack["sent"] == ["DevPath: 1 sự cố mới"]

    stack["containers"] = [container("backend"), container("worker")]
    m.run_check(config, logs.append)
    assert stack["sent"] == ["DevPath: 1 sự cố mới", "DevPath: đã ổn lại"]


def test_an_alert_raised_while_ntfy_is_down_arrives_when_it_is_back(
    stack: dict, tmp_path: Path
) -> None:
    config = _config_at(tmp_path)
    stack["ntfy_up"] = False
    stack["http"] = {"site": "trả HTTP 502"}
    m.run_check(config, lambda _: None)
    m.run_check(config, lambda _: None)
    assert m.load_state(tmp_path / "state.json", print).outbox[0]["title"] == "DevPath: 1 sự cố mới"

    stack["ntfy_up"] = True
    logs: list[str] = []
    m.run_check(config, logs.append)
    assert stack["sent"] == ["DevPath: 1 sự cố mới"]
    assert m.load_state(tmp_path / "state.json", print).outbox == []
    assert "Đã gửi bù 1 tin chờ từ lượt trước" in logs


def test_a_daemon_that_does_not_answer_is_itself_the_incident(
    stack: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_daemon(config: m.Config) -> None:
        raise RuntimeError("Cannot connect to the Docker daemon")

    monkeypatch.setattr(m, "read_containers", no_daemon)
    state = m.run_check(_config_at(tmp_path), lambda _: None)
    assert state.problems["docker"].detail.endswith("(Cannot connect to the Docker daemon)")


def test_a_round_that_cannot_see_containers_does_not_call_a_down_service_recovered(
    stack: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config_at(tmp_path)
    stack["containers"] = [container("backend"), container("worker", status="exited", exit_code=1)]
    m.run_check(config, lambda _: None)
    m.run_check(config, lambda _: None)
    assert stack["sent"] == ["DevPath: 1 sự cố mới"]

    def no_daemon(config: m.Config) -> None:
        raise RuntimeError("Cannot connect to the Docker daemon")

    monkeypatch.setattr(m, "read_containers", no_daemon)
    state = m.run_check(config, lambda _: None)
    assert "service:worker" in state.problems
    assert "DevPath: đã ổn lại" not in stack["sent"]


def test_the_check_command_exits_zero_whatever_it_found(
    stack: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env.prod"
    env.write_text("DOMAIN=d.example\n", encoding="utf-8")
    stack["http"] = {"site": "trả HTTP 502", "api": "trả HTTP 502"}
    monkeypatch.setenv("MONITOR_DISK_PATH", str(tmp_path))
    argv = ["check", "--env-file", str(env), "--state-dir", str(tmp_path)]
    assert m.main(argv) == 0
    assert m.main(["check", "--env-file", str(tmp_path / "missing")]) == 2


def test_problems_failing_the_same_way_share_one_line() -> None:
    refused = "không kết nối được ([Errno 111] Connection refused)"
    findings = {"site": refused, "api": refused, "catalog": refused, "service:nginx": "đã dừng"}
    _, message = _round(m.State(), findings, T0, confirm=1)
    assert message is not None
    assert message.title == "DevPath: 4 sự cố mới"
    assert message.body.splitlines()[:2] == [
        "✗ API /api/v1/health, Danh mục khóa học (API + CSDL), Trang chủ: "
        f"{refused} (từ 14:00 02/10)",
        "✗ Service nginx: đã dừng (từ 14:00 02/10)",
    ]
