"""Coordinator. No history or log storage is implemented."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

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
        # Energy Today is calculated from live production-power samples.
        # It is deliberately memory-only: no custom history/log is persisted.
        self._today_energy_wh = 0.0
        self._energy_day = None
        self._last_energy_time = None
        self._last_production_power = None

    def _update_today_energy(self, production_power):
        now = dt_util.now()
        today = now.date()

        if self._energy_day != today:
            self._energy_day = today
            self._today_energy_wh = 0.0
            self._last_energy_time = now
            self._last_production_power = production_power
            return

        if self._last_energy_time is None or self._last_production_power is None:
            self._last_energy_time = now
            self._last_production_power = production_power
            return

        elapsed = (now - self._last_energy_time).total_seconds()
        # Do not integrate across a long communication outage.
        if 0 < elapsed <= 120:
            average_power = (self._last_production_power + production_power) / 2
            self._today_energy_wh += max(average_power, 0) * elapsed / 3600

        self._last_energy_time = now
        self._last_production_power = production_power

    async def _async_update_data(self):
        try:
            data = await self.client.read_all()
            self._last_good_data = data

            production_power = data.get("summary", {}).get("production_power")
            if isinstance(production_power, (int, float)):
                self._update_today_energy(float(production_power))
                data.setdefault("summary", {})["pv_energy_today"] = round(
                    self._today_energy_wh / 1000, 3
                )

            return data
        except Exception as err:
            # The VARTA WebIF occasionally drops/renews its session. Do not turn
            # every HA entity into "unknown/unavailable" for a transient miss.
            # This is only an in-memory snapshot; no history/log data is stored.
            if self._last_good_data is not None:
                _LOGGER.debug("Temporary VARTA read failure; keeping last valid values: %s", err)
                return self._last_good_data
            raise
