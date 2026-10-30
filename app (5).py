"""
Оқушылар жетістіктері — Streamlit қосымшасы
Іске қосу:  streamlit run app.py
"""
import io
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ----------------------------------------------------------------------------
# БАПТАУЛАР
# ----------------------------------------------------------------------------
FORMS = {
    "Қалалық деңгей": "1I9ZRAsSqWx4KMAQN1pCDfD3mq4MTlzWl7pbgPbwzApQ",
    "Облыстық деңгей": "1jH0n3Qq36Ci7uqns32SlChns20g7TuuCIzc2QGnVY5o",
    "Республикалық деңгей": "1Pe0e_ZDrwgDmzEIXLks1ZL7oiAEfxYOuu9NuItziN8A",
    "Халықаралық деңгей": "1ducnojoUjRYl3vrRfZZ_ZJHGUSyM_UHER7z7ymwjRVg",
}

# I = 1 орын, II = 2 орын, III = 3 орын, G = грамота, S = сертификат
LEVELS = {
    "Қалалық деңгей": {
        "sheet_id": "1OftTCq5aM38oJUcewv6C-WK7HkVbbZS_k1VPxb5OnGE", "gid": None,
        "points": {"I": 4, "II": 3, "III": 2, "G": 1, "S": 0}, "icon": "🏙️", "color": "#4C9AFF",
    },
    "Облыстық деңгей": {
        "sheet_id": "1r7MjVLST4U6RNJcsfjN0ZAHeRiZJY_QO0rh6BXf9kUI", "gid": "300940831",
        "points": {"I": 8, "II": 6, "III": 4, "G": 2, "S": 0}, "icon": "🏞️", "color": "#36B37E",
    },
    "Республикалық деңгей": {
        "sheet_id": "1UkZxzOG7n_JEz7qxoVqO7sHGiVB8q7CiKy3Sa9NWzQc", "gid": None,
        "points": {"I": 16, "II": 12, "III": 8, "G": 4, "S": 0}, "icon": "🇰🇿", "color": "#FFAB00",
    },
    "Халықаралық деңгей": {
        "sheet_id": "1qOtSd_YEi1hEz5c-ILWWFNrfpuzHOuxG3etdEhOMhGw", "gid": None,
        "points": {"I": 32, "II": 24, "III": 16, "G": 8, "S": 0}, "icon": "🌍", "color": "#FF5630",
    },
}

AWARDS = [
    ("I", "🥇 І орын"),
    ("II", "🥈 ІІ орын"),
    ("III", "🥉 ІІІ орын"),
    ("G", "📜 Грамота"),
    ("S", "📄 Сертификат"),
]
AWARD_LABELS = [label for _, label in AWARDS]


# ----------------------------------------------------------------------------
# ДЕРЕКТЕРДІ ЖҮКТЕУ ЖӘНЕ ӨҢДЕУ
# ----------------------------------------------------------------------------
def csv_url(sheet_id: str, gid: str | None) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid:
        url += f"&gid={gid}"
    return url


@st.cache_data(ttl=60, show_spinner=False)
def load_sheet(sheet_id: str, gid: str | None) -> pd.DataFrame:
    r = requests.get(csv_url(sheet_id, gid), timeout=20)
    r.raise_for_status()
    if "text/html" in r.headers.get("Content-Type", ""):
        raise PermissionError(
            "Кесте жабық. Google Sheets-те «Доступ → Все, у кого есть ссылка → Читатель» қойыңыз."
        )
    return pd.read_csv(io.BytesIO(r.content), dtype=str, encoding="utf-8")


