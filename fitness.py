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
if "set_buffer" not in st.session_state:
    st.session_state["set_buffer"] = {}  # key: f"{tag}:{exercise}"
if "timer_end" not in st.session_state:
    st.session_state["timer_end"] = None
if "auto_timer_seconds" not in st.session_state:
    st.session_state["auto_timer_seconds"] = 90  # Default Auto-Pausenlänge

# ------------------------- HELPERS: STORAGE -------------------------
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

# ------------------------- HELPERS: TRAINING LOGIC -------------------------
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

def ex_type(tag: str, ex_name: str) -> str:
    for n, lr, hr, inc, tp in PLAN[tag]:
        if n == ex_name: return tp
    return "main"

def undo_last_set_today(tag: str, name: str):
    dfx = load_log()
    today = date.today().isoformat()
    sub = dfx[(dfx["tag"]==tag) & (dfx["exercise"]==name) & (dfx["date"]==today)]
    if sub.empty:
        st.info("Heute kein gespeicherter Satz für diese Übung.")
        return
    max_set = int(sub["set"].max())
    dfx = dfx[~((dfx["tag"]==tag) & (dfx["exercise"]==name) & (dfx["date"]==today) & (dfx["set"]==max_set))]
    save_log(dfx)
    st.success(f"Letzten Satz von heute entfernt (Satz {max_set}).")

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    tag = st.selectbox("Trainingstag", ["A","B"])
    block_start = st.date_input("Block-Start (für Deload-Timer)", value=date.today())
    deload_every = st.slider("Deload alle X Wochen", 6, 10, 8)
    deload_drop = st.slider("Deload: Gewichtsreduzierung (%)", 20, 45, 35)
    st.session_state["auto_timer_seconds"] = st.selectbox("Auto-Pause nach Speichern", [0,60,90,120], index=2)
    st.caption("RPE: 8 ≈ 2 Reps Reserve · 9 ≈ 1 RR · 10 = Versagen.")

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
            st.success("Alle Daten wurden gelöscht.")

# ------------------------- HEADER -------------------------
st.title("🏋️ Progressions-Coach (A/B)")
st.write(f"**Heute:** {date.today().isoformat()}  ·  **Tag {tag}**")
st.caption("Regelwerk: Double-Progression (erst Reps hoch, dann Gewicht). Deload bei Woche X oder Leistungseinbruch.")

# ------------------------- DELOAD HINWEIS -------------------------
df = load_log()
flag, meta = needs_deload(df, block_start, deload_every, slip_tol=2)
if flag:
    reason = "Kalender" if meta["time"] else ""
    if meta["fatigue"]:
        reason += (" & " if reason else "") + f"Leistungsabfall ({meta['slips']})"
    st.warning(f"🔻 Deload empfohlen: {reason}. Vorschlag: ~{deload_drop}% weniger Gewicht, Sätze −30–50%, 3–4 Wdh. in Reserve.")

# ------------------------- TAGES-FORTSCHRITT -------------------------
# Ziel-Sätze (heute) = Summe der Ziel-Sätze aus Tag A/B
today_tag_plan = PLAN[tag]
target_today = sum(SETS_MAIN if tp=="main" else SETS_ISO for (_,_,_,_,tp) in today_tag_plan)
done_today = 0
today_str = date.today().isoformat()
logged_today = df[df["date"] == today_str]
for _, _, _, _, tp in today_tag_plan:
    pass
done_today = len(logged_today[(logged_today["tag"]==tag)])

st.progress(min(done_today/target_today, 1.0))
st.caption(f"Heute erledigt: **{done_today}/{target_today} Sätze**")

