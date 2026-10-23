# Slang Ledger

> A small on-device model that turns casual, code-mixed Indonesian speech into
> structured finance entries.

Model bahasa kecil yang membaca kalimat keuangan sehari-hari — "kemarin jajan bakso
25rb", "dapat transferan dari nyokap 500 ribu", "isi bensin 60rb" — lalu mengubahnya
menjadi catatan terstruktur: jenis, nominal, item, kategori, dan tanggal. Berjalan di
HP, tanpa internet, dan tanpa mengirim teks ke mana pun.

Model ini awalnya dibangun untuk aplikasi **Nano Money** (mode **AI Lokal**), tetapi
bobotnya sendiri tidak terikat ke aplikasi itu. Repo ini berisi bobot model, jembatan
JNI, skrip pembuat data latih, set uji, dan catatan pemasangan.

Repo aplikasinya: <https://github.com/SNNN-011/Nano-Money>.

---

## Isi repo

| Folder | Isi |
| :--- | :--- |
| `model/` | `rank64.cact` — bobot model yang dipakai aplikasi (±60,5 MB) |
| `jni/` | `needle_jni.c` dan `build_android_so.ps1` — jembatan tipis Kotlin ↔ mesin Needle |
| `training/` | pembuat dataset (`generate_app_dataset.py`, `generate_dataset.py`) dan skema tool (`tools_app.json`, `tools.json`) |
| `eval/` | set uji 599 kalimat (`eval_clean_599.jsonl`) dan simulasi pemakaian aplikasi (`eval_app_sim.jsonl`) |
| `docs/` | `PASANG-LOKAL.md`, `PENJELASAN-OTAK-V5.md`, `UJI_HP.md` |

## Model

- **Berkas:** `model/rank64.cact` (63.437.076 byte)
- **MD5:** `90c128e4187ab114b5f65609a179e7af`
- **Basis:** **Needle** dari Cactus Compute, di-fine-tune untuk memilih tool
  `catat_masuk` / `catat_pengeluaran` dan mengisi argumennya (nominal, item, kategori,
  tanggal, deskripsi).
- **Nama internal:** `r10_cat_a` (r10 = putaran training ke-10, `cat_a` = varian kategori).
- **Masukan:** satu kalimat bebas + daftar kategori milik user di skema tool.
- **Keluaran:** satu panggilan tool dalam bentuk JSON.

Hasil uji di HP (bukan cuma unit test) pada 50 kalimat baru: 50/50 tercatat,
arah uang 50/50, nominal 50/50, kategori 47/50. Unit test JVM di repo aplikasi: 116 lulus.
Rincian lengkap ada di repo aplikasi, berkas `CATATAN-AI-LOKAL.md`.

## Cara pakai

1. **Salin bobot model** ke aplikasi:
   ```
   app/src/main/assets/rank64.cact
   ```
2. **Bangun library JNI** (butuh mesin Needle untuk Android arm64 dari upstream Cactus):
   ```
   jni/build_android_so.ps1
   ```
3. **Salin hasilnya** ke aplikasi:
   ```
   app/src/main/jniLibs/arm64-v8a/libneedle_jni.so
   ```
4. **Build aplikasi**, lalu pilih **AI Lokal** di atas kolom chat.

Detail langkah pemasangan (termasuk cara mendapatkan mesin dan model dasar) ada di
[`docs/PASANG-LOKAL.md`](docs/PASANG-LOKAL.md).

## Yang sengaja TIDAK ada di repo ini

| Berkas | Alasan |
| :--- | :--- |
| `libneedle.a`, `needle3.cact`, `libneedle_jni.so` | milik mesin Cactus; lisensinya *source-available* tersendiri, bukan Apache-2.0, jadi tidak didistribusikan ulang di sini |
| `data_app/*.jsonl`, `data/` | data latih berisi contoh keuangan; tidak dibagikan |
| checkpoint training lain (`r5_rank128_a`, `rank64_r8e1`) | hanya versi pemenang yang disimpan di repo |

## Lisensi dan atribusi

- Bobot `rank64.cact` adalah turunan dari model **Needle** (Cactus Compute) yang
  berlisensi **Apache-2.0**: <https://github.com/cactus-compute/needle/blob/main/LICENSE>
- **Mesin Cactus** yang menjadi `libneedle_jni.so` memakai lisensi *source-available*
  tersendiri, **bukan** Apache-2.0. Karena itu binernya tidak disertakan di repo ini.
- Skrip di repo ini belum punya lisensi eksplisit; repo bersifat privat.

## Keterbatasan

- Hanya mendukung teks; foto struk tetap harus lewat mode AI Gemini di aplikasi.
- Hanya dibangun untuk `arm64-v8a`.
- Prompt sengaja sesederhana baris tanggal (`date: 2026-10-22 Thu 08:00`); menambah
  konteks percakapan panjang justru menurunkan akurasi.
- Tiga kalimat pada uji 50 masih meleset kategorinya (hadiah lomba, ganti rugi asuransi,
  denda parkir). Perbaikan berikutnya lewat data latih, bukan tambal kata kunci.
