"""Drive the shipped SpGroupClient against APK-shaped HTTP fixtures."""

from __future__ import annotations

import json
import time

import pytest

from custom_components.sp_group.client import AuthError, Session, SpGroupClient
from custom_components.sp_group.const import (
    AUTH0_AUDIENCE,
    AUTH0_CLIENT_ID,
    AUTH0_GRANT_TYPE,
    AUTH0_REALM,
    AUTH0_REFRESH_GRANT,
    AUTH0_SCOPE,
    B2C_HOST,
    CONTENT_TYPE_JSON,
    HEADER_ID_TOKEN,
    IDENTITY_HOST,
    JARVIS_CHARTS_PATH,
    JARVIS_ME_PATH,
    OAUTH_TOKEN_PATH,
    USER_AGENT,
)

from .conftest import FixtureTransport, billed_totals_from_charts_payload, load_fixture


def test_login_returns_access_token_from_fixture() -> None:
    token_payload = json.loads(load_fixture("oauth_token_success.json"))
    transport = FixtureTransport()
    client = SpGroupClient("user@example.com", "secret", transport=transport)
    session = client.login()
    assert session.access_token == token_payload["access_token"]
    assert session.id_token == token_payload["id_token"]
    assert session.refresh_token == token_payload["refresh_token"]


def test_login_sends_auth0_password_realm_body() -> None:
    transport = FixtureTransport()
    client = SpGroupClient("user@example.com", "secret", transport=transport)
    client.login()
    recorded = transport.requests[0]
    assert recorded.method == "POST"
    assert recorded.url == f"{IDENTITY_HOST}{OAUTH_TOKEN_PATH}"
    assert recorded.headers["Content-Type"] == CONTENT_TYPE_JSON
    assert recorded.headers["Accept-Language"] == "en_US"
    assert recorded.headers["User-Agent"] == USER_AGENT
    assert recorded.body is not None
    body = json.loads(recorded.body.decode("utf-8"))
    assert body == {
        "client_id": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE,
        "username": "user@example.com",
        "password": "secret",
        "scope": AUTH0_SCOPE,
        "grant_type": AUTH0_GRANT_TYPE,
        "realm": AUTH0_REALM,
    }


def test_login_scope_includes_me_rbac() -> None:
    assert "me:rbac" in AUTH0_SCOPE
    assert "me:uportal" in AUTH0_SCOPE


def test_stored_session_skips_password_login() -> None:
    token_payload = json.loads(load_fixture("oauth_token_success.json"))
    session = Session(
        access_token=token_payload["access_token"],
        id_token=token_payload["id_token"],
        refresh_token=token_payload["refresh_token"],
        scope=token_payload["scope"],
        expires_at=int(time.time()) + 3600,
    )
    transport = FixtureTransport()
    client = SpGroupClient(
        "user@example.com", "secret", transport=transport, session=session
    )
    client.fetch_usage()
    assert all(not req.url.endswith(OAUTH_TOKEN_PATH) for req in transport.requests)


def test_refresh_sends_refresh_token_grant() -> None:
    token_payload = json.loads(load_fixture("oauth_token_success.json"))
    transport = FixtureTransport()
    client = SpGroupClient(
        "user@example.com",
        "secret",
        transport=transport,
        session=Session(
            access_token=token_payload["access_token"],
            id_token=token_payload["id_token"],
            refresh_token=token_payload["refresh_token"],
            scope=token_payload["scope"],
        ),
    )
    client.refresh()
    recorded = transport.requests[0]
    assert recorded.body is not None
    body = json.loads(recorded.body.decode("utf-8"))
    assert body["grant_type"] == AUTH0_REFRESH_GRANT
    assert body["refresh_token"] == token_payload["refresh_token"]
    assert body["client_id"] == AUTH0_CLIENT_ID


def test_fetch_usage_returns_kwh_and_water_from_charts_fixture() -> None:
    charts = json.loads(load_fixture("jarvis_charts.json"))
    expected_kwh, expected_m3 = billed_totals_from_charts_payload(charts)
    token_payload = json.loads(load_fixture("oauth_token_success.json"))
    me_payload = json.loads(load_fixture("jarvis_me.json"))
    premise_id = me_payload["premises"][0]["id"]

    transport = FixtureTransport()
    client = SpGroupClient("user@example.com", "secret", transport=transport)
    usage = client.fetch_usage()

    assert usage.electricity_kwh == expected_kwh
    assert usage.water_m3 == expected_m3
    assert usage.electricity_unit == "kWh"
    assert usage.water_unit == "m³"
    assert usage.premise_id == premise_id

    me_req = transport.requests[1]
    charts_req = transport.requests[2]
    bearer = f"Bearer {token_payload['access_token']}"
    assert me_req.method == "GET"
    assert me_req.url == f"{B2C_HOST}{JARVIS_ME_PATH}"
    assert me_req.headers["Authorization"] == bearer
    assert me_req.headers[HEADER_ID_TOKEN] == token_payload["id_token"]
    assert charts_req.method == "GET"
    assert charts_req.url == f"{B2C_HOST}{JARVIS_CHARTS_PATH}/{premise_id}"
    assert charts_req.headers["Authorization"] == bearer
    assert charts_req.headers[HEADER_ID_TOKEN] == token_payload["id_token"]


def test_me_forbidden_uses_server_error_description() -> None:
    class ForbiddenMeTransport(FixtureTransport):
        def request(
            self,
            method: str,
            url: str,
            headers: dict[str, str],
            body: bytes | None,
        ):
            from urllib.parse import urlparse

            from custom_components.sp_group.client import HttpResponse

            parsed = urlparse(url)
            if method == "GET" and parsed.path == JARVIS_ME_PATH:
                return HttpResponse(
                    403,
                    {"Content-Type": "application/json"},
                    b'{"error":"invalid_claim","error_description":"claim error"}',
                )
            return super().request(method, url, headers, body)

    client = SpGroupClient(
        "user@example.com", "secret", transport=ForbiddenMeTransport()
    )
    with pytest.raises(AuthError) as exc_info:
        client.fetch_usage()
    assert exc_info.value.error == "invalid_claim"
    assert "claim error" in exc_info.value.error_description


def test_invalid_credentials_raise_auth_error() -> None:
    fail_payload = json.loads(load_fixture("oauth_token_invalid_grant.json"))
    transport = FixtureTransport(fail_login=True)
    client = SpGroupClient("user@example.com", "wrong", transport=transport)
    with pytest.raises(AuthError) as exc_info:
        client.login()
    assert exc_info.value.error == fail_payload["error"]
    assert exc_info.value.error_description == fail_payload["error_description"]
    with pytest.raises(AuthError):
        client.fetch_usage()
    assert all(urlparse_path(req.url) != JARVIS_ME_PATH for req in transport.requests)
    assert all(
        not urlparse_path(req.url).startswith(JARVIS_CHARTS_PATH)
        for req in transport.requests
    )


def urlparse_path(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).path
