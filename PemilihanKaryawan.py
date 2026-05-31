# Mengimpor library utama
import streamlit as st
import pandas as pd

# Mengatur konfigurasi halaman Streamlit
st.set_page_config(page_title="SPK Karyawan - WP Method", layout="wide")

# Menambahkan CSS kustom minimalis untuk kartu metrik dan formula
st.markdown("""
<style>
.metric-card { background: #fff; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 4px solid #2c5364; text-align: center;}
.metric-val { font-size: 24px; font-weight: bold; color: #1a1a2e; }
.metric-lbl { font-size: 12px; color: #888; text-transform: uppercase; }
.formula { font-family: monospace; background: #f4f4f4; padding: 5px 10px; border-radius: 4px; color: #d63384;}
</style>
""", unsafe_allow_html=True)

# Menampilkan judul dan deskripsi aplikasi
st.title("Sistem Pemilihan Karyawan Berprestasi")
st.markdown("Penentuan penerima bonus tahunan berbasis standar evaluasi kinerja (WP Method). **Nilai bonus dibagikan secara proporsional** berdasarkan skor Vektor V masing-masing karyawan yang lolos ambang batas.")
st.divider()

# Fungsi untuk menormalisasi data ke rentang 1-10
def normalize_col(series):
    mn, mx = series.min(), series.max()
    # Mencegah pembagian dengan nol jika nilai semua baris sama
    return pd.Series([5.0]*len(series), index=series.index) if mx == mn else 1 + 9 * (series - mn) / (mx - mn)

# Konfigurasi Sidebar (Panel Samping)
with st.sidebar:
    st.header("Upload Dataset")
    # Widget untuk mengunggah file data
    uploaded_file = st.file_uploader("Upload salary_data.csv", type=["csv"])
    
    st.header("Pengaturan Bobot Kriteria")
    # Slider untuk mengatur tingkat kepentingan masing-masing kriteria
    w_age = st.slider("Umur (Benefit)", 1, 5, 3)
    w_edu = st.slider("Tingkat Pendidikan (Benefit)", 1, 5, 4)
    w_exp = st.slider("Pengalaman Kerja (Benefit)", 1, 5, 5)
    w_sal = st.slider("Gaji (Cost)", 1, 5, 2)
    w_gen = st.slider("Gender (Benefit)", 1, 5, 1)
    
    st.header("Kebijakan Bonus")
    # Input ambang batas kelulusan
    threshold_v = st.number_input("Ambang Batas Skor Minimal (V)", min_value=0.00000, value=0.00400, step=0.00010, format="%.5f")
    # Input total anggaran dana yang disediakan perusahaan untuk dibagi-bagi
    anggaran_total = st.number_input("Total Anggaran Bonus ($)", min_value=1000, value=50000, step=5000)

# Menghentikan sistem jika file belum diunggah
if not uploaded_file:
    st.info("Silakan unggah file dataset CSV Anda di sidebar.")
    st.stop()

# Membaca file dan membersihkan baris yang kosong
df = pd.read_csv(uploaded_file).dropna(how="all").dropna().reset_index(drop=True)

# Memastikan kolom yang dibutuhkan ada di dataset
req_cols = ["Age", "Education Level", "Years of Experience", "Salary"]
if any(c not in df.columns for c in req_cols):
    st.error("Kolom yang dibutuhkan tidak lengkap.")
    st.stop()

# Pemetaan nilai kategorikal menjadi numerik
df["Rating_Pendidikan"] = df["Education Level"].map({"Bachelor's": 1, "Master's": 2, "PhD": 3}).fillna(1)
df["Rating_Gender"] = df["Gender"].map({"Male": 1, "Female": 2, "Other": 1.5}).fillna(1) if "Gender" in df.columns else 1

# Mematikan bobot gender jika kolom tidak tersedia di dataset
w_gen = 0 if "Gender" not in df.columns else w_gen

# Normalisasi semua kolom kriteria
df["N_Age"] = normalize_col(df["Age"])
df["N_Edu"] = normalize_col(df["Rating_Pendidikan"])
df["N_Exp"] = normalize_col(df["Years of Experience"])
df["N_Salary"] = normalize_col(df["Salary"])
df["N_Gender"] = normalize_col(df["Rating_Gender"])

# Penyiapan bobot dan sifat kriteria untuk rumus WP
bobot_raw = [w_age, w_edu, w_exp, w_sal, w_gen]
jenis = ["benefit", "benefit", "benefit", "cost", "benefit"]
# Normalisasi bobot agar total bobot keseluruhan menjadi 1
w_norm = [b / sum(bobot_raw) for b in bobot_raw]
# Menambahkan minus pada pangkat jika kriteria bersifat cost
w_exp_list = [w if j == 'benefit' else -w for w, j in zip(w_norm, jenis)]

# Kalkulasi Vektor S (Perkalian setiap kriteria berpangkat)
vektor_s = []
for _, row in df.iterrows():
    si = 1.0
    for col, wp in zip(["N_Age", "N_Edu", "N_Exp", "N_Salary", "N_Gender"], w_exp_list):
        si *= max(row[col], 1e-9) ** wp
    vektor_s.append(si)
df["Vektor_S"] = vektor_s

# Kalkulasi Vektor V (Vektor S dibagi Total Vektor S)
df["Vektor_V"] = df["Vektor_S"] / sum(vektor_s)

# Menentukan ranking berdasarkan Vektor V terbesar
df["Rank"] = df["Vektor_V"].rank(ascending=False, method="min").astype(int)

