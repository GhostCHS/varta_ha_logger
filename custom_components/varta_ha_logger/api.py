"""Local HTTP client for the VARTA WebIF."""
from __future__ import annotations
import ast
import json
import re
from aiohttp import ClientSession, ClientTimeout

class VartaApiError(Exception): pass
class VartaAuthError(VartaApiError): pass

_ASSIGN_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*;\s*$', re.M | re.S)

def _parse_js(text: str) -> dict:
    out = {}
    # VARTA responses are simple JavaScript assignments. Parse each statement independently.
    for stmt in re.split(r';\s*(?:\r?\n|$)', text):
        stmt = stmt.strip()
        if not stmt: continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', stmt, re.S)
        if not m: continue
        key, raw = m.groups(); raw = raw.strip()
        try: out[key] = json.loads(raw)
        except Exception:
            try: out[key] = ast.literal_eval(raw)
            except Exception: out[key] = raw.strip('"')
    return out

class VartaClient:
    def __init__(self, session: ClientSession, host: str, username: str, password: str):
        self.session=session; self.host=host.strip().rstrip('/'); self.username=username; self.password=password
        if not self.host.startswith(('http://','https://')): self.host='http://'+self.host
        self._logged_in=False
    async def login(self):
        async with self.session.post(f"{self.host}/cgi/login", params={"user":self.username,"password":self.password}, timeout=ClientTimeout(total=8)) as r:
            if r.status != 200: raise VartaAuthError(f"VARTA login failed: HTTP {r.status}")
            await r.read(); self._logged_in=True
    async def _get(self, path: str) -> str:
        if not self._logged_in: await self.login()
        async with self.session.get(f"{self.host}{path}", timeout=ClientTimeout(total=8)) as r:
            if r.status == 401:
                self._logged_in=False; await self.login()
                async with self.session.get(f"{self.host}{path}", timeout=ClientTimeout(total=8)) as r2:
                    if r2.status != 200: raise VartaApiError(f"{path}: HTTP {r2.status}")
                    return await r2.text()
            if r.status != 200: raise VartaApiError(f"{path}: HTTP {r.status}")
            return await r.text()
    async def read_all(self) -> dict:
        info=_parse_js(await self._get('/cgi/info.js'))
        conf=_parse_js(await self._get('/cgi/ems_conf.js'))
        ems=_parse_js(await self._get('/cgi/ems_data.js'))
        energy=_parse_js(await self._get('/cgi/energy.js'))
        smtxt=await self._get('/cgi/functionSM')
        try: sunspec=json.loads(smtxt)
        except Exception: sunspec={}
        result={"info":info,"conf":conf,"ems":ems,"energy":energy,"sunspec":sunspec}
        # Dynamically map every configured VARTA array to names, preserving unknown/raw values too.
        for prefix in ('WR','EMeter','ENS','Batt','Charger'):
            names=conf.get(prefix+'_Conf') or conf.get(prefix.upper()+'_Conf')
            vals=ems.get(prefix+'_Data') or ems.get(prefix.upper()+'_Data')
            if isinstance(names,list) and isinstance(vals,list): result[prefix.lower()]={str(n): vals[i] if i<len(vals) else None for i,n in enumerate(names)}
        return result
