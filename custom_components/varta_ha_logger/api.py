"""Read-only local HTTP client for the VARTA WebIF."""
from __future__ import annotations

import ast
import json
import re
from aiohttp import ClientSession, ClientTimeout


class VartaApiError(Exception):
    pass


class VartaAuthError(VartaApiError):
    pass


def _decode_value(raw: str):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    try:
        return ast.literal_eval(raw)
    except Exception:
        pass
    if raw.lower() == "true": return True
    if raw.lower() == "false": return False
    try: return int(raw, 0)
    except Exception: pass
    try: return float(raw)
    except Exception: return raw.strip('"')


def _parse_js(text: str) -> dict:
    out = {}
    for statement in (text or "").split(';'):
        statement = statement.strip()
        if not statement: continue
        match = re.match(r'^(?:var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', statement, flags=re.S)
        if match: out[match.group(1)] = _decode_value(match.group(2))
    return out


def _map_array(names, vals):
    if not isinstance(names, list) or not isinstance(vals, list): return {}
    return {str(name): vals[i] if i < len(vals) else None for i, name in enumerate(names)}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _varta_three_phase_power(data: dict, voltage_prefix: str, current_prefix: str):
    """VARTA WebIF formula: sum(U_phase * I_phase) / 100."""
    terms = []
    for phase in ('L1', 'L2', 'L3'):
        voltage = _number(data.get(f'{voltage_prefix}{phase}'))
        current = _number(data.get(f'{current_prefix}{phase}'))
        if voltage is None or current is None:
            return None
        terms.append(voltage * current)
    return round(sum(terms) / 100)


def _weighted_soc(chargers: list[dict]):
    """Replicate ChargerUtils.calculateSoCFromData for known battery types."""
    weighted = 0.0
    weight_total = 0.0
    for charger in chargers:
        soc = _number(charger.get('SOC_GS'))
        battery = charger.get('battery') or {}
        if soc is None:
            soc = _number(battery.get('SOC_RACK'))
        if soc is None:
            continue
        battery_type = battery.get('Type')
        weight = 3 if battery_type == 5 else 6 if battery_type == 7 else 1
        weighted += soc * weight
        weight_total += weight
    return round(weighted / weight_total) if weight_total else None


