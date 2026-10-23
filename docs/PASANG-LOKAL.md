# Pemasangan AI Lokal ke aplikasi Nano-Money

Dokumen ini menjelaskan satu hal: **bagaimana model hasil latihan (`rank64.cact`)
dipasang ke aplikasi Android dan mengapa caranya seperti ini.** Cukup dibaca
sendiri, tanpa file lain.

Hasil akhir:

- Model jalan **di dalam HP, tanpa internet**.
- Gemini tetap ada, tidak diubah sama sekali. User memilih otaknya di tab chat.
- Foto struk hanya bisa di mode Gemini (otak lokalnya teks saja).

---

## 1. Isi paket pemasangan

| Bagian | Berkas | Ukuran | Peran |
|---|---|---|---|
| Otak (bobot) | `Nano-Money/app/src/main/assets/rank64.cact` | 63,4 MB | hasil latihan |
| Mesin | `Nano-Money/app/src/main/jniLibs/arm64-v8a/libneedle_jni.so` | 2,5 MB | menjalankan otak |
| Sumber mesin | `build_android/jni/needle_jni.c` | kecil | jembatan Kotlin ↔ C |
| Skrip bangun | `build_android/jni/build_android_so.ps1` | kecil | membuat `.so` |
| Mesin mentah | `build_android/android-arm64/libneedle.a` | 2,2 MB | bahan baku (static lib) |

Untuk Android, Cactus hanya menyediakan **static library** (`libneedle.a`) —
tidak ada `.so` siap pakai. Karena itu kita bikin sendiri satu `.so` yang
memuat mesin di dalamnya. Hasilnya `libneedle_jni.so` sudah berdiri sendiri:
tidak butuh mesin apa pun di HP, hanya lib bawaan Android (`libc`, `libm`,
`liblog`, `libdl`).

## 2. Yang perlu ada di laptop untuk membangun ulang `.so`

Hanya kalau mau **mengganti mesin** (mengganti model tidak perlu ini).

1. **NDK Android** (sudah ada di `C:\Users\yasin\AppData\Local\Temp\opencode\android-ndk-r26d`).
   Kalau hilang, unduh ulang:
   ```
   curl.exe -L -o android-ndk-r26d-windows.zip https://dl.google.com/android/repository/android-ndk-r26d-windows.zip
   tar -xf android-ndk-r26d-windows.zip -C C:\Users\yasin\AppData\Local\Temp\opencode
   ```
2. `build_android/android-arm64/` (cara mengunduh ulang ada di bagian 6).

