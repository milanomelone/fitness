import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os

st.set_page_config(page_title="Progressions-Coach A/B", layout="centered")

# ------------------------- PLAN -------------------------
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

SETS_MAIN = 3
SETS_ISO  = 2
CSV_PATH  = "workout_log.csv"

# ------------------------- SESSION STATE -------------------------
if "timer_end" not in st.session_state:
    st.session_state["timer_end"] = None
if "auto_timer_seconds" not in st.session_state:
    st.session_state["auto_timer_seconds"] = 90  # Auto-Pause nach ✅
if "saved_flags" not in st.session_state:
    # Merkt pro Übung/Satz, ob heute bereits per ✅ gespeichert wurde
    # key = f"{tag}:{exercise}:{date}:{setnr}" -> True/False
    st.session_state["saved_flags"] = {}
if "last_blink_ts" not in st.session_state:
    st.session_state["last_blink_ts"] = 0.0  # verhindert mehrfaches Blinken

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

def suggest_target(df: pd.DataFrame, tag: str, ex_name: str):
    lr = hr = inc = None
    tp = "main"
    for n, a, b, c, t in PLAN[tag]:
        if n == ex_name:
            lr, hr, inc, tp = a, b, c, t
            break
    hist_date, unit = last_unit(df, tag, ex_name)
    if unit is None or unit.empty:
        return {"msg": f"Erste Einheit: Startgewicht wählen. Ziel: {sets_target(tp)} Sätze {lr}–{hr}.",
                "mode": "start", "lr": lr, "hr": hr, "tp": tp}
    last_w = float(unit["weight"].max())
    reps_list = [int(x) for x in unit["reps"].tolist() if pd.notnull(x)]
    all_top = (len(reps_list) >= 1) and all(r >= hr for r in reps_list)
    if all_top:
        return {"msg": f"Heute **+{inc} kg** → Range reset ({lr}–{lr+1}). Letztes Mal ~{last_w:.1f} kg.",
                "mode":"add_weight","inc":inc,"base":last_w,"lr":lr,"hr":hr,"tp":tp}
    else:
        return {"msg": f"Heute **+1 Wdh./Satz** bei ~{last_w:.1f} kg, bis {hr} erreicht.",
                "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr,"tp":tp}

def weeks_since(d: date) -> int:
    return max(1, (date.today() - d).days // 7 + 1)

def needs_deload(df: pd.DataFrame, block_start: date, every_weeks: int = 8, slip_tol: int = 2):
    time_flag = (weeks_since(block_start) % every_weeks == 0)
    slips = 0
    for tag in ["A","B"]:
        for (name, *_ ) in PLAN[tag]:
            sub = df[(df["tag"]==tag) & (df["exercise"]==name)]
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

# ------------------------- TIMER RENDERING -------------------------
def render_sticky_timer_and_blink():
    """Floating Timer + 3x grün blinken + Beep + Vibration am Ende."""
    remaining = 0
    if st.session_state.get("timer_end"):
        remaining = max(0, int((st.session_state["timer_end"] - datetime.utcnow()).total_seconds()))
        if remaining == 0:
            st.session_state["timer_end"] = None
            # Blink + Beep + Vibration (einmal pro Ablauf)
            now_ts = datetime.utcnow().timestamp()
            if now_ts - st.session_state.get("last_blink_ts", 0) > 0.8:
                st.session_state["last_blink_ts"] = now_ts
                st.components.v1.html("""
                <style>
                  @keyframes flashGreen {
                    0%, 100% { opacity: 0; }
                    50% { opacity: .6; }
                  }
                  .flash-overlay {
                    position: fixed; inset: 0; background: #00c853; 
                    z-index: 9998; pointer-events: none;
                    animation: flashGreen 0.5s ease-in-out 3;
                  }
                </style>
                <div class="flash-overlay"></div>
                <audio autoplay>
                  <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=" type="audio/wav">
                </audio>
                <script>
                  if (navigator.vibrate) navigator.vibrate([160,80,160]);
                  setTimeout(() => {
                    const el = document.querySelector('.flash-overlay');
                    if (el) el.remove();
                  }, 1600);
                </script>
                """, height=0)

    # Floating Timer (immer sichtbar)
    st.markdown(f"""
    <div style="
        position: fixed; right: 16px; bottom: 16px;
        background: rgba(20,20,20,.92); color: #fff;
        padding: 10px 14px; border-radius: 12px;
        font-size: 24px; font-weight: 800; z-index: 9999;
        box-shadow: 0 8px 24px rgba(0,0,0,.35);
        border: 1px solid rgba(255,255,255,.08);
        -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px);
    ">
      ⏱ {remaining}s
    </div>
    """, unsafe_allow_html=True)

    # Auto-Refresh jede Sekunde solange Timer läuft
    if st.session_state.get("timer_end"):
        st.query_params["_"] = datetime.utcnow().timestamp()
        st.rerun()

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    tag = st.selectbox("Trainingstag", ["A","B"])
    block_start = st.date_input("Block-Start (für Deload-Timer)", value=date.today())
    deload_every = st.slider("Deload alle X Wochen", 6, 10, 8)
    deload_drop = st.slider("Deload: Gewichtsreduzierung (%)", 20, 45, 35)
    st.session_state["auto_timer_seconds"] = st.selectbox("Auto-Pause nach ✅", [0,60,90,120], index=2)
    st.caption("RPE: 8 ≈ 2 Reps Reserve · 9 ≈ 1 RR · 10 = Versagen.")

    st.markdown("---")
    st.subheader("⏱️ Pausen-Timer")
    col = st.columns(4)
    if col[0].button("▶️ 60s"):  st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=60)
    if col[1].button("▶️ 90s"):  st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=90)
    if col[2].button("▶️ 120s"): st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=120)
    if col[3].button("⏹"):       st.session_state["timer_end"] = None

    # Anzeige in der Sidebar
    remaining_sidebar = 0
    if st.session_state.get("timer_end"):
        remaining_sidebar = max(0, int((st.session_state["timer_end"] - datetime.utcnow()).total_seconds()))
        if remaining_sidebar == 0:
            st.session_state["timer_end"] = None
    st.markdown(f"<div style='font-size:32px; font-weight:800; text-align:center;'>{remaining_sidebar}s</div>", unsafe_allow_html=True)

    # CSV-Import
    st.markdown("### 📤 CSV importieren")
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
            st.success("Alle Daten wurden gelöscht.")