class VartaClient:
    def __init__(self, session: ClientSession, host: str, username: str, password: str):
        self.session=session; self.host=host.strip().rstrip('/'); self.username=username; self.password=password
        if not self.host.startswith(('http://','https://')): self.host='http://'+self.host
        self._session_id=None

    async def login(self):
        async with self.session.post(f"{self.host}/cgi/login", params={"user":self.username,"password":self.password}, timeout=ClientTimeout(total=8)) as response:
            if response.status != 200:
                self._session_id=None; raise VartaAuthError(f"VARTA login failed: HTTP {response.status}")
            await response.read(); cookie=response.cookies.get('webif.session.id')
            if cookie is None or not cookie.value:
                self._session_id=None; raise VartaAuthError("VARTA login returned no session cookie")
            self._session_id=cookie.value

    def _headers(self):
        return {'Cookie':f'webif.session.id={self._session_id}'} if self._session_id else {}

    async def _get(self,path,optional=False):
        if not self._session_id: await self.login()
        for attempt in range(2):
            async with self.session.get(f"{self.host}{path}",headers=self._headers(),timeout=ClientTimeout(total=8)) as response:
                if response.status==401 and attempt==0:
                    self._session_id=None; await self.login(); continue
                if response.status!=200:
                    if optional:return None
                    if response.status==401:raise VartaAuthError("VARTA session/login rejected")
                    raise VartaApiError(f"{path}: HTTP {response.status}")
                return await response.text()
        return None

    async def _optional_js(self,path):
        try:
            text=await self._get(path,optional=True); return _parse_js(text) if text else {}
        except Exception:return {}

    async def read_all(self):
        info=_parse_js(await self._get('/cgi/info.js')); conf=_parse_js(await self._get('/cgi/ems_conf.js')); ems=_parse_js(await self._get('/cgi/ems_data.js'))
        energy=await self._optional_js('/cgi/energy.js'); errors=await self._optional_js('/cgi/error.js'); service=await self._optional_js('/cgi/user_serv.js'); params=await self._optional_js('/cgi/param')
        smtxt=await self._get('/cgi/functionSM',optional=True)
        try:sunspec=json.loads(smtxt) if smtxt else {}
        except Exception:sunspec={}
        result={'info':info,'ems':ems,'energy':energy,'errors':errors,'service':service,'params':params,'sunspec':sunspec}
        aliases={'wr':('WR_Conf','WR_Data'),'emeter':('EMeter_Conf','EMETER_Data'),'ens':('ENS_Conf','ENS_Data'),'na':('NA_Conf','NA_Data')}
        for dest,(ck,dk) in aliases.items():result[dest]=_map_array(conf.get(ck),ems.get(dk))

        charger_names=conf.get('Charger_Conf') or []; batt_names=conf.get('Batt_Conf') or []; module_names=conf.get('Modul_Conf') or conf.get('Module_Conf') or []
        chargers=[]
        for index,raw in enumerate(ems.get('Charger_Data') or []):
            charger=_map_array(charger_names,raw); charger['_index']=index; batt_raw=charger.get('BattData')
            if isinstance(batt_raw,list):
                batt=_map_array(batt_names,batt_raw); modules=[]; module_raw=batt.get('ModulData')
                if isinstance(module_raw,list):
                    for mi,module in enumerate(module_raw):
                        mapped=_map_array(module_names,module); mapped['_index']=mi; modules.append(mapped)
                batt['modules']=modules; charger['battery']=batt
            chargers.append(charger)
        result['chargers']=chargers

        invs=sunspec.get('data',{}).get('Inverters') or []; inv=invs[0] if invs else {}; cycles=energy.get('Chrg_LoadCycles')

        # Reproduce the formulas used by the VARTA WebIF (U_chargers.js).
        # Element SX grid power: round(sum(U_V_Lx * Iw_V_Lx) / 100).
        grid_power = _varta_three_phase_power(result['emeter'], 'U_V_', 'Iw_V_')

        # Charge/discharge power: round(sum(U Insel Lx * I Insel Lx) / 100).
        charge_power = _varta_three_phase_power(result['wr'], 'U Insel ', 'I Insel ')

        # Production: PMB + PV meter contribution for Element SX.
        pmb = _number(result['wr'].get('PMB'))
        pv_meter_power = _varta_three_phase_power(result['emeter'], 'U_V_', 'Iw_PV_')
        production_power = None
        if pmb is not None:
            production_power = round(pmb + (pv_meter_power or 0))
        elif _number(inv.get('WAct')) is not None:
            production_power = round(inv.get('WAct'))

        # WebIF: calculateConsumptionPower(production, grid, charge)
        #        = max(production - grid - charge, 0)
        consumption = None
        if all(isinstance(v,(int,float)) for v in (production_power, grid_power, charge_power)):
            consumption = max(production_power - grid_power - charge_power, 0)

        # WebIF SOC weighting: battery type 5 => 3, type 7 => 6.
        soc = _weighted_soc(chargers)

        result['summary']={
            'device_serial':info.get('Device_Serial'),'ems_max_power':info.get('P_EMS_Max'),'ems_max_discharge_power':info.get('P_EMS_MaxDisc'),'charger_count':info.get('Anz_Charger'),
            'production_power':production_power,'house_consumption':consumption,'grid_power':grid_power,'battery_power':charge_power,'state_of_charge':soc,'pv_meter_power':pv_meter_power,
            'kaco_connected':inv.get('connected'),'kaco_active_power':_number(inv.get('WAct')),'kaco_max_power':inv.get('WMax'),'kaco_power_limit':sunspec.get('data',{}).get('WMaxLimPct'),
            'charge_cycles':(cycles or [None])[0] if isinstance(cycles,list) else cycles,'active_errors':len(errors.get('ErrorList') or []),
        }
        return result
