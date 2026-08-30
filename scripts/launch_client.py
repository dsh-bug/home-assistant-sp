#!/usr/bin/env python3
"""Fresh consumer of the shipped SP Group client against recorded fixtures."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve()
while ROOT != ROOT.parent:
    if (ROOT / "pyproject.toml").is_file():
        break
    ROOT = ROOT.parent
else:
    raise SystemExit("pyproject.toml not found")
sys.path.insert(0, str(ROOT))

from custom_components.sp_group.client import HttpResponse, SpGroupClient
from custom_components.sp_group.const import (
    B2C_HOST,
    IDENTITY_HOST,
    JARVIS_CHARTS_PATH,
    JARVIS_ME_PATH,
    OAUTH_TOKEN_PATH,
)

FIXTURES = ROOT / "tests" / "fixtures"


class LaunchFixtureTransport:
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        *,
        timeout: int | None = None,
    ) -> HttpResponse:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path
        if method == "POST" and origin == IDENTITY_HOST and path == OAUTH_TOKEN_PATH:
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                (FIXTURES / "oauth_token_success.json").read_bytes(),
            )
        if method == "GET" and origin == B2C_HOST and path == JARVIS_ME_PATH:
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                (FIXTURES / "jarvis_me.json").read_bytes(),
            )
        if (
            method == "GET"
            and origin == B2C_HOST
            and path.startswith(f"{JARVIS_CHARTS_PATH}/")
        ):
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                (FIXTURES / "jarvis_charts.json").read_bytes(),
            )
        raise LookupError(f"unexpected {method} {url}")


def main() -> None:
    client = SpGroupClient(transport=LaunchFixtureTransport())
    client.login("user@example.com", "secret")
    usage = client.fetch_usage()
    print(f"electricity_kwh={usage.electricity_kwh}")
    print(f"water_m3={usage.water_m3}")
    print(f"premise_id={usage.premise_id}")
    print(
        json.dumps(
            {"electricity_kwh": usage.electricity_kwh, "water_m3": usage.water_m3}
        )
    )


if __name__ == "__main__":
    main()