# ------------------------- HEADER -------------------------
st.title("🏋️ Progressions-Coach (A/B)")
st.write(f"**Heute:** {date.today().isoformat()}  ·  **Tag {tag}**")
st.caption("Double-Progression (erst Reps hoch, dann Gewicht). Deload bei Woche X oder Leistungseinbruch.")

# ------------------------- DELOAD HINWEIS -------------------------
df = load_log()
flag, meta = needs_deload(df, block_start, deload_every, slip_tol=2)
if flag:
    reason = "Kalender" if meta["time"] else ""
    if meta["fatigue"]:
        reason += (" & " if reason else "") + f"Leistungsabfall ({meta['slips']})"
    st.warning(f"🔻 Deload empfohlen: {reason}. Vorschlag: ~{deload_drop}% weniger Gewicht, Sätze −30–50%, 3–4 Wdh. in Reserve.")

# ------------------------- TAGES-FORTSCHRITT -------------------------
today_str = date.today().isoformat()
target_today = sum(SETS_MAIN if tp=="main" else SETS_ISO for (_,_,_,_,tp) in PLAN[tag])
done_today = len(df[(df["date"]==today_str) & (df["tag"]==tag)])
st.progress(min(done_today/target_today, 1.0))
st.caption(f"Heute erledigt: **{done_today}/{target_today} Sätze**")