Lalu:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\yasin\needle-nanomoney\build_android\jni\build_android_so.ps1
```

Hasil: `build_android/jni/out/arm64-v8a/libneedle_jni.so`. Salin ke
`Nano-Money/app/src/main/jniLibs/arm64-v8a/`.

### Tiga jebakan yang sudah pernah kena

| Gejala | Sebab | Obat |
|---|---|---|
| `__declspec attributes are not enabled` | memakai `jni.h` milik JDK Windows | jangan pakai; ambil `jni.h` dari NDK (sudah otomatis di skrip) |
| `undefined symbol: std::__ndk1::...` | mesin C++ butuh libc++ NDK | tambah `-lc++_static -lc++abi` |
| `undefined symbol: sinf`, `log` | butuh pustaka matematika | tambah `-lm` |

## 3. Aturan yang TIDAK boleh diubah (supaya hasil sama dengan hasil ujian)

Model ini diuji dengan cara tertentu; kalau aplikasi memanggilnya dengan cara
berbeda, akurasinya turun jauh dari angka ujian yang sudah diukur.

| Aturan | Nilai | Alasan |
|---|---|---|
| Prompt sistem | hanya `date: 2026-10-19 Mon 05:30` | ini bentuk yang dipakai saat melatih; prompt besar ala Gemini malah menurunkan akurasi |
| Daftar alat | dibangun runtime: 2 alat (`catat_pengeluaran`, `catat_masuk`), `category` ber-`enum` berisi daftar kategori user, `required` ["category"], pemisah tanpa spasi | lihat §8. Bentuk ini PERSIS yang dipakai saat melatih otak v5 (r1..r8). Bentuk lama (3 alat, tanpa `enum`) tidak pernah dilihat model v5 dan kategorinya anjlok ke 0,7-4% |
| Reset percakapan | **tiap permintaan** | saat ujian, tiap kalimat direset dulu (`stateless=True`). Tanpa reset, kalimat ke-2 menempel ke kalimat ke-1 |
| Panjang jawaban | `max_new_tokens = 128` | sama dengan setelan ujian |
| Nominal | dibaca dari kalimat user kalau tertulis jelas | model terbukti salah baca satuan besar ("2 juta" → 2000); kalimat user adalah sumber paling tepercaya. Kalau kalimatnya tidak menyebut nominal, jawaban model dipakai; kalau itu pun kosong, aplikasi bertanya |
| Tanggal | **tanggal hari ini** | keputusan user: tanggal tidak lagi urusan model |

Tempat aturan ini hidup di kode:

- `app/src/main/java/com/example/data/local/LocalEngine.kt` — prompt sistem, daftar alat, reset.
- `app/src/main/java/com/example/domain/LocalTransactionParser.kt` — terjemahan jawaban model → data aplikasi, plus tanggal hari ini dan penolakan nominal karangan.
- `app/src/main/java/com/example/domain/AmountReader.kt` — pembaca nominal dari kalimat user (satuan, tanda Rp, titik ribuan).

## 4. Cara aplikasi memilih otak

Satu titik pilih di `ChatViewModel.runAiRequest()`:

```
mode AI Lokal  -> LocalTransactionParser  (model di HP)
mode AI Gemini -> TransactionParserUseCase (jalur lama, tidak disentuh)
```

Sisanya dipakai bersama: indikator proses, cabang tanya-jawab, dialog
konfirmasi, penyaring kategori, penyimpanan. Jadi jalur Gemini tidak berubah
sama sekali; menambah mode lokal hanya menambah cabang di satu tempat.

Pilihan mode disimpan di prefs yang sama dengan setelan chat lain
(`chat_ai_mode`), bawaannya **Gemini** supaya perilaku aplikasi tidak berubah
sampai user memilih sendiri.

## 5. Mengganti model (paling sering dipakai)

```powershell
Copy-Item <model-baru>.cact C:\Users\yasin\nano-money\Nano-Money\app\src\main\assets\rank64.cact -Force
cd C:\Users\yasin\nano-money\Nano-Money
.\gradlew.bat :app:assembleDebug
```

Tidak perlu menyentuh `.so`, tidak perlu NDK. Nama file di aset boleh berubah,
asal nama di `LocalEngine.kt` (`MODEL_ASSET`) ikut diubah.

### Cara menarik model 63 MB dari mesin ke laptop

API teks VM membatasi ukuran, jadi lewat port terpublikasi:

1. Buat port untuk mesin model itu (butuh API key akun mesin tersebut):
   ```
   POST /v1/machines/<machineId>/ports   {"port":8000,"name":"xfer"}
   -> url: https://8000-<machineId>.instabox.tech
   ```
2. Di mesin: salin model ke direktori kosong, lalu `python3 -m http.server 8000`.
3. Dari laptop: `curl -o rank64.cact https://8000-<machineId>.instabox.tech/<file>.cact`
4. **Verifikasi md5** (wajib) sebelum dipakai, lalu bereskan: matikan server,
   hapus berkas, dan hapus portnya lagi.
5. Catatan: `data_app/tools.json` di repo ini adalah bentuk ERA v3 (3 alat tanpa
   `enum`) yang dipakai skrip eval lama. Yang dipakai aplikasi sekarang ada di
   `LocalToolsJson.kt` (lihat §8).

## 8. Daftar kategori harus ikut dikirim ke model (perubahan 20 Okt 2026)

Temuan: aplikasi tadinya mengirim `system` hanya berisi tanggal dan `TOOLS_JSON`
dengan `category` sebagai string biasa **tanpa `enum`**. Artinya daftar kategori
tidak pernah sampai ke model -- padahal semua otak v5 (r1..r8) dilatih dengan
daftar yang selalu ada (di `enum` skema tool).

Diukur dengan mode eval `app` (bentuk aplikasi persis, `vm/list_mode.py`):

| model | cara latihnya | exact di cara latih | exact di bentuk aplikasi | kategori benar |
|---|---|---|---|---|
| r8_rank128_b | enum | 13,5% | 1,7% | 31% -> 1% |
| r5_rank128_a | enum | 12,7% | 1,7% | 43% -> 0,7% |
| rank64 (terpasang sebelum perubahan ini) | v3 | 2,5-4,2% | 1,2% | 6,2% |

