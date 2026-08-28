# SP Group for Home Assistant

Unofficial custom integration that pulls billed electricity (kWh) and water (m³) from an SP e-account into Home Assistant Energy dashboard sensors.

Auth and usage HTTP contracts come from the current SP Android app (`sg.com.singaporepower.spservices` 15.10.0), not the 2018 `jarvis-api` blog.

## Install

Copy `custom_components/sp_group` into your Home Assistant `custom_components/` directory and restart. Add **SP Group** from Settings → Devices & Services. Sign in with the same e-account email and password as the SP app.

Sensors:

- `sensor.electricity` — `device_class=energy`, `state_class=total_increasing`, `kWh`
- `sensor.water` — `device_class=water`, `state_class=total_increasing`, `m³`

Values are the sum of billed period `consumption.current` from `GET /jarvis/v4/charts/{premise_id}`. That sum only grows when a new bill lands.

## Client without Home Assistant

```
uv sync --extra dev
uv run pytest
uv run python scripts/launch_client.py
```

Live login (optional): set `SP_USERNAME` and `SP_PASSWORD`.

## API (from APK 15.10.0)

1. `POST https://identity.spdigital.sg/oauth/token` Auth0 password-realm. Session is `access_token` plus `id_token`.
2. `GET https://b2c.api.spdigital.sg/jarvis/v3/me` with `Authorization: Bearer` and `X-id-token`.
3. `GET https://b2c.api.spdigital.sg/jarvis/v4/charts/{premise_id}` for `elec` and `water`.

Password login is still in the app. Singpass is not implemented here. EV charging, GreenUP, and bill pay are out of scope.

SSL pinning and Play Integrity in the APK are not reproduced. A non-app client may be rejected by production; parse and HA mapping still run against fixtures.
