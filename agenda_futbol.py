"""Agenda de fútbol con los datos públicos de ESPN (sin clave ni cuenta).

Consulta unas 15 direcciones (una por liga) y genera events.json con los
partidos de hoy y mañana (fechas de Santiago). Incluye:
  - 10 ligas principales + fútbol chileno
  - partidos de selecciones (amistosos, Nations League, etc.)

Uso:   python agenda_futbol.py      (necesita:  pip install requests)
"""
import datetime as dt
import json
import os
import re
import time
from collections import Counter
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("America/Santiago")
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
SALIDA = "events.json"
ING = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"  # bandera de Inglaterra

# (código ESPN, país o circuito, competición, bandera)
LIGAS = [
    ("eng.1", "Inglaterra", "Premier League", ING),
    ("esp.1", "España", "LaLiga", "🇪🇸"),
    ("ita.1", "Italia", "Serie A", "🇮🇹"),
    ("ger.1", "Alemania", "Bundesliga", "🇩🇪"),
    ("fra.1", "Francia", "Ligue 1", "🇫🇷"),
    ("ned.1", "Países Bajos", "Eredivisie", "🇳🇱"),
    ("por.1", "Portugal", "Primeira Liga", "🇵🇹"),
    ("bra.1", "Brasil", "Brasileirão", "🇧🇷"),
    ("arg.1", "Argentina", "Liga Profesional", "🇦🇷"),
    ("usa.1", "EE.UU.", "MLS", "🇺🇸"),
    ("chi.1", "Chile", "Primera División", "🇨🇱"),
    ("chi.2", "Chile", "Primera B", "🇨🇱"),
    ("fifa.friendly", "Selecciones", "Amistosos internacionales", "🌍"),
    ("uefa.nations", "Selecciones", "UEFA Nations League", "🌍"),
]
# Para completar selecciones desde el listado general de ESPN
NOTA_SELECCION = re.compile(
    r"Nations League|International Friendly|Qualif|Africa Cup|Asian Cup|Gold Cup|"
    r"European Championship|Copa Am|^World Cup", re.I)
NO_SELECCION = re.compile(r"Club|Women|Femen|Under|\bU-?\d{2}\b", re.I)
JUVENIL_O_FEMENINO = re.compile(r"\bU-?\d{2}\b|\bWomen\b| W$|\(W\)", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (agenda-deportiva)"}


def parse_fecha(s):
    s = s.replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        d = dt.datetime.strptime(s[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def estado(comp):
    t = comp.get("status", {}).get("type", {})
    name, state = t.get("name", ""), t.get("state")
    if "POSTPONED" in name:
        return "PST"
    if "CANCEL" in name:
        return "CANC"
    if "SUSPEND" in name or "ABANDON" in name:
        return "SUSP"
    if "HALFTIME" in name:
        return "HT"
    if state == "post":
        return "FT"
    if state == "in":
        return "2H" if "SECOND" in name else "1H"
    return "NS"


def minuto(comp):
    m = re.search(r"\d+", comp.get("status", {}).get("displayClock", "") or "")
    return int(m.group()) if m else None


def lado(comp, home_away, en_juego):
    c = next((x for x in comp["competitors"] if x.get("homeAway") == home_away), None)
    if c is None:
        c = comp["competitors"][0 if home_away == "home" else 1]
    team = c.get("team", {})
    gol = None
    if en_juego:
        try:
            gol = int(c.get("score"))
        except (TypeError, ValueError):
            gol = None
    return {"n": team.get("displayName") or team.get("name") or "?", "l": team.get("logo", ""), "g": gol}


def normalizar(ev, slug, pais, competicion, bandera):
    comp = ev["competitions"][0]
    est = estado(comp)
    jugado = est not in ("NS", "PST", "CANC")
    return {
        "id": int(ev["id"]),
        "ts": int(parse_fecha(ev["date"]).timestamp()),
        "st": est,
        "min": minuto(comp) if est in ("1H", "2H") else None,
        "h": lado(comp, "home", jugado),
        "a": lado(comp, "away", jugado),
        "lg": {"id": slug, "n": competicion, "c": pais, "f": bandera, "r": None},
    }


def pedir(slug, d0, d1, limite=300):
    """Devuelve (eventos, nota). Nunca lanza excepciones."""
    try:
        r = requests.get(f"{BASE}/{slug}/scoreboard", headers=HEADERS, timeout=30,
                         params={"dates": f"{d0:%Y%m%d}-{d1:%Y%m%d}", "limit": limite})
        if r.status_code == 404:
            return [], " (no existe)"
        r.raise_for_status()
        return r.json().get("events", []), ""
    except Exception as e:
        return [], f" (error: {type(e).__name__})"
    finally:
        time.sleep(0.4)


def nombre_seleccion(nota):
    base = nota.split(",")[0].strip()
    return {"Men's International Friendly": "Amistosos internacionales",
            "International Friendly": "Amistosos internacionales"}.get(base, base)


def main():
    hoy = dt.datetime.now(TZ).date()
    desde = dt.datetime.combine(hoy, dt.time.min, TZ)
    hasta = desde + dt.timedelta(days=2)  # hoy y mañana
    d0, d1 = hoy - dt.timedelta(days=1), hoy + dt.timedelta(days=2)  # margen por husos

    def en_ventana(ev):
        try:
            return desde <= parse_fecha(ev["date"]).astimezone(TZ) < hasta
        except (KeyError, ValueError):
            return False

    def valido(ev):
        nombres = [c.get("team", {}).get("displayName", "") for c in ev["competitions"][0]["competitors"]]
        return en_ventana(ev) and not any(JUVENIL_O_FEMENINO.search(n) for n in nombres)

    eventos, notas = {}, []
    for slug, pais, comp, bandera in LIGAS:
        evs, nota = pedir(slug, d0, d1)
        n = 0
        for ev in evs:
            if valido(ev) and int(ev["id"]) not in eventos:
                eventos[int(ev["id"])] = normalizar(ev, slug, pais, comp, bandera)
                n += 1
        notas.append(f"{slug}:{n}{nota}")

    # Listado general: solo para sumar partidos de selecciones que falten
    evs, nota = pedir("all", d0, d1, limite=1000)
    n = 0
    for ev in evs:
        texto = ev["competitions"][0].get("altGameNote", "") or ""
        if (valido(ev) and NOTA_SELECCION.search(texto) and not NO_SELECCION.search(texto)
                and int(ev["id"]) not in eventos):
            eventos[int(ev["id"])] = normalizar(ev, "all", "Selecciones", nombre_seleccion(texto), "🌍")
            n += 1
    notas.append(f"all(selecciones):{n}/{len(evs)}{nota}")

    lista = sorted(eventos.values(), key=lambda e: e["ts"])
    print(f"Partidos incluidos: {len(lista)}")
    for (pais, comp), n in sorted(Counter((e["lg"]["c"], e["lg"]["n"]) for e in lista).items(),
                                  key=lambda x: -x[1]):
        print(f"  {n:3d}  {pais} - {comp}")
    print("Detalle:", " | ".join(notas))

    if not lista and os.path.exists(SALIDA):
        try:
            if json.load(open(SALIDA, encoding="utf-8")).get("events"):
                print("Sin partidos nuevos: se conserva el archivo anterior.")
                return
        except (ValueError, OSError):
            pass
    salida = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "diag": " | ".join(notas), "events": lista}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"Listo: {SALIDA}")


if __name__ == "__main__":
    main()
