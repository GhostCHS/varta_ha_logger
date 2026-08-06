# VARTA HA Logger

Home Assistant Custom Integration für das lokale VARTA WebIF.

## Datenquelle
Die Integration greift ausschließlich per HTTP auf den VARTA Energiespeicher zu. Sie öffnet **keine eigene Modbus-Verbindung zum KACO-Wechselrichter**. KACO/SunSpec-Werte werden über die bereits vom VARTA bereitgestellten Daten gelesen.

Verwendete lokale Endpunkte: `cgi/info.js`, `cgi/ems_conf.js`, `cgi/ems_data.js`, `cgi/energy.js`, `cgi/functionSM`.

## Datenschutz / Speicherung
Die Integration implementiert **keinen eigenen Log- oder Historienspeicher**. Sie hält nur den jeweils aktuellen Polling-Datensatz im Home-Assistant-Coordinator. Ob Home Assistant Sensorzustände im Recorder speichert, wird separat durch die Home-Assistant-Recorder-Konfiguration bestimmt.

## Einrichtung
Als benutzerdefiniertes HACS-Repository hinzufügen, Home Assistant neu starten und unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → VARTA HA Logger** einrichten. Benötigt werden lokale IP/Hostname, Benutzername und Passwort des VARTA WebIF.

## Aktuell erkannte Daten
KACO Netz- und Inselspannungen/-ströme, System State, EMS Ctrl, Betriebsflags, PMB, KACO Online-Verbindung, aktuelle/maximale SunSpec-Leistung und Leistungsbegrenzung, VARTA Energy-Meter Spannungen/Ströme/PV-Ströme sowie die vom WebIF gelieferten Energiezähler.

Die Zuordnung der VARTA-Arrays wird anhand von `ems_conf.js` dynamisch eingelesen, sodass unbekannte Felder nicht fest in der HTTP-Schicht verdrahtet werden müssen.
