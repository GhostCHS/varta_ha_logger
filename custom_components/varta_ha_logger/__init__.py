from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import VartaClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import VartaCoordinator
PLATFORMS=['sensor','binary_sensor']
async def async_setup_entry(hass,entry):
    client=VartaClient(async_get_clientsession(hass),entry.data[CONF_HOST],entry.data[CONF_USERNAME],entry.data[CONF_PASSWORD])
    coordinator=VartaCoordinator(hass,client,entry.options.get(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL))
    await coordinator.async_config_entry_first_refresh(); hass.data.setdefault(DOMAIN,{})[entry.entry_id]=coordinator
    await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS); return True
async def async_unload_entry(hass,entry):
    ok=await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
    if ok:hass.data[DOMAIN].pop(entry.entry_id,None)
    return ok
