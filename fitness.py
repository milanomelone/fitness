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

# ------------------------- INIT SESSION STATE -------------------------
if "set_buffer" not in st.session_state:
    # key: f"{tag}:{exercise_name}" -> list of dicts [{"weight":..,"reps":..,"rpe":..}]
    st.session_state["set_buffer"] = {}

if "timer_end" not in st.session_state:
    st.session_state["timer_end"] = None

# ------------------------- HELPERS -------------------------
def sets_target(tp: str) -> int:
    return SETS_MAIN if tp == "main" else SETS_ISO

def load_log() -> pd.DataFrame:
    cols = ["date","tag","exercise","set","weight","reps","rpe","note"]
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            for c in cols:
                if c not in df.columns:
                    df[c] = None
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

def last_unit(df: pd.DataFrame, tag: str, ex_name: str):
    sub = df[(df["tag"] == tag) & (df["exercise"] == ex_name)]
    if sub.empty:
        return None, None
    dates = sorted(sub["date"].unique())
    d = dates[-1]
    return d, sub[sub["date"] == d]

def suggest_target(df: pd.DataFrame, tag: str, ex_name: str):
    # Config suchen
    lr = hr = inc = None
    tp = "main"
    for n, a, b, c, t in PLAN[tag]:
        if n == ex_name:
            lr, hr, inc, tp = a, b, c, t
            break

    hist_date, unit = last_unit(df, tag, ex_name)
    if unit is None or unit.empty:
        return {
            "msg": f"Erste Einheit: Startgewicht wählen. Ziel: {sets_target(tp)} Sätze im Bereich {lr}–{hr}.",
            "mode": "start", "lr": lr, "hr": hr, "tp": tp
        }

    last_w = float(unit["weight"].max())
    reps_list = [int(x) for x in unit["reps"].tolist() if pd.notnull(x)]
    all_top = (len(reps_list) >= 1) and all(r >= hr for r in reps_list)

    if all_top:
        return {
            "msg": f"Heute **+{inc} kg** → wieder unten starten ({lr}–{lr+1}). Letztes Mal ~{last_w:.1f} kg.",
            "mode": "add_weight","inc": inc,"base": last_w,"lr": lr,"hr": hr,"tp": tp
        }
    else:
        return {
            "msg": f"Heute **+1 Wdh./Satz** bei ~{last_w:.1f} kg, bis {hr} erreicht.",
            "mode": "add_rep","inc": 0.0,"base": last_w,"lr": lr,"hr": hr,"tp": tp
        }

