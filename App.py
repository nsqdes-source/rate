import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
import json
from datetime import datetime
import google.generativeai as genai

# استدعاء دالة توليد الـ PDF
from pdf_generator import generate_pdf_report

# ---------------------------------------------------------
# الثوابت المعتمدة (المفتاح التلقائي للذكاء الاصطناعي)
# ---------------------------------------------------------
DEFAULT_GEMINI_KEY = "AQ.Ab8RN6K5XWtbGxReZLsdHQiXi3VAiJDzXhPr5EQ8Qa_P7jskCQ"

# ---------------------------------------------------------
# 0. إعدادات الصفحة وقاعدة البيانات
# ---------------------------------------------------------
st.set_page_config(
    page_title="تصنيف شركات العمرة",
    page_icon="🕋",
    layout="wide"
)

def init_db():
    conn = sqlite3.connect("umrah_evaluations.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eval_date TEXT,
            company_name TEXT,
            final_score REAL,
            tier TEXT,
            score_packages REAL,
            score_exp REAL,
            score_prog REAL,
            incentives REAL,
            penalties REAL,
            raw_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_evaluation(company_name, results):
    conn = sqlite3.connect("umrah_evaluations.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO evaluations 
        (eval_date, company_name, final_score, tier, score_packages, score_exp, score_prog, incentives, penalties, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        company_name,
        results['final_score'],
        results['tier'],
        results['score_packages'],
        results['score_exp'],
        results['score_prog'],
        results['total_incentives'],
        results['penalties'],
        json.dumps(results['raw_data'])
    ))
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 1. محرك التقييم الحسابي
# ---------------------------------------------------------
def calculate_umrah_company_score(data, lang="العربية"):
    # أ. تنوع باقات الخدمات (15%)
    total_entry = data.get("total_entry_pilgrims", 0) or 1
    p_luxury = min(1.0, (data.get("luxury_pilgrims", 0) or 0) / total_entry) * 7.0
    p_medium = min(1.0, (data.get("medium_pilgrims", 0) or 0) / total_entry) * 5.0
    p_economy = min(1.0, (data.get("economy_pilgrims", 0) or 0) / total_entry) * 3.0
    score_packages = p_luxury + p_medium + p_economy

    # ب. تجربة المعتمر وجودة الخدمة والمخالفات التشغيلية (45%)
    p_satisfaction = ((data.get("satisfaction_score_pct", 0.0) or 0.0) / 100.0) * 10.0
    p_quality = ((data.get("service_quality_pct", 0.0) or 0.0) / 100.0) * 5.0
    
    total_complaints = data.get("total_complaints", 0) or 0
    closed_complaints = data.get("closed_complaints", 0) or 0
    p_complaints = (closed_complaints / total_complaints * 10.0) if total_complaints > 0 else 10.0

    total_departing = data.get("total_departing_pilgrims", 0) or 1
    p_enrichment = min(1.0, (data.get("enrichment_beneficiaries", 0) or 0) / total_departing) * 10.0

    total_visited = data.get("total_visited_pilgrims", 0) or 0
    unaffected = data.get("unaffected_pilgrims", 0) or 0
    p_compliance = (unaffected / total_visited * 10.0) if total_visited > 0 else 10.0

    score_exp = p_satisfaction + p_quality + p_complaints + p_enrichment + p_compliance

    # ج. الالتزام بالبرنامج (40%)
    total_entry_rec = data.get("total_entry_records", 0) or 1
    p_entry_match = ((data.get("matched_entry_records", 0) or 0) / total_entry_rec) * 10.0
    
    p_arr_boarding = min(1.0, (data.get("arrival_boarding_orders", 0) or 0) / total_entry) * 5.0
    p_inter_boarding = min(1.0, (data.get("intercity_boarding_orders", 0) or 0) / total_departing) * 5.0
    p_dep_boarding = min(1.0, (data.get("departure_boarding_orders", 0) or 0) / total_departing) * 5.0

    total_exit_rec = data.get("total_exit_records", 0) or 1
    p_exit_match = ((data.get("matched_exit_records", 0) or 0) / total_exit_rec) * 10.0

    total_housing = data.get("total_housing_programs", 0) or 1
    p_housing = ((data.get("confirmed_housing", 0) or 0) / total_housing) * 5.0

    score_prog = p_entry_match + p_arr_boarding + p_inter_boarding + p_dep_boarding + p_exit_match + p_housing

    # مجموع النتيجة الأساسية (100%)
    base_score = score_packages + score_exp + score_prog

    # د. المحفزات (Incentives)
    gift_points = ((data.get("economy_gifts", 0) or 0) * 1) + \
                  ((data.get("medium_gifts", 0) or 0) * 4) + \
                  ((data.get("luxury_gifts", 0) or 0) * 20)
    gift_incentive = min(5.0, (gift_points / 8000.0) * 5.0)

    umrah_plus_points = (data.get("umrah_plus_beneficiaries", 0) or 0) * 2
    umrah_plus_incentive = min(10.0, (umrah_plus_points / 2000.0) * 10.0)

    award_incentive = 5.0 if data.get("has_ministry_award", False) else 0.0

    total_incentives = gift_incentive + umrah_plus_incentive + award_incentive

    # هـ. الخصومات (Penalties)
    severe_violation_penalty = 5.0 if data.get("has_severe_violation", False) else 0.0

    # النتيجة النهائية
    final_score = min(100.0, max(0.0, base_score + total_incentives - severe_violation_penalty))

    if lang == "العربية":
        if final_score >= 90:
            tier = "الفئة الماسية (Class A)"
        elif final_score >= 75:
            tier = "الفئة الذهبية (Class B)"
        elif final_score >= 60:
            tier = "الفئة الفضية (Class C)"
        else:
            tier = "غير معتمد / يحتاج تحسين"
    else:
        if final_score >= 90:
            tier = "Diamond Tier (Class A)"
        elif final_score >= 75:
            tier = "Gold Tier (Class B)"
        elif final_score >= 60:
            tier = "Silver Tier (Class C)"
        else:
            tier = "Unaccredited / Needs Improvement"

    return {
        "final_score": round(final_score, 2),
        "base_score": round(base_score, 2),
        "score_packages": round(score_packages, 2),
        "score_exp": round(score_exp, 2),
        "score_prog": round(score_prog, 2),
        "gift_incentive": round(gift_incentive, 2),
        "umrah_plus_incentive": round(umrah_plus_incentive, 2),
        "award_incentive": round(award_incentive, 2),
        "total_incentives": round(total_incentives, 2),
        "incentives": round(total_incentives, 2),
        "severe_violation_penalty": round(severe_violation_penalty, 2),
        "penalties": round(severe_violation_penalty, 2),
        "tier": tier,
        "raw_data": data
    }

# ---------------------------------------------------------
# 2. وكيل الذكاء الاصطناعي للاستشارات (عبر Google Gemini)
# ---------------------------------------------------------
def generate_ai_advisor_report(results, api_key=DEFAULT_GEMINI_KEY, language="العربية"):
    raw = results['raw_data']
    warnings = []
    actions = []

    if language == "العربية":
        if raw.get('has_severe_violation', False):
            warnings.append("🚨 **خصم مباشر (-5%):** تم رصد مخالفة جسيمة خلال الشهر.")
        
        total_visited = raw.get('total_visited_pilgrims', 0) or 0
        unaffected = raw.get('unaffected_pilgrims', 0) or 0
        if total_visited > 0 and (unaffected / total_visited) < 0.95:
            affected_cnt = total_visited - unaffected
            warnings.append(f"⚠️ **مخالفات تشغيلية:** تم رصد تأثر {affected_cnt} معتمر بمخالفات أثناء الزيارات الميدانية.")

        if raw.get('umrah_plus_beneficiaries', 0) < 1000:
            pts_needed = 1000 - raw.get('umrah_plus_beneficiaries', 0)
            gain = round((pts_needed * 2 / 2000) * 10, 1)
            actions.append(f"💡 **تفعيل مبادرة (عمرة+):** تسجيل {pts_needed} معتمر إضافي يمنحك زيادة تحفيزية قدرها **+{gain}%**.")
    else:
        if raw.get('has_severe_violation', False):
            warnings.append("🚨 **Direct Penalty (-5%):** A severe violation was recorded during the month.")
        
        total_visited = raw.get('total_visited_pilgrims', 0) or 0
        unaffected = raw.get('unaffected_pilgrims', 0) or 0
        if total_visited > 0 and (unaffected / total_visited) < 0.95:
            affected_cnt = total_visited - unaffected
            warnings.append(f"⚠️ **Operational Violations:** {affected_cnt} pilgrims were affected by field inspection violations.")

        if raw.get('umrah_plus_beneficiaries', 0) < 1000:
            pts_needed = 1000 - raw.get('umrah_plus_beneficiaries', 0)
            gain = round((pts_needed * 2 / 2000) * 10, 1)
            actions.append(f"💡 **Activate (Umrah+) Initiative:** Registering {pts_needed} additional pilgrims grants an incentive bonus of **+{gain}%**.")

    if api_key and api_key.strip():
        clean_key = api_key.strip()
        try:
            genai.configure(api_key=clean_key)
            
            if language == "العربية":
                prompt = f"""أنت مستشار تنفيذي متخصص في تقييم شركات العمرة. قم بتحليل بيانات الشركة التالية وتقديم 3 توصيات عمل استراتيجية لرفع تصنيفها:
- النتيجة النهائية: {results['final_score']}%
- التصنيف المستحق: {results['tier']}
- محور تنوع الباقات: {results['score_packages']}/15
- محور تجربة المعتمر والجودة: {results['score_exp']}/45
- محور الالتزام بالبرنامج: {results['score_prog']}/40
- مجموع المحفزات: +{results['total_incentives']}%
- الخصومات المطبقة: -{results['penalties']}%

تعليمات صارمة: يجب أن تكون الإجابة والتحليل والتوصيات بالكامل باللغة العربية فقط، واستخدم أسلوباً استشارياً راقياً ومباشراً."""
            else:
                prompt = f"""You are an executive consultant specializing in evaluating Umrah companies. Analyze the following company data and provide 3 strategic business recommendations to improve its performance:
- Final Score: {results['final_score']}%
- Current Tier: {results['tier']}
- Package Diversity Pillar: {results['score_packages']}/15
- Pilgrim Experience & Quality Pillar: {results['score_exp']}/45
- Program Commitment Pillar: {results['score_prog']}/40
- Total Incentives: +{results['total_incentives']}%
- Applied Penalties: -{results['penalties']}%

CRITICAL INSTRUCTION: The full analysis and all recommendations MUST be strictly in English."""

            candidate_models = [
                'gemini-1.5-flash',
                'gemini-2.0-flash',
                'gemini-1.5-pro',
                'models/gemini-1.5-flash'
            ]

            spinner_msg = "🤖 جاري تحليل البيانات وإعداد التوصيات..." if language == "العربية" else "🤖 Analyzing data and generating recommendations..."
            
            with st.spinner(spinner_msg):
                for model_name in candidate_models:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        if response and response.text:
                            header = "### 🤖 تحليل ومقترحات الذكاء الاصطناعي (Gemini):" if language == "العربية" else "### 🤖 AI Advisor Analysis & Recommendations (Gemini):"
                            return f"{header}\n\n{response.text}"
                    except Exception:
                        continue
            
            warn_msg = "⚠️ تعذر الحصول على رد من نماذج Gemini. تم عرض التقرير الأساسي التلقائي." if language == "العربية" else "⚠️ Could not get a response from Gemini. Showing basic auto-report."
            st.warning(warn_msg)
        except Exception as e:
            err_prefix = "حدث خطأ أثناء الاتصال بـ Gemini: " if language == "العربية" else "Error connecting to Gemini: "
            st.error(f"{err_prefix}{e}")

    # التقرير البديل للنظام
    if language == "العربية":
        report = "### 🤖 تقرير وكيل الذكاء الاصطناعي للاستشارات\n\n"
        if warnings:
            report += "#### 🛑 التحذيرات والمخاطر العاجلة:\n" + "\n".join([f"- {w}" for w in warnings]) + "\n\n"
        if actions:
            report += "#### 🚀 أسرع الفرص لرفع التصنيف:\n" + "\n".join([f"- {a}" for a in actions]) + "\n\n"
    else:
        report = "### 🤖 AI Advisor Consultation Report\n\n"
        if warnings:
            report += "#### 🛑 Immediate Risks & Warnings:\n" + "\n".join([f"- {w}" for w in warnings]) + "\n\n"
        if actions:
            report += "#### 🚀 Top Opportunities to Upgrade Tier:\n" + "\n".join([f"- {a}" for a in actions]) + "\n\n"
    return report

# ---------------------------------------------------------
# 3. الرسوم البيانية التفاعلية
# ---------------------------------------------------------
def render_charts(results, language="العربية"):
    is_ar = (language == "العربية")
    c1, c2 = st.columns(2)
    
    gauge_title = "مؤشر التقييم النهائي (%)" if is_ar else "Final Score Gauge (%)"
    categories = ['تنوع الباقات', 'تجربة المعتمر والجودة', 'الالتزام بالبرنامج'] if is_ar else ['Package Diversity', 'Pilgrim Exp & Quality', 'Program Commitment']
    radar_title = "نسبة الإنجاز حسب المحاور الرئيسية" if is_ar else "Pillar Performance Breakdown"

    with c1:
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = results['final_score'],
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': gauge_title},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "#1F4E78"},
                'steps': [
                    {'range': [0, 60], 'color': "#FFD2D2"},
                    {'range': [60, 75], 'color': "#D9E1F2"},
                    {'range': [75, 90], 'color': "#FFE699"},
                    {'range': [90, 100], 'color': "#E2EFDA"}
                ]
            }
        ))
        fig_gauge.update_layout(height=300)
        st.plotly_chart(fig_gauge, width="stretch")

    with c2:
        scores = [
            (results['score_packages'] / 15.0) * 100,
            (results['score_exp'] / 45.0) * 100,
            (results['score_prog'] / 40.0) * 100
        ]
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=scores + [scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(31, 78, 120, 0.4)',
            line_color='#1F4E78'
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            title=radar_title,
            height=300
        )
        st.plotly_chart(fig_radar, width="stretch")

