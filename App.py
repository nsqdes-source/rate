import streamlit as st

# استخدام st.number_input مع إضاقة step=1 وتحديد min_value ومفتاح فريد (key)
gifts_medium = st.number_input(
    "عدد الهدايا المتوسطة (4 نقاط)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,  # تحديد المقدار الذي تزيد/تنقص به القيمة عند الضغط
    key="gifts_medium_key"  # مفتاح فريد للحقل لتثبيت حالته في session_state
)

gifts_eco = st.number_input(
    "عدد الهدايا الاقتصادية (1 نقطة)",
    min_value=0,
    max_value=100,
    value=0,
    step=1,
    key="gifts_eco_key"
)

# لحساب النسبة أو النقاط مباشرة
st.write(f"نسبة: {gifts_medium * 4.0}")