def weeks_since(d: date) -> int:
    return max(1, (date.today() - d).days // 7 + 1)

def needs_deload(df: pd.DataFrame, block_start: date, every_weeks: int = 8, slip_tol: int = 2):
    # 1) Zeitbasiert
    time_flag = (weeks_since(block_start) % every_weeks == 0)
    # 2) Leistungsabfall (Reptotal bei gleicher Last)
    slips = 0
    for tag in ["A", "B"]:
        for (name, *_ ) in PLAN[tag]:
            sub = df[(df["tag"] == tag) & (df["exercise"] == name)]
            if sub.empty:
                continue
            days = sorted(sub["date"].unique())
            if len(days) < 2:
                continue
            d1, d2 = days[-2], days[-1]
            u1 = sub[sub["date"] == d1]
            u2 = sub[sub["date"] == d2]
            if u1.empty or u2.empty:
                continue
            w1 = float(u1["weight"].max())
            w2 = float(u2["weight"].max())
            if abs(w1 - w2) <= 0.5:
                if int(u2["reps"].sum()) < int(u1["reps"].sum()):
                    slips += 1
    fatigue_flag = (slips >= slip_tol)
    return (time_flag or fatigue_flag), {"time": time_flag, "fatigue": fatigue_flag, "slips": slips}

def ex_type(tag: str, ex_name: str) -> str:
    for n, lr, hr, inc, tp in PLAN[tag]:
        if n == ex_name:
            return tp
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
    tag = st.selectbox("Trainingstag", ["A", "B"])
    block_start = st.date_input("Block-Start (für Deload-Timer)", value=date.today())
    deload_every = st.slider("Deload alle X Wochen", 6, 10, 8)
    deload_drop = st.slider("Deload: Gewichtsreduzierung (%)", 20, 45, 35)
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
                if c not in df_new.columns:
                    df_new[c] = None
            df_all = pd.concat([df_old, df_new[cols]], ignore_index=True).drop_duplicates()
            save_log(df_all)
            st.success("CSV importiert – Fortschritt übernommen.")
        except Exception as e:
            st.error(f"Import fehlgeschlagen: {e}")

    st.markdown("---")
    with st.expander("⚠️ Datenverwaltung"):
        confirm = st.checkbox("Ich bestätige, dass ich alle Trainingsdaten löschen möchte.")
        if st.button("🗑️ Alle Trainingsdaten löschen", disabled=not confirm):
            save_log(pd.DataFrame(columns=["date","tag","exercise","set","weight","reps","rpe","note"]))
            st.success("Alle Daten wurden gelöscht.")

# ------------------------- HEADER -------------------------
st.title("🏋️ Progressions-Coach (A/B)")
st.write(f"**Heute:** {date.today().isoformat()}  ·  **Tag {tag}**")
st.caption("Regelwerk: Double-Progression (erst Wiederholungen hoch, dann Gewicht). Deload bei Woche X oder Leistungseinbruch.")

# ------------------------- DELOAD HINWEIS -------------------------
df = load_log()
flag, meta = needs_deload(df, block_start, deload_every, slip_tol=2)
if flag:
    reason = "Kalender" if meta["time"] else ""
    if meta["fatigue"]:
        reason += (" & " if reason else "") + f"Leistungsabfall ({meta['slips']})"
    st.warning(f"🔻 Deload empfohlen: {reason}. Vorschlag: ~{deload_drop}% weniger Gewicht, Sätze −30–50%, 3–4 Wdh. in Reserve.")

# ------------------------- ÜBUNGEN / BUFFER / LOG -------------------------
for i, (name, lr, hr, inc, tp) in enumerate(PLAN[tag], start=1):
    st.subheader(f"{i}. {name} · Ziel {lr}–{hr} Wdh.")
    sug = suggest_target(df, tag, name)
    st.markdown("**Coach:** " + sug["msg"])

    buffer_key = f"{tag}:{name}"
    if buffer_key not in st.session_state["set_buffer"]:
        st.session_state["set_buffer"][buffer_key] = []

    # Defaults
    _, last_u = last_unit(df, tag, name)
    default_w = float(last_u["weight"].max()) if (last_u is not None and not last_u.empty) else 0.0
    base_w = float(sug.get("base", default_w))

    # Eingaben + Satz in Buffer
    c1, c2, c3, c4 = st.columns([1.2, 0.9, 0.9, 1.3])
    w = c1.number_input("Gewicht (kg)", min_value=0.0, step=0.5, value=base_w, key=f"w_{tag}_{i}")
    r = c2.number_input("Wdh.", min_value=0, step=1, value=lr, key=f"r_{tag}_{i}")
    rpe = c3.slider("RPE", 5.0, 10.0, 8.0, 0.5, key=f"rpe_{tag}_{i}")
    add = c4.button("➕ Satz hinzufügen", key=f"add_{tag}_{i}")

    if add:
        st.session_state["set_buffer"][buffer_key].append({
            "weight": float(w), "reps": int(r), "rpe": float(rpe)
        })
        st.success(f"Satz geplant: {w:.1f} kg × {int(r)} (RPE {rpe})")

    # Status & geplante Sätze anzeigen
    target_sets = sets_target(sug.get("tp", tp))
    current_sets = len(st.session_state["set_buffer"][buffer_key])
    st.caption(f"Geplante Sätze im Buffer: {current_sets}/{target_sets}")

    if current_sets > 0:
        for idx_buf, row in enumerate(st.session_state["set_buffer"][buffer_key]):
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.0, 0.9, 0.9, 0.9, 0.8])
            cc1.markdown(f"**Satz {idx_buf+1}**")
            cc2.write(f"{row['weight']:.1f} kg")
            cc3.write(f"{row['reps']} Wdh.")
            cc4.write(f"RPE {row['rpe']:.1f}")
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
                    "weight": row["weight"],
                    "reps": row["reps"],
                    "rpe": row["rpe"],
                    "note": ""
                })

            st.session_state["set_buffer"][buffer_key] = []
            df = load_log()
            st.success("Sätze gespeichert.")
            st.rerun()

        # Optional: Undo für bereits gespeicherte Sätze von heute
        if st.button("↩️ Letzten **gespeicherten** Satz von heute zurücknehmen", key=f"undo_{buffer_key}"):
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

# Anzeige
st.markdown(
    f"<div style='font-size:48px; font-weight:700; text-align:center;'>{remaining}s</div>",
    unsafe_allow_html=True
)

# Auto-Refresh jede Sekunde solange Timer aktiv
if st.session_state["timer_end"]:
    st.experimental_set_query_params(_=datetime.utcnow().timestamp())  # kleine State-Änderung
    st.experimental_rerun()

# Beep & Vibration wenn abgelaufen
if remaining == 0 and st.session_state.get("just_beeped") != date.today().isoformat():
    st.components.v1.html("""
    <audio id="beep" autoplay>
      <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=" type="audio/wav">
    </audio>
    <script>
      if (navigator.vibrate) navigator.vibrate([150,80,150]);
    </script>
    """, height=0)
    st.session_state["just_beeped"] = date.today().isoformat()

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