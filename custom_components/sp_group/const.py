"""SP Group integration constants extracted from APK 15.10.0."""

from datetime import timedelta

DOMAIN = "sp_group"
ATTRIBUTION = "Data provided by SP Group"

IDENTITY_HOST = "https://identity.spdigital.sg"
B2C_HOST = "https://b2c.api.spdigital.sg"

OAUTH_TOKEN_PATH = "/oauth/token"
JARVIS_ME_PATH = "/jarvis/v3/me"
JARVIS_CHARTS_PATH = "/jarvis/v4/charts"
JARVIS_PPMS_PATH = "/jarvis/v3/ppms/balance"
JARVIS_SMRD_PATH = "/jarvis/v3/smrd-uportal"

AUTH0_CLIENT_ID = "z1tl6I1V6HI201ule9tmSALb97hw8Biu"
AUTH0_AUDIENCE = "https://profile.up.spdigital.sg/"
# Mh.a.h() joins these for Auth0Api.login. Missing me:* scopes yields
# MuleSoft 403 invalid_claim on /jarvis/v3/me.
AUTH0_SCOPE = (
    "openid email profile offline_access enroll read:authenticators "
    "user_metadata me me:uportal me:eva me:rbac"
)
AUTH0_GRANT_TYPE = "http://auth0.com/oauth/grant-type/password-realm"
AUTH0_REFRESH_GRANT = "refresh_token"
AUTH0_REALM = "Username-Password-Authentication"
TOKEN_EXPIRY_BUFFER_SECONDS = 60

CONF_ACCESS_TOKEN = "access_token"
CONF_ID_TOKEN = "id_token"
CONF_REFRESH_TOKEN = "refresh_token"

USER_AGENT = "Infinity/15.10.0 (Android)"
HEADER_ID_TOKEN = "X-id-token"
CONTENT_TYPE_JSON = "application/json; charset=utf-8"
ACCEPT_LANGUAGE = "en_US"

UPDATE_INTERVAL = timedelta(hours=1)

DEVICE_CLASS_ENERGY = "energy"
DEVICE_CLASS_WATER = "water"
DEVICE_CLASS_GAS = "gas"
DEVICE_CLASS_MONETARY = "monetary"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"
STATE_CLASS_MEASUREMENT = "measurement"
UNIT_KWH = "kWh"
UNIT_M3 = "m³"
UNIT_SGD = "SGD"
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"

SENSOR_KEY_ELECTRICITY = "electricity"
SENSOR_KEY_WATER = "water"
SENSOR_KEY_GAS = "gas"
SENSOR_KEY_ELECTRICITY_LAST = "electricity_last_period"
SENSOR_KEY_WATER_LAST = "water_last_period"
SENSOR_KEY_GAS_LAST = "gas_last_period"
SENSOR_KEY_ACCOUNT = "account"
SENSOR_KEY_PPMS = "ppms_credit"
