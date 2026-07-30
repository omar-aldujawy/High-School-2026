import re
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# 0. الإعدادات العامة وتنسيق الواجهة (RTL)
# =============================================================================
TARGET_YEAR = 2026

st.set_page_config(
    page_title=f"نتيجة الطلاب {TARGET_YEAR}",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# تطبيق اتجاه الكتابة من اليمين لليسار (RTL)
st.markdown(
    """
    <style>
    .stApp, .stMarkdown, .stMetric, h1, h2, h3, p, label { direction: rtl; text-align: right; }
    [data-testid="stMetricValue"] { direction: ltr; }
    .footer-text {
        text-align: center;
        padding: 15px;
        font-weight: bold;
        color: #555555;
        border-top: 1px solid #e6e6e6;
        margin-top: 30px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

APP_DIR = Path(__file__).parent
RESULTS_FILE = APP_DIR / "all_students_results.csv.gz"
DATA_2026_FILE = APP_DIR / "2026.csv"
SUMMARY_FILE = APP_DIR / "summary_by_year.csv"


# =============================================================================
# 1. الدوال المساعدة ومعالجة البيانات
# =============================================================================
def normalize_arabic(text: str) -> str:
    """توحيد الأشكال المختلفة للحروف العربية لضمان مرونة البحث."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    return text


COLUMN_KEYWORDS = {
    "seating_no": ["جلوس", "seating_no", "seating"],
    "name": ["اسم", "name"],
    "total_degree": ["مجموع", "الدرجة", "الدرجه", "total_degree", "degree"],
    "student_case_desc": ["حالة الطالب", "الحالة", "student_case_desc", "status"],
}


def smart_rename(df: pd.DataFrame, keyword_map: dict) -> tuple[pd.DataFrame, dict]:
    """إعادة تسمية الأعمدة ذكياً بالكلمات المفتاحية."""
    rename_map = {}
    if any("?" in str(col) for col in df.columns[:3]):
        cols = list(df.columns)
        rename_map[cols[0]] = "seating_no"
        rename_map[cols[1]] = "name"
        rename_map[cols[2]] = "total_degree"
        return df.rename(columns=rename_map), rename_map

    for new_name, keywords in keyword_map.items():
        if new_name in df.columns:
            continue
        for col in df.columns:
            if any(kw in str(col) for kw in keywords):
                rename_map[col] = new_name
                break

    return df.rename(columns=rename_map), rename_map


def get_student_status(row: pd.Series) -> str:
    """تحديد حالة الطالب بدقة (ساقط - دور تاني - ناجح)."""
    case_desc = str(
        row.get("student_case_desc", row.get("status", row.get("original_status", "")))
    ).strip()

    # 1. البحث عن الدور الثاني أولاً
    if any(kw in case_desc for kw in ["ثان", "تان", "ثاني", "تاني", "دور 2"]):
        return "⚠️ دور تاني"

    # 2. شرط أقل من 50% ساقط
    pct = float(row.get("percentage", 0))
    if pct < 50 or any(kw in case_desc for kw in ["راسب", "ساقط"]):
        return "🔴 ساقط"

    # 3. الناجح
    return "✅ ناجح"


def render_cyan_percentage_chart(df, score_column):
    """دالة رسم بطاقة إحصائيات توزيع النسب المئوية بتصميم نيون لبني مضبوطة الاتجاهات."""
    total_count = len(df)

    bins = [-1, 50, 55, 60, 65, 70, 75, 80, 85, 90, 101]
    labels = [
        "below-50%",
        "50-55%",
        "55-60%",
        "60-65%",
        "65-70%",
        "70-75%",
        "75-80%",
        "80-85%",
        "85-90%",
        "+90%",
    ]

    df_copy = df.copy()
    df_copy["range"] = pd.cut(
        df_copy[score_column], bins=bins, labels=labels, right=False
    )
    counts = df_copy["range"].value_counts().reindex(labels, fill_value=0)

    css = """
    <style>
    .stats-card-cyan {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 24px;
        padding: 28px;
        color: #f8fafc;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(56, 189, 248, 0.05);
        max-width: 650px;
        margin: 20px auto;
        direction: rtl;
        box-sizing: border-box;
    }
    .stats-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 25px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        direction: rtl;
    }
    .stats-title {
        font-size: 20px;
        font-weight: 700;
        color: #38bdf8;
    }
    .stats-total {
        font-size: 13px;
        color: #94a3b8;
        background: rgba(255, 255, 255, 0.05);
        padding: 4px 12px;
        border-radius: 12px;
    }
    .stat-row-cyan {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
        direction: rtl;
        gap: 10px;
    }
    .stat-label-cyan {
        font-size: 13px;
        font-weight: 600;
        color: #cbd5e1;
        width: 90px;
        text-align: right;
        direction: ltr;
    }
    .bar-container-cyan {
        flex-grow: 1;
        background-color: #090d16;
        height: 10px;
        border-radius: 20px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        justify-content: flex-start;
        direction: ltr;
    }
    .bar-fill-cyan {
        background: linear-gradient(90deg, #4facfe, #00f2fe);
        height: 100%;
        border-radius: 20px;
        box-shadow: 0 0 8px rgba(79, 172, 254, 0.6);
    }
    .stat-val-box {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 130px;
        justify-content: flex-end;
        direction: ltr;
    }
    .stat-count {
        font-size: 13px;
        font-weight: 700;
        color: #ffffff;
    }
    .stat-pct-tag {
        font-size: 11px;
        font-weight: 600;
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        padding: 2px 8px;
        border-radius: 8px;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }
    </style>
    """

    html_content = f"""
    {css}
    <div class="stats-card-cyan">
        <div class="stats-header">
            <div class="stats-title">توزيع النسب المئوية</div>
            <div class="stats-total">الإجمالي: {total_count:,}</div>
        </div>
    """

    for label in reversed(labels):
        count = counts[label]
        pct = (count / total_count * 100) if total_count > 0 else 0

        if count >= 1000:
            formatted_count = f"{count/1000:.1f}K+"
        else:
            formatted_count = str(count)

        html_content += f"""
        <div class="stat-row-cyan">
            <div class="stat-label-cyan">{label}</div>
            <div class="bar-container-cyan">
                <div class="bar-fill-cyan" style="width: {pct}%;"></div>
            </div>
            <div class="stat-val-box">
                <span class="stat-count">{formatted_count}</span>
                <span class="stat-pct-tag">{pct:.2f}%</span>
            </div>
        </div>
        """

    html_content += "</div>"

    st.markdown(html_content, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_results() -> pd.DataFrame:
    if not RESULTS_FILE.exists():
        return pd.DataFrame()

    needed_cols = [
        "seating_no",
        "name",
        "total_degree",
        "max_degree",
        "percentage",
        "rank",
    ]

    try:
        df = pd.read_csv(
            RESULTS_FILE,
            usecols=lambda c: c in needed_cols
            or c in ["year", "student_case_desc", "status"],
            dtype={"seating_no": str},
        )
    except Exception:
        df = pd.read_csv(RESULTS_FILE)

    df["seating_no"] = df["seating_no"].astype(str).str.strip()

    if "year" in df.columns:
        df = df[df["year"] == TARGET_YEAR].copy()

    # --- دمج بيانات حالة الطالب من ملف 2026.csv ---
    if DATA_2026_FILE.exists():
        try:
            try:
                data_2026 = pd.read_csv(
                    DATA_2026_FILE,
                    encoding="utf-8",
                    usecols=["seating_no", "student_case_desc"],
                )
            except Exception:
                data_2026 = pd.read_csv(
                    DATA_2026_FILE,
                    encoding="cp1256",
                    usecols=["seating_no", "student_case_desc"],
                )

            data_2026, _ = smart_rename(data_2026, COLUMN_KEYWORDS)

            if (
                "seating_no" in data_2026.columns
                and "student_case_desc" in data_2026.columns
            ):
                data_2026["seating_no"] = (
                    data_2026["seating_no"].astype(str).str.strip()
                )
                case_map = data_2026.set_index("seating_no")[
                    "student_case_desc"
                ].to_dict()
                df["student_case_desc"] = (
                    df["seating_no"]
                    .map(case_map)
                    .fillna(df.get("student_case_desc", "غير محدد"))
                )
        except Exception:
            pass

    df["normalized_name"] = df["name"].apply(normalize_arabic)
    df["final_status"] = df.apply(get_student_status, axis=1)

    return df


results = load_results()

st.title(f"🎓 تطبيق نتيجة الطلاب - سنة {TARGET_YEAR}")

if results.empty:
    st.error(
        f"الملف `all_students_results.csv.gz` غير موجود أو لا يحتوي على بيانات لسنة {TARGET_YEAR}."
    )
    st.stop()

# إنشاء التبويبات الأساسية للواجهة
tab_search, tab_board, tab_stats, tab_compare_years = st.tabs([
    "🔍 البحث عن نتيجة",
    "🏆 لوحة الشرف",
    "📊 إحصائيات السنة",
    "📈 مقارنة مع السنين السابقة",
])

# =============================================================================
# التبويب الأول: البحث عن نتيجة طالب
# =============================================================================
with tab_search:
    st.subheader(f"ابحث برقم الجلوس أو بالاسم (سنة {TARGET_YEAR})")

    query = st.text_input(
        "رقم الجلوس أو جزء من الاسم",
        placeholder="مثال: 12345, عمر الدجوي / محمد شادي ",
        key="search_query",
    )

    if query:
        query = query.strip()
        is_seating_match = results["seating_no"].str.contains(
            query, case=False, na=False
        )

        normalized_query = normalize_arabic(query)
        words = [re.escape(w) for w in normalized_query.split() if w]
        regex_pattern = ".*".join(words)

        is_name_match = results["normalized_name"].str.contains(
            regex_pattern, case=False, na=False, regex=True
        )
        matches = results[is_seating_match | is_name_match]

        if matches.empty:
            st.warning("لا توجد نتيجة مطابقة. تأكد من رقم الجلوس أو الاسم.")
        else:
            for _, row in matches.sort_values("rank").iterrows():
                status = row["final_status"]
                with st.container(border=True):
                    st.markdown(f"### {row['name']}")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("رقم الجلوس", row["seating_no"])
                    c2.metric(
                        "المجموع",
                        f"{int(row['total_degree'])} / {int(row['max_degree'])}",
                    )
                    c3.metric("النسبة", f"{row['percentage']}%")
                    c4.metric("الترتيب", f"#{int(row['rank'])}")
                    c5.metric("الحالة", status)
    else:
        st.info("اكتب رقم الجلوس أو الاسم في الخانة أعلاه للبدء بالبحث.")

# =============================================================================
# التبويب الثاني: لوحة الشرف
# =============================================================================
with tab_board:
    st.subheader(f"لوحة الشرف - أوائل سنة {TARGET_YEAR}")

    top_n = st.slider(
        "عدد الأسماء المعروضة", min_value=10, max_value=100, value=100, step=10
    )
    board_df = results.sort_values("rank").head(top_n).copy()
    board_df["الحالة"] = board_df["final_status"]

    board = board_df[
        [
            "rank",
            "seating_no",
            "name",
            "total_degree",
            "max_degree",
            "percentage",
            "الحالة",
        ]
    ].rename(
        columns={
            "rank": "الترتيب",
            "seating_no": "رقم الجلوس",
            "name": "الاسم",
            "total_degree": "المجموع",
            "max_degree": "المجموع الكلي",
            "percentage": "النسبة %",
        }
    )

    medal = {1: "🥇", 2: "🥈", 3: "🥉"}
    board.insert(0, "", board["الترتيب"].map(medal).fillna(""))
    st.dataframe(board, use_container_width=True, hide_index=True)

    csv_bytes = board.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ تحميل لوحة الشرف (CSV)",
        data=csv_bytes,
        file_name=f"honor_board_{TARGET_YEAR}.csv",
        mime="text/csv",
    )

# =============================================================================
# التبويب الثالث: إحصائيات السنة
# =============================================================================
with tab_stats:
    col_stat1, col_stat2 = st.columns(2)

    with col_stat1:
        fig_hist = px.histogram(
            results,
            x="total_degree",
            nbins=30,
            title=f"<b>توزيع المجموع الكلي للطلاب لسنة {TARGET_YEAR}</b>",
            labels={"total_degree": "المجموع الكلي", "count": "عدد الطلاب"},
            color_discrete_sequence=["#1F77B4"],
        )
        fig_hist.update_traces(
            hovertemplate="<b>المجموع:</b> %{x}<br><b>عدد الطلاب:</b> %{y}<extra></extra>"
        )
        fig_hist.update_layout(height=400)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_stat2:
        status_df = results["final_status"].value_counts().reset_index()
        status_df.columns = ["الحالة", "count"]

        fig_pass_pie = px.pie(
            status_df,
            values="count",
            names="الحالة",
            title=f"<b>توزيع حالات الطلاب لسنة {TARGET_YEAR}</b>",
            hole=0.4,
            color="الحالة",
            color_discrete_map={
                "✅ ناجح": "#2E7D32",
                "⚠️ دور تاني": "#F57C00",
                "🔴 ساقط": "#D32F2F",
            },
        )
        fig_pass_pie.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>الحالة:</b> %{label}<br><b>العدد:</b> %{value:,}<br><b>النسبة:</b> %{percent}",
        )
        fig_pass_pie.update_layout(height=400)
        st.plotly_chart(fig_pass_pie, use_container_width=True)

    st.markdown("---")
    # عرض بطاقة توزيع النسب المئوية المخصصة
    render_cyan_percentage_chart(results, score_column="percentage")

# =============================================================================
# التبويب الرابع: مقارنة مع السنين السابقة
# =============================================================================
with tab_compare_years:
    st.subheader("📈 مقارنة توزيع النسب المئوية للطلاب (2024 VS 2025 VS 2026)")

    YEARS = [2024, 2025, 2026]
    CONFIG = {
        2024: {
            "file": "mat_2024.csv",
            "max_degree": 410,
            "color": "#636EFA",
            "encoding": "utf-8",
        },
        2025: {
            "file": "mat_2025.csv",
            "max_degree": 320,
            "color": "#EF553B",
            "encoding": "utf-8",
        },
        2026: {
            "file": "mat_2026.csv",
            "max_degree": 320,
            "color": "#00CC96",
            "encoding": "utf-8",
        },
    }

    @st.cache_data(ttl=3600)
    def load_and_bin_years():
        binned_data = {}
        bins = list(range(0, 101, 10))

        for year in YEARS:
            cfg = CONFIG[year]
            file_path = APP_DIR / cfg["file"]

            if not file_path.exists():
                continue

            try:
                try:
                    df = pd.read_csv(file_path, encoding=cfg["encoding"])
                except Exception:
                    df = pd.read_csv(file_path, encoding="cp1256")

                df, _ = smart_rename(df, COLUMN_KEYWORDS)

                if "total_degree" in df.columns:
                    count_col = df.columns[1] if len(df.columns) > 1 else None
                    pcts = (df["total_degree"] / cfg["max_degree"]) * 100

                    if (
                        count_col
                        and df[count_col].dtype in ["int64", "float64"]
                        and count_col != "name"
                    ):
                        df["pct"] = pcts
                        df["bin"] = pd.cut(df["pct"], bins=bins, include_lowest=True)
                        binned_series = df.groupby("bin", observed=False)[
                            count_col
                        ].sum()
                    else:
                        binned_series = (
                            pd.cut(pcts, bins=bins, include_lowest=True)
                            .value_counts()
                            .sort_index()
                        )

                    binned_data[year] = binned_series
            except Exception:
                pass

        return binned_data

    binned = load_and_bin_years()

    if binned and len(binned) > 0:
        available_years = list(binned.keys())
        ref_year = available_years[0]
        ranges = [
            f"{int(i.left)}–{int(i.right)}" for i in binned[ref_year].index
        ]

        fig = go.Figure(
            data=[
                go.Bar(
                    name=str(year),
                    x=ranges,
                    y=binned[year].values,
                    marker_color=CONFIG[year]["color"],
                    hovertemplate=(
                        f"{year}<br>النسبة: %{{x}}%<br>عدد الطلاب:"
                        " %{y:,}<extra></extra>"
                    ),
                )
                for year in available_years
            ]
        )

        fig.update_layout(
            title="<b>2024 VS 2025 VS 2026</b>",
            xaxis_title="نطاق النسبة المئوية (%)",
            yaxis_title="عدد الطلاب",
            barmode="group",
            template="plotly_white",
            hovermode="x",
            height=500,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(
            "ملفات المقارنة (`mat_2024.csv`, `mat_2025.csv`, `mat_2026.csv`) غير"
            " متوفرة أو بها مشكلة في التنسيق لعرض المقارنة."
        )

# =============================================================================
# الحقوق والتوقيع (Footer)
# =============================================================================
st.caption(f"مصدر البيانات: نتائج طلاب سنة {TARGET_YEAR}")
st.markdown(
    "<div class='footer-text'>مع تحيات<br>MDKLi Team @2026</div>",
    unsafe_allow_html=True,
)




# streamlit run streamlit_app_v2.py