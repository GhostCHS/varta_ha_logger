from __future__ import annotations

import re
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

SKIP_ROOTS={'params'}
KNOWN={
 ('summary','production_power'):('PV-Leistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','house_consumption'):('Hausverbrauch',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','grid_power'):('Netzleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','battery_power'):('Batterieleistung',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT),
 ('summary','state_of_charge'):('Batterie-Ladezustand',SensorDeviceClass.BATTERY,PERCENTAGE,SensorStateClass.MEASUREMENT),
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
 ('info','Device_Description'):('Gerätebezeichnung',None,None,None),
 ('info','Serial_EMeter'):('Seriennummer Energiezähler',None,None,None),
 ('ems','Zeit'):('Letzte Aktualisierung VARTA',None,None,None),
}
for phase in ('L1','L2','L3'):
 KNOWN[('wr',f'U Verbund {phase}')]=(f'Wechselrichter Netzspannung {phase}',SensorDeviceClass.VOLTAGE,UnitOfElectricPotential.VOLT,SensorStateClass.MEASUREMENT)
 KNOWN[('wr',f'I Verbund {phase}')]=(f'Wechselrichter Netzstrom {phase}',SensorDeviceClass.CURRENT,UnitOfElectricCurrent.AMPERE,SensorStateClass.MEASUREMENT)
 KNOWN[('wr',f'U Insel {phase}')]=(f'Notstrom Spannung {phase}',SensorDeviceClass.VOLTAGE,UnitOfElectricPotential.VOLT,SensorStateClass.MEASUREMENT)
 KNOWN[('wr',f'I Insel {phase}')]=(f'Notstrom Strom {phase}',SensorDeviceClass.CURRENT,UnitOfElectricCurrent.AMPERE,SensorStateClass.MEASUREMENT)
 KNOWN[('emeter',f'U_V_{phase}')]=(f'Netzspannung {phase}',SensorDeviceClass.VOLTAGE,UnitOfElectricPotential.VOLT,SensorStateClass.MEASUREMENT)
 KNOWN[('emeter',f'Iw_V_{phase}')]=(f'Netzleistung {phase}',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT)
 KNOWN[('emeter',f'Iw_PV_{phase}')]=(f'PV-Leistung {phase}',SensorDeviceClass.POWER,UnitOfPower.WATT,SensorStateClass.MEASUREMENT)

FRIENDLY_ROOTS={
 'info':'Gerät', 'ems':'Energiespeicher', 'energy':'Energie', 'errors':'Fehler',
 'service':'Service', 'sunspec':'Wechselrichter', 'wr':'Wechselrichter',
 'emeter':'Energiezähler', 'ens':'Netzschutz', 'na':'Netzschutz',
 'chargers':'Batterieladegerät', 'summary':'',
}
FRIENDLY_KEYS={
 'OnlineStatus':'Online-Status','System State':'Systemstatus','SK':'Schaltkontakt',
 'EMS Ctrl':'EMS-Steuerung','BetrFlags1':'Betriebsstatus 1','BetrFlags2':'Betriebsstatus 2','PMB':'Leistungsmanagement',
 'SOC_GS':'Ladezustand','BattData':'Batteriedaten','Type':'Typ','ModulData':'Moduldaten',
 'FilterZeit':'Filterzeit','ErrorList':'Fehlerliste','NA_ErrorList':'Netzschutz-Fehlerliste',
}

def _slug(parts):return re.sub(r'[^a-z0-9_]+','_','_'.join(str(x) for x in parts).lower()).strip('_')
def _friendly(parts):
 root=FRIENDLY_ROOTS.get(parts[0],str(parts[0]).replace('_',' ').title()) if parts else ''
 rest=[]
 for p in parts[1:]:
  if isinstance(p,int):rest.append(str(p+1))
  else:rest.append(FRIENDLY_KEYS.get(str(p),str(p).replace('_',' ')))
 text=' '.join(([root] if root else [])+rest).strip()
 return text or 'VARTA Sensor'
def _flatten(value,path=()):
 if isinstance(value,dict):
  for key,child in value.items():
   if not str(key).startswith('_'):yield from _flatten(child,path+(key,))
 elif isinstance(value,list):
  for index,child in enumerate(value):yield from _flatten(child,path+(index,))
 elif value is None or isinstance(value,(str,int,float,bool)):yield path,value
def _value_at(data,path):
 cur=data
 for part in path:
  try:cur=cur[part] if isinstance(part,int) else cur.get(part)
  except (IndexError,KeyError,TypeError,AttributeError):return None
 return cur

class VartaDynamicSensor(CoordinatorEntity,SensorEntity):
 def __init__(self,coordinator,entry_id,path):
  super().__init__(coordinator);self.path=path;self._attr_unique_id=f'varta_{entry_id}_{_slug(path)}';meta=KNOWN.get(path);self._attr_name=meta[0] if meta else _friendly(path)
  if meta:self._attr_device_class=meta[1];self._attr_native_unit_of_measurement=meta[2];self._attr_state_class=meta[3]
 @property
 def native_value(self):
  value=_value_at(self.coordinator.data,self.path);return value if value is None or isinstance(value,(str,int,float,bool)) else None
 @property
 def device_info(self):
  info=self.coordinator.data.get('info',{});serial=str(info.get('Device_Serial','varta'))
  return {'identifiers':{(DOMAIN,serial)},'name':'VARTA Energiespeicher','manufacturer':'VARTA Storage','model':str(info.get('Device_Description','VARTA')),'serial_number':serial,'sw_version':str(info.get('SW_Version_EMS','')),'configuration_url':self.coordinator.client.host}

async def async_setup_entry(hass,entry,async_add_entities):
 coordinator=hass.data[DOMAIN][entry.entry_id];seen=set();entities=[]
 for path,_ in _flatten(coordinator.data):
  if not path or path[0] in SKIP_ROOTS:continue
  if path in {('summary','kaco_connected'),('summary','pv_meter_power')}:continue
  key=_slug(path)
  if not key or key in seen:continue
  seen.add(key);entities.append(VartaDynamicSensor(coordinator,entry.entry_id,path))
 async_add_entities(entities)
