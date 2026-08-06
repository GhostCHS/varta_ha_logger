"""Coordinator. No history or log storage is implemented."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class VartaCoordinator(DataUpdateCoordinator):
    """Poll VARTA while retaining the last valid snapshot on short outages."""

    def __init__(self, hass, client, interval):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="VARTA",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self._last_good_data = None

    async def _async_update_data(self):
        try:
            data = await self.client.read_all()
            self._last_good_data = data
            return data
        except Exception as err:
            # The VARTA WebIF occasionally drops/renews its session. Do not turn
            # every HA entity into "unknown/unavailable" for a transient miss.
            # This is only an in-memory snapshot; no history/log data is stored.
            if self._last_good_data is not None:
                _LOGGER.debug("Temporary VARTA read failure; keeping last valid values: %s", err)
                return self._last_good_data
            raise
