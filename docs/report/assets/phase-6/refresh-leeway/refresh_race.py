"""Two tabs, one refresh cookie -- the race the refresh-token leeway is for.

Talks HTTP to a running API, so every request gets its own database session
the way it does in production (the pytest client shares one session, and
cannot race). Run inside the backend container:

    docker compose exec -T backend python - < refresh_race.py

Environment: API (default http://localhost:8000/api/v1), CONCURRENT trials
(default 10), LATE trials (3), REPLAY_AFTER seconds (35; 0 skips it).

Each trial signs up a fresh `@e2e.devpath.example` account, so one trial's
theft verdict cannot leak into the next; `python -m scripts.purge_e2e` removes
them afterwards.

  concurrent  both tabs refresh with the same cookie at the same moment
  late        the second refresh leaves 1 s after the first one answered,
              still carrying the old cookie -- a tab whose request left before
              the other tab's Set-Cookie landed, or a retry after a lost answer
  replay      the old cookie again, REPLAY_AFTER seconds later -- beyond any
              leeway, so it must still read as theft

After each trial: which of the tokens handed out still refresh, i.e. whether
the person is still signed in.
"""

import asyncio
import os
import uuid

import httpx

API = os.environ.get("API", "http://localhost:8000/api/v1")
COOKIE = "devpath_refresh"
CONCURRENT = int(os.environ.get("CONCURRENT", "10"))
LATE = int(os.environ.get("LATE", "3"))
REPLAY_AFTER = float(os.environ.get("REPLAY_AFTER", "35"))


async def sign_up(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/auth/register",
        json={
            "email": f"refresh-race-{uuid.uuid4().hex[:12]}@e2e.devpath.example",
            "password": "refresh-race-password",
            "full_name": "Refresh Race",
        },
    )
    response.raise_for_status()
    return response.cookies[COOKIE]


async def refresh(client: httpx.AsyncClient, token: str) -> tuple[int, str]:
    """(status, new token or error code). The cookie is sent by hand, so the
    client's own jar never decides which token goes out."""
    response = await client.post("/auth/refresh", headers={"Cookie": f"{COOKIE}={token}"})
    if response.status_code == 200:
        return 200, response.cookies[COOKIE]
    return response.status_code, response.json()["detail"]["code"]


def describe(result: tuple[int, str]) -> str:
    status, value = result
    return "200" if status == 200 else f"{status} {value}"


async def still_signed_in(client: httpx.AsyncClient, results: list[tuple[int, str]]) -> str:
    issued = [value for status, value in results if status == 200]
    alive = 0
    for token in issued:
        if (await refresh(client, token))[0] == 200:
            alive += 1
    verdict = "still signed in" if alive else "SIGNED OUT"
    return f"tokens issued {len(issued)}, still working {alive} -> {verdict}"


async def main() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=30) as client:
        print(f"API {API}")

        print(f"\n== concurrent: two refreshes with one cookie at once, {CONCURRENT} trials")
        for trial in range(1, CONCURRENT + 1):
            token = await sign_up(client)
            results = list(await asyncio.gather(refresh(client, token), refresh(client, token)))
            line = "  ".join(f"{tab}={describe(r)}" for tab, r in zip("AB", results, strict=True))
            print(f"#{trial:<2} {line:<40} {await still_signed_in(client, results)}")

        print(f"\n== late: the old cookie again 1 s after the first answer, {LATE} trials")
        for trial in range(1, LATE + 1):
            token = await sign_up(client)
            first = await refresh(client, token)
            await asyncio.sleep(1)
            second = await refresh(client, token)
            line = f"A={describe(first)}  B={describe(second)}"
            print(f"#{trial:<2} {line:<40} {await still_signed_in(client, [first, second])}")

        if REPLAY_AFTER > 0:
            print(f"\n== replay: the old cookie again {REPLAY_AFTER:g} s after the first answer")
            token = await sign_up(client)
            first = await refresh(client, token)
            await asyncio.sleep(REPLAY_AFTER)
            second = await refresh(client, token)
            line = f"A={describe(first)}  B={describe(second)}"
            print(f"#1  {line:<40} {await still_signed_in(client, [first, second])}")


asyncio.run(main())
