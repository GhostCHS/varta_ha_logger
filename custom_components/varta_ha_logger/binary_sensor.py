from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
class VartaInverterOnline(CoordinatorEntity,BinarySensorEntity):
    _attr_name='KACO verbunden'; _attr_unique_id='varta_kaco_connected'; _attr_device_class=BinarySensorDeviceClass.CONNECTIVITY
    @property
    def is_on(self):
        inv=(self.coordinator.data.get('sunspec',{}).get('data',{}).get('Inverters') or [{}])[0]; return bool(inv.get('connected'))
    @property
    def extra_state_attributes(self):
        inv=(self.coordinator.data.get('sunspec',{}).get('data',{}).get('Inverters') or [{}])[0]; return {k:inv.get(k) for k in ('info','hostname','port','address')}
async def async_setup_entry(hass,entry,async_add_entities):
    async_add_entities([VartaInverterOnline(hass.data[DOMAIN][entry.entry_id])])
