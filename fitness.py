import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os

st.set_page_config(page_title="Progressions-Coach A/B", layout="centered")

# ------------------------- SESSION STATE (früh, damit Timer sofort kann) -------------------------
if "timer_start" not in st.session_state: st.session_state["timer_start"] = None
if "timer_end" not in st.session_state:   st.session_state["timer_end"]   = None
if "auto_timer_seconds" not in st.session_state: st.session_state["auto_timer_seconds"] = 90
if "saved_flags" not in st.session_state: st.session_state["saved_flags"] = {}
if "chosen_map" not in st.session_state:  st.session_state["chosen_map"]  = {}  # key: (tag, idx, date) -> chosen_name
if "autopilot" not in st.session_state:   st.session_state["autopilot"]   = False
if "focus_anchor" not in st.session_state:st.session_state["focus_anchor"]= ""
if "current_date" not in st.session_state:
    st.session_state["current_date"] = date.today().isoformat()

# Tageswechsel -> Haken & Auswahl leeren
if st.session_state["current_date"] != date.today().isoformat():
    st.session_state["current_date"] = date.today().isoformat()
    st.session_state["saved_flags"].clear()
    st.session_state["chosen_map"].clear()
    st.session_state["focus_anchor"] = ""

# ------------------------- STICKY TIMER (immer rendern, ganz oben) -------------------------
def render_sticky_timer():
    start_ms = int(st.session_state["timer_start"].timestamp() * 1000) if st.session_state.get("timer_start") else 0
    end_ms   = int(st.session_state["timer_end"].timestamp() * 1000)   if st.session_state.get("timer_end")   else 0
    html = """
    <script>
    (function(){
      var W = window.parent || window, D = W.document;
      if (!W.gxTimer) {
        W.gxTimer = {
          tStart:0, tEnd:0, done:false, badge:null,
          start:function(s){var n=Date.now();this.tStart=n;this.tEnd=n+s*1000;this.done=false;},
          stop:function(){this.tStart=0;this.tEnd=0;this.done=true;if(this.badge) this.badge.textContent='⏱ 0s';},
          shift:function(ms){if(!this.tEnd) return; this.tEnd=Math.max(Date.now(), this.tEnd+ms);},
          blink:function(){
            var old=D.getElementById('gx-flash-overlay'); if(old&&old.parentNode) old.parentNode.removeChild(old);
            var ov=D.createElement('div'); ov.id='gx-flash-overlay';
            ov.style.cssText='position:fixed;inset:0;background:#00c853;opacity:0;pointer-events:none;z-index:2147483647;transition:opacity 120ms ease';
            D.body.appendChild(ov); void ov.offsetHeight;
            var f=0,intv=setInterval(function(){ov.style.opacity=(f%2===0)?'0.65':'0';f++;if(f>=10){clearInterval(intv);if(ov&&ov.parentNode)ov.parentNode.removeChild(ov);}},500);
          },
          beep:function(){
            try{var ctx=new (W.AudioContext||W.webkitAudioContext)(),o=ctx.createOscillator(),g=ctx.createGain();
            o.type='sine';o.frequency.value=880;o.connect(g);g.connect(ctx.destination);
            g.gain.setValueAtTime(0.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(0.5,ctx.currentTime+0.02);
            g.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+0.35);o.start();o.stop(ctx.currentTime+0.37);}catch(e){}}
        };
        var p=D.createElement('div'); p.id='gx-timer-panel';
        p.style.cssText='position:fixed;right:16px;top:16px;z-index:2147483647;display:flex;gap:8px;align-items:center';
        var b=D.createElement('div'); b.id='gx-timer-badge'; b.textContent='⏱ 0s';
        b.style.cssText='background:rgba(20,20,20,.92);color:#fff;padding:8px 12px;border-radius:12px;font-size:18px;font-weight:800;border:1px solid rgba(255,255,255,.08);box-shadow:0 8px 24px rgba(0,0,0,.35)';
        W.gxTimer.badge=b;
        function mk(id,lab){var x=D.createElement('button');x.id=id;x.textContent=lab;x.style.cssText='font-size:12px;font-weight:800;line-height:1;padding:8px 10px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:rgba(32,32,32,.95);color:#fff;cursor:pointer';x.onmousedown=()=>x.style.transform='translateY(1px)';x.onmouseup=()=>x.style.transform='';return x;}
        var s60=mk('gx60','60s'),s90=mk('gx90','90s'),s120=mk('gx120','120s'),m5=mk('gxm5','−5s'),p5=mk('gxp5','+5s'),stp=mk('gxstp','Stop');
        p.appendChild(b); p.appendChild(s60); p.appendChild(s90); p.appendChild(s120); p.appendChild(m5); p.appendChild(p5); p.appendChild(stp); D.body.appendChild(p);
        s60.onclick=function(){W.gxTimer.start(60)}; s90.onclick=function(){W.gxTimer.start(90)}; s120.onclick=function(){W.gxTimer.start(120)};
        m5.onclick=function(){W.gxTimer.shift(-5000)}; p5.onclick=function(){W.gxTimer.shift(5000)}; stp.onclick=function(){W.gxTimer.stop()};
        function fmt(s){if(s<60)return s+'s';var m=Math.floor(s/60),x=s%60;return m+':' + (x<10?('0'+x):x);}
        function tick(){var e=W.gxTimer.tEnd;if(!e){b.textContent='⏱ 0s';return;} var rem=Math.floor((e-Date.now())/1000);
          if(rem<=0){b.textContent='⏱ 0s'; if(!W.gxTimer.done){W.gxTimer.done=true;W.gxTimer.blink();W.gxTimer.beep(); if(W.navigator&&W.navigator.vibrate)W.navigator.vibrate([200,100,200,100,200]);} return;}
          b.textContent='⏱ '+fmt(rem);}
        tick(); W.setInterval(tick,250);
      }
      // Backend-Zeiten in Singleton setzen
      var newStart = """ + str(start_ms) + """;
      var newEnd   = """ + str(end_ms) + """;
      if (newEnd > 0) { W.gxTimer.tStart = newStart; W.gxTimer.tEnd = newEnd; W.gxTimer.done=false; }
    })();
    </script>
    """
    st.components.v1.html(html, height=1)