Jadi keluhan "kategori, nama item, nominal ngaco" bukan tanda modelnya bodoh:
aplikasi memang tidak pernah memberi daftar yang dia butuhkan.

Perbaikannya: aplikasi **sudah punya** daftar kategori user di database
(`incomeCategories`, `expenseCategories` di `LocalTransactionParser.parseTransaction`).
Sekarang daftar itu diteruskan ke model lewat `LocalEngine.setCategories(...)`,
dan `LocalToolsJson` membangun ulang skema tool:

```json
[{"name":"catat_pengeluaran","parameters":{"type":"object","properties":{"amount":{"type":"integer"},"category":{"type":"string","enum":["Makanan", "..."]},"item":{"type":"string"},"date":{"type":"string"}},"required":["category"]}},{"name":"catat_masuk", ...}]
```

Aturan bentuknya (harus sama persis dengan latihannya):

- hanya 2 alat, urutan `catat_pengeluaran` lalu `catat_masuk` (alat `tanya`
  tidak ada di data latih v5, jadi tidak boleh dikirim)
- `category` ber-`enum` berisi daftar kategori user
- `required` = `["category"]`
- pemisah JSON tanpa spasi (mesin merender `json.dumps(..., separators=(",",":"))`)
- `system` tetap cuma baris tanggal (aturan §3 tidak berubah)

Daftar kategori kosong -> `enum` tidak dikirim (jatuh ke bentuk tanpa daftar).

Hasil setelah perubahan (simulasi aplikasi, `vm/make_app_sim.py`, 200 baris,
daftar kategori app: 6 pengeluaran + 4 pemasukan, 23 di antaranya baris
"harus diam"):

| metrik | sebelum: otak lama + app lama (tanpa daftar) | sesudah: otak baru + app baru (daftar ikut) | otak lama + app baru (jangan campur) |
|---|---|---|---|
| exact | 1,2% | **14,0%** | 2,5% |
| jenis (arah masuk/keluar) | 74,1% | **88,1%** | 44,6% |
| nama item benar | 56,3% | **78,6%** | 21,4% |
| nominal benar | 16,1% | **26,3%** | 12,9% |
| kategori benar | 6,2% | **29,5%** | 10,2% |
| patuh daftar | - | 100% | 100% |

Kolom ketiga penting: otak lama dilatih dengan bentuk era v3 (3 alat tanpa
`enum`), jadi memberi `enum` padanya justru membuatnya lebih buruk. **Bentuk
aplikasi dan otak harus dibarengkan** -- kalau otak diganti, bentuk prefix-nya
ikut disesuaikan.

Kasus "harus diam" (pesan angka saja seperti "5jt") masih gagal: 11 dari 23.
Ini tidak bisa dibenerkan di sisi aplikasi, perlu data latih tambahan.

## 6. Kalau mesin/model sumber di laptop hilang

Mesin Android diunduh sekali:

```powershell
cd C:\Users\yasin\needle-nanomoney
.\.venv\Scripts\needle.exe download android-arm64 --out build_android
```

Isi `build_android/android-arm64/`: `libneedle.a`, `needle` (CLI), `needle.h`,
`needle3.cact` (model dasar publik, bukan hasil latihan).

Model hasil latihan (`rank64.cact`) tidak bisa diunduh dari API teks VM (batas
256 KiB). Cara mengambilnya: jalankan server HTTP sementara di VM, buka satu
port, unduh, verifikasi md5, lalu tutup portnya.

- md5 `rank64.cact` yang benar: `6aa293c6fbda541ae30289d50dac75bb` (63.437.076 B)
  — otak **r8 epoch-1**, dipasang 20 Okt 2026. Model lama yang diganti:
  `4f1c756ecda063bc390382cb9218e32a` (arsip: `ck/arkas/rank64.cact.terpasang`).
- **Jangan** pakai `needle build <ckpt> --out ...` tanpa `--lora`: perintah itu
  hanya menyalin model dasar publik (35.335.380 B), bukan hasil latihan.

## 7. Cek cepat sebelum kirim ke HP

