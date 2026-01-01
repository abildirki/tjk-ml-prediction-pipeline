# Proje Durumu: TJK Veri Analizi ve Tahmin Sistemi

## ✅ Tamamlananlar (19.12.2025)
1.  **Dual-Source Scraper (Program + Sonuçlar):**
    *   TJK Program (AGF, Orijin, Kilo) ve Sonuç (Derece, Sıralama) verilerini birleştiren yapı kuruldu.
    *   `run_scrape.py` scripti ile "Akıllı Güncelleme" (Smart Resume) özelliği eklendi.
    *   Veri seti: 05.05.2025 - 19.12.2025 arası eksiksiz çekildi.
    *   Toplam: 4.200+ Yarış, 42.000+ Koşu kaydı.

2.  **Veri Kalitesi:**
    *   At isimleri temizlendi.
    *   Eksik veriler (Cinsiyet vb.) yönetildi.
    *   Veritabanı tutarlılığı doğrulandı.

3.  **Tahmin Denemeleri:**
    *   `predict_race.py`: Basit puanlama sistemi (HP + AGF).
    *   `predict_advanced.py`: Gelişmiş ağırlıklı sistem (Form + Pist + Jokey).
    *   **Keşif:** Form puanının önemi anlaşıldı ("Hold My Heart" örneği).

## 🚀 Sonraki Adımlar (ML Pipeline)
Hedef: **Feature Engineering + Gradient Boosting (XGBoost/LightGBM)**

1.  **Kurulum:**
    *   `pip install scikit-learn xgboost lightgbm`
    
2.  **Feature Engineering (Öznitelik Üretimi):**
    *   **At Özellikleri:** Son 3 yarış ortalaması, Aynı pist/mesafe kazanma oranı, Form trendi.
    *   **Jokey Özellikleri:** Jokey kazanma oranı, At-Jokey uyumu.
    *   **Relative (Göreli) Özellikler:** Yarış içindeki kilo sırası, handikap farkı (Normalize edilmiş).

3.  **Modelleme:**
    *   Hedef Değişken: `Top3` (1=Tabela, 0=Yok).
    *   Model: XGBoost Classifier.
    *   Validation: Zaman bazlı (TimeSeriesSplit).

4.  **Tahmin Motoru:**
    *   Gelecek yarış programını alıp, modele sokup % olasılık üreten script.

## 📝 Notlar
*   Veritabanı konumu: `c:\Users\Ali\Desktop\tjk\tjk.db`
*   Çalışma klasörü: `c:\Users\Ali\Desktop\tjk\tjk_v2`
