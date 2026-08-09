import os
import json
import sqlite3
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import google.generativeai as genai

# استدعاء دالة توليد تقرير الـ PDF
try:
    from pdf_generator import generate_pdf_report
except ImportError:
    generate_pdf_report = None

# --------------------------------------------------
# 1. إعدادات الصفحة الأساسية
# --------------------------------------------------
st.set_page_config(
    page_title="نظام تقييم العمرة والوكلاء",
    page_icon="🕋",
    layout="wide"
)

# --------------------------------------------------
# 2. إعداد مفتاح الذكاء الاصطناعي (الشريط الجانبي)
# --------------------------------------------------
st.sidebar.title("⚙️ الإعدادات والتحكم")

# محاولة قراءة المفتاح المسجل سابقاً في الأسرار أو المتغيرات
default_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 إعدادات الذكاء الاصطناعي")
user_api_key = st.sidebar.text_input(
    "أدخل مفتاح Gemini API:",
    value=default_key,
    type="password",
    help="أدخل المفتاح الخاص بك من Google AI Studio لتفعيل التحليل الذكي التفاعلي"
)

GEMINI_API_KEY = user_api_key

# --------------------------------------------------
# 3. دالة توليد التقرير الذكي عبر Gemini مع الخطة البديلة
# --------------------------------------------------
def generate_ai_insights(evaluation_data):
    """
    توليد التقرير باستخدام Gemini API عند توفر المفتاح،
    أو إرجاع التقرير المحسوب محلياً عند غيابه أو حدوث خطأ.
    """
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            أنت وكيل ذكاء اصطناعي متخصص في الاستشارات وتقييم خدمات العمرة.
            قم بتحليل البيانات التالية وتقديم تقرير استشاري مركز يتضمن:
            1. التحذيرات والمخاطر العاجلة.
            2. أسرع الفرص لرفع التصنيف.
            
            البيانات:
            {json.dumps(evaluation_data, ensure_ascii=False, indent=2)}
            """
            
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text, True
        except Exception as e:
            st.sidebar.warning(f"تعذر الاتصال بـ Gemini: {e}")
            
    # التقرير المحتسب محلياً (Fallback) عند عدم عمل API
    fallback_report = """
### 🛑 التحذيرات والمخاطر العاجلة:
* 🚨 **خصم مباشر (-5%):** تم رصد مخالفة جسيمة خلال الشهر.
* ⚠️ **مخالفات تشغيلية:** تم رصد تأثر 10 معتمر بمخالفات أثناء الزيارات الميدانية.

### 🚀 أسرع الفرص لرفع التصنيف:
* 💡 **تفعيل مبادرة (عمرة+):** تسجيل 960 معتمر إضافي يمنحك زيادة تحفيزية قدرها **+9.6%**.
    """
    return fallback_report, False

# --------------------------------------------------
# 4. واجهة المستخدم الرئيسية والتطبيقات
# --------------------------------------------------
st.title("🕋 نظام تقييم شركات العمرة والوكلاء")
st.markdown("---")

# بيانات تجريبية للتقييم
sample_data = {
    "Direct_Deductions": -5.0,
    "Violations_Count": 10,
    "Registered_Pilgrims": 960,
    "Incentive_Potential": 9.6
}

# شريط الحالة للذكاء الاصطناعي
st.subheader("🤖 تقرير وكيل الذكاء الاصطناعي للاستشارات")

report_content, is_ai_generated = generate_ai_insights(sample_data)

if not is_ai_generated:
    st.warning("⚠️ تم عرض التقرير الأساسي التلقائي. تعذر الحصول على رد من نماذج Gemini.")

# عرض التقرير
st.markdown(report_content)

st.markdown("---")

# --------------------------------------------------
# 5. عرض الرسوم البيانية والأدوات الإضافية
# --------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 توزيع الأداء والمخالفات")
    fig = go.Figure(data=[
        go.Bar(name='الخصومات المباشرة', x=['المخالفات'], y=[5], marker_color='crimson'),
        go.Bar(name='فرص التحسين', x=['المبادرات'], y=[9.6], marker_color='forestgreen')
    ])
    fig.update_layout(barmode='group', template='plotly_dark')
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📄 تصدير التقارير")
    st.info("يمكنك تصدير ملخص التقييم والبيانات إلى ملف PDF شامل.")
    
    if st.button("📥 تحميل التقرير بصيغة PDF"):
        if generate_pdf_report:
            pdf_data = generate_pdf_report(sample_data, report_content)
            st.download_button(
                label="تنزيل ملف PDF",
                data=pdf_data,
                file_name=f"Umrah_Evaluation_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("دالة `generate_pdf_report` غير متاحة في ملف `pdf_generator.py`.")
