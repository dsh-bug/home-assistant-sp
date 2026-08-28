"""SP Group Auth0 + Jarvis HTTP client.

Contract taken from APK sg.com.singaporepower.spservices 15.10.0
(Auth0ApiService, LoginRequest, JarvisApiServiceV2, HistoryChartResponseModel).
"""

from __future__ import annotations

import json
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .const import (
    ACCEPT_LANGUAGE,
    AUTH0_AUDIENCE,
    AUTH0_CLIENT_ID,
    AUTH0_GRANT_TYPE,
    AUTH0_REALM,
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


class AuthError(Exception):
    """Login rejected by identity.spdigital.sg (invalid credentials or Auth0 error)."""

    def __init__(self, error: str, error_description: str = "") -> None:
        self.error = error
        self.error_description = error_description
        super().__init__(error_description or error)


class UsageError(Exception):
    """Usage payload missing electricity or water readings."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse: ...


class UrllibTransport:
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> HttpResponse:
        request = Request(url, data=body, method=method, headers=dict(headers))
        context = ssl.create_default_context()
        try:
            with urlopen(request, timeout=30, context=context) as response:
                return HttpResponse(
                    status=int(response.status),
                    headers={k: v for k, v in response.headers.items()},
                    body=response.read(),
                )
        except HTTPError as exc:
            return HttpResponse(
                status=int(exc.code),
                headers={k: v for k, v in (exc.headers.items() if exc.headers else [])},
                body=exc.read(),
            )


@dataclass(frozen=True)
class Session:
    access_token: str
    id_token: str
    refresh_token: str | None
    scope: str | None


@dataclass(frozen=True)
class UsageReadings:
    electricity_kwh: float
    water_m3: float
    premise_id: str
    electricity_unit: str
    water_unit: str


def _decode_json(body: bytes) -> object:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise UsageError(f"{label} is not an object")
    return value


def _float(value: object) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return 0.0


def _normalize_volume_unit(unit: str) -> str:
    compact = unit.replace(" ", "").lower()
    if compact in {"m3", "m³", "cum", "cu.m", "cbm"}:
        return "m³"
    return unit or "m³"


def _sum_billed_current(utility: object, label: str) -> tuple[float, str]:
    model = _require_mapping(utility, label)
    data = model.get("data")
    if not isinstance(data, list) or not data:
        raise UsageError(f"{label} has no billed periods")
    total = 0.0
    unit = ""
    for row in data:
        item = _require_mapping(row, f"{label} period")
        raw_unit = item.get("unit")
        if isinstance(raw_unit, str) and raw_unit:
            unit = raw_unit
        consumption = item.get("consumption")
        if not isinstance(consumption, dict):
            raise UsageError(f"{label} period missing consumption")
        total += _float(consumption.get("current"))
    return total, unit


class SpGroupClient:
    def __init__(
        self,
        username: str,
        password: str,
        transport: Transport | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._transport = transport or UrllibTransport()
        self._session: Session | None = None

    def login(self) -> Session:
        payload = {
            "client_id": AUTH0_CLIENT_ID,
            "audience": AUTH0_AUDIENCE,
            "username": self._username,
            "password": self._password,
            "scope": AUTH0_SCOPE,
            "grant_type": AUTH0_GRANT_TYPE,
            "realm": AUTH0_REALM,
        }
        response = self._transport.request(
            "POST",
            f"{IDENTITY_HOST}{OAUTH_TOKEN_PATH}",
            {
                "Content-Type": CONTENT_TYPE_JSON,
                "Accept-Language": ACCEPT_LANGUAGE,
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            json.dumps(payload).encode("utf-8"),
        )
        body = _decode_json(response.body)
        mapping = body if isinstance(body, dict) else {}
        if response.status >= 400:
            error = str(mapping.get("error") or mapping.get("code") or "invalid_grant")
            description = str(
                mapping.get("error_description")
                or mapping.get("description")
                or "authentication failed"
            )
            raise AuthError(error, description)
        access_token = mapping.get("access_token")
        id_token = mapping.get("id_token")
        if not isinstance(access_token, str) or not access_token:
            raise AuthError("invalid_grant", "access_token missing")
        if not isinstance(id_token, str) or not id_token:
            raise AuthError("invalid_grant", "id_token missing")
        refresh = mapping.get("refresh_token")
        scope = mapping.get("scope")
        session = Session(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh if isinstance(refresh, str) else None,
            scope=scope if isinstance(scope, str) else None,
        )
        self._session = session
        return session

    def fetch_usage(self) -> UsageReadings:
        session = self._session or self.login()
        auth_headers = {
            "Authorization": f"Bearer {session.access_token}",
            HEADER_ID_TOKEN: session.id_token,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        me_response = self._transport.request(
            "GET",
            f"{B2C_HOST}{JARVIS_ME_PATH}",
            auth_headers,
            None,
        )
        self._raise_auth_if_denied(me_response, "utility account")
        me_body = _require_mapping(_decode_json(me_response.body), "utility account")
        premise_id = self._select_premise_id(me_body)
        charts_response = self._transport.request(
            "GET",
            f"{B2C_HOST}{JARVIS_CHARTS_PATH}/{premise_id}",
            auth_headers,
            None,
        )
        self._raise_auth_if_denied(charts_response, "charts")
        charts = _require_mapping(_decode_json(charts_response.body), "charts")
        electricity_kwh, elec_unit = _sum_billed_current(charts.get("elec"), "elec")
        water_m3, water_unit = _sum_billed_current(charts.get("water"), "water")
        if elec_unit and elec_unit.lower() not in {"kwh", "kw·h"}:
            raise UsageError(f"unexpected electricity unit {elec_unit!r}")
        return UsageReadings(
            electricity_kwh=electricity_kwh,
            water_m3=water_m3,
            premise_id=premise_id,
            electricity_unit="kWh",
            water_unit=_normalize_volume_unit(water_unit),
        )

    def _raise_auth_if_denied(self, response: HttpResponse, label: str) -> None:
        if response.status in {401, 403}:
            raise AuthError("unauthorized", f"{label} rejected session token")
        if response.status >= 400:
            raise UsageError(f"{label} HTTP {response.status}")

    def _select_premise_id(self, account: dict[str, object]) -> str:
        premises = account.get("premises")
        if not isinstance(premises, list) or not premises:
            raise UsageError("no premises on utility account")
        active: list[str] = []
        fallback: list[str] = []
        for raw in premises:
            if not isinstance(raw, dict):
                continue
            premise_id = raw.get("id")
            if not isinstance(premise_id, str) or not premise_id:
                continue
            fallback.append(premise_id)
            if raw.get("active") is True:
                active.append(premise_id)
        chosen = active or fallback
        if not chosen:
            raise UsageError("premise id missing")
        return chosen[0]
