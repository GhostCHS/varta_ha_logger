from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

# Deliberately expose only useful, interpreted values. Raw CGI arrays remain
# available internally to the integration but no longer clutter the HA device.
SENSORS = {
 ('summary','production_power'):('Produktionsleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','pv_energy_today'):('PV-Energie heute',SensorDeviceClass.ENERGY,UnitOfEnergy.KILO_WATT_HOUR,SensorStateClass.TOTAL_INCREASING),
 ('summary','house_consumption'):('Energieverbrauch',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','grid_export_power'):('Netzeinspeisung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','grid_import_power'):('Netzbezug',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','battery_charge_power'):('Batterie Ladeleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','battery_discharge_power'):('Batterie Entladeleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','state_of_charge'):('Ladezustand',SensorDeviceClass.BATTERY,PERCENTAGE,SensorStateClass.MEASUREMENT),
 ('summary','ems_max_power'):('Maximale EMS-Leistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','ems_max_discharge_power'):('Maximale Entladeleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','charger_count'):('Anzahl Batterieladegeräte',None,None,None),
 ('summary','kaco_active_power'):('Wechselrichter Leistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','kaco_max_power'):('Wechselrichter Nennleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','kaco_power_limit'):('Wechselrichter Leistungsbegrenzung',None,PERCENTAGE,SensorStateClass.MEASUREMENT),
 ('summary','charge_cycles'):('Batterie-Ladezyklen',None,None,SensorStateClass.TOTAL_INCREASING),
 ('summary','active_errors'):('Aktive Fehler',None,None,SensorStateClass.MEASUREMENT),
 ('energy','EGrid_AC_DC'):('Energie aus dem Netz geladen',SensorDeviceClass.ENERGY,UnitOfEnergy.WATT_HOUR,SensorStateClass.TOTAL_INCREASING),
 ('energy','EGrid_DC_AC'):('Energie ins Netz abgegeben',SensorDeviceClass.ENERGY,UnitOfEnergy.WATT_HOUR,SensorStateClass.TOTAL_INCREASING),
 ('energy','EWr_AC_DC'):('Wechselrichter Ladeenergie',SensorDeviceClass.ENERGY,UnitOfEnergy.WATT_HOUR,SensorStateClass.TOTAL_INCREASING),
 ('info','Device_Serial'):('Seriennummer Energiespeicher',None,None,None),
 ('info','Serial_EMeter'):('Seriennummer Energiezähler',None,None,None),
 ('ems','Zeit'):('Letzte Aktualisierung VARTA',None,None,None),
}


def _value_at(data,path):
    cur=data
    for part in path:
        if not isinstance(cur,dict): return None
        cur=cur.get(part)
    return cur


class VartaSensor(CoordinatorEntity,SensorEntity):
    def __init__(self,coordinator,entry_id,path,meta):
        super().__init__(coordinator)
        self.path=path
        self._attr_unique_id=f"varta_{entry_id}_{'_'.join(path)}"
        self._attr_name=meta[0]
        self._attr_device_class=meta[1]
        self._attr_native_unit_of_measurement=meta[2]
        self._attr_state_class=meta[3]
        if path == ('summary', 'pv_energy_today'):
            self._attr_icon = 'mdi:solar-power'

    @property
    def native_value(self):
        return _value_at(self.coordinator.data,self.path)

    @property
    def device_info(self):
        info=self.coordinator.data.get('info',{})
        serial=str(info.get('Device_Serial','varta'))
        return {
            'identifiers':{(DOMAIN,serial)},
            'name':'VARTA Energiespeicher',
            'manufacturer':'VARTA Storage',
            'model':str(info.get('Device_Description','VARTA')),
            'serial_number':serial,
            'sw_version':str(info.get('SW_Version_EMS','')),
            'configuration_url':self.coordinator.client.host,
        }


async def async_setup_entry(hass,entry,async_add_entities):
    coordinator=hass.data[DOMAIN][entry.entry_id]
    entities=[]
    for path,meta in SENSORS.items():
        # Add known sensors even when an optional endpoint is temporarily empty;
        # coordinator retention will keep the last valid values on later misses.
        entities.append(VartaSensor(coordinator,entry.entry_id,path,meta))
    async_add_entities(entities)