# ------------------------- ÜBUNGEN / BUFFER / LOG -------------------------
for i, (name, lr, hr, inc, tp) in enumerate(PLAN[tag], start=1):
    sug = suggest_target(df, tag, name)
    buffer_key = f"{tag}:{name}"
    if buffer_key not in st.session_state["set_buffer"]:
        st.session_state["set_buffer"][buffer_key] = []

    # Ziel/Status
    target_sets = sets_target(sug.get("tp", tp))
    current_sets = len(st.session_state["set_buffer"][buffer_key])

    # Hintergrundfarbe nach Fortschritt
    if current_sets == 0:
        box_color = "#f6f6f6"       # grau
    elif current_sets < target_sets:
        box_color = "#fff3cd"       # gelb
    elif current_sets == target_sets:
        box_color = "#d4edda"       # grün
    else:
        box_color = "#c3e6cb"       # noch grüner (overachieve)

    st.markdown(
        f"<div style='background-color:{box_color}; padding:12px; border-radius:10px;'>"
        f"<div style='font-weight:700; font-size:18px;'>{i}. {name} · Ziel {lr}–{hr} Wdh.</div>"
        f"<div style='opacity:0.8;'>Coach: {sug['msg']}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    # Defaults
    _, last_u = last_unit(df, tag, name)
    default_w = float(last_u["weight"].max()) if (last_u is not None and not last_u.empty) else 0.0
    base_w = float(sug.get("base", default_w))

    # Inputs + Buffer
    c1, c2, c3, c4 = st.columns([1.3, 0.9, 0.9, 1.3])
    w = c1.number_input("Gewicht (kg)", min_value=0.0, step=0.5, value=base_w, key=f"w_{tag}_{i}")
    r = c2.number_input("Wdh.", min_value=0, step=1, value=lr, key=f"r_{tag}_{i}")
    rpe = c3.slider("RPE", 5.0, 10.0, 8.0, 0.5, key=f"rpe_{tag}_{i}")
    add = c4.button("➕ Satz hinzufügen", key=f"add_{tag}_{i}")

    if add:
        st.session_state["set_buffer"][buffer_key].append({"weight": float(w), "reps": int(r), "rpe": float(rpe)})
        st.success(f"Satz geplant: {w:.1f} kg × {int(r)} (RPE {rpe})")

    st.caption(f"Geplante Sätze im Buffer: {current_sets}/{target_sets}")

    # Geplante Sätze + Bearbeiten/Löschen
    if current_sets > 0:
        for idx_buf, row in enumerate(st.session_state["set_buffer"][buffer_key]):
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.0, 0.9, 0.9, 0.9, 0.8])
            cc1.markdown(f"**Satz {idx_buf+1}**")
            # kleine Edit-Felder
            row["weight"] = cc2.number_input("kg", min_value=0.0, step=0.5, value=row["weight"], key=f"eb_w_{buffer_key}_{idx_buf}")
            row["reps"]   = cc3.number_input("Wdh", min_value=0, step=1, value=row["reps"], key=f"eb_r_{buffer_key}_{idx_buf}")
            row["rpe"]    = cc4.slider("RPE", 5.0, 10.0, float(row["rpe"]), 0.5, key=f"eb_rpe_{buffer_key}_{idx_buf}")
            if cc5.button("🗑️ Löschen", key=f"del_{buffer_key}_{idx_buf}"):
                del st.session_state["set_buffer"][buffer_key][idx_buf]
                st.info("Satz entfernt.")
                st.rerun()

        cbuf1, cbuf2 = st.columns(2)
        if cbuf1.button("🧹 Alle geplanten Sätze verwerfen", key=f"clear_{buffer_key}"):
            st.session_state["set_buffer"][buffer_key] = []
            st.info("Alle geplanten Sätze verworfen.")
            st.rerun()

        if cbuf2.button("💾 Geplante Sätze speichern", key=f"save_{buffer_key}"):
            today = date.today().isoformat()
            sub_today = df[(df["tag"] == tag) & (df["exercise"] == name) & (df["date"] == today)]
            next_set = 1 if sub_today.empty else int(sub_today["set"].max()) + 1

            # persistieren
            for k, row in enumerate(st.session_state["set_buffer"][buffer_key]):
                append_row({
                    "date": today,
                    "tag": tag,
                    "exercise": name,
                    "set": next_set + k,
                    "weight": float(row["weight"]),
                    "reps": int(row["reps"]),
                    "rpe": float(row["rpe"]),
                    "note": ""
                })

            # Buffer leeren, df aktualisieren
            st.session_state["set_buffer"][buffer_key] = []
            df = load_log()
            st.success("Sätze gespeichert.")

            # Auto-Pause starten (falls eingestellt)
            secs = int(st.session_state["auto_timer_seconds"])
            if secs > 0:
                st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=secs)

            st.rerun()

        # Undo-Button
        if st.button("↩️ Letzten gespeicherten Satz von heute zurücknehmen", key=f"undo_{buffer_key}"):
            undo_last_set_today(tag, name)
            df = load_log()
            st.rerun()

# ------------------------- PAUSEN-TIMER -------------------------
st.markdown("---")
st.subheader("⏱️ Pausen-Timer")

c1, c2, c3, c4, c5 = st.columns(5)
if c1.button("▶️ 60 s"):
    st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=60)
if c2.button("▶️ 90 s"):
    st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=90)
if c3.button("▶️ 120 s"):
    st.session_state["timer_end"] = datetime.utcnow() + timedelta(seconds=120)
if c4.button("+30 s") and st.session_state["timer_end"]:
    st.session_state["timer_end"] = st.session_state["timer_end"] + timedelta(seconds=30)
if c5.button("⏹ Stopp"):
    st.session_state["timer_end"] = None

remaining = 0
if st.session_state["timer_end"]:
    remaining = int((st.session_state["timer_end"] - datetime.utcnow()).total_seconds())
    if remaining <= 0:
        st.session_state["timer_end"] = None
        remaining = 0

st.markdown(
    f"<div style='font-size:48px; font-weight:700; text-align:center;'>{remaining}s</div>",
    unsafe_allow_html=True
)

# Auto-Refresh / Beep & Vibration bei 0
if st.session_state["timer_end"]:
    # State-Änderung erzwingen für Auto-Update
    st.experimental_set_query_params(_=datetime.utcnow().timestamp())
    st.experimental_rerun()
else:
    # Beep einmal pro Ablauf
    st.components.v1.html("""
    <audio id="beep" autoplay>
      <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=" type="audio/wav">
    </audio>
    <script>
      if (navigator.vibrate) navigator.vibrate([150,80,150]);
    </script>
    """, height=0)

# ------------------------- VERLAUF & EXPORT -------------------------
st.markdown("---")
with st.expander("📒 Letzte 30 Einträge"):
    hist = load_log()
    if hist.empty:
        st.info("Noch nichts geloggt.")
    else:
        st.dataframe(hist.tail(30), use_container_width=True)

# CSV-Export (Download)
hist = load_log()
csv_bytes = hist.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 CSV exportieren",
    data=csv_bytes,
    file_name=f"workout_log_{date.today().isoformat()}.csv",
    mime="text/csv"
)

st.caption("Tipps: Neutrale Griffe bei Reizung, kein harter Lockout, langsame Negative. "
           "Deload: Gewicht −30–40 %, Sätze −30–50 %, 3–4 Wdh. in Reserve.")