1. Ukuran aset 63.437.076 B.
2. `libneedle_jni.so` ada di `app/src/main/jniLibs/arm64-v8a/`.
3. `.\gradlew.bat :app:testDebugUnitTest` hijau.
4. APK debug terbangun dan ukurannya wajar (±63 MB lebih besar dari sebelumnya).

Daftar kalimat untuk diuji di HP: lihat `UJI_HP.md`.

## 9. Perbaikan setelah uji di HP (20 Okt 2026)

Keluhan yang muncul saat dipakai di HP: "beli bensin" masuk kategori Makanan,
deskripsi kadang kosong, dan masuk/keluar kadang tertukar.

Akar masalahnya dibuktikan dulu, bukan ditebak: `vm/probe_app.py` menjalankan
model dengan prefix PERSIS milik aplikasi (system cuma tanggal + 2 alat dengan
`enum` kategori user). Hasilnya:

- Model sendiri yang menjawab `bensin` -> `Makanan` (padahal Transportasi ada di
  daftar). Jadi bukan salah aplikasi.
- `item` sering tidak diisi model -> deskripsi kosong (13 dari 200 baris simulasi).
- "isi bensin", "transfer 25rb" -> model tidak memanggil alat sama sekali.

Tiga perbaikan di sisi aplikasi (`2205877`), semuanya diukur di 200 baris
`evcommon/eval_app_sim.jsonl` lewat `vm/measure_hint.py`:

| Perbaikan | Sebelum | Sesudah |
|---|---|---|
| Kategori dari kata kunci data latih (`CategoryHints`) | 29,5% | 37,8% (15 diperbaiki, 2 meleset) |
| Deskripsi saat `item` kosong (dari kalimat user) | 13/200 kosong | 0 kosong |
| Transaksi tanpa panggilan alat ("isi bensin") | "bukan transaksi" | tanya nominal |
| Jawaban singkat "masuk"/"50rb" | dipanggil ke model, bisa tanya berulang | dijawab aplikasi tanpa model |

Tabel kata->kategori di `CategoryHints.kt` diambil dari data latih
(`vm/build_category_hints.py`), kata ambigu (gopay, ovo, dana, total, tri)
dibuang. Saran hanya dipakai kalau kategorinya memang ada di daftar user untuk
jenis yang sudah dikoreksi; kalau user mengganti nama kategori, saran dilewati.

Kalimat untuk diuji di HP setelah memasang APK ini:

1. `beli bensin 50rb` -> Pengeluaran, Transportasi, deskripsi "Bensin".
2. `makan siang 25 ribu` -> Pengeluaran, Makanan (bukan deskripsi kosong).
3. `isi bensin` -> ditanya nominal, BUKAN "hanya bisa mencatat transaksi".
4. `terima gaji 5 juta` -> Pemasukan, Gaji.
5. `bayar wifi 300rb` -> Pengeluaran, Tagihan.
6. `5jt` lalu jawab `masuk` -> langsung Pemasukan 5.000.000 tanpa tanya lagi.

### 9a. Ronde kedua: 34 kalimat dijalankan langsung di HP (20 Okt 2026)

Setelah ronde pertama dicoba, masih ada yang salah di HP. Uji di HP dipakai
supaya yang diukur adalah mesin dan model sungguhan, bukan tiruan: 34 kalimat
dijalankan lewat `UjiHpDeviceTest` di Redmi Note 8 Pro (`am instrument`), hasilnya
dibaca dari logcat tag `UJI30`.

Yang masih salah dan sebabnya:

| Kalimat | Hasil lama | Sebab |
|---|---|---|
| `sewa kos 2 juta` | PEMASUKAN | kategori model (Freelance) menang atas kata kerja "sewa" |
| `uang kiriman ibu 500 ribu` | PENGELUARAN | "kirim" dianggap kata kerja keluar |
| `gajian 5jt` | ditanya masuk/keluar | kata "gajian" tidak dipakai sebagai bukti |
| `uang 200 ribu`, `ada 1 juta nih` | dicatat PEMASUKAN | isinya cuma nominal, model menebak arah |
| `ongkos ojek` | "bukan transaksi" | "ongkos" tidak ada di daftar kata kerja |
| `kemarin beli sepatu`, `cashback 35 ribu masuk` | item "Beli"/"Masuk" | item model berupa kata kerja, dipakai apa adanya |

