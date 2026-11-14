"""Agenda de fútbol de prueba con API-Football (plan gratis).

Consulta solo 2 fechas (hoy y mañana) y se queda con:
  - 10 ligas principales + fútbol chileno (Primera, Primera B, Copa Chile)
  - partidos de selecciones (amistosos, Nations League, clasificatorias...)

Genera:
  events.json        eventos normalizados (el formato que usaría la app)
  agenda_futbol.html página para ver el resultado (banderas y escudos)

En Google Colab:
    !python agenda_futbol.py
y se descarga solo el HTML (ábrelo en tu navegador).
"""
import datetime as dt
import json
import os
import re
import time
from collections import Counter
from zoneinfo import ZoneInfo

import requests

KEY = os.getenv("APISPORTS_KEY") or "86014b6bc41372355dc7e7348ac26c97"
BASE = "https://v3.football.api-sports.io"
TZ = "America/Santiago"  # las fechas consultadas son fechas locales de este huso

TOP_LIGAS = {
    39: "Premier League", 140: "LaLiga", 135: "Serie A", 78: "Bundesliga",
    61: "Ligue 1", 88: "Eredivisie", 94: "Primeira Liga", 71: "Brasileirão",
    128: "Liga Profesional Argentina", 253: "MLS", 265: "Primera División Chile",
    266: "Primera B Chile", 267: "Copa Chile",
}
JUVENIL_O_FEMENINO = re.compile(r"\bU\d{2}\b|\bWomen\b| W$")
TORNEOS_SELECCIONES = {"UEFA Euro Championship", "Copa America", "Africa Cup of Nations",
                       "Asian Cup", "CONCACAF Gold Cup"}


def es_seleccion(liga):
    n = liga["name"]
    if liga.get("country") != "World" or "Women" in n or re.search(r"\bU\d{2}\b", n):
        return False
    return (n == "Friendlies" or "Nations League" in n or "Qualification" in n
            or n.startswith("World Cup") or n in TORNEOS_SELECCIONES)


def incluir(f):
    l, t = f["league"], f["teams"]
    if JUVENIL_O_FEMENINO.search(t["home"]["name"]) or JUVENIL_O_FEMENINO.search(t["away"]["name"]):
        return False
    return l["id"] in TOP_LIGAS or es_seleccion(l)


def normalizar(f):
    l, t, g, s = f["league"], f["teams"], f["goals"], f["fixture"]["status"]
    return {
        "id": f["fixture"]["id"], "ts": f["fixture"]["timestamp"],
        "st": s["short"], "min": s.get("elapsed"),
        "h": {"n": t["home"]["name"], "l": t["home"]["logo"], "g": g["home"]},
        "a": {"n": t["away"]["name"], "l": t["away"]["logo"], "g": g["away"]},
        "lg": {"id": l["id"], "n": l["name"], "c": l["country"], "f": l.get("flag"),
               "r": l.get("round")},
    }


def pedir_fecha(fecha):
    """Devuelve (partidos, nota). No lanza excepciones: la nota explica qué pasó."""
    try:
        r = requests.get(f"{BASE}/fixtures", headers={"x-apisports-key": KEY}, timeout=30,
                         params={"date": fecha.isoformat(), "timezone": TZ})
        try:
            j = r.json()
        except ValueError:
            return [], f" (respuesta no válida, HTTP {r.status_code}: {r.text[:80]!r})"
        if j.get("errors"):
            return j.get("response", []), f" errors={j['errors']}"
        return j.get("response", []), ""
    except Exception as e:  # sin red, tiempo agotado, etc.
        return [], f" (fallo de conexión: {type(e).__name__})"


