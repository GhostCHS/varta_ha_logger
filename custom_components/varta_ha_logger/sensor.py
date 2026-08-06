from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfElectricPotential,UnitOfElectricCurrent,UnitOfPower,UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

FIXED=[
('wr_u_l1','KACO Netzspannung L1',('wr','U Verbund L1'),UnitOfElectricPotential.VOLT,'voltage'),('wr_u_l2','KACO Netzspannung L2',('wr','U Verbund L2'),UnitOfElectricPotential.VOLT,'voltage'),('wr_u_l3','KACO Netzspannung L3',('wr','U Verbund L3'),UnitOfElectricPotential.VOLT,'voltage'),
('wr_i_l1','KACO Netzstrom L1',('wr','I Verbund L1'),UnitOfElectricCurrent.AMPERE,'current'),('wr_i_l2','KACO Netzstrom L2',('wr','I Verbund L2'),UnitOfElectricCurrent.AMPERE,'current'),('wr_i_l3','KACO Netzstrom L3',('wr','I Verbund L3'),UnitOfElectricCurrent.AMPERE,'current'),
('wr_island_u_l1','KACO Inselspannung L1',('wr','U Insel L1'),UnitOfElectricPotential.VOLT,'voltage'),('wr_island_u_l2','KACO Inselspannung L2',('wr','U Insel L2'),UnitOfElectricPotential.VOLT,'voltage'),('wr_island_u_l3','KACO Inselspannung L3',('wr','U Insel L3'),UnitOfElectricPotential.VOLT,'voltage'),
('wr_island_i_l1','KACO Inselstrom L1',('wr','I Insel L1'),UnitOfElectricCurrent.AMPERE,'current'),('wr_island_i_l2','KACO Inselstrom L2',('wr','I Insel L2'),UnitOfElectricCurrent.AMPERE,'current'),('wr_island_i_l3','KACO Inselstrom L3',('wr','I Insel L3'),UnitOfElectricCurrent.AMPERE,'current'),
('wr_system_state','KACO System State',('wr','System State'),None,None),('wr_sk','KACO SK',('wr','SK'),None,None),('wr_ems_ctrl','KACO EMS Ctrl',('wr','EMS Ctrl'),None,None),('wr_flags1','KACO Betriebsflags 1',('wr','BetrFlags1'),None,None),('wr_flags2','KACO Betriebsflags 2',('wr','BetrFlags2'),None,None),('wr_pmb','KACO PMB',('wr','PMB'),None,None),
('meter_u_l1','VARTA Zähler Spannung L1',('emeter','U_V_L1'),UnitOfElectricPotential.VOLT,'voltage'),('meter_u_l2','VARTA Zähler Spannung L2',('emeter','U_V_L2'),UnitOfElectricPotential.VOLT,'voltage'),('meter_u_l3','VARTA Zähler Spannung L3',('emeter','U_V_L3'),UnitOfElectricPotential.VOLT,'voltage'),
('meter_i_l1','VARTA Zähler Netzstrom L1',('emeter','Iw_V_L1'),UnitOfElectricCurrent.AMPERE,'current'),('meter_i_l2','VARTA Zähler Netzstrom L2',('emeter','Iw_V_L2'),UnitOfElectricCurrent.AMPERE,'current'),('meter_i_l3','VARTA Zähler Netzstrom L3',('emeter','Iw_V_L3'),UnitOfElectricCurrent.AMPERE,'current'),
('meter_pv_i_l1','VARTA Zähler PV-Strom L1',('emeter','Iw_PV_L1'),UnitOfElectricCurrent.AMPERE,'current'),('meter_pv_i_l2','VARTA Zähler PV-Strom L2',('emeter','Iw_PV_L2'),UnitOfElectricCurrent.AMPERE,'current'),('meter_pv_i_l3','VARTA Zähler PV-Strom L3',('emeter','Iw_PV_L3'),UnitOfElectricCurrent.AMPERE,'current'),
('grid_ac_dc','Energie Netz AC→DC',('energy','EGrid_AC_DC'),UnitOfEnergy.WATT_HOUR,'energy'),('grid_dc_ac','Energie Netz DC→AC',('energy','EGrid_DC_AC'),UnitOfEnergy.WATT_HOUR,'energy'),('wr_ac_dc','Energie WR AC→DC',('energy','EWr_AC_DC'),UnitOfEnergy.WATT_HOUR,'energy'),
]
class VartaSensor(CoordinatorEntity,SensorEntity):
    def __init__(self,c,uid,name,path,unit,device_class):
        super().__init__(c); self._attr_unique_id='varta_'+uid; self._attr_name=name; self.path=path; self._attr_native_unit_of_measurement=unit; self._attr_device_class=device_class
    @property
    def native_value(self):
        d=self.coordinator.data
        for p in self.path:
            if not isinstance(d,dict): return None
            d=d.get(p)
        return d
    @property
    def device_info(self):
        i=self.coordinator.data.get('info',{}); return {'identifiers':{(DOMAIN,str(i.get('Device_Serial','varta')))},'name':'VARTA Energiespeicher','manufacturer':'VARTA Storage','serial_number':str(i.get('Device_Serial',''))}
class SunSpecSensor(VartaSensor):
    @property
    def native_value(self):
        inv=(self.coordinator.data.get('sunspec',{}).get('data',{}).get('Inverters') or [{}])[0]; return inv.get(self.path[-1])
async def async_setup_entry(hass,entry,async_add_entities):
    c=hass.data[DOMAIN][entry.entry_id]; ents=[VartaSensor(c,*x) for x in FIXED]
    for key,name,unit,dc in [('WAct','KACO aktuelle Leistung',UnitOfPower.WATT,'power'),('WMax','KACO maximale Leistung',UnitOfPower.WATT,'power')]: ents.append(SunSpecSensor(c,'sunspec_'+key.lower(),name,('sunspec',key),unit,dc))
    data=c.data.get('sunspec',{}).get('data',{}); ents += [VartaSensor(c,'wmax_total','SunSpec Gesamtleistung Maximum',('sunspec','data','WMaxTotal'),UnitOfPower.WATT,'power'),VartaSensor(c,'wmax_lim_pct','SunSpec Leistungsbegrenzung',('sunspec','data','WMaxLimPct'),'%',None)]
    async_add_entities(ents)
