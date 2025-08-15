import streamlit as st
import pandas as pd
from datetime import datetime, date
import os, json

st.set_page_config(page_title="Progressions-Coach A/B", layout="centered")

# ---------------- PLAN (deiner) ----------------
PLAN = {
  "A": [
    ("Schrägbankdrücken KH/LH", 6, 10, 2.5, "main"),
    ("Plate-Loaded Press",       8, 10, 2.5, "main"),
    ("Schulterpresse",           8, 10, 2.5, "main"),
    ("Kabel-Seitheben einarmig",12, 15, 1.0, "iso"),
    ("Fliegende (Kabel/Maschine)",12,15,1.0,"iso"),
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

# ---------------- Google Sheets (optional) ----------------
USE_SHEETS = bool(os.getenv("GSERVICE_JSON") and os.getenv("GSHEET_ID"))
if USE_SHEETS:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["GSERVICE_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["GSHEET_ID"])
    ws = sh.sheet1

CSV_PATH = "workout_log.csv"  # Fallback lokal (auf Streamlit Cloud nur temporär)

# ---------------- Helpers ----------------
def ex_type(name, tag):
    for n,lr,hr,inc,tp in PLAN[tag]:
        if n == name: return tp
    return "main"

def sets_target(tp):
    return SETS_MAIN if tp=="main" else SETS_ISO

def load_log() -> pd.DataFrame:
    cols = ["date","tag","exercise","set","weight","reps","rpe","note"]
    if USE_SHEETS:
        rows = ws.get_all_records()
        if not rows: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows)
        return df[cols] if set(cols).issubset(df.columns) else pd.DataFrame(columns=cols)
    else:
        if os.path.exists(CSV_PATH):
            return pd.read_csv(CSV_PATH)
        return pd.DataFrame(columns=cols)

def save_row(row: dict):
    if USE_SHEETS:
        ws.append_row([row[k] for k in ["date","tag","exercise","set","weight","reps","rpe","note"]])
    else:
        df = load_log()
        df.loc[len(df)] = row
        df.to_csv(CSV_PATH, index=False)

def last_unit(df, tag, ex_name):
    sub = df[(df["tag"]==tag) & (df["exercise"]==ex_name)]
    if sub.empty: return None, None
    dates = sorted(sub["date"].unique())
    d = dates[-1]
    return d, sub[sub["date"]==d]

def suggest_target(df, tag, ex_name):
    """Double Progression:
       - wenn alle Sätze beim letzten Mal >= high_reps -> Gewicht +inc
       - sonst: gleiche Last, heute +1 Wdh./Satz
    """
    # Suche Config
    lr=hr=inc=None
    for n, a, b, c, _ in PLAN[tag]:
        if n==ex_name: lr,hr,inc = a,b,c
    hist_date, unit = last_unit(df, tag, ex_name)
    if unit is None or unit.empty:
        return {"msg": f"Erste Einheit: wähle ein Startgewicht. Ziel {sets_target(ex_type(ex_name, tag))} Sätze im Bereich {lr}–{hr}.",
                "mode": "start", "lr":lr, "hr":hr}

    last_w = unit["weight"].max()
    reps = unit["reps"].tolist()
    all_top = all(r >= hr for r in reps) and len(reps) >= 1
    if all_top:
        return {"msg": f"Heute **+{inc} kg** → wieder unten starten ({lr}–{lr+1}). Letztes Mal ~{last_w} kg.",
                "mode":"add_weight","inc":inc,"base":last_w,"lr":lr,"hr":hr}
    else:
        return {"msg": f"Heute **+1 Wdh. je Satz** bei ~{last_w} kg, bis {hr} erreicht.",
                "mode":"add_rep","inc":0.0,"base":last_w,"lr":lr,"hr":hr}

def weeks_since(d: date):
    return max(1, (date.today() - d).days // 7 + 1)

def needs_deload(df, block_start: date, every_weeks: int = 8, slip_tol: int = 2):
    time_flag = (weeks_since(block_start) % every_weeks == 0)
    # Leistungsabfall-Check (vereinfachtes Reptotal bei gleicher Last)
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
            w1 = u1["weight"].max(); w2 = u2["weight"].max()
            if w1 and w2 and abs(float(w1) - float(w2)) <= 0.5:
                if u2["reps"].sum() < u1["reps"].sum():
                    slips += 1
    fatigue_flag = (slips >= slip_tol)
    return (time_flag or fatigue_flag), {"time":time_flag,"fatigue":fatigue_flag,"slips":slips}

# ---------------- UI ----------------
st.title("🏋️ Progressions-Coach (Tag A/B)")

# Sidebar Settings
with st.sidebar:
    st.header("⚙️ Einstellungen")
    tag = st.selectbox("Trainingstag", ["A","B"])
    block_start = st.date_input("Block-Start (für Deload-Timer)", value=date.today())
    deload_every = st.slider("Deload alle X Wochen", 6, 10, 8)
    deload_drop = st.slider("Deload: Gewichtsreduzierung (%)", 20, 45, 35)
    st.caption("Tipp: Bei Ellbogen-Reizung neutrale Griffe nutzen, kein harter Lockout, langsame Negative.")

df = load_log()

flag, meta = needs_deload(df, block_start, deload_every, slip_tol=2)
if flag:
    reason = "Kalender" if meta["time"] else ""
    if meta["fatigue"]:
        reason += (" & " if reason else "") + f"Leistungsabfall ({meta['slips']})"
    st.warning(f"🔻 Deload empfohlen: {reason}. Vorschlag: ~{deload_drop}% weniger Gewicht, Sätze −30–50%, 3–4 Wdh. in Reserve.")

st.write(f"**Heute:** {date.today().isoformat()}  ·  **Tag {tag}**")

for i,(name, lr, hr, inc, tp) in enumerate(PLAN[tag], start=1):
    st.subheader(f"{i}. {name} · Ziel {lr}–{hr} Wdh.")
    sug = suggest_target(df, tag, name)
    st.markdown("**Coach:** " + sug["msg"])

    # Eingabe + Log
    c1, c2, c3, c4 = st.columns([1.3,1,1,1.2])
    # Default-Gewicht aus letzter Einheit
    _, last_u = last_unit(df, tag, name)
    default_w = float(last_u["weight"].max()) if (last_u is not None and not last_u.empty) else 0.0
    base_w = sug.get("base", default_w)
    w = c1.number_input("Gewicht (kg)", min_value=0.0, step=0.5, value=float(base_w), key=f"w_{tag}_{i}")
    r = c2.number_input("Wdh.", min_value=0, step=1, value=lr, key=f"r_{tag}_{i}")
    rpe = c3.slider("RPE", 5.0, 10.0, 8.0, 0.5, key=f"rpe_{tag}_{i}")
    ok = c4.button("✔️ Satz loggen", key=f"log_{tag}_{i}")

    if ok:
        # determine next set number
        sub = df[(df["tag"]==tag) & (df["exercise"]==name) & (df["date"]==date.today().isoformat())]
        set_nr = 1 if sub.empty else int(sub["set"].max()) + 1
        row = {
            "date": date.today().isoformat(),
            "tag": tag,
            "exercise": name,
            "set": set_nr,
            "weight": float(w),
            "reps": int(r),
            "rpe": float(rpe),
            "note": ""
        }
        save_row(row)
        st.success(f"Geloggt: {name} – {w:.1f} kg × {int(r)} (RPE {rpe})")

st.divider()
with st.expander("📒 Letzte 30 Einträge"):
    hist = load_log()
    if hist.empty:
        st.info("Noch nichts geloggt.")
    else:
        st.dataframe(hist.tail(30), use_container_width=True)

st.caption("Regelwerk: Double-Progression (erst Reps hoch, dann Gewicht). Deload bei Woche X oder Leistungseinbruch.")p
