"""Anwesenheit: Spezifikation."""
from __future__ import annotations

from .framework import Field, Spec

DOMAIN = "anwesenheit"
TITLE = "Anwesenheit"
PREFIX = "anwesenheit"
VERSION = "1.0.0"
DESCRIPTION = "„Ich gehe / Ich bin da“: Licht, Heizung und Kamera-Push nach Anwesenheit."
DASHBOARD_PATH = "dashboard-anwesenheit"

# (Schlüssel, Name, Entität)
LIGHTS = [
    ("wohnzimmer", "Wohnzimmer", "light.wohnzimmer"),
    ("ecke", "Wohnzimmer Ecke", "light.wohnzimmer_ecke"),
    ("sofa", "Sofa", "light.kiste"),
    ("esszimmer", "Esszimmer", "light.smart_ceiling_light"),
    ("tv", "TvLicht", "light.schlaflicht"),
    ("h618c", "H618C", "light.wohnzimmer_h618c"),
    ("flur", "Flurlicht", "switch.flurlicht_steckdose_1"),
]
LIGHT_DEFAULT_KOMMEN = {"wohnzimmer"}
# (Schlüssel, Name, Klima-Entität)
ROOMS = [
    ("wohnzimmer", "Wohnzimmer", "climate.wohnzimmer"),
    ("bad", "Bad", "climate.badezimmer"),
]
# (Name, Bewegungssensor, Kamera)
CAMS = {
    "keller": ("Keller", "binary_sensor.kamera_bewegung", "camera.kamera_mainstream"),
    "flur": ("Flur", "binary_sensor.flur_bewegung", "camera.flur"),
    "buero": ("Büro", "binary_sensor.buero_bewegung", "camera.buero"),
}
PRESENT = ("home", "unknown", "unavailable")
WER = ["Person 1 und Person 2", "Nur Person 1", "Nur Person 2", "Nur manuell"]

FIELDS = [
    Field("notify_person1", "mobile_app_mein_handy", "text", "Notify-Dienst Person 1"),
    Field("notify_person2", "mobile_app_partner_handy", "text", "Notify-Dienst Person 2"),
    Field("person_person1", "person.person1", "entity", "Person Person 1", ("person",)),
    Field("person_person2", "person.person2", "entity", "Person Person 2", ("person",)),
    Field("lock", "lock.haustuer", "entity", "Haustür-Schloss (für Warnung)", ("lock",)),
    Field("drucker", "binary_sensor.drucker_druckt", "entity", "Drucker druckt (für Warnung)", ("binary_sensor",)),
    Field("sonne", "sun.sun", "entity", "Sonne", ("sun",)),
]


def _present(rt, who: str) -> bool:
    return (rt.state(rt.cfg(f"person_{who}")) or "unavailable") in PRESENT


def jemand_da(rt) -> bool:
    ch, di = _present(rt, "person1"), _present(rt, "person2")
    wer = rt.get("anwesenheit_wer")
    if wer == "Person 1 und Person 2":
        return ch or di
    if wer == "Nur Person 1":
        return ch
    if wer == "Nur Person 2":
        return di
    return False


def niemand_da(rt) -> bool:
    return rt.get("anwesenheit_wer") != "Nur manuell" and not jemand_da(rt)


def anzeige(rt) -> str:
    names = [n for n, w in (("Person 1", "person1"), ("Person 2", "person2")) if _present(rt, w)]
    return ("Zuhause: " + " und ".join(names)) if names else "Niemand da"


def anzahl(rt) -> int:
    return int(_present(rt, "person1")) + int(_present(rt, "person2"))


