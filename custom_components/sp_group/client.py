"""SP Group Auth0 + Jarvis HTTP client.

Contract taken from APK sg.com.singaporepower.spservices 15.10.0
(Auth0ApiService, LoginRequest, JarvisApiServiceV2, HistoryChartResponseModel,
PremiseResponseModel, PremiseAccountModel, PpmsCreditBalance, MeterReadingModel).
"""

from __future__ import annotations

import base64
import json
import ssl
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .const import (
    ACCEPT_LANGUAGE,
    AMI_DAILY_MONTHS,
    AMI_DATE_FORMAT,
    AMI_GROUPED_BY_DAILY,
    AMI_GROUPED_BY_HALF_HOUR,
    AMI_HALF_HOUR_DAYS,
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
    JARVIS_AMI_PATH,
    JARVIS_CHARTS_PATH,
    JARVIS_ME_PATH,
    JARVIS_PPMS_PATH,
    JARVIS_SMRD_PATH,
    OAUTH_TOKEN_PATH,
    TOKEN_EXPIRY_BUFFER_SECONDS,
    USER_AGENT,
)


class AuthError(Exception):
    """Login rejected by identity.spdigital.sg (invalid credentials or Auth0 error)."""

    def __init__(self, error: str, error_description: str = "") -> None:
        self.error = error
        self.error_description = error_description
        super().__init__(error_description or error)