Perbaikannya (`8301b72`): kata kerja user menang dari kategori model (kecuali
kalimatnya menyebut kategori arah lawan, mis. "dapat tagihan listrik"),
`transfer`/`kirim` tidak dipakai sebagai bukti arah, kalimat yang isinya cuma
nominal ditanya arahnya, dan item yang isinya cuma kata kerja dibuang supaya
deskripsi diambil dari kalimat user.

Hasil 34 kalimat yang sama, sebelum vs sesudah, di HP yang sama:

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| jenis benar | 18/22 | **21/21** |
| nominal benar | 20/22 | **21/21** |
| item benar | 20/22 | **21/21** |
| kategori benar | 22/22 | 19/21 |
| bertanya benar | 6/7 | **9/9** |
| menolak benar | 4/5 | **4/4** |
| gagal jawab | 0 | 0 |

Dua kategori yang belum kena (`cashback`, `uang kiriman ibu`) memang tidak punya
kategori bawaan yang cocok -- di data latih keduanya adalah nama kategori buatan
user, jadi di aplikasi jatuh ke "Lainnya". Itu disengaja: lebih baik "Lainnya"
daripada dikarang jadi "Gaji".

Unit test domain: 89 lulus.


## 10. Pindah ke satu aplikasi tanpa kehilangan data (20 Okt 2026)

Aplikasi lama di HP (`com.aistudio.pencatatkeuangan.jwtyqp`) ditandatangani
dengan kunci Google AI Studio, sedangkan APK dari repo ini memakai
`debug.keystore` sendiri. Android menolak menimpa (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`),
jadi data tidak bisa dipertahankan dengan cara "pasang di atas".

Urutan yang dipakai dan berhasil:

1. Cadangkan data aplikasi lama (tanpa root, karena build lama debuggable):
   `adb exec-out run-as <pkg> tar -cf - . > data-lama.tar`
   Simpan juga APK lamanya (`adb pull` dari `pm path`).
2. `adb uninstall <pkg>`, lalu pasang APK baru dengan `applicationId` yang sama
   (`versionCode`/`versionName` tetap 1/1.0 supaya pembaruan berikutnya juga
   menimpa, bukan memasang aplikasi kedua).
3. Kembalikan hanya `databases/` dan `files/`: tar di-push ke `/sdcard/Download`,
   lalu `cat ... | run-as <pkg> sh -c 'cat > restore.tar'` dan
   `tar -xf restore.tar ./databases ./files`. Jangan pakai `adb shell ... < file`
   untuk data biner: isinya terpotong.
4. Buka aplikasi satu kali. Konversi database polos -> terenkripsi berjalan
   sendiri (lihat §11).

Izin (kamera, notifikasi) tetap harus disentuh user satu kali karena MIUI
menolak `pm grant` dari shell (`Neither user 2000 ... GRANT_RUNTIME_PERMISSIONS`).

## 11. Bug konversi database yang membuat aplikasi crash (diperbaiki)

`AppDatabase.migratePlaintextToEncryptedIfNeeded` dulu mengekspor lewat
`ATTACH ... KEY x'<hex>'`. SQLCipher memperlakukan bentuk itu sebagai raw key
tanpa KDF, sedangkan jalur buka runtime (`SupportFactory(byte[])`) memakai
PBKDF2, jadi kuncinya tidak pernah cocok dan konversi selalu gagal.

Perbaikan (commit app `43495f8`):

- file sementara dibuat lewat API yang sama dengan runtime
  (`openDatabase(path, passphraseBytes, ...)`), bukan `ATTACH ... KEY x'...'`;
- DB lama dibuka sebagai `ATTACH ... AS plain KEY ''` lalu tabel disalin
  (`INSERT INTO main."t" SELECT * FROM plain."t"`) beserta `user_version`,
  sehingga Room tetap menjalankan migrasi 3->8 seperti biasa;
- berkas sementara dipindah ke direktori `databases/` (bukan `cache/`) dan
  `-wal`/`-shm` milik database polos dihapus setelah penggantian.

Hasil uji di Redmi Note 8 Pro: 13 transaksi lama kembali utuh (saldo
Rp 13.526.000), aplikasi tidak crash, dan 34 kalimat uji tetap lulus
(jenis 21/21, nominal 21/21, item 21/21, kategori 19/21, tanya 9/9, tolak 4/4).
Unit test domain: 90 lulus.
