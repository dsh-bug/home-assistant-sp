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
- Do not add water in Energy. SP only bills water monthly, so there is no hourly or daily water series.
- Gas: `sensor.sp_group_utilities_gas` when the charts payload has billed gas periods

When the premise has AMI electricity (`ami_elec`), the electricity sensor uses the same AMI series as the SP app: 30-minute slots for the last 31 days, plus daily points for about a year. The feed lags a few hours; empty slots after the last reported interval are dropped. Energy folds two slots into each clock hour because Home Assistant energy statistics are hourly. Water is billed monthly only. The water total and last-billed sensors stay as numbers; they are not imported as Energy hourly statistics.

Last billed period sensors (`*_last_billed`) are the latest bill. Do not add those as Energy grid sources. `Electricity today` and `Electricity last 30 min` are AMI measurements. The 30-minute sensor is the last slot SP has published, not the clock hour.

## Entities

| Entity | What it is |
| --- | --- |
| Electricity | Cumulative billed kWh (`total_increasing`) |
| Water | Cumulative billed m³ (monthly bills, not an Energy hourly source) |
| Gas | Cumulative billed usage, only if Jarvis returns gas periods |
| Electricity / water / gas last billed | Latest billed period amount (`measurement`) |
| Account | Account status, diagnostic. Attributes include address, account number, utilities, AMI flag, retailer, next meter-reading window |
| Prepaid credit | PPMS balance in SGD, only when `/me` says a prepaid account exists |
| Last bill | Latest utility bill in SGD from Njord history |
| Amount due | Outstanding payable in SGD. Negative is a credit |
| Electricity / water meter | Last actual register from SMRD (`total_increasing`) |
| Electricity this month | Green Goals month-to-date kWh vs `goal_target` |

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
7. `GET https://b2c.api.spdigital.sg/njord/v4/payables` for the amount due (Njord stores dollars as integer cents)
8. `GET https://b2c.api.spdigital.sg/njord/v3/history?account_numbers={account}` for the latest `type=bill` row. PDF download URLs are not stored.
9. `GET https://b2c.api.spdigital.sg/jarvis/v5/greengoals/targets` for the current month's used vs target. Zero used and target rows are skipped.

The session refresh token is stored on the config entry so Home Assistant restarts do not password-login every time.

Download diagnostics from the integration page if you need to file a bug. Tokens and the password are not included.

## Use

Add the cumulative electricity sensor as the Energy dashboard grid source. Leave Water empty in Energy. Use `Water last billed` for the last month's m³.

## Known limitations

AMI electricity is 30-minute slots for 31 days and daily points for about 13 months, matching the app's Today / month / year charts. Last bill and amount due are the same Njord dollar figures the app shows. Green Goals is month-to-date used vs a target, not the AMI today sensor. EV charging, GreenUP quests, bill pay mutations, meter-reading submission, Tengah FCU cooling, and Singpass login are not included. Town-gas sensors appear only when Jarvis returns billed `gas` periods. Prepaid credit is skipped when the account is not PPMS.

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
