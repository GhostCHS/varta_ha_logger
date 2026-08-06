from __future__ import annotations
import re
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

SKIP_ROOTS = {'conf'}

def _slug(parts):
    return re.sub(r'[^a-z0-9_]+','_','_'.join(str(x) for x in parts).lower()).strip('_')

def _friendly(parts):
    return 'VARTA ' + ' / '.join(str(p + 1) if isinstance(p,int) else str(p).replace('_',' ') for p in parts)

def _flatten(value,path=()):
    if isinstance(value,dict):
        for key,child in value.items():
            if not str(key).startswith('_'):
                yield from _flatten(child,path+(key,))
    elif isinstance(value,list):
        for index,child in enumerate(value):
            yield from _flatten(child,path+(index,))
    elif value is None or isinstance(value,(str,int,float,bool)):
        yield path,value

def _value_at(data,path):
    cur=data
    for part in path:
        try:
            cur=cur[part] if isinstance(part,int) else cur.get(part)
        except (IndexError,KeyError,TypeError,AttributeError):
            return None
    return cur

class VartaDynamicSensor(CoordinatorEntity,SensorEntity):
    def __init__(self,coordinator,entry_id,path):
        super().__init__(coordinator)
        self.path=path
        self._attr_unique_id=f'varta_{entry_id}_{_slug(path)}'
        self._attr_name=_friendly(path)
    @property
    def native_value(self):
        value=_value_at(self.coordinator.data,self.path)
        return value if value is None or isinstance(value,(str,int,float,bool)) else None
    @property
    def device_info(self):
        info=self.coordinator.data.get('info',{})
        serial=str(info.get('Device_Serial','varta'))
        return {'identifiers':{(DOMAIN,serial)},'name':'VARTA Energiespeicher','manufacturer':'VARTA Storage','model':str(info.get('Device_Description','VARTA')),'serial_number':serial}

async def async_setup_entry(hass,entry,async_add_entities):
    coordinator=hass.data[DOMAIN][entry.entry_id]
    seen=set(); entities=[]
    for path,_ in _flatten(coordinator.data):
        if not path or path[0] in SKIP_ROOTS: continue
        key=_slug(path)
        if not key or key in seen: continue
        seen.add(key)
        entities.append(VartaDynamicSensor(coordinator,entry.entry_id,path))
    async_add_entities(entities)
