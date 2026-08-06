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
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw, 0)
    except Exception:
        pass
    try:
        return float(raw)
    except Exception:
        return raw.strip('"')


def _parse_js(text: str) -> dict:
    """Parse VARTA's simple JavaScript/parameter assignments."""
    out = {}
    pattern = r'(?ms)^\s*(?:var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?);\s*(?=\n|$)'
    for match in re.finditer(pattern, text or ""):
        out[match.group(1)] = _decode_value(match.group(2))
    return out


def _map_array(names, vals):
    if not isinstance(names, list) or not isinstance(vals, list):
        return {}
    return {str(name): vals[i] if i < len(vals) else None for i, name in enumerate(names)}


class VartaClient:
    def __init__(self, session: ClientSession, host: str, username: str, password: str):
        self.session = session
        self.host = host.strip().rstrip('/')
        self.username = username
        self.password = password
        if not self.host.startswith(('http://', 'https://')):
            self.host = 'http://' + self.host
        self._session_id: str | None = None

    async def login(self):
        """Login and explicitly retain the WebIF cookie.

        Home Assistant's shared aiohttp cookie jar may reject cookies set by a
        literal IP address. Therefore the VARTA session id is captured from the
        response and sent explicitly on subsequent requests.
        """
        async with self.session.post(
            f"{self.host}/cgi/login",
            params={"user": self.username, "password": self.password},
            timeout=ClientTimeout(total=8),
        ) as response:
            if response.status != 200:
                self._session_id = None
                raise VartaAuthError(f"VARTA login failed: HTTP {response.status}")
            await response.read()
            cookie = response.cookies.get('webif.session.id')
            if cookie is None or not cookie.value:
                self._session_id = None
                raise VartaAuthError("VARTA login returned no session cookie")
            self._session_id = cookie.value

    def _headers(self) -> dict[str, str]:
        if not self._session_id:
            return {}
        return {'Cookie': f'webif.session.id={self._session_id}'}

    async def _get(self, path: str, optional: bool = False) -> str | None:
        if not self._session_id:
            await self.login()
        for attempt in range(2):
            async with self.session.get(
                f"{self.host}{path}",
                headers=self._headers(),
                timeout=ClientTimeout(total=8),
            ) as response:
                if response.status == 401 and attempt == 0:
                    self._session_id = None
                    await self.login()
                    continue
                if response.status != 200:
                    if optional:
                        return None
                    if response.status == 401:
                        raise VartaAuthError("VARTA session/login rejected")
                    raise VartaApiError(f"{path}: HTTP {response.status}")
                return await response.text()
        return None

    async def _optional_js(self, path: str) -> dict:
        try:
            text = await self._get(path, optional=True)
            return _parse_js(text) if text else {}
        except Exception:
            return {}

    async def read_all(self) -> dict:
        info = _parse_js(await self._get('/cgi/info.js'))
        conf = _parse_js(await self._get('/cgi/ems_conf.js'))
        ems = _parse_js(await self._get('/cgi/ems_data.js'))
        energy = await self._optional_js('/cgi/energy.js')
        errors = await self._optional_js('/cgi/error.js')
        service = await self._optional_js('/cgi/user_serv.js')
        params = await self._optional_js('/cgi/param')

        smtxt = await self._get('/cgi/functionSM', optional=True)
        try:
            sunspec = json.loads(smtxt) if smtxt else {}
        except Exception:
            sunspec = {}

        result = {
            'info': info,
            'ems': ems,
            'energy': energy,
            'errors': errors,
            'service': service,
            'params': params,
            'sunspec': sunspec,
        }

        aliases = {
            'wr': ('WR_Conf', 'WR_Data'),
            'emeter': ('EMeter_Conf', 'EMETER_Data'),
            'ens': ('ENS_Conf', 'ENS_Data'),
            'na': ('NA_Conf', 'NA_Data'),
        }
        for dest, (conf_key, data_key) in aliases.items():
            result[dest] = _map_array(conf.get(conf_key), ems.get(data_key))

        charger_names = conf.get('Charger_Conf') or []
        batt_names = conf.get('Batt_Conf') or []
        module_names = conf.get('Modul_Conf') or conf.get('Module_Conf') or []
        chargers = []
        raw_chargers = ems.get('Charger_Data') or []
        if isinstance(raw_chargers, list):
            for index, raw in enumerate(raw_chargers):
                charger = _map_array(charger_names, raw)
                charger['_index'] = index
                batt_raw = charger.get('BattData')
                if isinstance(batt_raw, list):
                    batt = _map_array(batt_names, batt_raw)
                    modules = []
                    module_raw = batt.get('ModulData')
                    if isinstance(module_raw, list):
                        for module_index, module in enumerate(module_raw):
                            mapped = _map_array(module_names, module)
                            mapped['_index'] = module_index
                            modules.append(mapped)
                    batt['modules'] = modules
                    charger['battery'] = batt
                chargers.append(charger)
        result['chargers'] = chargers

        invs = sunspec.get('data', {}).get('Inverters') or []
        inv = invs[0] if invs else {}
        cycles = energy.get('Chrg_LoadCycles')
        result['summary'] = {
            'device_serial': info.get('Device_Serial'),
            'ems_max_power': info.get('P_EMS_Max'),
            'ems_max_discharge_power': info.get('P_EMS_MaxDisc'),
            'charger_count': info.get('Anz_Charger'),
            'kaco_connected': inv.get('connected'),
            'kaco_active_power': inv.get('WAct'),
            'kaco_max_power': inv.get('WMax'),
            'kaco_power_limit': sunspec.get('data', {}).get('WMaxLimPct'),
            'charge_cycles': (cycles or [None])[0] if isinstance(cycles, list) else cycles,
            'active_errors': len(errors.get('ErrorList') or []),
        }
        return result
