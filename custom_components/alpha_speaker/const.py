"""Константы интеграции Alpha Speaker."""

DOMAIN = "alpha_speaker"
NAME = "Alpha Connector"
INTEGRATION_VERSION = "2.2.3"

CONF_GRPC_PORT = "grpc_port"
CONF_EVENT_PREFIX = "event_prefix"
CONF_MAX_SPEAKERS = "max_speakers"
# Оставлены для чтения старых config entries; текущая интеграция не использует
# внешний HTTP API Home Assistant и не требует long-lived token.
CONF_HA_TOKEN = "ha_token"
CONF_HA_URL = "ha_url"

DEFAULT_GRPC_PORT = 50051
DEFAULT_EVENT_PREFIX = "alpha_speaker_"
DEFAULT_MAX_SPEAKERS = 10

SERVICE_SEND_TTS = "send_tts"
SERVICE_RELOAD_SPEAKERS = "reload_speakers"
SERVICE_TEST_CONNECTION = "test_connection"

EVENT_SPEAKER_CONNECTED = f"{DEFAULT_EVENT_PREFIX}connected"
EVENT_SPEAKER_DISCONNECTED = f"{DEFAULT_EVENT_PREFIX}disconnected"
EVENT_SPEAKER_COMMAND = f"{DEFAULT_EVENT_PREFIX}command"
EVENT_SPEAKER_TTS_REQUEST = f"{DEFAULT_EVENT_PREFIX}tts_request"
EVENT_SPEAKER_TTS_RESPONSE = f"{DEFAULT_EVENT_PREFIX}tts_response"
EVENT_SPEAKER_TTS_SENT = f"{DEFAULT_EVENT_PREFIX}tts_command_sent"
EVENT_CONNECTOR_STARTED = f"{DEFAULT_EVENT_PREFIX}connector_started"
EVENT_CONNECTOR_STOPPED = f"{DEFAULT_EVENT_PREFIX}connector_stopped"

SENSOR_CONNECTOR = "alpha_speaker_connector"
SENSOR_STATS = "alpha_speakers_stats"

ICON_SPEAKER = "mdi:speaker"
ICON_SPEAKER_MULTIPLE = "mdi:speaker-multiple"
ICON_MICROPHONE = "mdi:microphone"
ICON_CONNECTION = "mdi:connection"

PLATFORMS = ["sensor", "binary_sensor", "media_player"]

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_storage"
SIGNAL_SPEAKER_UPDATE = f"{DOMAIN}_speaker_update"
