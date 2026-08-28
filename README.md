# SP Group for Home Assistant

Unofficial custom integration for Singapore Power e-accounts. It exposes billed electricity (kWh) and water (m³) as Energy-dashboard sensors.

Auth and usage HTTP contracts come from SP Android app `sg.com.singaporepower.spservices` 15.10.0.

## Install

### HACS (custom repository)

1. HACS → Integrations → Custom repositories
2. URL: `https://github.com/maci0/home-assistant-sp`, category Integration
3. Download **SP Group**, then restart Home Assistant
4. Settings → Devices & services → Add integration → **SP Group**
5. Sign in with the same e-account email and password as the SP app

### Manual

Copy `custom_components/sp_group` into `<config>/custom_components/sp_group` and restart.

## Energy dashboard

After the first successful poll, billed months are imported as long-term statistics.

- Grid consumption: `sensor.sp_group_utilities_electricity`
- Water: `sensor.sp_group_utilities_water` (Water section, not Grid)

These are billed totals, not live AMI ticks. Usage appears on bill dates and stays flat between bills.

Each sensor also has `premise_id`, `last_period`, `last_period_amount`, and `period_count`.

## What it does

1. `POST https://identity.spdigital.sg/oauth/token` Auth0 password-realm (scopes include `me me:uportal me:eva me:rbac`)
2. `GET https://b2c.api.spdigital.sg/jarvis/v3/me` for the premise
3. `GET https://b2c.api.spdigital.sg/jarvis/v4/charts/{premise_id}` for `elec` and `water`

The session refresh token is stored on the config entry so Home Assistant restarts do not password-login every time.

## Not included

EV charging, GreenUP, bill pay, meter-reading submission, gas, Singpass-only login.

## Troubleshooting

- **invalid_claim / rejected session token:** the client must request the `me:*` scopes. Use this repo, not a stale copy.
- **Suspicious request requires verification:** Auth0 bot detection after many password logins. Sign in once in the SP app, wait a few minutes, then reload or reauthenticate the integration.
- **No Energy statistics:** wait for the first poll, hard-refresh the Energy settings page, then pick the sensors above.

## Development

```
uv sync --extra dev
uv run pytest
uv run python scripts/launch_client.py
```

Optional live call: `SP_USERNAME` and `SP_PASSWORD`.