HTML = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Agenda de fútbol (datos reales)</title>
<style>
:root{--bg:#EFF2F5;--card:#fff;--ink:#131B26;--mute:#5B6776;--line:#D9DFE6;--accent:#0E7C7B;--on:#fff;--live:#D64045;--soonbg:#FFF1D6;--soon:#8A5200;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0F151C;--card:#18212B;--ink:#EAF0F6;--mute:#9AA7B6;--line:#263241;--accent:#3CC4BE;--on:#0F151C;--live:#FF6B70;--soonbg:#3A2D10;--soon:#F2B84B;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
.app{max-width:480px;margin:0 auto;padding:calc(20px + env(safe-area-inset-top,0px)) 16px calc(40px + env(safe-area-inset-bottom,0px))}
h1{font-size:2rem;line-height:1.05;margin:0;letter-spacing:-.02em}
.date,.tz{margin:4px 0 0;color:var(--mute);font-size:.9rem}
.days{display:flex;gap:8px;overflow-x:auto;margin:16px -16px 0;padding:2px 16px 6px}
.day{flex:0 0 auto;min-width:56px;padding:8px 6px;border:1px solid var(--line);border-radius:14px;background:var(--card);color:var(--ink);font:inherit;text-align:center;cursor:pointer}
.day b{display:block;font-size:1.25rem}.day span{font-size:.8rem;color:var(--mute)}
.day[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--on)}
.day[aria-pressed="true"] span{color:var(--on)}
.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:10px;margin-top:14px}
.filters label{display:block;font-size:.8rem;color:var(--mute);margin-bottom:3px}
select{width:100%;padding:10px 8px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit;font-size:.95rem}
.count{margin:18px 0 8px;font-size:.9rem;color:var(--mute)}
ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.ev{display:grid;grid-template-columns:58px 1fr auto;gap:12px;align-items:center;padding:12px;background:var(--card);border:1px solid var(--line);border-radius:16px}
.ev.done{opacity:.6}
.time{font-weight:800;font-size:1.4rem;letter-spacing:-.02em;line-height:1}
.comp{display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--mute);margin-bottom:2px}
.fg{width:18px;height:13px;object-fit:cover;border-radius:2px;flex:0 0 auto}
.tm{display:flex;align-items:center;gap:8px;margin:4px 0}
.tm .n{font-weight:600;flex:1;min-width:0}
.tm .g{font-size:1.05rem;min-width:1ch;text-align:right}
.cr{width:26px;height:26px;object-fit:contain;flex:0 0 auto}
.chip{display:inline-block;margin-top:4px;padding:2px 8px;border-radius:99px;font-size:.78rem;font-weight:600;background:var(--line);color:var(--mute)}
.chip.live{background:var(--live);color:#fff}.chip.soon{background:var(--soonbg);color:var(--soon)}
.bell{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);background:transparent;color:var(--mute);display:grid;place-items:center;cursor:pointer}
.bell[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--on)}
.bell svg{width:20px;height:20px}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.empty{padding:28px 16px;text-align:center;color:var(--mute);background:var(--card);border:1px dashed var(--line);border-radius:16px}
.foot{margin-top:26px;font-size:.85rem;color:var(--mute)}
.foot button{margin-top:10px;padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit;cursor:pointer}
#toast{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom,0px));transform:translate(-50%,20px);max-width:92vw;padding:12px 16px;border-radius:12px;background:var(--ink);color:var(--bg);opacity:0;pointer-events:none;transition:.25s}
#toast.on{opacity:1;transform:translate(-50%,0)}
</style></head><body>
<main class="app">
<h1>Agenda de fútbol</h1>
<p class="date" id="date"></p><p class="tz" id="tz"></p>
<div class="days" id="days" role="group" aria-label="Elegir día"></div>
<div class="filters">
<div><label for="fs">Deporte</label><select id="fs" disabled><option>Fútbol</option></select></div>
<div><label for="fr">País o circuito</label><select id="fr"></select></div>
<div><label for="fc">Competición</label><select id="fc"></select></div>
</div>
<p class="count" id="count" aria-live="polite"></p>
<ul id="list"></ul>
<p class="foot">Datos reales de API-Football (plan gratuito: solo ayer, hoy y mañana). Generado: __GEN__.<br><span id="diag">__NOTA__</span><br>
<button id="test">Probar notificación de inicio</button></p>
</main><div id="toast" role="status"></div>
<script>
const E=__DATA__;
const $=q=>document.querySelector(q);
const now=Date.now();
const tf=new Intl.DateTimeFormat(undefined,{hour:"2-digit",minute:"2-digit"});
const key=ms=>new Date(ms).toLocaleDateString("en-CA");
const ES={"World":"Selecciones","England":"Inglaterra","Spain":"España","Italy":"Italia","Germany":"Alemania","France":"Francia","Netherlands":"Países Bajos","Brazil":"Brasil","USA":"EE.UU.","Switzerland":"Suiza","Belgium":"Bélgica","Peru":"Perú","Mexico":"México","Japan":"Japón"};
const cn=c=>ES[c]||c;
const esc=s=>String(s).replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const ev=E.map(e=>({...e,s:e.ts*1000})).sort((a,b)=>a.s-b.s);
const dias=[...new Set(ev.map(e=>key(e.s)))].sort();
const st={d:Math.max(0,dias.indexOf(key(now))),r:"",c:""};
let favs=new Set();
try{favs=new Set(JSON.parse(localStorage.getItem("favs")||"[]"))}catch(e){}
const save=()=>{try{localStorage.setItem("favs",JSON.stringify([...favs]))}catch(e){}};
$("#date").textContent=new Date().toLocaleDateString("es",{weekday:"long",day:"numeric",month:"long"});
$("#tz").textContent="Horarios en tu zona: "+Intl.DateTimeFormat().resolvedOptions().timeZone;
function buildDays(){
  $("#days").innerHTML=dias.map((k,i)=>{const d=new Date(k+"T12:00:00");
    return `<button class="day" data-i="${i}" aria-pressed="${i===st.d}"><span>${k===key(now)?"Hoy":d.toLocaleDateString("es",{weekday:"short"}).replace(".","")}</span><b>${d.getDate()}</b></button>`}).join("");
}
const uniq=a=>[...new Set(a)];
function opts(sel,list,label,val){sel.innerHTML=`<option value="">${label}</option>`+list.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join("");sel.value=val}
function buildSelects(){
  opts($("#fr"),uniq(ev.map(e=>e.lg.c)).sort((a,b)=>cn(a).localeCompare(cn(b))).map(c=>[c,cn(c)]),"Todos",st.r);
  const byR=ev.filter(e=>!st.r||e.lg.c===st.r);
  opts($("#fc"),uniq(byR.map(e=>e.lg.n)).sort().map(n=>[n,n]),"Todas",st.c);
}
const LIVE=["1H","2H","HT","ET","BT","P","LIVE","INT"],DONE=["FT","AET","PEN"];
function status(e){
  if(LIVE.includes(e.st))return{chip:`<span class="chip live">En vivo${e.min?" "+e.min+"′":""}</span>`};
  if(DONE.includes(e.st))return{cls:"done",chip:'<span class="chip">Finalizado</span>'};
  if(["PST","CANC","ABD","SUSP"].includes(e.st))return{cls:"done",chip:`<span class="chip">${({PST:"Aplazado",CANC:"Cancelado"})[e.st]||"Suspendido"}</span>`};
  const m=Math.round((e.s-now)/6e4);
  return m>0&&m<=60?{chip:`<span class="chip soon">Empieza en ${m} min</span>`}:{};
}
const team=t=>`<div class="tm"><img class="cr" src="${esc(t.l)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"><span class="n">${esc(t.n)}</span>${t.g===null?"":`<b class="g">${t.g}</b>`}</div>`;
const bell='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';
function render(){
  const k=dias[st.d];
  const list=ev.filter(e=>key(e.s)===k&&(!st.r||e.lg.c===st.r)&&(!st.c||e.lg.n===st.c));
  $("#count").textContent=list.length?`${list.length} ${list.length===1?"partido":"partidos"}`:"";
  $("#list").innerHTML=list.length?list.map(e=>{
    const s=status(e),on=favs.has(e.id);
    const flag=e.lg.f?`<img class="fg" src="${esc(e.lg.f)}" alt="" onerror="this.style.display='none'">`:"🌍";
    return`<li class="ev ${s.cls||""}"><div class="time">${tf.format(e.s)}</div><div><div class="comp">${flag}<span>${esc(cn(e.lg.c))} · ${esc(e.lg.n)}</span></div>${team(e.h)}${team(e.a)}${s.chip||""}</div><button class="bell" data-id="${e.id}" aria-pressed="${on}" aria-label="Avisarme al comenzar: ${esc(e.h.n)} vs ${esc(e.a.n)}">${bell}</button></li>`}).join(""):'<li class="empty">No hay partidos con estos filtros. Prueba otro día o elige “Todos”.</li>';
}
let tt;
function toast(m){const t=$("#toast");t.textContent=m;t.classList.add("on");clearTimeout(tt);tt=setTimeout(()=>t.classList.remove("on"),3200)}
function notify(a,b){toast(a+": "+b);try{if("Notification" in window&&Notification.permission==="granted")new Notification(a,{body:b})}catch(e){}}
const LN=(window.Capacitor&&window.Capacitor.isNativePlatform&&window.Capacitor.isNativePlatform())?window.Capacitor.Plugins.LocalNotifications:null;
async function programar(id,titulo,cuerpo,cuando){
  try{
    const p=await LN.requestPermissions();
    if(p.display!=="granted"){toast("Activa los permisos de notificación del teléfono");return false}
    await LN.schedule({notifications:[{id,title:titulo,body:cuerpo,schedule:{at:new Date(cuando),allowWhileIdle:true}}]});
    return true;
  }catch(err){toast("No se pudo programar el aviso");return false}
}
const timers={};
function arm(){
  if(LN)return;
  Object.values(timers).forEach(clearTimeout);
  favs.forEach(id=>{const e=ev.find(x=>x.id==id),w=e&&e.s-Date.now();if(w>0&&w<2e9)timers[id]=setTimeout(()=>notify("Comienza ahora",e.h.n+" vs "+e.a.n),w)});
}
$("#days").onclick=e=>{const b=e.target.closest(".day");if(!b)return;st.d=+b.dataset.i;buildDays();render()};
$("#fr").onchange=e=>{st.r=e.target.value;st.c="";buildSelects();render()};
$("#fc").onchange=e=>{st.c=e.target.value;render()};
$("#list").onclick=async e=>{
  const b=e.target.closest(".bell");if(!b)return;
  const id=+b.dataset.id,x=ev.find(v=>v.id===id);
  if(favs.has(id)){
    favs.delete(id);
    if(LN){try{await LN.cancel({notifications:[{id}]})}catch(err){}}
    toast("Aviso quitado");
  }else{
    if(x.s<=Date.now()){toast("Ese partido ya empezó");return}
    if(LN){if(!(await programar(id,"Comienza ahora",x.h.n+" vs "+x.a.n,x.s)))return}
    else{try{if("Notification" in window&&Notification.permission==="default")Notification.requestPermission()}catch(err){}}
    favs.add(id);toast("Te avisaremos a las "+tf.format(x.s));
  }
  save();arm();render();
};
$("#test").onclick=async()=>{
  if(LN){if(await programar(999999,"Comienza ahora","Chile vs Perú",Date.now()+5000))toast("Llegará en unos 5 segundos");return}
  try{if("Notification" in window&&Notification.permission==="default")Notification.requestPermission()}catch(e){}
  notify("Comienza ahora","Chile vs Perú");
};
buildDays();buildSelects();render();arm();
</script></body></html>"""


def generar_html(eventos, ruta="agenda_futbol.html", nota=""):
    ahora = dt.datetime.now(ZoneInfo(TZ)).strftime("%d-%m-%Y %H:%M")
    datos = json.dumps(eventos, ensure_ascii=False).replace("</", "<\\/")
    with open(ruta, "w", encoding="utf-8") as f:
        nota = nota.replace("&", "&amp;").replace("<", "&lt;")
        f.write(HTML.replace("__DATA__", datos).replace("__GEN__", ahora).replace("__NOTA__", nota))


def main():
    notas, eventos = [], []
    try:
        hoy = dt.datetime.now(ZoneInfo(TZ)).date()
        fixtures = []
        for i in range(2):  # hoy y mañana: 2 solicitudes
            fecha = hoy + dt.timedelta(days=i)
            resp, nota = pedir_fecha(fecha)
            print(f"{fecha}: {len(resp)} partidos en todo el mundo{nota}")
            notas.append(f"{fecha}: {len(resp)} partidos{nota}")
            fixtures += resp
            time.sleep(7)  # plan gratis: 10 solicitudes por minuto

        elegidos = {f["fixture"]["id"]: f for f in fixtures if incluir(f)}
        eventos = sorted((normalizar(f) for f in elegidos.values()), key=lambda e: e["ts"])
        notas.append(f"incluidos: {len(eventos)}")

        print(f"\nIncluidos: {len(eventos)} partidos")
        for (lid, nombre, pais), n in sorted(
                Counter((e["lg"]["id"], e["lg"]["n"], e["lg"]["c"]) for e in eventos).items(),
                key=lambda x: -x[1]):
            print(f"  {n:3d}  [{lid}] {pais} - {nombre}")

        otras = Counter((f["league"]["id"], f["league"]["name"], f["league"]["country"])
                        for f in fixtures if f["fixture"]["id"] not in elegidos)
        print("\nLigas con más partidos que NO se incluyeron (por si falta alguna):")
        for (lid, nombre, pais), n in otras.most_common(15):
            print(f"  {n:3d}  [{lid}] {pais} - {nombre}")
    except Exception as e:
        notas.append(f"error inesperado: {type(e).__name__}: {e}")
        print(notas[-1])

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=1)
    generar_html(eventos, nota="Diagnóstico: " + " | ".join(notas))
    print("\nListo: events.json y agenda_futbol.html")
    try:
        from google.colab import files
        files.download("agenda_futbol.html")
        files.download("events.json")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
