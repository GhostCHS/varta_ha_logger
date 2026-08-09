from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST,CONF_PASSWORD,CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import VartaAuthError,VartaClient
from .const import DOMAIN
class VartaConfigFlow(config_entries.ConfigFlow,domain=DOMAIN):
    VERSION=1
    async def async_step_user(self,user_input=None):
        errors={}
        if user_input:
            try:
                c=VartaClient(async_get_clientsession(self.hass),user_input[CONF_HOST],user_input[CONF_USERNAME],user_input[CONF_PASSWORD]); await c.login(); data=await c.read_all()
                serial=str(data.get('info',{}).get('Device_Serial',user_input[CONF_HOST])); await self.async_set_unique_id(serial); self._abort_if_unique_id_configured(); return self.async_create_entry(title=f"VARTA {serial}",data=user_input)
            except VartaAuthError: errors['base']='invalid_auth'
            except Exception: errors['base']='cannot_connect'
        schema=vol.Schema({vol.Required(CONF_HOST):str,vol.Required(CONF_USERNAME):str,vol.Required(CONF_PASSWORD):str})
        return self.async_show_form(step_id='user',data_schema=schema,errors=errors)
