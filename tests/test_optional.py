"""Optional EV, GreenUP, FCU, and notification parsers skip empty accounts."""

from __future__ import annotations

import json

from custom_components.sp_group.client import (
    SpGroupClient,
    _parse_bill_delivery,
    _parse_ev_last_charge,
    _parse_ev_session,
    _parse_ev_unpaid,
    _parse_ev_wallet,
    _parse_fcu_status,
    _parse_greenup,
    _parse_paired_fcus,
    _parse_unread,
)
from custom_components.sp_group.const import (
    SENSOR_KEY_EV_LAST_CHARGE,
    SENSOR_KEY_GREENUP_POINTS,
    SENSOR_KEY_UNREAD_NOTIFICATIONS,
)
from custom_components.sp_group.mapper import sensors_from_usage

from .conftest import FixtureTransport


def test_greenup_and_unread_appear_when_payloads_exist() -> None:
    class ExtraTransport(FixtureTransport):
        def request(self, method, url, headers, body):
            from urllib.parse import urlparse

            from custom_components.sp_group.client import HttpResponse

            parsed = urlparse(url)
            if method == "POST" and parsed.path == "/1up/authenticated/graphql":
                return HttpResponse(
                    200,
                    {"Content-Type": "application/json"},
                    json.dumps(
                        {
                            "data": {
                                "account": {
                                    "node": {
                                        "totalPoints": 12,
                                        "projectedLevelStatus": "MAINTAIN",
                                        "tier": {
                                            "node": {
                                                "level": 1,
                                                "name": "Sprout",
                                                "pointsToLevelUp": 150,
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    ).encode(),
                )
            if (
                method == "GET"
                and parsed.path == "/notifications/v1/notifications"
            ):
                return HttpResponse(
                    200,
                    {"Content-Type": "application/json"},
                    b'{"total_unread_notifications": 3}',
                )
            if method == "GET" and parsed.path == "/eva/v2/order/receipts":
                return HttpResponse(
                    200,
                    {"Content-Type": "application/json"},
                    json.dumps(
                        {
                            "data": [
                                {
                                    "total_consumption": 18.5,
                                    "transaction_amount": 12.3,
                                    "created_at": "2026-08-01T10:00:00+08:00",
                                    "transaction_status": "COMPLETED",
                                    "address": "Example Hub",
                                }
                            ]
                        }
                    ).encode(),
                )
            return super().request(method, url, headers, body)

    usage = SpGroupClient(
        "user@example.com", "secret", transport=ExtraTransport()
    ).fetch_usage()
    assert usage.greenup is not None
    assert usage.greenup.points == 12
    assert usage.unread_notifications == 3
    assert usage.ev_last_charge is not None
    assert usage.ev_last_charge.kwh == 18.5
    by_key = {spec.key: spec for spec in sensors_from_usage(usage)}
    assert by_key[SENSOR_KEY_GREENUP_POINTS].native_value == 12
    assert by_key[SENSOR_KEY_UNREAD_NOTIFICATIONS].native_value == 3
    assert by_key[SENSOR_KEY_EV_LAST_CHARGE].native_value == 18.5


def test_empty_optional_payloads_are_skipped() -> None:
    assert _parse_ev_wallet({"points_balance": 0, "dollar_balance": "0.00"}) is None
    assert _parse_ev_last_charge({"data": []}) is None
    assert _parse_ev_session({"data": None}) is None
    assert _parse_ev_unpaid({"data": {"orders": []}}) is None
    assert _parse_unread({}) is None
    assert _parse_bill_delivery({"preferences": []}, "1") is None
    paired = _parse_paired_fcus(
        {"errors": [{"message": "Unauthorized"}], "data": None}
    )
    assert paired == []
    assert _parse_greenup({"data": {"account": None}}) is None
    assert (
        _parse_fcu_status({"fcu_not_paired": True}, "thing", "Living") is None
    )
