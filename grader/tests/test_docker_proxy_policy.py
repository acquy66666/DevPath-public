"""What the Docker proxy lets through, rule by rule, without a daemon.

The fixture `docker_create_body.json` is not written by hand: it is the body
Docker CLI 29.7 sent for one real grading run through `runner.sandbox`,
captured on the way to the daemon. So the first test is the one that matters
most in practice -- the runner, unchanged, is allowed -- and every test after
it takes that body and changes one thing an attacker holding the grading
worker would want changed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proxy import policy
from proxy.policy import Denied, Kind

FIXTURE = Path(__file__).parent / "fixtures" / "docker_create_body.json"
ROOT = "/var/lib/devpath-grading"
NAME = "devpath-grading-ea88257d6a284d0688ae3dd9f8e256c7"
CONTAINER_ID = "351f3e700402a40625ed0142f0ed8a028f7490fa3df51a9e29b2cf9402e23474"
CONFIG = policy.Config(workspace_root=ROOT)


def captured() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def create(body: dict, *, name: str = NAME, config: policy.Config = CONFIG) -> None:
    route = policy.route("POST", f"/v1.55/containers/create?name={name}")
    policy.check_create(route, json.dumps(body).encode(), config)


def denied_with(body: dict, fragment: str) -> None:
    with pytest.raises(Denied, match=fragment):
        create(body)


# --- the runner itself ----------------------------------------------------------


def test_the_create_the_runner_actually_sends_is_allowed() -> None:
    create(captured())


def test_the_compile_check_is_the_same_cell_with_a_longer_command() -> None:
    from runner.sandbox import COMPILE_COMMAND

    body = captured()
    body["Cmd"] = list(COMPILE_COMMAND)
    create(body)


def test_a_lower_limit_an_instructor_chose_is_still_a_sandbox() -> None:
    body = captured()
    body["HostConfig"].update(Memory=64 * 2**20, MemorySwap=64 * 2**20)
    body["HostConfig"]["Ulimits"] = [{"Name": "cpu", "Soft": 1, "Hard": 2}]
    create(body)


# --- one change at a time, each one a way out ---------------------------------


def _host(**changes) -> dict:
    body = captured()
    body["HostConfig"].update(changes)
    return body


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"Privileged": True}, "Privileged not allowed"),
        ({"Binds": ["/:/host"]}, "Binds not allowed"),
        ({"NetworkMode": "host"}, "no network"),
        ({"NetworkMode": "bridge"}, "no network"),
        ({"NetworkMode": ""}, "NetworkMode is required"),
        ({"ReadonlyRootfs": False}, "ReadonlyRootfs is required"),
        ({"CapDrop": None}, "CapDrop is required"),
        ({"CapDrop": ["NET_RAW"]}, "every capability"),
        ({"CapAdd": ["SYS_ADMIN"]}, "CapAdd not allowed"),
        ({"SecurityOpt": ["seccomp=unconfined"]}, "security options not allowed"),
        ({"SecurityOpt": ["no-new-privileges", "apparmor=unconfined"]}, "security options"),
        ({"SecurityOpt": None}, "SecurityOpt is required"),
        ({"Memory": 0}, "Memory is required"),
        ({"Memory": 8 * 2**30, "MemorySwap": 8 * 2**30}, "memory limit out of range"),
        ({"MemorySwap": -1}, "no swap"),
        ({"MemorySwappiness": 100}, "swappiness"),
        ({"NanoCpus": 0}, "NanoCpus is required"),
        ({"NanoCpus": 4_000_000_000}, "cpu share out of range"),
        ({"PidsLimit": 0}, "PidsLimit is required"),
        ({"PidsLimit": -1}, "pids limit out of range"),
        ({"PidsLimit": 100_000}, "pids limit out of range"),
        ({"Ulimits": None}, "Ulimits is required"),
        ({"Ulimits": [{"Name": "cpu", "Soft": 5, "Hard": 600}]}, "cpu time limit"),
        ({"Ulimits": [{"Name": "nofile", "Soft": 5, "Hard": 6}]}, "must be cpu"),
        (
            {
                "Ulimits": [
                    {"Name": "cpu", "Soft": 5, "Hard": 6},
                    {"Name": "nproc", "Soft": 1, "Hard": 1},
                ]
            },
            "exactly one ulimit",
        ),
        ({"Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=64m", "/etc": "rw"}}, "only /tmp"),
        ({"Tmpfs": {"/tmp": "rw,nosuid,nodev,exec,size=64m"}}, "nosuid,nodev,noexec"),
        ({"Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec"}}, "must have a size"),
        ({"Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=4096m"}}, "too large"),
        ({"Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=64m,mode=1777"}}, "tmpfs option"),
        ({"LogConfig": {"Type": "json-file", "Config": {}}}, "must not keep a log"),
        ({"LogConfig": None}, "LogConfig is required"),
        ({"PidMode": "host"}, "PidMode not allowed"),
        ({"IpcMode": "host"}, "IpcMode not allowed"),
        ({"UTSMode": "host"}, "UTSMode not allowed"),
        ({"UsernsMode": "host"}, "UsernsMode not allowed"),
        ({"CgroupnsMode": "host"}, "CgroupnsMode not allowed"),
        ({"CgroupParent": "/"}, "CgroupParent not allowed"),
        ({"Devices": [{"PathOnHost": "/dev/sda", "PathInContainer": "/dev/sda"}]}, "Devices"),
        ({"DeviceRequests": [{"Driver": "nvidia", "Count": -1}]}, "DeviceRequests"),
        ({"VolumesFrom": ["devpath-postgres-1"]}, "VolumesFrom"),
        ({"Sysctls": {"kernel.core_pattern": "|/tmp/x"}}, "Sysctls"),
        ({"Runtime": "runsc-unconfined"}, "Runtime"),
        ({"PortBindings": {"80/tcp": [{"HostPort": "80"}]}}, "PortBindings"),
        ({"ExtraHosts": ["host.docker.internal:host-gateway"]}, "ExtraHosts"),
        ({"OomScoreAdj": -1000}, "OomScoreAdj"),
        ({"OomKillDisable": True}, "OomKillDisable"),
        ({"MaskedPaths": []}, "MaskedPaths must be left at its default"),
        ({"ReadonlyPaths": []}, "ReadonlyPaths must be left at its default"),
        ({"RestartPolicy": {"Name": "always", "MaximumRetryCount": 0}}, "restart policy"),
        ({"AutoRemove": True}, "AutoRemove"),
        ({"Init": False, "Privileged": True}, "Privileged"),
    ],
)
def test_a_way_out_of_the_sandbox_is_refused(changes: dict, fragment: str) -> None:
    denied_with(_host(**changes), fragment)


def _mount(**changes) -> dict:
    body = captured()
    body["HostConfig"]["Mounts"][0].update(changes)
    return body


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"Source": "/"}, "outside the workspace"),
        ({"Source": "/var/run/docker.sock"}, "outside the workspace"),
        ({"Source": f"{ROOT}/devpath-grading-nk3hif1e/../../../../etc"}, "outside the workspace"),
        ({"Source": f"{ROOT}/devpath-grading-nk3hif1e"}, "outside the workspace"),
        ({"Source": f"{ROOT}/devpath-grading-nk3hif1e/code/"}, "outside the workspace"),
        ({"Source": f"{ROOT}x/devpath-grading-nk3hif1e/code"}, "outside the workspace"),
        ({"ReadOnly": False}, "read-only"),
        ({"Target": "/"}, "must target /sandbox"),
        ({"Type": "volume"}, "bind mount"),
        ({"BindOptions": {"Propagation": "rshared"}}, "bind options"),
        ({"VolumeOptions": {"DriverConfig": {"Name": "local"}}}, "mount fields not allowed"),
    ],
)
def test_the_one_mount_is_the_submission_and_read_only(changes: dict, fragment: str) -> None:
    denied_with(_mount(**changes), fragment)


def test_a_second_mount_is_refused() -> None:
    body = captured()
    body["HostConfig"]["Mounts"].append(
        {"Type": "bind", "Source": "/", "Target": "/host", "ReadOnly": True}
    )
    denied_with(body, "exactly one mount")


def test_a_submission_directory_that_is_a_link_somewhere_else_is_refused() -> None:
    linked = policy.Config(workspace_root=ROOT, is_plain_directory=lambda path: False)
    with pytest.raises(Denied, match="not a plain directory"):
        create(captured(), config=linked)


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"Image": "alpine"}, "image not allowed"),
        ({"Image": "devpath-sandbox-python:latest"}, "image not allowed"),
        ({"Image": "devpath-backend:prod"}, "image not allowed"),
        ({"Labels": {"devpath.grading": "1", "com.docker.compose.project": "devpath"}}, "labels"),
        ({"Labels": None}, "labels"),
        ({"User": "0:0"}, "user must be"),
        ({"User": "root"}, "user must be"),
        ({"User": ""}, "user must be"),
        ({"Entrypoint": ["sh", "-c"]}, "Entrypoint"),
        ({"Env": ["LD_PRELOAD=/tmp/x.so"]}, "Env"),
        ({"Tty": True}, "Tty"),
        ({"WorkingDir": "/"}, "working directory"),
        ({"Cmd": None}, "command"),
        ({"Cmd": ["sh"] * 50}, "command"),
        ({"Volumes": {"/data": {}}}, "Volumes"),
        ({"Healthcheck": {"Test": ["CMD", "true"]}}, "Healthcheck"),
        ({"NetworkingConfig": {"EndpointsConfig": {"devpath_default": {}}}}, "none network"),
    ],
)
def test_the_container_is_the_sandbox_image_run_as_the_sandbox_user(
    changes: dict, fragment: str
) -> None:
    body = captured()
    body.update(changes)
    denied_with(body, fragment)


def test_a_body_without_host_config_is_refused() -> None:
    body = captured()
    del body["HostConfig"]
    denied_with(body, "HostConfig is required")


@pytest.mark.parametrize(
    "name", ["postgres", "devpath-grading-", "devpath-grading-XYZ", f"{NAME}x", "../" + NAME]
)
def test_the_container_must_be_named_like_a_grading_run(name: str) -> None:
    with pytest.raises(Denied):
        create(captured(), name=name)


def test_a_platform_is_refused() -> None:
    route = policy.route("POST", f"/containers/create?name={NAME}&platform=linux/arm64")
    with pytest.raises(Denied, match="platform"):
        policy.check_create(route, json.dumps(captured()).encode(), CONFIG)


def test_a_body_that_is_not_json_is_refused() -> None:
    route = policy.route("POST", f"/containers/create?name={NAME}")
    with pytest.raises(Denied, match="not JSON"):
        policy.check_create(route, b"{not json", CONFIG)


def test_an_unknown_field_docker_adds_later_is_refused_until_someone_looks() -> None:
    denied_with(_host(SomethingNew=True), "SomethingNew not allowed")


def test_zero_values_of_fields_the_cli_always_sends_are_fine() -> None:
    body = captured()
    body["HostConfig"].update(Dns=[], GroupAdd=None, ConsoleSize=[0, 0], Links=None, CpuShares=0)
    create(body)


# --- routes -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "target", "kind"),
    [
        ("HEAD", "/_ping", Kind.PING),
        ("GET", "/_ping", Kind.PING),
        ("POST", f"/v1.55/containers/create?name={NAME}", Kind.CREATE),
        ("GET", f"/v1.55/containers/{NAME}/json", Kind.INSPECT),
        (
            "POST",
            f"/v1.55/containers/{CONTAINER_ID}/attach?stderr=1&stdin=1&stdout=1&stream=1",
            Kind.ATTACH,
        ),
        ("POST", f"/v1.55/containers/{CONTAINER_ID}/wait?condition=next-exit", Kind.WAIT),
        ("POST", f"/v1.55/containers/{CONTAINER_ID}/start", Kind.START),
        ("POST", f"/v1.55/containers/{NAME}/kill", Kind.KILL),
        ("POST", f"/v1.55/containers/{NAME}/kill?signal=KILL", Kind.KILL),
        ("DELETE", f"/v1.55/containers/{NAME}?force=1", Kind.REMOVE),
    ],
)
def test_every_call_a_grading_run_makes_is_routed(method: str, target: str, kind: Kind) -> None:
    """The exact list captured from one real run, plus kill (the wall-clock
    timeout's path)."""
    assert policy.route(method, target).kind is kind


@pytest.mark.parametrize(
    ("method", "target"),
    [
        ("POST", f"/v1.55/containers/{NAME}/exec"),
        ("POST", "/v1.55/containers/devpath-postgres-1/exec"),
        ("POST", "/v1.55/exec/abc/start"),
        ("POST", "/v1.55/images/create?fromImage=alpine"),
        ("POST", "/v1.55/build"),
        ("GET", "/v1.55/containers/json"),
        ("GET", "/v1.55/info"),
        ("GET", "/v1.55/version"),
        ("GET", "/v1.55/events"),
        ("POST", "/v1.55/networks/create"),
        ("POST", "/v1.55/volumes/create"),
        ("POST", "/v1.55/containers/prune"),
        ("PUT", f"/v1.55/containers/{NAME}/archive?path=/tmp"),
        ("POST", f"/v1.55/containers/{NAME}/update"),
        ("POST", f"/v1.55/containers/{NAME}/commit"),
        ("POST", "/v1.55/containers/devpath-postgres-1/kill"),
        ("DELETE", "/v1.55/containers/devpath-postgres-1?force=1"),
        ("POST", "/v1.55/containers/../images/create"),
        ("POST", "/v1.55/containers/%2e%2e/images/create"),
        ("POST", "//v1.55/containers/create"),
        ("POST", "/v1.55/swarm/init"),
        ("GET", "/v1.55/containers/abc123/json"),
        ("DELETE", f"/v1.55/containers/{NAME}?force=1&link=1"),
        ("POST", f"/v1.55/containers/{NAME}/wait?condition=forever"),
        ("POST", f"/v1.55/containers/{NAME}/kill?signal=../../x"),
        ("POST", f"/v1.55/containers/{NAME}/start?checkpoint=x"),
    ],
)
def test_anything_else_is_refused(method: str, target: str) -> None:
    with pytest.raises(Denied):
        policy.route(method, target)


# --- ownership -----------------------------------------------------------------------


def inspected(**changes) -> dict:
    record = {
        "Name": f"/{NAME}",
        "Config": {"Labels": {"devpath.grading": "1"}},
        "Mounts": [
            {"Type": "bind", "Source": f"{ROOT}/devpath-grading-nk3hif1e/code", "RW": False}
        ],
    }
    record.update(changes)
    return record


def test_a_grading_container_may_be_operated_on() -> None:
    for kind in (Kind.START, Kind.ATTACH, Kind.WAIT, Kind.KILL, Kind.INSPECT, Kind.REMOVE):
        policy.check_owned(inspected(), kind, CONFIG)


@pytest.mark.parametrize(
    "changes",
    [
        {"Config": {"Labels": {"com.docker.compose.service": "postgres"}}},
        {"Config": {"Labels": None}},
        {"Name": "/devpath-postgres-1"},
    ],
)
def test_any_other_container_may_not(changes: dict) -> None:
    with pytest.raises(Denied, match="not a grading container"):
        policy.check_owned(inspected(**changes), Kind.REMOVE, CONFIG)


def test_the_mount_is_checked_again_at_start_because_that_is_when_it_happens() -> None:
    moved = inspected(Mounts=[{"Type": "bind", "Source": "/etc", "RW": False}])
    policy.check_owned(moved, Kind.INSPECT, CONFIG)
    with pytest.raises(Denied, match="outside the workspace"):
        policy.check_owned(moved, Kind.START, CONFIG)

    linked = policy.Config(workspace_root=ROOT, is_plain_directory=lambda path: False)
    with pytest.raises(Denied, match="not a plain directory"):
        policy.check_owned(inspected(), Kind.START, linked)


# --- configuration ----------------------------------------------------------------


def test_the_workspace_must_be_an_absolute_path() -> None:
    with pytest.raises(SystemExit):
        policy.Config.from_env({"DEVPATH_GRADING_WORKSPACE": "relative/path"})


def test_the_image_list_comes_from_the_environment() -> None:
    config = policy.Config.from_env(
        {"DEVPATH_GRADING_WORKSPACE": "/w/", "DOCKER_PROXY_IMAGES": "a:1, b:2"}
    )
    assert config.workspace_root == "/w"
    assert config.images == {"a:1", "b:2"}
    assert policy.Config.from_env({"DEVPATH_GRADING_WORKSPACE": "/w"}).images == {
        "devpath-sandbox-python:v1"
    }


def test_the_fixture_is_still_what_it_says_it_is() -> None:
    """Guard against the fixture being edited into something the policy likes:
    these are the runner's own flags, read back."""
    body = captured()
    host = body["HostConfig"]
    assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True
    assert host["CapDrop"] == ["ALL"] and host["SecurityOpt"] == ["no-new-privileges"]
    assert host["Mounts"][0]["ReadOnly"] is True
    assert copy.deepcopy(body) == captured()


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("Volumes", {"/data": {}}, "Volumes"),
        ("ExposedPorts", {"80/tcp": {}}, "ExposedPorts"),
        ("NetworkingConfig", {"EndpointsConfig": {"devpath_default": {}}}, "none network"),
        (
            "NetworkingConfig",
            {"EndpointsConfig": {"none": {"Aliases": ["db"]}}},
            "endpoint settings",
        ),
    ],
)
def test_a_mapping_whose_keys_are_the_data_is_never_empty(
    field: str, value: dict, fragment: str
) -> None:
    """The first draft treated `{"/data": {}}` as nothing, because every value
    in it was empty -- a writable volume, and a network, both let through."""
    body = captured()
    body[field] = value
    denied_with(body, fragment)


def test_endpoint_settings_left_at_their_zero_values_are_fine() -> None:
    body = captured()
    body["NetworkingConfig"] = {"EndpointsConfig": {"none": {"Aliases": None, "IPAddress": ""}}}
    create(body)