render_sticky_timer()  # <-- jetzt IMMER sichtbar, direkt ab Start

# ------------------------- PLAN & EXERCISE POOL -------------------------
PLAN = {
    "A": [
        ("Schrägbankdrücken KH/LH", 6, 10, 2.5, "main"),
        ("Plate-Loaded Press",       8, 10, 2.5, "main"),
        ("Schulterpresse",           8, 10, 2.5, "main"),
        ("Kabel-Seitheben einarmig",12, 15, 1.0, "iso"),
        ("Fliegende (Kabel/Maschine)",12,15, 1.0, "iso"),
        ("Trizepsdrücken Seil",     12, 15, 1.0, "iso"),
        ("Overhead-Trizeps Seil",   12, 15, 1.0, "iso"),
        ("Bauchmaschine",           15, 15, 1.0, "core")
    ],
    "B": [
        ("Latzug eng Neutralgriff",  8, 12, 2.5, "main"),
        ("Rudern eng Kabel",         8, 12, 2.5, "main"),
        ("Rudern Maschine (Brustauflage)",10,12,2.5,"main"),
        ("Beinpresse",              10, 12, 5.0, "main"),
        ("Beinstrecker",            12, 15, 2.0, "iso"),
        ("Beinbeuger liegend",      12, 15, 2.0, "iso"),
        ("Kabel-Curls Seil",        10, 12, 1.0, "iso"),
        ("Hammer Curls KH",         12, 15, 1.0, "iso"),
        ("Face Pulls Kabel",        12, 15, 0.5, "prehab")
    ]
}
EXERCISE_POOL = sorted(list({
    n for day in PLAN.values() for (n, *_ ) in day
}.union({
    "Brustpresse Maschine","Dips","Butterfly Maschine",
    "Latzug breit","Klimmzug (assistiert)","T-Bar Rudern",
    "Ausfallschritte","Beinbeuger sitzend","Seitheben KH","Overhead-Press LH"
})))

