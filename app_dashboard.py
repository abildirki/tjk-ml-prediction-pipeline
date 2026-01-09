
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

st.set_page_config(page_title="TJK AI V2", page_icon="🏇", layout="wide")

st.title("🏇 TJK Yapay Zeka Tahmin Sistemi v2.0")
st.markdown("Advanced Machine Learning Prediction & Coupon Generation")

# Sidebar
st.sidebar.header("Ayarlar")
city = st.sidebar.selectbox("Şehir Seçiniz", ["Adana", "İstanbul", "İzmir", "Bursa", "Ankara", "Kocaeli", "Antalya", "Diyarbakır", "Şanlıurfa", "Elazığ"])
target_date = st.sidebar.date_input("Tarih", datetime.date.today())

run_btn = st.sidebar.button("🚀 Tahminleri Çalıştır", type="primary")

if run_btn:
    with st.spinner(f"{city} için veriler analiz ediliyor..."):
        # 1. Run Generator
        gen = CouponGenerator()
        # Ensure we pass datetime.date
        result = gen.process(city, target_date)

        if "error" in result:
            st.error(result['error'])
        else:
            st.success("Analiz Tamamlandı!")

            # Display Coupons
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🎫 Ekonomik Kupon")
                st.text_area("Eco", result['eco'], height=300)

            with col2:
                st.subheader("🛡️ Geniş Kupon")
                st.text_area("Wide", result['wide'], height=300)

            st.divider()

            # Display Banko / Risk
            st.info(f"**Banko:** {result['banko']}")
            if result['risky'] != "Yok":
                st.warning(f"**Riskli Ayaklar:** {result['risky']}")

            st.divider()

            # Display Detailed Analysis (Dataframe)
            st.subheader("🔍 Detaylı Yarış Analizi")

            try:
                # Fetch raw predictions for visualization
                preds = get_predictions_for_date(target_date, city)
                if preds is not None and not preds.empty:
                    # Sort by Race No -> Win Prob
                    preds = preds.sort_values(['race_no', 'prob_win'], ascending=[True, False])

                    # Format
                    display_cols = ['race_no', 'horse_name', 'jockey_name', 'prob_win', 'prob_place', 'prob_sp', 'agf', 'form_score']

                    # Group by Race for tabs
                    races = sorted(preds['race_no'].unique())
                    tabs = st.tabs([f"Koşu {r}" for r in races])

                    for i, r_no in enumerate(races):
                        with tabs[i]:
                            r_df = preds[preds['race_no'] == r_no].copy()

                            # Highlight top picks
                            st.write(f"**Koşu {r_no} Tahminleri**")

                            # Custom formatting
                            r_df['Kazanma %'] = (r_df['prob_win'] * 100).map('{:.1f}%'.format)
                            r_df['Tabela %'] = (r_df['prob_place'] * 100).map('{:.1f}%'.format)
                            r_df['Sürpriz %'] = (r_df['prob_sp'] * 100).map('{:.1f}%'.format)

                            # Show as table
                            st.dataframe(
                                r_df[['horse_name', 'jockey_name', 'Kazanma %', 'Tabela %', 'Sürpriz %', 'agf', 'form_score']],
                                use_container_width=True,
                                hide_index=True
                            )

                            # Charts
                            st.bar_chart(r_df.set_index('horse_name')['prob_win'])

            except Exception as e:
                st.warning(f"Detaylı tablo yüklenemedi: {e}")

st.sidebar.markdown("---")
st.sidebar.info("Model: XGBoost (Win/Place/Surprise)\nVersion: 2.1\nDev: Jules")
