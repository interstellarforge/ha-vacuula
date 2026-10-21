"""Constants for the Vacuula integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "vacuula"

DEFAULT_HOST = "6a057cb4-vacuula"  # hostname of the Vacuula Home Assistant app
DEFAULT_PORT = 80

ROBOT_TYPE_GEN4 = "neato.gen4"

# Fallback poll; live updates arrive through the server-sent-event stream.
POLL_INTERVAL = timedelta(seconds=60)

CLEANING_MODES = ["eco", "turbo", "auto", "max"]
NAVIGATION_MODES = ["normal", "gentle"]
DEFAULT_CLEANING_MODE = "auto"
DEFAULT_NAVIGATION_MODE = "normal"

ACTIONS = [
    "invalid",
    "cleaning",
    "docking",
    "diagnostic_test",
    "updating_software",
    "cleaning_standby",
]

# Robot "abilities" (command names understood by the robot through Vacuula)
ABILITY_STATE = "state.show"
ABILITY_START = "cleaning.start"
ABILITY_PAUSE = "cleaning.pause"
ABILITY_RESUME = "cleaning.resume"
ABILITY_CANCEL = "cleaning.cancel"
ABILITY_RETURN = "navigation.return_to_base"
ABILITY_FIND_ME = "utilities.find_me"

SERVICE_CLEAN_ZONES = "clean_zones"
SERVICE_GET_ZONES = "get_zones"
