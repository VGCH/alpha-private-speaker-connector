"""Constants for Alpha Private Speaker integration."""
DOMAIN = "alpha_speaker"
NAME = "Alpha Connector"

# Configuration keys
CONF_GRPC_PORT = "grpc_port"
CONF_EVENT_PREFIX = "event_prefix"
CONF_MAX_SPEAKERS = "max_speakers"
CONF_RECONNECT_TIMEOUT = "reconnect_timeout"
CONF_DEBUG = "debug"
CONF_LOG_LEVEL = "log_level"
CONF_HA_TOKEN = "ha_token"
CONF_HA_URL = "ha_url"

# Defaults
DEFAULT_GRPC_PORT = 50051
DEFAULT_EVENT_PREFIX = "alpha_speaker_"
DEFAULT_MAX_SPEAKERS = 10
DEFAULT_RECONNECT_TIMEOUT = 30
DEFAULT_DEBUG = False
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_HA_URL = "http://localhost:8123"

# Services
SERVICE_SEND_TTS = "send_tts"
SERVICE_RELOAD_SPEAKERS = "reload_speakers"
SERVICE_TEST_CONNECTION = "test_connection"

# Events
EVENT_SPEAKER_CONNECTED = f"{DEFAULT_EVENT_PREFIX}connected"
EVENT_SPEAKER_DISCONNECTED = f"{DEFAULT_EVENT_PREFIX}disconnected"
EVENT_SPEAKER_COMMAND = f"{DEFAULT_EVENT_PREFIX}command"
EVENT_SPEAKER_TTS_REQUEST = f"{DEFAULT_EVENT_PREFIX}tts_request"
EVENT_SPEAKER_TTS_RESPONSE = f"{DEFAULT_EVENT_PREFIX}tts_response"
EVENT_SPEAKER_TTS_SENT = f"{DEFAULT_EVENT_PREFIX}tts_command_sent"
EVENT_CONNECTOR_STARTED = f"{DEFAULT_EVENT_PREFIX}connector_started"
EVENT_CONNECTOR_STOPPED = f"{DEFAULT_EVENT_PREFIX}connector_stopped"

# Sensors
SENSOR_CONNECTOR = "alpha_speaker_connector"
SENSOR_STATS = "alpha_speakers_stats"

# Icons
ICON_SPEAKER = "mdi:speaker"
ICON_SPEAKER_MULTIPLE = "mdi:speaker-multiple"
ICON_MICROPHONE = "mdi:microphone"
ICON_CONNECTION = "mdi:connection"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "media_player"]

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_storage"

# Signal for updates
SIGNAL_SPEAKER_UPDATE = f"{DOMAIN}_speaker_update"