def detect_columns(df: pd.DataFrame) -> dict:
    """Баған атауларын кілт сөздер арқылы анықтайды."""
    cols = {}
    for c in df.columns:
        s = str(c)
        low = s.lower()
        m = re.search(r"\[\s*диплом\s+([іi]{1,3})\s+орын", s, flags=re.I)
        if m:
            cols[{1: "I", 2: "II", 3: "III"}[len(m.group(1))]] = c
        elif re.search(r"\[\s*грамота", low):
            cols["G"] = c
        elif re.search(r"\[\s*сертификат", low):
            cols["S"] = c
        elif "аты" in low and "жөн" in low:
            cols["name"] = c
        elif low.strip().startswith("сынып"):
            cols["class"] = c
    for c in df.columns:  # суреттер сілтемесі бар баған
        if df[c].astype(str).str.contains("drive.google.com", na=False).any():
            cols["files"] = c
            break
    return cols


def clean_name(n) -> str:
    words = str(n if pd.notna(n) else "").split()
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


def clean_class(c) -> str:
    return re.sub(r"[^\w]", "", str(c if pd.notna(c) else "")).upper()


def name_key(name: str) -> str:
    # Тек тегі + аты: «Оралбекова Айгерім» және «Оралбекова Айгерім Канатовна» бір оқушы
    return " ".join(name.lower().replace("ё", "е").split()[:2])


def extract_ids(text) -> list:
    return re.findall(r"id=([\w-]+)", str(text if pd.notna(text) else ""))


def to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).clip(lower=0).astype(int)


def longest(x):
    return max(x, key=len)


def last_nonempty(x):
    return next((v for v in reversed(list(x)) if v), "")


def build_level_table(df: pd.DataFrame, level: str) -> pd.DataFrame:
    cols = detect_columns(df)
    if "name" not in cols:
        raise ValueError("«Аты-жөні» бағаны табылмады")
    pts = LEVELS[level]["points"]

    t = pd.DataFrame(index=df.index)
    t["Аты-жөні"] = df[cols["name"]].map(clean_name)
    t["Сынып"] = df[cols["class"]].map(clean_class) if "class" in cols else ""
    for key, label in AWARDS:
        t[label] = to_int(df[cols[key]]) if key in cols else 0
    t["files"] = df[cols["files"]].map(extract_ids) if "files" in cols else [[] for _ in range(len(df))]

    # Аты-жөнінде әріп жоқ жолдарды (тест жазбалары: «1», «2») алып тастаймыз
    t = t[t["Аты-жөні"].str.contains(r"[^\W\d_]", regex=True)]
    if t.empty:
        return pd.DataFrame(columns=["key", "Аты-жөні", "Сынып", *AWARD_LABELS, "Балл", "files"])

    t["key"] = t["Аты-жөні"].map(name_key)
    agg = {"Аты-жөні": longest, "Сынып": last_nonempty, "files": lambda x: sum(x, [])}
    agg.update({label: "sum" for label in AWARD_LABELS})
    t = t.groupby("key", as_index=False).agg(agg)

    t["Балл"] = sum(t[label] * pts[key] for key, label in AWARDS)
    return sort_rank(t)


def sort_rank(t: pd.DataFrame) -> pd.DataFrame:
    return t.sort_values(
        ["Балл", "🥇 І орын", "🥈 ІІ орын", "🥉 ІІІ орын"], ascending=False
    ).reset_index(drop=True)


def build_overall(tables: dict) -> pd.DataFrame:
    frames = []
    for level, t in tables.items():
        if not t.empty:
            frames.append(t.assign(Деңгей=level))
    if not frames:
        return pd.DataFrame()
    allx = pd.concat(frames, ignore_index=True)

    agg = {"Аты-жөні": longest, "Сынып": last_nonempty, "files": lambda x: sum(x, []), "Балл": "sum"}
    agg.update({label: "sum" for label in AWARD_LABELS})
    overall = allx.groupby("key", as_index=False).agg(agg)

    by_level = allx.pivot_table(index="key", columns="Деңгей", values="Балл", aggfunc="sum", fill_value=0)
    overall = overall.merge(by_level, left_on="key", right_index=True, how="left")
    for level in LEVELS:
        if level not in overall:
            overall[level] = 0
    return sort_rank(overall)


