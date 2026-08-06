"""Local HTTP client for the VARTA WebIF.

Read-only: this integration never writes parameters to the VARTA or KACO.
"""
from __future__ import annotations
import ast
import json
import re
from aiohttp import ClientSession, ClientTimeout

class VartaApiError(Exception): pass
class VartaAuthError(VartaApiError): pass


def _parse_js(text: str) -> dict:
    """Parse the simple `Name = value;` JavaScript returned by VARTA."""
    out = {}
    # Match assignments non-greedily up to a semicolon. Arrays may span lines.
    for m in re.finditer(r'(?ms)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?);\s*(?=\n|$)', text):
        key, raw = m.group(1), m.group(2).strip()
        try:
            out[key] = json.loads(raw)
        except Exception:
            try:
                out[key] = ast.literal_eval(raw)
            except Exception:
                out[key] = raw.strip('"')
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
        self._logged_in = False

    async def login(self):
        async with self.session.post(
            f"{self.host}/cgi/login",
            params={"user": self.username, "password": self.password},
            timeout=ClientTimeout(total=8),
        ) as r:
            if r.status != 200:
                raise VartaAuthError(f"VARTA login failed: HTTP {r.status}")
            await r.read()
            self._logged_in = True

    async def _get(self, path: str, optional: bool = False) -> str | None:
        if not self._logged_in:
            await self.login()
        async with self.session.get(f"{self.host}{path}", timeout=ClientTimeout(total=8)) as r:
            if r.status == 401:
                self._logged_in = False
                await self.login()
                async with self.session.get(f"{self.host}{path}", timeout=ClientTimeout(total=8)) as r2:
                    if r2.status != 200:
                        if optional:
                            return None
                        raise VartaApiError(f"{path}: HTTP {r2.status}")
                    return await r2.text()
            if r.status != 200:
                if optional:
                    return None
                raise VartaApiError(f"{path}: HTTP {r.status}")
            return await r.text()

    async def _optional_js(self, path: str) -> dict:
        try:
            text = await self._get(path, optional=True)
            return _parse_js(text) if text else {}
        except Exception:
            return {}

    async def read_all(self) -> dict:
        # Core pages known to be used by the VARTA WebIF.
        info = _parse_js(await self._get('/cgi/info.js'))
        conf = _parse_js(await self._get('/cgi/ems_conf.js'))
        ems = _parse_js(await self._get('/cgi/ems_data.js'))

        # Additional read-only WebIF pages. Availability depends on firmware/user level.
        energy = await self._optional_js('/cgi/energy.js')
        errors = await self._optional_js('/cgi/error.js')
        user_serv = await self._optional_js('/cgi/user_serv.js')
        params = await self._optional_js('/cgi/param')

        smtxt = await self._get('/cgi/functionSM', optional=True)
        try:
            sunspec = json.loads(smtxt) if smtxt else {}
        except Exception:
            sunspec = {}

        result = {
            'info': info, 'conf': conf, 'ems': ems, 'energy': energy,
            'errors': errors, 'user_serv': user_serv, 'params': params,
            'sunspec': sunspec,
        }

        # Top-level arrays: map every firmware-provided field name to its value.
        aliases = {
            'wr': ('WR_Conf', 'WR_Data'),
            'emeter': ('EMeter_Conf', 'EMETER_Data'),
            'ens': ('ENS_Conf', 'ENS_Data'),
            'na': ('NA_Conf', 'NA_Data'),
        }
        for dest, (ckey, dkey) in aliases.items():
            result[dest] = _map_array(conf.get(ckey), ems.get(dkey))

        # Charger_Data is an array of chargers. Each charger can contain BattData,
        # which itself contains one or more battery modules.
        charger_names = conf.get('Charger_Conf') or []
        batt_names = conf.get('Batt_Conf') or []
        module_names = conf.get('Modul_Conf') or conf.get('Module_Conf') or []
        chargers = []
        raw_chargers = ems.get('Charger_Data') or []
        if isinstance(raw_chargers, list):
            for ci, charger_raw in enumerate(raw_chargers):
                charger = _map_array(charger_names, charger_raw)
                charger['_index'] = ci
                # BattData is normally the final nested array/object in Charger_Data.
                batt_raw = charger.get('BattData')
                if isinstance(batt_raw, list):
                    batt = _map_array(batt_names, batt_raw)
                    module_raw = batt.get('ModulData')
                    modules = []
                    if isinstance(module_raw, list):
                        for mi, mod in enumerate(module_raw):
                            mapped = _map_array(module_names, mod)
                            mapped['_index'] = mi
                            modules.append(mapped)
                    batt['modules'] = modules
                    charger['battery'] = batt
                chargers.append(charger)
        result['chargers'] = chargers
        return result
