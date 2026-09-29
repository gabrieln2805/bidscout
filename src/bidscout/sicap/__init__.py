"""The only part of bidscout that knows how to speak to SEAP / SICAP."""

from bidscout.sicap.client import SicapClient
from bidscout.sicap.filters import validate_filters

__all__ = ["SicapClient", "validate_filters"]