# Mengurutkan tabel berdasarkan peringkat
df_rank = df.sort_values("Vektor_V", ascending=False).reset_index(drop=True)
df_rank.index += 1 # Menyesuaikan index dimulai dari 1

# --- LOGIKA PENENTUAN STATUS & BONUS PROPORSIONAL ---
# Melabeli karyawan yang lolos ambang batas
df_rank["Status Keputusan"] = ["Mendapat Bonus" if v >= threshold_v else "Tidak Mendapat Bonus" for v in df_rank["Vektor_V"]]

# Menjumlahkan total skor Vektor V KHUSUS dari karyawan yang mendapat bonus saja
total_v_penerima = df_rank[df_rank["Status Keputusan"] == "Mendapat Bonus"]["Vektor_V"].sum()

# Menghitung nominal bonus individu
bonus_list = []
for _, row in df_rank.iterrows():
    if row["Status Keputusan"] == "Mendapat Bonus" and total_v_penerima > 0:
        # Porsi bonus = (Skor V individu / Total V Semua Penerima) * Anggaran Total
        bonus = (row["Vektor_V"] / total_v_penerima) * anggaran_total
        bonus_list.append(bonus)
    else:
        # Jika tidak memenuhi syarat, bonus 0
        bonus_list.append(0)

# Memasukkan perhitungan bonus ke kolom tabel
df_rank["Nilai Bonus Diterima"] = bonus_list

# Variabel pembantu untuk metrik dashboard
jumlah_penerima = len(df_rank[df_rank["Status Keputusan"] == "Mendapat Bonus"])
bonus_tertinggi = df_rank["Nilai Bonus Diterima"].max() if jumlah_penerima > 0 else 0
name_col = "Job Title" if "Job Title" in df.columns else df.columns[0]

# Membagi antarmuka menjadi 4 Tab
t1, t2, t3, t4 = st.tabs(["Data & Hasil", "Proses WP", "Visualisasi", "Export"])

with t1:
    # Menampilkan 4 kartu metrik utama
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Total Karyawan</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-val">{jumlah_penerima} Orang</div><div class="metric-lbl">Lolos Ambang Batas</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-val">$ {bonus_tertinggi:,.0f}</div><div class="metric-lbl">Bonus Tertinggi</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-val">$ {anggaran_total:,.0f}</div><div class="metric-lbl">Total Anggaran</div></div>', unsafe_allow_html=True)
    
    # Menampilkan tabel hasil akhir
    st.subheader(f"Daftar Keputusan Karyawan (Ambang Batas V >= {threshold_v:.5f})")
    cols_show = ["Rank", name_col, "Education Level", "Years of Experience", "Salary", "Vektor_V", "Status Keputusan", "Nilai Bonus Diterima"]
    if "Gender" in df.columns: cols_show.insert(3, "Gender")
    st.dataframe(df_rank[cols_show], hide_index=True, use_container_width=True)

with t2:
    # Menjelaskan transparansi proses algoritma kepada pengguna
    st.subheader("Langkah Perhitungan WP")
    st.markdown("1. **Kriteria & Bobot:** Bobot dinormalisasi (Sigma W = 1). Kriteria cost diberi pangkat negatif.")
    st.dataframe(pd.DataFrame({"Kriteria": ["Umur", "Pendidikan", "Pengalaman", "Gaji", "Gender"], "Tipe": jenis, "Bobot Input": bobot_raw, "Pangkat WP": w_exp_list}), hide_index=True)
    
    st.markdown("2. **Normalisasi Data:** Skala 1-10 untuk kestabilan perhitungan matematika.")
    st.dataframe(df_rank[[name_col, "N_Age", "N_Edu", "N_Exp", "N_Salary", "N_Gender"]].head(), hide_index=True)
    
    st.markdown("3. **Keputusan Vektor S & Vektor V:**")
    st.markdown('<p class="formula">S_i = Perkalian (x_ij ^ w_j)  |  V_i = S_i / Total S_i</p>', unsafe_allow_html=True)
    st.dataframe(df_rank[[name_col, "Vektor_S", "Vektor_V", "Status Keputusan"]].head(), hide_index=True)

with t3:
    # Menampilkan grafik bawaan Streamlit
    st.subheader("Visualisasi Data")
    top_df = df_rank.head(15).copy()
    top_df["Label"] = top_df[name_col].astype(str) + " #" + top_df["Rank"].astype(str)
    
    st.markdown("**Perbandingan Skor Kandidat Teratas (Top 15)**")
    chart_data = top_df.set_index("Label")["Vektor_V"]
    st.bar_chart(chart_data)
    
    st.markdown("**Hubungan Masa Kerja dengan Nilai Gaji Saat Ini (Top 15)**")
    scatter_data = top_df.set_index("Years of Experience")["Salary"]
    st.scatter_chart(scatter_data)

with t4:
    # Tombol fungsionalitas untuk mengekspor data
    st.subheader("Unduh Laporan Keputusan")
    exp_cols = [name_col, "Education Level", "Age", "Years of Experience", "Salary", "Vektor_S", "Vektor_V", "Rank", "Status Keputusan", "Nilai Bonus Diterima"]
    if "Gender" in df.columns: exp_cols.insert(2, "Gender")
    
    st.download_button(
        label="Download Laporan Keputusan (CSV)", 
        data=df_rank[exp_cols].to_csv(index=False).encode("utf-8"), 
        file_name="laporan_keputusan_bonus_proporsional.csv", 
        mime="text/csv", 
        use_container_width=True
    )