
import streamlit as st
import pandas as pd
import datetime
import sys
import os

# Add src to path
if "src" not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from tjk.coupon_generator import CouponGenerator
from tjk.ml.inference import get_predictions_for_date

st.set_page_config(
    page_title="TJK AI Pro",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Professional Look
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .big-font {
        font-size:24px !important;
        font-weight: bold;
    }
    .card {
        padding: 20px;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #333;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/tr/b/b6/T%C3%BCrkiye_Jokey_Kul%C3%BCb%C3%BC_logosu.png", width=100)
    st.title("TJK AI Pro v2.2")
    st.markdown("---")
    city = st.selectbox("📍 Şehir Seçiniz", ["Adana", "İstanbul", "İzmir", "Bursa", "Ankara", "Kocaeli", "Antalya", "Diyarbakır", "Şanlıurfa", "Elazığ"])
    target_date = st.date_input("📅 Tarih", datetime.date.today())
    st.markdown("---")
    run_btn = st.button("🚀 Analizi Başlat", type="primary", use_container_width=True)
    st.info("Model: XGBoost Optimized\nLogic: Smart Coverage")

# Main Content
st.title(f"🏇 {city} Yarış Analizi")
st.markdown(f"**Tarih:** {target_date.strftime('%d %B %Y')}")

if run_btn:
    with st.spinner(f"📡 {city} verileri çekiliyor ve yapay zeka tarafından analiz ediliyor..."):
        # Run Generator
        gen = CouponGenerator()
        result = gen.process(city, target_date)

        if "error" in result:
            st.error(result['error'])
        else:
            st.success("Analiz Başarıyla Tamamlandı!")

            # --- METRICS ROW ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Banko Adayı", value=result['banko'].split('\n')[0].replace('Yok', '-'))
            with col2:
                risk_val = "Yok" if result['risky'] == "Yok" else f"{len(result['risky'].split(','))} Ayak"
                st.metric(label="Riskli Ayaklar", value=risk_val, delta_color="inverse")
            with col3:
                st.metric(label="Sistem Durumu", value="Online", delta="Güncel")

            st.divider()

            # --- COUPON SECTION ---
            st.subheader("🎫 Kupon Tahminleri")

            c1, c2 = st.columns(2)

            with c1:
                st.markdown("### 🟢 Ekonomik Kurgu")
                st.text_area("Düşük Bütçeli & Güvenli", result['eco'], height=350)

            with c2:
                st.markdown("### 🔴 Geniş Kurgu")
                st.text_area("Sürpriz Arayanlar İçin", result['wide'], height=350)

            st.divider()

            # --- DETAILED ANALYSIS ---
            st.subheader("🔍 Koşu Bazlı Detaylı Analiz")

            try:
                preds = get_predictions_for_date(target_date, city)
                if preds is not None and not preds.empty:
                    # Tabs for races
                    races = sorted(preds['race_no'].unique())
                    tabs = st.tabs([f"Koşu {r}" for r in races])

                    for i, r_no in enumerate(races):
                        with tabs[i]:
                            r_df = preds[preds['race_no'] == r_no].copy()
                            r_df = r_df.sort_values('prob_win', ascending=False)

                            # Formatting for display
                            display_df = r_df.copy()
                            display_df['Kazanma %'] = (display_df['prob_win'] * 100).map('{:.1f}%'.format)
                            display_df['İlk 3 %'] = (display_df['prob_place'] * 100).map('{:.1f}%'.format)
                            display_df['Sürpriz Skoru'] = (display_df['prob_sp'] * 100).map('{:.1f}'.format)

                            # Add Icons based on probability
                            def get_status(row):
                                if row['prob_win'] > 0.40: return "⭐ Favori"
                                if row['prob_sp'] > 0.40: return "⚡ Sürpriz"
                                return ""
                            display_df['Durum'] = display_df.apply(get_status, axis=1)

                            # Style the dataframe
                            st.dataframe(
                                display_df[['horse_name', 'jockey_name', 'Durum', 'Kazanma %', 'İlk 3 %', 'Sürpriz Skoru', 'hp', 'form_score']],
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Kazanma %": st.column_config.ProgressColumn(
                                        "Kazanma İhtimali",
                                        format="%s",
                                        min_value=0,
                                        max_value=100,
                                    ),
                                }
                            )

            except Exception as e:
                st.warning(f"Detaylı analiz yüklenemedi: {e}")

else:
    st.info("Analizi başlatmak için soldaki butonu kullanın.")
    st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=2070&auto=format&fit=crop", caption="Professional AI Racing Analysis")
