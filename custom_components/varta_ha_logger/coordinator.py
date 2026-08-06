"""Coordinator. No history or log storage is implemented."""
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import VartaApiError

class VartaCoordinator(DataUpdateCoordinator):
    def __init__(self,hass,client,interval):
        super().__init__(hass, logger=__import__('logging').getLogger(__name__), name='VARTA', update_interval=timedelta(seconds=interval)); self.client=client
    async def _async_update_data(self):
        try: return await self.client.read_all()
        except VartaApiError as e: raise UpdateFailed(str(e)) from e
        except Exception as e: raise UpdateFailed(f'VARTA communication failed: {e}') from e