# ------------------------- PRO ÜBUNG: ALPHA-STYLE SET-ZEILEN -------------------------
for i, (name, lr, hr, inc, tp) in enumerate(PLAN[tag], start=1):
    sug = suggest_target(df, tag, name)
    today = today_str
    ex_prefix = f"{tag}:{name}:{today}"
    target_sets = sets_target(tp)

    # Gespeicherte Sätze heute (für Farbe & Defaults)
    today_sets = df[(df["date"]==today) & (df["tag"]==tag) & (df["exercise"]==name)]
    saved_count = 0 if today_sets.empty else int(today_sets["set"].max())

    # ---- DARK-MODE-FARBEN nach gespeichertem Fortschritt ----
    if saved_count == 0:
        box_bg = "#2b2b2b"
    elif saved_count < target_sets:
        box_bg = "#3a3a1d"
    elif saved_count == target_sets:
        box_bg = "#1d3a1d"
    else:
        box_bg = "#144d14"

    st.markdown(
        f"""
        <div style="
            background-color:{box_bg};
            padding:12px; border-radius:10px;
            color:#fff; line-height:1.35;
            border:1px solid rgba(255,255,255,0.08);
        ">
          <div style="font-weight:700; font-size:18px;">
            {i}. {name} · Ziel {lr}–{hr} Wdh.
          </div>
          <div style="opacity:0.95;"><b>Coach:</b> {sug['msg']}</div>
          <div style="opacity:0.8; font-size:13px; margin-top:4px;">
            Heute gespeichert: {saved_count}/{target_sets}
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Standardvorschlag aus letzter Einheit
    _, last_u = last_unit(df, tag, name)
    last_weight = float(last_u["weight"].max()) if (last_u is not None and not last_u.empty) else 0.0
    base_w = float(sug.get("base", last_weight))
    base_r = lr

    st.write("")  # Abstand

    # Feste Set-Zeilen mit ✅
    for s in range(1, target_sets + 1):
        flag_key = f"{ex_prefix}:{s}"
        # ist dieser Satz bereits gespeichert?
        stored_already = st.session_state["saved_flags"].get(flag_key, False) or (s <= saved_count)

        # Defaults aus vorherigem Satz heute übernehmen
        if s > 1:
            prev = df[(df["date"]==today) & (df["tag"]==tag) & (df["exercise"]==name) & (df["set"]==s-1)]
            if not prev.empty:
                base_w = float(prev["weight"].iloc[0])
                base_r = int(prev["reps"].iloc[0])

        c1, c2, c3, c4 = st.columns([1.3, 0.8, 0.9, 0.7])
        w = c1.number_input(f"Satz {s} – Gewicht (kg)", min_value=0.0, step=0.5,
                            value=base_w, key=f"w_{ex_prefix}_{s}", disabled=stored_already)
        r = c2.number_input("Wdh.", min_value=0, step=1,
                            value=base_r, key=f"r_{ex_prefix}_{s}", disabled=stored_already)
        rpe = c3.slider("RPE", 5.0, 10.0, 8.0, 0.5,
                        key=f"rpe_{ex_prefix}_{s}", disabled=stored_already)
        save_now = c4.checkbox("✅", value=stored_already, key=f"chk_{ex_prefix}_{s}")

        # Wenn Haken gesetzt und noch nicht gespeichert -> sofort persistieren
        if save_now and not stored_already:
            # Set-Nummer korrekt bestimmen (falls Reihenfolge gesprungen)
            sub_today = df[(df["date"]==today) & (df["tag"]==tag) & (df["exercise"]==name)]
            next_set = 1 if sub_today.empty else int(sub_today["set"].max()) + 1
            set_number = max(next_set, s)

            append_row({
                "date": today,
                "tag": tag,
                "exercise": name,
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
                st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=secs)

            # Refresh
            df = load_log()
            st.rerun()

    # Undo & Reset (nur diese Übung, heute)
    cundo1, cundo2 = st.columns(2)
    if cundo1.button("↩️ Letzten Satz (heute) zurücknehmen", key=f"undo_btn_{ex_prefix}"):
        undo_last_set_today(tag, name)
        df = load_log()
        st.rerun()

    if cundo2.button("🧹 Heutige Eingaben (nur diese Übung) zurücksetzen", key=f"reset_today_{ex_prefix}"):
        for s in range(1, target_sets + 1):
            st.session_state["saved_flags"].pop(f"{ex_prefix}:{s}", None)
            st.session_state.pop(f"w_{ex_prefix}_{s}", None)
            st.session_state.pop(f"r_{ex_prefix}_{s}", None)
            st.session_state.pop(f"rpe_{ex_prefix}_{s}", None)
            st.session_state.pop(f"chk_{ex_prefix}_{s}", None)
        st.info("Heutige Eingaben zurückgesetzt.")
        st.rerun()

# ------------------------- FLOATING TIMER RENDER -------------------------
render_sticky_timer_and_blink()

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