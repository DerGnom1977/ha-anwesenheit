"""Anwesenheit: Fachlogik (Port von anwesenheit.yaml)."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import Event, ServiceCall

from .const import CAMS, DOMAIN, LIGHTS, ROOMS, jemand_da, niemand_da
from .framework import LogicBase

_LOGGER = logging.getLogger(__name__)
URL = "/dashboard-anwesenheit/anwesenheit"


class Logic(LogicBase):
    def __init__(self, rt) -> None:
        super().__init__(rt)
        self._timers: dict[str, object] = {}
        self._cam_busy = False
        rt.actions.update(
            gehen=lambda: self.gehen(False, False),
            gehen_erzwingen=lambda: self.gehen(True, False),
            kommen=lambda: self.kommen(False),
            test=self.testlauf,
            reset=self._reset,
        )

    async def _reset(self) -> None:
        self.rt.reset_defaults()

    async def async_start(self) -> None:
        rt = self.rt
        persons = [rt.cfg("person_person1"), rt.cfg("person_person2")]
        rt.track_state(persons, self._person_changed)
        rt.track_state(persons + [rt.cfg("sonne")], rt.refresh)
        rt.track_state([c[1] for c in CAMS.values()], self._motion)

        async def _gehen(call: ServiceCall) -> None:
            await self.gehen(call.data.get("erzwingen", False), call.data.get("test", False))

        async def _kommen(call: ServiceCall) -> None:
            await self.kommen(call.data.get("test", False))

        opt = {vol.Optional("erzwingen"): bool, vol.Optional("test"): bool}
        rt.register_service("gehen", _gehen, vol.Schema(opt))
        rt.register_service("kommen", _kommen, vol.Schema({vol.Optional("test"): bool}))
        async def _test(call: ServiceCall) -> None:
            await self.testlauf()

        rt.register_service("testlauf", _test)

    # -- Auslöser -----------------------------------------------------------
    async def _person_changed(self, event: Event) -> None:
        rt = self.rt
        eid = event.data["entity_id"]
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if new is None:
            return
        unsub = self._timers.pop(eid, None)
        if unsub:
            unsub()  # type: ignore[operator]
        if old is not None and old.state == "home" and new.state != "home":
            minuten = int(rt.flt("anwesenheit_verzoegerung", 5))

            async def _fire(_now, eid=eid) -> None:
                self._timers.pop(eid, None)
                if rt.state(eid) == "home":
                    return
                if rt.get("anwesenheit_modus") == "Zuhause":
                    if niemand_da(rt):
                        await self.gehen(True, False)

            self._timers[eid] = rt.later(minuten * 60, _fire)
        elif new.state == "home":
            if rt.get("anwesenheit_modus") == "Niemand da" and jemand_da(rt):
                await self.kommen(False)

    async def _motion(self, event: Event) -> None:
        rt = self.rt
        new = event.data.get("new_state")
        if new is None or new.state != "on" or self._cam_busy:
            return
        eid = event.data["entity_id"]
        key = next((k for k, c in CAMS.items() if c[1] == eid), None)
        if key is None:
            return
        if rt.get("anwesenheit_modus") != "Niemand da" or not rt.on("anwesenheit_kamera_push"):
            return
        if key != "keller" and not rt.on("anwesenheit_kamera_weitere"):
            return
        self._cam_busy = True
        rt.spawn(self._push_kamera(key))

    async def _push_kamera(self, key: str) -> None:
        rt = self.rt
        ort, _, kamera = CAMS[key]
        try:
            await rt.notify(
                f"🎥 Bewegung: {ort}",
                "Es wurde Bewegung erkannt, während niemand zuhause ist.",
                {
                    "entity_id": kamera,
                    "tag": "anwesenheit_kamera",
                    "url": "/dashboard-kamera",
                    "push": {"interruption-level": "time-sensitive"},
                },
            )
            await asyncio.sleep(300)
        finally:
            self._cam_busy = False

    # -- Meldung ------------------------------------------------------------
    async def melden(self, titel: str, nachricht: str, stufe: str = "active") -> None:
        await self.rt.notify(
            titel,
            nachricht,
            {"tag": "anwesenheit", "url": URL, "push": {"interruption-level": stufe}},
        )

    # -- Szenen -------------------------------------------------------------
    async def gehen(self, erzwingen: bool, test: bool) -> None:
        rt = self.rt
        from .const import anzahl

        if not erzwingen and anzahl(rt) > 1:
            await self.melden(
                "🚪 Nichts geändert",
                "Es ist noch jemand zuhause. Mit „Trotzdem alles aus“ erzwingst du die Szene.",
            )
            return
        vorher = rt.get("anwesenheit_modus")
        an = []
        for k, name, eid in LIGHTS:
            if rt.on(f"anwesenheit_licht_{k}_gehen") and rt.is_state(eid, "on"):
                an.append((name, eid))
        heizung = ""
        if rt.on("anwesenheit_heizung_aktiv"):
            heizung = ", ".join(
                f"{n} {rt.flt(f'anwesenheit_heizung_{k}_weg', 14)} °C" for k, n, _ in ROOMS
            )
        warnung = []
        if rt.on("anwesenheit_warn_haustuer") and not rt.is_state(rt.cfg("lock"), "locked"):
            warnung.append("Die Haustür ist nicht abgeschlossen.")
        if rt.on("anwesenheit_warn_drucker") and rt.is_state(rt.cfg("drucker"), "on"):
            warnung.append("Der Drucker druckt noch.")
        if not test:
            rt.set("anwesenheit_modus", "Niemand da")
            for _, eid in an:
                await rt.call(eid.split(".")[0], "turn_off", {"entity_id": eid})
            if rt.on("anwesenheit_heizung_aktiv"):
                for k, _, clim in ROOMS:
                    temp = rt.attr(clim, "temperature")
                    if isinstance(temp, (int, float)) and rt.state(clim) == "heat":
                        if vorher == "Zuhause":
                            rt.set(f"anwesenheit_heizung_{k}_gemerkt", float(temp))
                        await rt.call(
                            "climate",
                            "set_temperature",
                            {"entity_id": clim, "temperature": rt.flt(f"anwesenheit_heizung_{k}_weg", 14)},
                        )
        liste = ", ".join(n for n, _ in an) or "kein Licht an"
        text = ("Würde ausschalten: " if test else "Aus: ") + liste + ". "
        if heizung:
            text += f"Heizung: {heizung}. "
        text += "Die Kamera würde scharf geschaltet." if test else "Kamera ist scharf."
        if warnung:
            text += " " + " ".join(warnung)
        await self.melden(
            "🧪 Testlauf: Ich gehe" if test else "🚪 Alle weg",
            text,
            "time-sensitive" if warnung else "active",
        )

    async def kommen(self, test: bool) -> None:
        rt = self.rt
        vorher = rt.get("anwesenheit_modus")
        dunkel_ok = (not rt.on("anwesenheit_nur_dunkel")) or rt.is_state(rt.cfg("sonne"), "below_horizon")
        an = [(k, n, e) for k, n, e in LIGHTS if rt.on(f"anwesenheit_licht_{k}_kommen") and dunkel_ok]

        def ziel(k: str) -> float:
            gemerkt = rt.flt(f"anwesenheit_heizung_{k}_gemerkt", 0)
            if rt.on("anwesenheit_heizung_wiederherstellen") and gemerkt >= 8:
                return gemerkt
            return rt.flt(f"anwesenheit_heizung_{k}_da", 20)

        heizung = ""
        if rt.on("anwesenheit_heizung_aktiv") and vorher == "Niemand da":
            heizung = ", ".join(f"{n} {ziel(k)} °C" for k, n, _ in ROOMS)
        if not test:
            rt.set("anwesenheit_modus", "Zuhause")
            if rt.on("anwesenheit_heizung_aktiv") and vorher == "Niemand da":
                for k, _, clim in ROOMS:
                    if rt.state(clim) == "heat":
                        await rt.call("climate", "set_temperature", {"entity_id": clim, "temperature": ziel(k)})
            for _, _, eid in an:
                dom = eid.split(".")[0]
                data: dict = {"entity_id": eid}
                if dom == "light":
                    data["brightness_pct"] = int(rt.flt("anwesenheit_helligkeit", 60))
                await rt.call(dom, "turn_on", data)
        liste = ", ".join(n for _, n, _ in an) or "kein Licht"
        text = ("Würde einschalten: " if test else "An: ") + liste + ". "
        if heizung:
            text += f"Heizung: {heizung}. "
        text += "Die Kamera würde ausgeschaltet." if test else "Kamera ist aus."
        await self.melden("🧪 Testlauf: Ich bin da" if test else "🏠 Willkommen zuhause", text)

    async def testlauf(self) -> None:
        await self.gehen(True, True)
        await self.kommen(True)
