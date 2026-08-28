# SP Group for Home Assistant

Unofficial custom integration for Singapore Power e-accounts. It exposes billed electricity (kWh), water (m³), and gas when the account has billed periods, as Energy-dashboard sensors, plus account diagnostics.

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

After the first successful poll, usage is imported as long-term statistics.

- Grid consumption: `sensor.sp_group_utilities_electricity`
- Water: `sensor.sp_group_utilities_water` (Water section, not Grid)
- Gas: `sensor.sp_group_utilities_gas` when the charts payload has billed gas periods

When the premise has AMI electricity (`ami_elec`), the electricity sensor uses the same AMI series as the SP app: 30-minute slots folded into hours for the last 31 days, plus daily points for about a year. Energy then shows hourly bars instead of one yearly lump. Water stays billed months (no AMI water on typical accounts).

Last billed period sensors (`*_last_billed`) are the latest bill. Do not add those as Energy grid sources. `Electricity today` and `Electricity last hour` are AMI measurements.

## Entities

| Entity | What it is |
| --- | --- |
| Electricity | Cumulative billed kWh (`total_increasing`) |
| Water | Cumulative billed m³ (`total_increasing`) |
| Gas | Cumulative billed usage, only if Jarvis returns gas periods |
| Electricity / water / gas last billed | Latest billed period amount (`measurement`) |
| Account | Account status, diagnostic. Attributes include address, account number, utilities, AMI flag, retailer, next meter-reading window |
| Prepaid credit | PPMS balance in SGD, only when `/me` says a prepaid account exists |

Shared attributes on usage sensors: `premise_id`, `address`, `account_number`, `last_period`, `last_period_amount`, `period_count`, `average_consumption`, `comparison`.

Reconfigure the entry from the integration page if the e-account password changes. Reauth starts automatically when the stored session is rejected.

## What it does

Polls about once an hour:

1. `POST https://identity.spdigital.sg/oauth/token` Auth0 password-realm (scopes include `me me:uportal me:eva me:rbac`)
2. `GET https://b2c.api.spdigital.sg/jarvis/v3/me` for the premise and account
3. `GET https://b2c.api.spdigital.sg/jarvis/v4/charts/{premise_id}` for `elec`, `water`, and `gas`
4. `POST https://b2c.api.spdigital.sg/jarvis/v3/ami/charts` when `ami_elec` is true (`grouped_by` `day` for 30-minute slots, `month` for daily)
5. `GET https://b2c.api.spdigital.sg/jarvis/v3/smrd-uportal/{premise_id}` for the next meter-reading window (ignored if it fails)
6. `GET https://b2c.api.spdigital.sg/jarvis/v3/ppms/balance/{premise_id}` only if `ppms_details.exists` is true

The session refresh token is stored on the config entry so Home Assistant restarts do not password-login every time.

Download diagnostics from the integration page if you need to file a bug. Tokens and the password are not included.

## Use

Add the cumulative electricity sensor as the Energy dashboard grid source, and the water sensor under Water. Automations can read last-billed amounts or account status without using those as energy statistics.

## Known limitations

AMI electricity is 30-minute slots for 31 days and daily points for about 13 months, matching the app's Today / month / year charts. EV charging, GreenUP, bill pay, meter-reading submission, and Singpass login are not included. Town-gas sensors appear only when Jarvis returns billed `gas` periods. Prepaid credit is skipped when the account is not PPMS.

## Remove

Settings → Devices & services → SP Group → Delete. Then remove the folder from `custom_components` if you installed it manually, or delete the HACS download, and restart.

## Troubleshooting

- **invalid_claim / rejected session token:** the client must request the `me:*` scopes. Use this repo, not a stale copy.
- **Suspicious request requires verification:** Auth0 bot detection after many password logins. Sign in once in the SP app, wait a few minutes, then reload or reauthenticate the integration.
- **No Energy statistics:** wait for the first poll, hard-refresh the Energy settings page, then pick the cumulative sensors above, not the last-billed ones.

## Development

```
uv sync --extra dev
uv run pytest
uv run python scripts/launch_client.py
```

Optional live call: `SP_USERNAME` and `SP_PASSWORD`.