SETS_MAIN = 3
SETS_ISO  = 2
CSV_PATH  = "workout_log.csv"

# ------------------------- STORAGE HELPERS -------------------------
def load_log() -> pd.DataFrame:
    cols = ["date","tag","exercise","set","weight","reps","rpe","note"]
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            for c in cols:
                if c not in df.columns: df[c] = None
            return df[cols]
        except Exception:
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def save_log(df: pd.DataFrame):
    df.to_csv(CSV_PATH, index=False)

def append_row(row: dict):
    df = load_log()
    df.loc[len(df)] = row
    save_log(df)

# ------------------------- TRAINING LOGIC -------------------------
def sets_target(tp: str) -> int:
    return SETS_MAIN if tp == "main" else SETS_ISO

def last_unit(df: pd.DataFrame, tag: str, ex_name: str):
    sub = df[(df["tag"] == tag) & (df["exercise"] == ex_name)]
    if sub.empty: return None, None
    dates = sorted(sub["date"].unique())
    d = dates[-1]
    return d, sub[sub["date"] == d]

def suggest_target(df: pd.DataFrame, tag: str, ex_name: str, fallback_meta=None):
    # Range/Inc/Typ ermitteln (bei Tausch fallbacks nutzen)
    lr = hr = inc = None
    tp = "main"
    found = False
    for n, a, b, c, t in PLAN[tag]:
        if n == ex_name:
            lr, hr, inc, tp = a, b, c, t
            found = True
            break
    if not found:
        if fallback_meta is not None:
            lr, hr, inc, tp = fallback_meta
        else:
            lr, hr, inc, tp = 8, 12, 2.5, "main"

    hist_date, unit = last_unit(df, tag, ex_name)
    if unit is None or unit.empty:
        return {"msg": f"Erste Einheit: Startgewicht wählen. Ziel: {sets_target(tp)} Sätze {lr}–{hr}.",
                "mode": "start", "lr": lr, "hr": hr, "tp": tp}

    last_w = float(unit["weight"].max())
    reps_list = [int(x) for x in unit["reps"].tolist() if pd.notnull(x)]
    rpe_list  = [float(x) for x in unit["rpe"].tolist()  if pd.notnull(x)]
    max_rpe   = max(rpe_list) if rpe_list else 8.0
    avg_reps  = sum(reps_list)/len(reps_list) if reps_list else 0
    sets_cnt  = len(reps_list) if reps_list else 0

    all_top       = (sets_cnt >= 1) and all(r >= hr for r in reps_list)
    many_below_lr = (sets_cnt >= 1) and (sum(r < lr for r in reps_list) >= max(1, sets_cnt // 2))
    near_top      = (sets_cnt >= 1) and all(r >= lr for r in reps_list) and (avg_reps >= (hr - 1))

    if all_top and max_rpe <= 9.0:
        return {"msg": f"Heute **+{inc} kg** → Range reset ({lr}–{lr+1}). Letztes Mal ~{last_w:.1f} kg (RPE max {max_rpe:.1f}).",
                "mode":"add_weight","inc":inc,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

    if max_rpe >= 9.5 and not all_top:
        hint = "Gewicht halten, Reps Richtung oberes Ziel bringen."
        if many_below_lr:
            hint = "Gewicht halten (optional −1–2 kg), erst stabil in den Zielbereich kommen."
        return {"msg": f"{hint} Letztes Mal: ~{last_w:.1f} kg, Ø{avg_reps:.1f} Wdh., RPE max {max_rpe:.1f}.",
                "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

    if many_below_lr:
        return {"msg": f"Gewicht halten (optional −1–2 kg). Ziel: erst {lr}–{hr} stabil erreichen. Letztes Mal ~{last_w:.1f} kg.",
                "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

    if near_top and max_rpe <= 9.0:
        return {"msg": f"Heute **+1 Wdh./Satz** bei ~{last_w:.1f} kg, bis {hr} erreicht. RPE ok ({max_rpe:.1f}).",
                "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

    return {"msg": f"Heute **+1 Wdh./Satz** bei ~{last_w:.1f} kg. Wenn RPE ≤ 9 bleibt, bald +{inc} kg.",
            "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

def weeks_since(d: date) -> int:
    return max(1, (date.today() - d).days // 7 + 1)

def needs_deload(df: pd.DataFrame, block_start: date, every_weeks: int = 8, slip_tol: int = 2):
    time_flag = (weeks_since(block_start) % every_weeks == 0)
    slips = 0
    for t in ["A","B"]:
        for (name, *_ ) in PLAN[t]:
            sub = df[(df["tag"]==t) & (df["exercise"]==name)]
            if sub.empty: continue
            days = sorted(sub["date"].unique())
            if len(days) < 2: continue
            d1, d2 = days[-2], days[-1]
            u1 = sub[sub["date"]==d1]; u2 = sub[sub["date"]==d2]
            if u1.empty or u2.empty: continue
            w1 = float(u1["weight"].max()); w2 = float(u2["weight"].max())
            if abs(w1 - w2) <= 0.5 and int(u2["reps"].sum()) < int(u1["reps"].sum()):
                slips += 1
    fatigue_flag = (slips >= slip_tol)
    return (time_flag or fatigue_flag), {"time": time_flag, "fatigue": fatigue_flag, "slips": slips}

def undo_last_set_today(tag: str, name: str):
    dfx = load_log()
    today = date.today().isoformat()
    sub = dfx[(dfx["date"]==today) & (dfx["tag"]==tag) & (dfx["exercise"]==name)]
    if sub.empty:
        st.info("Heute kein gespeicherter Satz für diese Übung.")
        return
    max_set = int(sub["set"].max())
    dfx = dfx[~((dfx["date"]==today) & (dfx["tag"]==tag) & (dfx["exercise"]==name) & (dfx["set"]==max_set))]
    save_log(dfx)
    st.session_state["saved_flags"].pop(f"{tag}:{name}:{today}:{max_set}", None)
    st.success(f"Satz {max_set} zurückgenommen.")

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    tag = st.selectbox("Trainingstag", ["A","B"])
    block_start = st.date_input("Block-Start (für Deload-Timer)", value=date.today())
    deload_every = st.slider("Deload alle X Wochen", 6, 10, 8)
    deload_drop = st.slider("Deload: Gewichtsreduzierung (%)", 20, 45, 35)
    st.session_state["auto_timer_seconds"] = st.selectbox("Auto-Pause nach ✅", [0,60,90,120], index=2)
    st.toggle("🧭 Autopilot (Satz→Satz springen)", key="autopilot")
    st.caption("RPE: 8 ≈ 2 RR · 9 ≈ 1 RR · 10 = Versagen.")
    st.markdown("---")
    st.subheader("📤 CSV importieren")
    uploaded = st.file_uploader("Vorherige workout_log.csv auswählen", type=["csv"])
    if uploaded is not None:
        try:
            df_old = load_log()
            df_new = pd.read_csv(uploaded)
            cols = ["date","tag","exercise","set","weight","reps","rpe","note"]
            for c in cols:
                if c not in df_new.columns: df_new[c] = None
            df_all = pd.concat([df_old, df_new[cols]], ignore_index=True).drop_duplicates()
            save_log(df_all)
            st.success("CSV importiert – Fortschritt übernommen.")
        except Exception as e:
            st.error(f"Import fehlgeschlagen: {e}")
    st.markdown("---")
    with st.expander("⚠️ Datenverwaltung"):
        confirm = st.checkbox("Ich bestätige, dass ich alle Trainingsdaten löschen möchte.")
        if st.button("🗑️ Alle Daten löschen", disabled=not confirm):
            save_log(pd.DataFrame(columns=["date","tag","exercise","set","weight","reps","rpe","note"]))
            st.session_state["saved_flags"].clear()
            st.session_state["chosen_map"].clear()
            st.success("Alle Daten wurden gelöscht.")

# ------------------------- HEADER -------------------------
st.title("🏋️ Progressions-Coach (A/B)")
st.write(f"**Heute:** {date.today().isoformat()}  ·  **Tag {tag}**")
st.caption("Double-Progression (Reps zuerst, dann Gewicht). Coach berücksichtigt RPE + Reps. Deload bei Woche X oder Leistungseinbruch.")

# ------------------------- DELOAD HINWEIS -------------------------
df = load_log()
flag, meta = needs_deload(df, block_start, deload_every, slip_tol=2)
if flag:
    reason = "Kalender" if meta["time"] else ""
    if meta["fatigue"]:
        reason += (" & " if reason else "") + f"Leistungsabfall ({meta['slips']})"
    st.warning(f"🔻 Deload empfohlen: {reason}. Vorschlag: ~{deload_drop}% weniger Gewicht, Sätze −30–50 %, 3–4 Wdh. in Reserve.")

# ------------------------- AUTOPILOT: ggf. scrollen -------------------------
if st.session_state["focus_anchor"]:
    st.components.v1.html(f"""
    <script>
      const el = window.parent.document.getElementById("{st.session_state['focus_anchor']}");
      if (el) el.scrollIntoView({{behavior:'smooth', block:'center'}});
    </script>
    """, height=0)

# ------------------------- TAGES-FORTSCHRITT -------------------------
today_str = date.today().isoformat()
target_today = sum(SETS_MAIN if tp=="main" else SETS_ISO for (_,_,_,_,tp) in PLAN[tag])
done_today = len(df[(df["date"]==today_str) & (df["tag"]==tag)])
st.progress(min(done_today/target_today, 1.0))
st.caption(f"Heute erledigt: **{done_today}/{target_today} Sätze**")

# ------------------------- PRO ÜBUNG -------------------------
for i, (orig_name, lr, hr, inc, tp) in enumerate(PLAN[tag], start=1):
    # Übung heute wählen (Tausch möglich)
    choose_key = (tag, i, today_str)
    default_name = st.session_state["chosen_map"].get(choose_key, orig_name)
    chosen_name = st.selectbox(f"Übung {i} heute:", EXERCISE_POOL,
                               index=EXERCISE_POOL.index(default_name) if default_name in EXERCISE_POOL else 0,
                               key=f"choose_{tag}_{i}_{today_str}")
    st.session_state["chosen_map"][choose_key] = chosen_name

    # Coach-Empfehlung (bei Tausch Range des Originals als Fallback)
    sug = suggest_target(df, tag, chosen_name, fallback_meta=(lr,hr,inc,tp))

    # Wie viele Sätze heute?
    target_sets = sets_target(tp)

    # Heutige Sätze (für Farbe & Defaults)
    today_sets = df[(df["date"]==today_str) & (df["tag"]==tag) & (df["exercise"]==chosen_name)]
    saved_count = 0 if today_sets.empty else int(today_sets["set"].max())

    # Box-Farbe
    if saved_count == 0:            box_bg = "#2b2b2b"
    elif saved_count < target_sets: box_bg = "#3a3a1d"
    elif saved_count == target_sets:box_bg = "#1d3a1d"
    else:                           box_bg = "#144d14"

    st.markdown(
        f"""
        <div style="background:{box_bg};padding:12px;border-radius:10px;color:#fff;line-height:1.35;border:1px solid rgba(255,255,255,0.08)" id="ex_{i}">
          <div style="font-weight:700;font-size:18px;">{i}. {chosen_name} · Ziel {lr}–{hr} Wdh.</div>
          <div style="opacity:0.95;"><b>Coach:</b> {sug['msg']}</div>
          <div style="opacity:0.8;font-size:13px;margin-top:4px;">Heute gespeichert: {saved_count}/{target_sets}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Defaults aus letzter Einheit
    _, last_u = last_unit(df, tag, chosen_name)
    last_weight = float(last_u["weight"].max()) if (last_u is not None and not last_u.empty) else 0.0
    base_w = float(sug.get("base", last_weight))
    base_r = lr

    st.write("")  # Abstand

    # Satz-Zeilen
    for s in range(1, target_sets + 1):
        anchor_id = f"a_{tag}_{i}_{s}"
        st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)

        flag_key = f"{tag}:{chosen_name}:{today_str}:{s}"
        stored_already = st.session_state["saved_flags"].get(flag_key, False) or (s <= saved_count)

        # Defaults aus vorherigem Satz heute übernehmen
        if s > 1:
            prev = df[(df["date"]==today_str) & (df["tag"]==tag) & (df["exercise"]==chosen_name) & (df["set"]==s-1)]
            if not prev.empty:
                base_w = float(prev["weight"].iloc[0])
                base_r = int(prev["reps"].iloc[0])

        c1, c2, c3, c4 = st.columns([1.3, 0.8, 0.9, 0.7])
        w = c1.number_input(f"Satz {s} – Gewicht (kg)", min_value=0.0, step=0.5,
                            value=base_w, key=f"w_{tag}_{i}_{s}", disabled=stored_already)
        r = c2.number_input("Wdh.", min_value=0, step=1,
                            value=base_r, key=f"r_{tag}_{i}_{s}", disabled=stored_already)
        rpe = c3.slider("RPE", 5.0, 10.0, 8.0, 0.5,
                        key=f"rpe_{tag}_{i}_{s}", disabled=stored_already)
        save_now = c4.checkbox("✅", value=stored_already, key=f"chk_{tag}_{i}_{s}")

        # Speichern + Autopilot vorwärts springen
        if save_now and not stored_already:
            sub_today = df[(df["date"]==today_str) & (df["tag"]==tag) & (df["exercise"]==chosen_name)]
            next_set = 1 if sub_today.empty else int(sub_today["set"].max()) + 1
            set_number = max(next_set, s)

            append_row({
                "date": today_str,
                "tag": tag,
                "exercise": chosen_name,  # echte (ggf. getauschte) Übung
                "set": set_number,
                "weight": float(w),
                "reps": int(r),
                "rpe": float(rpe),
                "note": ""
            })
            st.session_state["saved_flags"][flag_key] = True

            # Auto-Pause nach ✅
            secs = int(st.session_state.get("auto_timer_seconds", 0))
            if secs > 0:
                st.session_state["timer_start"] = datetime.utcnow()
                st.session_state["timer_end"]   = st.session_state["timer_start"] + timedelta(seconds=secs)

            # Autopilot: nächste Ziel-Position
            if st.session_state["autopilot"]:
                if s < target_sets:
                    st.session_state["focus_anchor"] = f"a_{tag}_{i}_{s+1}"
                else:
                    st.session_state["focus_anchor"] = f"ex_{i+1}" if i < len(PLAN[tag]) else ""
            df = load_log()
            st.rerun()

    # Undo & Reset (nur diese Übung, heute)
    cundo1, cundo2 = st.columns(2)
    if cundo1.button("↩️ Letzten Satz (heute) zurücknehmen", key=f"undo_btn_{tag}_{i}"):
        undo_last_set_today(tag, chosen_name)
        df = load_log()
        st.rerun()
    if cundo2.button("🧹 Heutige Eingaben (nur diese Übung) zurücksetzen", key=f"reset_today_{tag}_{i}"):
        for s in range(1, target_sets + 1):
            st.session_state["saved_flags"].pop(f"{tag}:{chosen_name}:{today_str}:{s}", None)
            for k in (f"w_{tag}_{i}_{s}", f"r_{tag}_{i}_{s}", f"rpe_{tag}_{i}_{s}", f"chk_{tag}_{i}_{s}"):
                st.session_state.pop(k, None)
        st.info("Heutige Eingaben zurückgesetzt.")
        st.rerun()

# ------------------------- VERLAUF & EXPORT -------------------------
st.markdown("---")
with st.expander("📒 Letzte 30 Einträge"):
    hist = load_log()
    if hist.empty:
        st.info("Noch nichts geloggt.")
    else:
        st.dataframe(hist.tail(30), use_container_width=True)

csv_bytes = load_log().to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 CSV exportieren",
    data=csv_bytes,
    file_name=f"workout_log_{date.today().isoformat()}.csv",
    mime="text/csv"
)

st.caption("Tipps: Neutrale Griffe bei Reizung, kein harter Lockout, langsame Negative. "
           "Deload: Gewicht −30–40 %, Sätze −30–50 %, 3–4 Wdh. in Reserve.")