# ----------------------------------------------------------------------------
# КӨРСЕТУ
# ----------------------------------------------------------------------------
def show_table(t: pd.DataFrame, extra_cols=()):
    view = t.copy()
    view.insert(0, "№", range(1, len(view) + 1))
    view["Суреттер"] = view["files"].map(len)
    show_cols = ["№", "Аты-жөні", "Сынып", *AWARD_LABELS, *extra_cols, "Суреттер", "Балл"]
    st.dataframe(
        view[show_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Балл": st.column_config.ProgressColumn(
                "Балл", format="%d", min_value=0, max_value=int(max(view["Балл"].max(), 1))
            )
        },
    )


def podium(top3: pd.DataFrame):
    medals = ["🥇", "🥈", "🥉"]
    heights = [190, 140, 105]
    colors = ["#F5C518", "#C0C0C0", "#CD7F32"]
    order = [1, 0, 2]  # 2-орын | 1-орын | 3-орын
    cols = st.columns(3)
    for col, i in zip(cols, order):
        with col:
            if i >= len(top3):
                continue
            r = top3.iloc[i]
            st.markdown(
                f"""
                <div style="text-align:center">
                  <div style="font-size:64px;line-height:1">{medals[i]}</div>
                  <div style="font-weight:700;font-size:18px;margin-top:6px">{r['Аты-жөні']}</div>
                  <div style="opacity:.7">{r['Сынып']} сынып</div>
                  <div style="font-size:22px;font-weight:800;margin:4px 0 8px">{int(r['Балл'])} балл</div>
                  <div style="height:{heights[i]}px;background:{colors[i]};border-radius:12px 12px 0 0;
                              display:flex;align-items:center;justify-content:center;
                              font-size:56px;font-weight:900;color:white;
                              text-shadow:0 2px 6px rgba(0,0,0,.35)">{i + 1}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def show_diploma_images(top3: pd.DataFrame):
    medals = ["🥇", "🥈", "🥉"]
    for i, (_, r) in enumerate(top3.iterrows()):
        ids = list(dict.fromkeys(r["files"]))  # қайталауларсыз
        with st.expander(f"{medals[i]} {r['Аты-жөні']} — дипломдар суреттері ({len(ids)})", expanded=i == 0):
            if not ids:
                st.info("Сурет жүктелмеген.")
                continue
            img_cols = st.columns(4)
            for j, fid in enumerate(ids):
                with img_cols[j % 4]:
                    st.image(f"https://drive.google.com/thumbnail?id={fid}&sz=w600", use_container_width=True)
                    st.markdown(f"[Ашу ↗](https://drive.google.com/open?id={fid})")


def tab_forms():
    st.subheader("📝 Жетістіктерді тіркеу формалары")
    st.write("Деңгейді таңдап, Google форманы толтырыңыз:")
    cols = st.columns(2)
    for i, (level, form_id) in enumerate(FORMS.items()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {LEVELS[level]['icon']} {level}")
                p = LEVELS[level]["points"]
                st.caption(f"1 орын — {p['I']} · 2 орын — {p['II']} · 3 орын — {p['III']} · грамота — {p['G']} балл")
                st.link_button(
                    "Форманы ашу →",
                    f"https://docs.google.com/forms/d/{form_id}/viewform",
                    use_container_width=True,
                    type="primary",
                )


def tab_results():
    c1, c2 = st.columns([4, 1])
    c1.subheader("📊 Нәтижелер")
    if c2.button("🔄 Жаңарту", use_container_width=True):
        st.cache_data.clear()

    tables = {}
    with st.spinner("Кестелер жүктелуде..."):
        for level, cfg in LEVELS.items():
            try:
                tables[level] = build_level_table(load_sheet(cfg["sheet_id"], cfg["gid"]), level)
            except Exception as e:
                tables[level] = None
                tables[f"_err_{level}"] = str(e)

    sub_tabs = st.tabs([f"{LEVELS[l]['icon']} {l}" for l in LEVELS])
    for sub, level in zip(sub_tabs, LEVELS):
        with sub:
            p = LEVELS[level]["points"]
            st.caption(
                f"Балл: 🥇 1 орын — **{p['I']}**, 🥈 2 орын — **{p['II']}**, "
                f"🥉 3 орын — **{p['III']}**, 📜 грамота — **{p['G']}**, сертификат — {p['S']}"
            )
            t = tables[level]
            if t is None:
                st.error(f"Кестені жүктеу мүмкін болмады: {tables[f'_err_{level}']}")
                continue
            if t.empty:
                st.info("Әзірге жауаптар жоқ.")
                continue
            m = st.columns(4)
            m[0].metric("Оқушылар", len(t))
            m[1].metric("🥇 І орын", int(t["🥇 І орын"].sum()))
            m[2].metric("🥈 ІІ орын", int(t["🥈 ІІ орын"].sum()))
            m[3].metric("🥉 ІІІ орын", int(t["🥉 ІІІ орын"].sum()))
            show_table(t)

    # ------------------------- ҮЗДІК 10 ---------------------------------
    st.divider()
    st.header("🏆 Үздік 10 оқушы (барлық деңгей бойынша)")
    ok = {k: v for k, v in tables.items() if not k.startswith("_err_") and v is not None}
    overall = build_overall(ok)
    if overall.empty:
        st.info("Деректер жоқ.")
        return
    top10 = overall.head(10)

    podium(top10.head(3))
    st.write("")

    show_table(top10, extra_cols=list(LEVELS))

    # 1-график: деңгейлер бойынша балл
    long = top10.melt(id_vars=["Аты-жөні"], value_vars=list(LEVELS), var_name="Деңгей", value_name="Балл")
    fig = px.bar(
        long, x="Балл", y="Аты-жөні", color="Деңгей", orientation="h",
        color_discrete_map={l: LEVELS[l]["color"] for l in LEVELS},
        title="Үздік 10: деңгейлер бойынша балл",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, legend_title_text="", height=480)
    st.plotly_chart(fig, use_container_width=True)

    g1, g2 = st.columns(2)
    # 2-график: 1, 2, 3 орындар саны
    places = top10.melt(
        id_vars=["Аты-жөні"], value_vars=["🥇 І орын", "🥈 ІІ орын", "🥉 ІІІ орын"],
        var_name="Орын", value_name="Саны",
    )
    fig2 = px.bar(
        places, x="Аты-жөні", y="Саны", color="Орын", barmode="group",
        color_discrete_map={"🥇 І орын": "#F5C518", "🥈 ІІ орын": "#A9A9A9", "🥉 ІІІ орын": "#CD7F32"},
        title="1, 2, 3 орындар саны",
    )
    fig2.update_layout(legend_title_text="", xaxis_title="", xaxis_tickangle=-35)
    g1.plotly_chart(fig2, use_container_width=True)

    # 3-график: барлық марапаттардың үлесі
    totals = overall[AWARD_LABELS].sum()
    fig3 = go.Figure(go.Pie(
        labels=totals.index, values=totals.values, hole=0.45,
        marker_colors=["#F5C518", "#A9A9A9", "#CD7F32", "#4C9AFF", "#C1C7D0"],
    ))
    fig3.update_layout(title="Барлық марапаттар үлесі")
    g2.plotly_chart(fig3, use_container_width=True)

    st.subheader("🖼️ Жүлдегерлердің дипломдары")
    show_diploma_images(top10.head(3))

    csv = top10.drop(columns=["key", "files"]).to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Үздік 10 (CSV)", csv, "top10.csv", "text/csv")


def main():
    st.set_page_config(page_title="Оқушылар жетістіктері", page_icon="🏆", layout="wide")
    st.title("🏆 Оқушылар жетістіктері")
    t1, t2 = st.tabs(["📝 Формалар", "📊 Нәтижелер"])
    with t1:
        tab_forms()
    with t2:
        tab_results()


if __name__ == "__main__":
    main()
