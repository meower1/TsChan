"""Application-wide constants for tschan."""

# ── Application ──────────────────────────────────────────────────────────────

APP_NAME = "tschan"
VERSION = "1.0.0"
STATE_FILE = ".tschan.json"
DATA_DIR = "ts3-data"
ENV_FILE = ".env"
COMPOSE_FILE = "docker-compose.yml"

# ── TS3 Default Ports ────────────────────────────────────────────────────────

DEFAULT_VOICE_PORT = 9987
DEFAULT_QUERY_PORT_RAW = 10011
DEFAULT_QUERY_PORT_SSH = 10022
DEFAULT_FILE_PORT = 30033
DEFAULT_MAX_CLIENTS = 32

# ── Docker Images ────────────────────────────────────────────────────────────

DEFAULT_TS3_IMAGE = "mbentley/teamspeak:latest"
IRAN_TS3_IMAGE = "docker.devneeds.ir/mbentley/teamspeak:latest"
DEFAULT_AUDIOBOT_IMAGE = "splamy/ts3audiobot:master"
IRAN_AUDIOBOT_IMAGE = "docker.devneeds.ir/splamy/ts3audiobot:master"
DEFAULT_PYTHON_IMAGE = "python:3.12-slim"
IRAN_PYTHON_IMAGE = "docker.devneeds.ir/library/python:3.12-slim"
DEFAULT_PIP_INDEX = "https://pypi.org/simple/"
IRAN_PIP_INDEX = "https://pypi.devneeds.ir/simple/"

# ── Network ──────────────────────────────────────────────────────────────────

DOCKER_NETWORK = "ts3-net"
QUERY_IP_ALLOWLIST = "127.0.0.1\n::1\n172.16.0.0/12\n"

# ── Template Identifiers ────────────────────────────────────────────────────

TEMPLATE_MEOWERS_HANGOUT = "meowers_hangout"
TEMPLATE_NEON_ARENA = "neon_arena"
TEMPLATE_COZY_DEN = "cozy_den"

TEMPLATE_DISPLAY_NAMES: dict[str, str] = {
    "meowers_hangout": "🐱 {name}'s hangout",
    "neon_arena": "🎮 neon arena",
    "cozy_den": "☕ the cozy den",
}

# Maps template key → suffix appended to the user's server name for the
# virtualserver_name in TS3.
TEMPLATE_SERVER_NAME_SUFFIX: dict[str, str] = {
    "meowers_hangout": "'s hangout",
    "neon_arena": "'s neon arena",
    "cozy_den": "'s cozy den",
}