# ---------------------------------------------------------
# 4. واجهة المستخدم الرئيسية
# ---------------------------------------------------------
st.sidebar.header("⚙️ الخيارات والإعدادات / Settings")
ai_language = st.sidebar.selectbox("لغة التقرير والنظام / System Language:", ["العربية", "English"])
is_ar = (ai_language == "العربية")

input_mode_options = ["إدخال يدوي (Manual)", "استيراد ملف Excel"] if is_ar else ["Manual Entry", "Excel Import"]
input_mode = st.sidebar.radio("طريقة إدخال البيانات / Input Mode:" if is_ar else "Data Input Method:", input_mode_options)

app_title = "🕋 نظام إدارة وتصنيف شركات العمرة 1448هـ" if is_ar else "🕋 Umrah Companies Evaluation & Classification System 1448H"
st.title(app_title)

tab1_title = "📊 إجراء التقييم الحالية" if is_ar else "📊 Current Evaluation"
tab2_title = "📜 سجل التقييمات التاريخية" if is_ar else "📜 Evaluation History"
tab1, tab2 = st.tabs([tab1_title, tab2_title])

with tab1:
    company_name_label = "اسم الشركة / الرخصة:" if is_ar else "Company Name / License:"
    default_company = "شركة عمرة النموذجية" if is_ar else "Model Umrah Company"
    company_name = st.text_input(company_name_label, default_company)

    data = {}

    if "إدخال يدوي" in input_mode or "Manual" in input_mode:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 1️⃣ تنوع الباقات (15%)" if is_ar else "### 1️⃣ Package Diversity (15%)")
            
            col_lux_in, col_lux_out = st.columns([3, 2])
            with col_lux_in:
                luxury_pilgrims = st.number_input("عدد الباقات الفاخرة" if is_ar else "Luxury Packages Count", min_value=0, value=0, step=1, key="in_lux_pax")

            col_mid_in, col_mid_out = st.columns([3, 2])
            with col_mid_in:
                medium_pilgrims = st.number_input("عدد الباقات المتوسطة" if is_ar else "Medium Packages Count", min_value=0, value=0, step=1, key="in_mid_pax")

            col_eco_in, col_eco_out = st.columns([3, 2])
            with col_eco_in:
                economy_pilgrims = st.number_input("عدد الباقات الاقتصادية" if is_ar else "Economy Packages Count", min_value=0, value=0, step=1, key="in_eco_pax")

            v_lux = int(luxury_pilgrims)
            v_mid = int(medium_pilgrims)
            v_eco = int(economy_pilgrims)
            total_entry_pilgrims = v_lux + v_mid + v_eco

            p_lux_pct = (v_lux / total_entry_pilgrims * 100.0) if total_entry_pilgrims > 0 else 0.0
            p_mid_pct = (v_mid / total_entry_pilgrims * 100.0) if total_entry_pilgrims > 0 else 0.0
            p_eco_pct = (v_eco / total_entry_pilgrims * 100.0) if total_entry_pilgrims > 0 else 0.0

            ratio_text = "النسبة:" if is_ar else "Ratio:"
            with col_lux_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{p_lux_pct:.1f}%**")

            with col_mid_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{p_mid_pct:.1f}%**")

            with col_eco_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{p_eco_pct:.1f}%**")

            total_pkg_label = "إجمالي عدد الباقات (تلقائي)" if is_ar else "Total Packages (Auto)"
            pkg_unit = "باقة" if is_ar else "Packages"
            st.text_input(total_pkg_label, value=f"{total_entry_pilgrims} {pkg_unit}", disabled=True)

            st.markdown("---")
            st.markdown("### 🎁 المحفزات والجوائز" if is_ar else "### 🎁 Incentives & Awards")
            
            col_g_lux_in, col_g_lux_out = st.columns([3, 2])
            with col_g_lux_in:
                luxury_gifts = st.number_input("عدد الهدايا الفاخرة (20 نقطة)" if is_ar else "Luxury Gifts Count (20 pts)", min_value=0, value=0, step=1, key="in_g_lux")

            col_g_mid_in, col_g_mid_out = st.columns([3, 2])
            with col_g_mid_in:
                medium_gifts = st.number_input("عدد الهدايا المتوسطة (4 نقاط)" if is_ar else "Medium Gifts Count (4 pts)", min_value=0, value=0, step=1, key="in_g_mid")

            col_g_eco_in, col_g_eco_out = st.columns([3, 2])
            with col_g_eco_in:
                economy_gifts = st.number_input("عدد الهدايا الاقتصادية (1 نقطة)" if is_ar else "Economy Gifts Count (1 pt)", min_value=0, value=0, step=1, key="in_g_eco")

            v_g_lux = int(luxury_gifts)
            v_g_mid = int(medium_gifts)
            v_g_eco = int(economy_gifts)
            total_gifts = v_g_lux + v_g_mid + v_g_eco

            g_lux_pct = (v_g_lux / total_gifts * 100.0) if total_gifts > 0 else 0.0
            g_mid_pct = (v_g_mid / total_gifts * 100.0) if total_gifts > 0 else 0.0
            g_eco_pct = (v_g_eco / total_gifts * 100.0) if total_gifts > 0 else 0.0

            with col_g_lux_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{g_lux_pct:.1f}%**")

            with col_g_mid_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{g_mid_pct:.1f}%**")

            with col_g_eco_out:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"{ratio_text} **{g_eco_pct:.1f}%**")

            gift_unit = "هدية" if is_ar else "Gifts"
            st.text_input("إجمالي عدد الهدايا (تلقائي)" if is_ar else "Total Gifts (Auto)", value=f"{total_gifts} {gift_unit}", disabled=True)

            umrah_plus_beneficiaries = st.number_input("معتمري مبادرة (عمرة+)" if is_ar else "Umrah+ Beneficiaries", min_value=0, value=0, step=1, key="in_umrah_plus")
            has_ministry_award = st.checkbox("حاصل على جائزة من الوزارة (+5%)" if is_ar else "Has Ministry Award (+5%)", key="in_has_award")

        with col2:
            st.markdown("### 2️⃣ تجربة المعتمر والجودة (45%)" if is_ar else "### 2️⃣ Pilgrim Experience & Quality (45%)")
            
            satisfaction_score_pct = st.number_input("رضا المعتمرين (%)" if is_ar else "Pilgrim Satisfaction (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="in_sat")
            service_quality_pct = st.number_input("تقييم جودة الخدمة (%)" if is_ar else "Service Quality Score (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="in_qual")

            st.caption("معالجة الشكاوى والبلاغات:" if is_ar else "Complaints & SLA Handling:")
            total_complaints = st.number_input("إجمالي البلاغات الواردة" if is_ar else "Total Complaints Received", min_value=0, value=0, step=1, key="in_tot_comp")
            closed_complaints = st.number_input("البلاغات المعالجة وفق SLA" if is_ar else "Resolved Complaints (SLA)", min_value=0, value=0, step=1, key="in_cls_comp")

            total_departing_pilgrims = st.number_input("إجمالي المعتمرين المغادرين" if is_ar else "Total Departing Pilgrims", min_value=0, value=0, step=1, key="in_tot_dep")
            enrichment_beneficiaries = st.number_input("المستفيدون من الخدمات الإثرائية" if is_ar else "Enrichment Service Beneficiaries", min_value=0, value=0, step=1, key="in_enrich")

            st.markdown("---")
            st.markdown("### ⚠️ المخالفات والامتثال" if is_ar else "### ⚠️ Violations & Compliance")
            total_visited_pilgrims = st.number_input("إجمالي المعتمرين في الزيارات الميدانية" if is_ar else "Total Visited Pilgrims", min_value=0, value=0, step=1, key="in_tot_vis")
            unaffected_pilgrims = st.number_input("عدد المعتمرين غير المتأثرين بمخالفات" if is_ar else "Pilgrims Unaffected by Violations", min_value=0, value=0, step=1, key="in_unaff_pax")
            has_severe_violation = st.checkbox("رصد مخالفة جسيمة خلال الشهر (-5%)" if is_ar else "Severe Violation Recorded (-5%)", key="in_severe_viol")

        with col3:
            st.markdown("### 3️⃣ الالتزام بالبرنامج (40%)" if is_ar else "### 3️⃣ Program Commitment (40%)")

            total_entry_records = st.number_input("إجمالي سجلات القدوم" if is_ar else "Total Arrival Records", min_value=0, value=0, step=1, key="in_tot_ent_rec")
            matched_entry_records = st.number_input("سجلات القدوم المتطابقة" if is_ar else "Matched Arrival Records", min_value=0, value=0, step=1, key="in_mtch_ent_rec")

            arrival_boarding_orders = st.number_input("أوامر إركاب الوصول الصادرة" if is_ar else "Arrival Boarding Orders Issued", min_value=0, value=0, step=1, key="in_arr_board")
            intercity_boarding_orders = st.number_input("أوامر إركاب بين المدن الصادرة" if is_ar else "Intercity Boarding Orders Issued", min_value=0, value=0, step=1, key="in_inter_board")
            departure_boarding_orders = st.number_input("أوامر إركاب المغادرة الصادرة" if is_ar else "Departure Boarding Orders Issued", min_value=0, value=0, step=1, key="in_dep_board")

            total_exit_records = st.number_input("إجمالي سجلات المغادرة" if is_ar else "Total Departure Records", min_value=0, value=0, step=1, key="in_tot_ext_rec")
            matched_exit_records = st.number_input("سجلات المغادرة المتطابقة" if is_ar else "Matched Departure Records", min_value=0, value=0, step=1, key="in_mtch_ext_rec")

            total_housing_programs = st.number_input("إجمالي برامج العمرة مع السكن" if is_ar else "Total Housing Programs", min_value=0, value=0, step=1, key="in_tot_hsg")
            confirmed_housing = st.number_input("المؤكد سكنهم إلكترونياً عند الوصول" if is_ar else "Electronically Confirmed Housing", min_value=0, value=0, step=1, key="in_cnfm_hsg")

    else:
        uploaded_file = st.file_uploader("رفع ملف Excel:" if is_ar else "Upload Excel File:", type=['xlsx', 'csv'])
        if uploaded_file:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            data = df.iloc[0].to_dict()
        else:
            st.stop()

    btn_label = "🚀 احتساب التقييم وحفظ النتيجة" if is_ar else "🚀 Calculate & Save Evaluation"
    if st.button(btn_label, type="primary"):
        if "إدخال يدوي" in input_mode or "Manual" in input_mode:
            data = {
                'total_entry_pilgrims': total_entry_pilgrims,
                'luxury_pilgrims': v_lux,
                'medium_pilgrims': v_mid,
                'economy_pilgrims': v_eco,
                'economy_gifts': v_g_eco,
                'medium_gifts': v_g_mid,
                'luxury_gifts': v_g_lux,
                'umrah_plus_beneficiaries': umrah_plus_beneficiaries,
                'has_ministry_award': has_ministry_award,
                'satisfaction_score_pct': satisfaction_score_pct,
                'service_quality_pct': service_quality_pct,
                'total_complaints': total_complaints,
                'closed_complaints': closed_complaints,
                'total_departing_pilgrims': total_departing_pilgrims,
                'enrichment_beneficiaries': enrichment_beneficiaries,
                'total_visited_pilgrims': total_visited_pilgrims,
                'unaffected_pilgrims': unaffected_pilgrims,
                'has_severe_violation': has_severe_violation,
                'total_entry_records': total_entry_records,
                'matched_entry_records': matched_entry_records,
                'arrival_boarding_orders': arrival_boarding_orders,
                'intercity_boarding_orders': intercity_boarding_orders,
                'departure_boarding_orders': departure_boarding_orders,
                'total_exit_records': total_exit_records,
                'matched_exit_records': matched_exit_records,
                'total_housing_programs': total_housing_programs,
                'confirmed_housing': confirmed_housing
            }

        results = calculate_umrah_company_score(data, ai_language)
        save_evaluation(company_name, results)

        st.session_state['latest_results'] = results
        st.session_state['latest_company'] = company_name

        st.rerun()

    # عرض نتائج التقييم الأخير والتقرير
    if 'latest_results' in st.session_state and st.session_state['latest_results']:
        results = st.session_state['latest_results']
        comp_name = st.session_state['latest_company']

        st.success("تم حساب وحفظ النتيجة بنجاح!" if is_ar else "Evaluation calculated and saved successfully!")

        res_c1, res_c2, res_c3, res_c4 = st.columns(4)
        res_c1.metric("الدرجة النهائية" if is_ar else "Final Score", f"{results['final_score']}%")
        res_c2.metric("التصنيف المستحق" if is_ar else "Earned Tier", results['tier'])
        res_c3.metric("إجمالي المحفزات" if is_ar else "Total Incentives", f"+{results['total_incentives']}%")
        res_c4.metric("خصم المخالفات الجسيمة" if is_ar else "Severe Penalties", f"-{results['penalties']}%")

        render_charts(results, ai_language)
        st.markdown("---")
        
        # استدعاء الذكاء الاصطناعي بالمفتاح التلقائي واللغة المختارة
        ai_report = generate_ai_advisor_report(results, DEFAULT_GEMINI_KEY, ai_language)
        st.markdown(ai_report)

        # توليد تقرير PDF بنفس اللغة المختارة
        pdf_bytes = generate_pdf_report(comp_name, results, ai_language)
        
        pdf_btn_label = "📄 تصدير التقرير النهائي (PDF)" if is_ar else "📄 Export Final Report (PDF)"
        pdf_filename = f"تقرير_تقييم_{comp_name}.pdf" if is_ar else f"Evaluation_Report_{comp_name}.pdf"

        st.download_button(
            label=pdf_btn_label,
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            width="stretch"
        )

with tab2:
    hist_title = "📜 السجل التاريخي لتقييمات الشركات" if is_ar else "📜 Historical Evaluation Log"
    st.subheader(hist_title)
    
    conn = sqlite3.connect("umrah_evaluations.db")
    df_history = pd.read_sql_query("SELECT id, eval_date, company_name, final_score, tier, score_packages, score_exp, score_prog, incentives, penalties FROM evaluations ORDER BY id DESC", conn)
    conn.close()

    if not df_history.empty:
        st.dataframe(df_history, width="stretch")
        line_title = "تطور الدرجة النهائية عبر التقييمات المتعاقبة" if is_ar else "Score Progress Over Time"
        fig_history = px.line(df_history, x="eval_date", y="final_score", color="company_name", markers=True, title=line_title)
        st.plotly_chart(fig_history, width="stretch")
    else:
        st.info("لا توجد تقييمات محفوظة حتى الآن." if is_ar else "No historical evaluation records found.")