class UsageError(Exception):
    """Usage payload missing billed utility readings."""


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
    expires_at: int | None = None

    def is_expired(self, now: int | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = int(time.time() if now is None else now)
        return current >= self.expires_at - TOKEN_EXPIRY_BUFFER_SECONDS


SG_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class PeriodReading:
    start: datetime
    amount: float
    previous: float | None = None
    status: str | None = None


@dataclass(frozen=True)
class UtilitySeries:
    total: float
    unit: str
    periods: tuple[PeriodReading, ...]
    average: float | None
    comparison: str | None


@dataclass(frozen=True)
class PremiseInfo:
    id: str
    address: str | None
    account_number: str | None
    account_status: str | None
    account_type: str | None
    premise_type: str | None
    utilities: tuple[str, ...]
    ami_elec: bool | None
    retailer_name: str | None
    ppms_exists: bool


@dataclass(frozen=True)
class MeterReadingInfo:
    message: str | None
    title: str | None
    start: str | None
    end: str | None


@dataclass(frozen=True)
class UsageReadings:
    premise: PremiseInfo
    electricity: UtilitySeries | None
    water: UtilitySeries | None
    gas: UtilitySeries | None
    meter_reading: MeterReadingInfo | None = None
    ppms_credit: float | None = None
    ppms_updated_at: str | None = None
    ami_hourly: tuple[PeriodReading, ...] = ()
    ami_daily: tuple[PeriodReading, ...] = ()

    @property
    def premise_id(self) -> str:
        return self.premise.id

    @property
    def electricity_kwh(self) -> float:
        return self.electricity.total if self.electricity else 0.0

    @property
    def water_m3(self) -> float:
        return self.water.total if self.water else 0.0

    @property
    def electricity_unit(self) -> str:
        return self.electricity.unit if self.electricity else "kWh"

    @property
    def water_unit(self) -> str:
        return self.water.unit if self.water else "m³"

    @property
    def electricity_periods(self) -> tuple[PeriodReading, ...]:
        return self.electricity.periods if self.electricity else ()

    @property
    def water_periods(self) -> tuple[PeriodReading, ...]:
        return self.water.periods if self.water else ()

    @property
    def gas_periods(self) -> tuple[PeriodReading, ...]:
        return self.gas.periods if self.gas else ()


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


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _jwt_exp(token: str) -> int | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + ("=" * (-len(parts[1]) % 4))
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    exp = claims.get("exp") if isinstance(claims, dict) else None
    try:
        return int(exp) if exp is not None else None
    except (TypeError, ValueError):
        return None


def _session_from_oauth(
    mapping: dict[str, object], fallback_refresh: str | None
) -> Session:
    access_token = mapping.get("access_token")
    id_token = mapping.get("id_token")
    if not isinstance(access_token, str) or not access_token:
        raise AuthError("invalid_grant", "access_token missing")
    if not isinstance(id_token, str) or not id_token:
        raise AuthError("invalid_grant", "id_token missing")
    refresh = mapping.get("refresh_token")
    scope = mapping.get("scope")
    return Session(
        access_token=access_token,
        id_token=id_token,
        refresh_token=refresh if isinstance(refresh, str) else fallback_refresh,
        scope=scope if isinstance(scope, str) else None,
        expires_at=_jwt_exp(access_token),
    )


def _oauth_headers() -> dict[str, str]:
    return {
        "Content-Type": CONTENT_TYPE_JSON,
        "Accept-Language": ACCEPT_LANGUAGE,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


def _normalize_volume_unit(unit: str) -> str:
    compact = unit.replace(" ", "").lower()
    if compact in {"m3", "m³", "cum", "cu.m", "cbm"}:
        return "m³"
    return unit or "m³"


def _energy_or_volume_unit(unit: str, kind: str) -> str:
    compact = unit.replace(" ", "").lower()
    if kind == "elec":
        if unit and compact not in {"kwh", "kw·h"}:
            raise UsageError(f"unexpected electricity unit {unit!r}")
        return "kWh"
    if kind == "water":
        return _normalize_volume_unit(unit)
    if compact in {"kwh", "kw·h"}:
        return "kWh"
    return _normalize_volume_unit(unit)


def _parse_period_start(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SG_TZ)
    return parsed


def _parse_utility(utility: object, kind: str) -> UtilitySeries | None:
    if not isinstance(utility, dict):
        return None
    data = utility.get("data")
    if not isinstance(data, list) or not data:
        return None
    total = 0.0
    unit = ""
    periods: list[PeriodReading] = []
    for row in data:
        item = _require_mapping(row, f"{kind} period")
        raw_unit = item.get("unit")
        if isinstance(raw_unit, str) and raw_unit:
            unit = raw_unit
        consumption = item.get("consumption")
        if not isinstance(consumption, dict):
            raise UsageError(f"{kind} period missing consumption")
        amount = _float(consumption.get("current"))
        total += amount
        start = _parse_period_start(item.get("period"))
        status = _optional_str(item.get("status"))
        previous = _optional_float(consumption.get("previous"))
        if start is not None:
            periods.append(
                PeriodReading(
                    start=start, amount=amount, previous=previous, status=status
                )
            )
    if not periods:
        return None
    return UtilitySeries(
        total=total,
        unit=_energy_or_volume_unit(unit, kind),
        periods=tuple(periods),
        average=_optional_float(utility.get("average_consumption")),
        comparison=_optional_str(utility.get("comparison_message"))
        or _optional_str(utility.get("comparison_type")),
    )


def _first_account(premise: dict[str, object]) -> dict[str, object]:
    accounts = premise.get("accounts")
    if isinstance(accounts, list) and accounts and isinstance(accounts[0], dict):
        return accounts[0]
    return {}


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _parse_premise(premise: dict[str, object]) -> PremiseInfo:
    premise_id = premise.get("id")
    if not isinstance(premise_id, str) or not premise_id:
        raise UsageError("premise id missing")
    account = _first_account(premise)
    contestable = premise.get("contestable_details")
    contestable_map = contestable if isinstance(contestable, dict) else {}
    meter = premise.get("meter_details")
    meter_map = meter if isinstance(meter, dict) else {}
    ami = meter_map.get("ami_elec")
    ppms = premise.get("ppms_details")
    ppms_exists = False
    if isinstance(ppms, dict) and ppms.get("exists") is True:
        ppms_exists = True
    return PremiseInfo(
        id=premise_id,
        address=_optional_str(premise.get("address"))
        or _optional_str(account.get("address")),
        account_number=_optional_str(account.get("account_number")),
        account_status=_optional_str(account.get("account_status")),
        account_type=_optional_str(account.get("account_type")),
        premise_type=_optional_str(premise.get("type")),
        utilities=_string_tuple(account.get("utilities")),
        ami_elec=ami if isinstance(ami, bool) else None,
        retailer_name=_optional_str(contestable_map.get("retailer_name")),
        ppms_exists=ppms_exists,
    )


def _parse_meter_reading(body: object) -> MeterReadingInfo | None:
    if not isinstance(body, dict):
        return None
    period = body.get("latest_submission_period")
    period_map = period if isinstance(period, dict) else {}
    info = MeterReadingInfo(
        message=_optional_str(body.get("message")),
        title=_optional_str(period_map.get("title")),
        start=_optional_str(period_map.get("start_date")),
        end=_optional_str(period_map.get("end_date")),
    )
    if not any((info.message, info.title, info.start, info.end)):
        return None
    return info


def _ami_stamp(value: datetime) -> str:
    return value.astimezone(SG_TZ).strftime(AMI_DATE_FORMAT)


def _parse_ami_rows(body: object) -> tuple[PeriodReading, ...]:
    if not isinstance(body, dict):
        return ()
    history = body.get("history")
    if not isinstance(history, list):
        return ()
    periods: list[PeriodReading] = []
    for block in history:
        if not isinstance(block, dict):
            continue
        rows = block.get("data")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            start = _parse_period_start(row.get("date"))
            amount = _optional_float(row.get("consumption"))
            if start is None or amount is None:
                continue
            periods.append(PeriodReading(start=start, amount=amount))
    return tuple(sorted(periods, key=lambda item: item.start))


class SpGroupClient:
    def __init__(
        self,
        username: str,
        password: str,
        transport: Transport | None = None,
        session: Session | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._transport = transport or UrllibTransport()
        self._session = session

    @property
    def session(self) -> Session | None:
        return self._session

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
        mapping = self._oauth_post(payload)
        session = _session_from_oauth(mapping, None)
        self._session = session
        return session

    def refresh(self) -> Session:
        current = self._session
        if current is None or not current.refresh_token:
            raise AuthError("invalid_grant", "refresh_token missing")
        payload = {
            "client_id": AUTH0_CLIENT_ID,
            "refresh_token": current.refresh_token,
            "scope": AUTH0_SCOPE,
            "grant_type": AUTH0_REFRESH_GRANT,
        }
        mapping = self._oauth_post(payload)
        session = _session_from_oauth(mapping, current.refresh_token)
        self._session = session
        return session

    def ensure_session(self) -> Session:
        current = self._session
        if current is not None and not current.is_expired() and current.access_token:
            return current
        if current is not None and current.refresh_token:
            try:
                return self.refresh()
            except AuthError:
                pass
        return self.login()

    def _oauth_post(self, payload: dict[str, str]) -> dict[str, object]:
        response = self._transport.request(
            "POST",
            f"{IDENTITY_HOST}{OAUTH_TOKEN_PATH}",
            _oauth_headers(),
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
        return mapping

    def fetch_usage(self) -> UsageReadings:
        session = self.ensure_session()
        try:
            return self._fetch_usage_with(session)
        except AuthError:
            if session.refresh_token:
                session = self.refresh()
                return self._fetch_usage_with(session)
            raise

    def _auth_headers(self, session: Session) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {session.access_token}",
            HEADER_ID_TOKEN: session.id_token,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _jarvis_get(self, session: Session, path: str) -> HttpResponse:
        return self._transport.request(
            "GET",
            f"{B2C_HOST}{path}",
            self._auth_headers(session),
            None,
        )

    def _jarvis_post(
        self, session: Session, path: str, payload: dict[str, str]
    ) -> HttpResponse:
        headers = dict(self._auth_headers(session))
        headers["Content-Type"] = CONTENT_TYPE_JSON
        return self._transport.request(
            "POST",
            f"{B2C_HOST}{path}",
            headers,
            json.dumps(payload).encode("utf-8"),
        )

    def _fetch_usage_with(self, session: Session) -> UsageReadings:
        me_response = self._jarvis_get(session, JARVIS_ME_PATH)
        self._raise_auth_if_denied(me_response, "utility account")
        me_body = _require_mapping(_decode_json(me_response.body), "utility account")
        premise = self._select_premise(me_body)
        info = _parse_premise(premise)
        charts_response = self._jarvis_get(session, f"{JARVIS_CHARTS_PATH}/{info.id}")
        self._raise_auth_if_denied(charts_response, "charts")
        charts = _require_mapping(_decode_json(charts_response.body), "charts")
        electricity = _parse_utility(charts.get("elec"), "elec")
        water = _parse_utility(charts.get("water"), "water")
        gas = _parse_utility(charts.get("gas"), "gas")
        if electricity is None and water is None and gas is None:
            raise UsageError("no billed utilities")
        meter_reading = self._fetch_meter_reading(session, info.id)
        ppms_credit, ppms_updated = self._fetch_ppms(session, info)
        ami_hourly, ami_daily = self._fetch_ami(session, info)
        return UsageReadings(
            premise=info,
            electricity=electricity,
            water=water,
            gas=gas,
            meter_reading=meter_reading,
            ppms_credit=ppms_credit,
            ppms_updated_at=ppms_updated,
            ami_hourly=ami_hourly,
            ami_daily=ami_daily,
        )

    def _fetch_meter_reading(
        self, session: Session, premise_id: str
    ) -> MeterReadingInfo | None:
        response = self._jarvis_get(session, f"{JARVIS_SMRD_PATH}/{premise_id}")
        if response.status >= 400:
            return None
        try:
            body = _decode_json(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return _parse_meter_reading(body)

    def _fetch_ppms(
        self, session: Session, premise: PremiseInfo
    ) -> tuple[float | None, str | None]:
        if not premise.ppms_exists:
            return None, None
        response = self._jarvis_get(session, f"{JARVIS_PPMS_PATH}/{premise.id}")
        if response.status >= 400:
            return None, None
        try:
            body = _decode_json(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, None
        if not isinstance(body, dict):
            return None, None
        amount = _optional_float(body.get("amount"))
        updated = _optional_str(body.get("updated_at"))
        return amount, updated

    def _fetch_ami(
        self, session: Session, premise: PremiseInfo
    ) -> tuple[tuple[PeriodReading, ...], tuple[PeriodReading, ...]]:
        if premise.ami_elec is not True:
            return (), ()
        now = datetime.now(SG_TZ)
        day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        day_start = (now - timedelta(days=AMI_HALF_HOUR_DAYS - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month = now.month - (AMI_DAILY_MONTHS - 1)
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        month_start = now.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        hourly = self._fetch_ami_range(
            session, premise.id, AMI_GROUPED_BY_HALF_HOUR, day_start, day_end
        )
        daily = self._fetch_ami_range(
            session, premise.id, AMI_GROUPED_BY_DAILY, month_start, day_end
        )
        return hourly, daily

    def _fetch_ami_range(
        self,
        session: Session,
        premise_id: str,
        grouped_by: str,
        start: datetime,
        end: datetime,
    ) -> tuple[PeriodReading, ...]:
        payload = {
            "premise_id": premise_id,
            "start": _ami_stamp(start),
            "end": _ami_stamp(end),
            "grouped_by": grouped_by,
            "utility_type": "electric",
        }
        response = self._jarvis_post(session, JARVIS_AMI_PATH, payload)
        if response.status >= 400:
            return ()
        try:
            body = _decode_json(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ()
        return _parse_ami_rows(body)

    def _raise_auth_if_denied(self, response: HttpResponse, label: str) -> None:
        if response.status < 400:
            return
        mapping: dict[str, object] = {}
        try:
            decoded = _decode_json(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            decoded = {}
        if isinstance(decoded, dict):
            mapping = decoded
        extra = str(
            mapping.get("error_description")
            or mapping.get("error")
            or mapping.get("message")
            or ""
        )
        if response.status in {401, 403}:
            raise AuthError(
                str(mapping.get("error") or "unauthorized"),
                extra or f"{label} HTTP {response.status}",
            )
        raise UsageError(
            f"{label} HTTP {response.status}" + (f": {extra}" if extra else "")
        )

    def _select_premise(self, account: dict[str, object]) -> dict[str, object]:
        premises = account.get("premises")
        if not isinstance(premises, list) or not premises:
            raise UsageError("no premises on utility account")
        active: list[dict[str, object]] = []
        fallback: list[dict[str, object]] = []
        for raw in premises:
            if not isinstance(raw, dict):
                continue
            premise_id = raw.get("id")
            if not isinstance(premise_id, str) or not premise_id:
                continue
            fallback.append(raw)
            if raw.get("active") is True:
                active.append(raw)
        chosen = active or fallback
        if not chosen:
            raise UsageError("premise id missing")
        return chosen[0]