SPECS = [
    Spec("select", "anwesenheit_modus", "Modus", "mdi:home-account", options=["Zuhause", "Niemand da"], default="Zuhause"),
    Spec("select", "anwesenheit_wer", "Wer zählt?", "mdi:account-multiple-check", options=WER, default=WER[0]),
    Spec("number", "anwesenheit_verzoegerung", "Erst umschalten nach", "mdi:timer-sand", 5, 1, 30, 1, "min", "slider"),
    Spec("number", "anwesenheit_helligkeit", "Helligkeit beim Kommen", "mdi:brightness-6", 60, 10, 100, 5, "%", "slider"),
    Spec("switch", "anwesenheit_nur_dunkel", "Beim Kommen Licht nur, wenn es dunkel ist", "mdi:weather-night", True),
    Spec("switch", "anwesenheit_heizung_aktiv", "Heizung steuern", "mdi:radiator", True),
    Spec("switch", "anwesenheit_heizung_wiederherstellen", "Beim Kommen vorherige Temperatur wiederherstellen", "mdi:restore", True),
    Spec("switch", "anwesenheit_kamera_push", "Bewegung Keller: Push mit Bild", "mdi:cctv", True),
    Spec("switch", "anwesenheit_kamera_weitere", "Flur- und Bürokamera auch", "mdi:cctv", False),
    Spec("switch", "anwesenheit_warn_haustuer", "Beim Gehen warnen, wenn Haustür offen", "mdi:door-open", True),
    Spec("switch", "anwesenheit_warn_drucker", "Beim Gehen warnen, wenn Drucker druckt", "mdi:printer-3d", True),
    Spec("switch", "anwesenheit_ziel_person1", "Push an Person 1", "mdi:cellphone-message", True),
    Spec("switch", "anwesenheit_ziel_person2", "Push an Person 2", "mdi:cellphone-message", False),
]
for _k, _n, _e in LIGHTS:
    SPECS.append(Spec("switch", f"anwesenheit_licht_{_k}_gehen", f"{_n}: beim Gehen aus", "mdi:lightbulb-off-outline", True))
    SPECS.append(Spec("switch", f"anwesenheit_licht_{_k}_kommen", f"{_n}: beim Kommen an", "mdi:lightbulb-on-outline", _k in LIGHT_DEFAULT_KOMMEN))
for _k, _n, _e in ROOMS:
    SPECS.append(Spec("number", f"anwesenheit_heizung_{_k}_weg", f"{_n}: Temperatur, wenn niemand da", "mdi:thermometer-minus", 14, 8, 28, 0.5, "°C", "box"))
    SPECS.append(Spec("number", f"anwesenheit_heizung_{_k}_da", f"{_n}: Temperatur, wenn jemand da", "mdi:thermometer-plus", 20, 8, 28, 0.5, "°C", "box"))
    SPECS.append(Spec("number", f"anwesenheit_heizung_{_k}_gemerkt", f"{_n}: gemerkte Temperatur", "mdi:content-save", 0, 0, 28, 0.5, "°C", "box"))
SPECS += [
    Spec("sensor", "anwesenheit_anzeige", "Anwesenheit Anzeige", "mdi:home-account", fn=anzeige),
    Spec("sensor", "anwesenheit_anzahl_zuhause", "Anwesenheit Anzahl zuhause", "mdi:account-multiple", fn=anzahl),
    Spec("binary_sensor", "anwesenheit_jemand_da", "Anwesenheit Jemand da", "mdi:home-account", fn=jemand_da),
    Spec("binary_sensor", "anwesenheit_niemand_da", "Anwesenheit Niemand da", "mdi:home-off", fn=niemand_da),
    Spec("button", "anwesenheit_ich_gehe", "Ich gehe", "mdi:door-exit", press="gehen"),
    Spec("button", "anwesenheit_ich_gehe_erzwingen", "Trotzdem alles aus", "mdi:door-exit", press="gehen_erzwingen"),
    Spec("button", "anwesenheit_ich_bin_da", "Ich bin da", "mdi:home", press="kommen"),
    Spec("button", "anwesenheit_testlauf", "Testlauf (nur melden)", "mdi:test-tube", press="test"),
    Spec("button", "anwesenheit_standardwerte", "Standardwerte setzen", "mdi:restore", press="reset"),
]

SECTIONS = [
    ("Status", ["anwesenheit_anzeige", "anwesenheit_anzahl_zuhause", "anwesenheit_modus", "anwesenheit_wer", "anwesenheit_verzoegerung"]),
    ("Szenen", ["anwesenheit_ich_gehe", "anwesenheit_ich_gehe_erzwingen", "anwesenheit_ich_bin_da", "anwesenheit_testlauf"]),
    ("Licht beim Gehen", [f"anwesenheit_licht_{k}_gehen" for k, _, _ in LIGHTS]),
    ("Licht beim Kommen", ["anwesenheit_nur_dunkel", "anwesenheit_helligkeit"] + [f"anwesenheit_licht_{k}_kommen" for k, _, _ in LIGHTS]),
    ("Heizung", ["anwesenheit_heizung_aktiv", "anwesenheit_heizung_wiederherstellen"] + [f"anwesenheit_heizung_{k}_{s}" for k, _, _ in ROOMS for s in ("weg", "da", "gemerkt")]),
    ("Kamera und Warnungen", ["anwesenheit_kamera_push", "anwesenheit_kamera_weitere", "anwesenheit_warn_haustuer", "anwesenheit_warn_drucker"]),
    ("Meldungen", ["anwesenheit_ziel_person1", "anwesenheit_ziel_person2", "anwesenheit_standardwerte"]),
]
