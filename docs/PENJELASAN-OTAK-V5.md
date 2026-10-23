# Penjelasan otak Nano-Money (v5) — versi bahasa manusia

Ditulis 20 Oktober 2026, 20.17 WIB. Semua angka di sini diambil dari mesin
latih dan dari aplikasi yang terpasang di HP, bukan perkiraan.

---

## 1. Sekarang aplikasi pakai otak yang mana?

Aplikasi di HP **sudah punya otak**, dan otak itu **bukan v5**.

| Hal | Isinya |
|---|---|
| Nama file | `rank64.cact` (nama file saja, isinya rank 128) |
| Ukuran | 63,4 MB |
| MD5 | `6aa293c6fbda541ae30289d50dac75bb` |
| Asal | latihan **r8 epoch-1** (tahap pertama dari dua tahap) |
| Selesai dilatih | 20 Okt 06.14 UTC (13.14 WIB) |
| Hasil di simulasi aplikasi (200 kalimat) | exact 14,0%, arah 88,1%, nama item 78,6% |

Jadi yang menjawab chat kamu sekarang adalah otak "setengah jadi" dari r8.
Ini otak terbaik dari tahap pertama. Tahap keduanya (epoch-2) masih digoreng
di 8 mesin, dan belum ada satu pun yang selesai.

---

## 2. Otak dasarnya apa?

Otaknya bernama **needle3**, buatan Cactus Compute.

- Model kecil: **121 juta parameter**, 20 lapis, kamus 8.192 kata.
- Ukuran setelah dipadatkan untuk HP: sekitar **60 MB**.
- Jenisnya khusus **tool calling**: dia tidak mengobrol panjang, tugasnya
  mengubah kalimat jadi panggilan alat seperti `catat_pengeluaran(...)`.

Analogi: needle3 itu seperti **juru catat magang yang pintar tapi belum tahu
istilah warung**. Dia sudah bisa memegang pulpen dan mengisi formulir, tapi
belum tahu bahwa "jajan bakso 15rb" artinya uang keluar, dan belum tahu
kategori apa yang dipakai aplikasi ini.

Angka aslinya, sebelum dilatih sama sekali (100 kalimat uji):

- jawaban persis benar: 28% — tapi **semua** berasal dari kalimat yang
  dijawab "bukan transaksi". Artinya dia aman tapi tidak berguna.
- nominal benar: 3,3%
- kategori benar: 1,4%
- nama item benar: 0%

Setelah dilatih sebentar saja (50 langkah), dia mulai mencatat, tapi nominal
dan kategorinya masih kacau.

### Kenapa harus dilatih?

Karena ada tiga hal yang tidak ada di otak dasarnya:

1. **Mengenali kalimat uang gaya Indonesia.** "Beli galon 22rb", "dapet
   komisi 750rb", "ada duit 750rb" — mana yang transaksi, mana yang cuma
   omongan.
2. **Mengambil isi transaksi.** Nominal, nama barang, tanggal.
3. **Memilih kategori dari daftar milik user.** Aplikasi punya kategori
   bawaan (Makanan, Transportasi, Tagihan, Gaji, ...), dan user bisa bikin
   sendiri (Kopi, Servis motor, Kucing). Otak dasar hanya tahu 11 kategori
   umum; dia belum terlatih **menyalin** nama dari daftar yang dikirim
   aplikasi. Inilah inti v5.

Tanpa latihan, aplikasi harus menebak semuanya sendiri dengan aturan tulis
tangan. Itu yang terjadi sebelum otak lokal dipasang, dan hasilnya banyak
meleset.

---

## 3. Kenapa 8 mesin, bukan 1?

Karena kita **tidak tahu resep mana yang paling enak** sebelum dicoba.
Resep yang masuk akal di atas kertas belum tentu menang di kalimat asli.

Analogi: kamu mau bikin 8 versi sambal untuk lomba. Bahan dasarnya sama
(cabe, bawang, garam), yang beda caraolah dan takarannya. Daripada masak satu
per satu (8 × 18 jam = 6 hari), kamu masak 8 dapur sekaligus dalam satu malam,
lalu juri mencicipi semuanya di meja yang sama.

"Juri" di sini adalah **599 kalimat uji yang sama** untuk semua kandidat.
Kalimat uji itu tidak ada di data latih, jadi tidak bisa dihafal.

Yang diputar sebagai variabel:

- **Letak daftar kategori**: di skema alat (`enum`), di instruksi pembuka
  (`system`), atau di kalimat user (`query`).
- **Isi data latih**: profil A (dasar) vs B (dasar + 2.000 baris yang
  menekankan "nama barang cocok dengan nama kategori").
- **Rank LoRA**: 64 vs 128. Analoginya ukuran buku catatan tambahan yang
  ditempel ke otak. Rank 128 = buku lebih tebal, daya tampung lebih besar,
  tapi juga lebih berat.
- **Jumlah epoch**: 2 vs 3. Epoch = berapa kali seluruh bahan dibaca.
  3 epoch = bahan dibaca 3 kali, lebih lama, bisa lebih hafal tapi juga
  bisa jadi terlalu kaku.
- **Batas panjang daftar kategori**: 20 nama vs tanpa batas.

### Delapan resep itu

| Run | Bedanya dalam satu kalimat |
|---|---|
| **r1_enum_a** | Daftar kategori ditaruh di skema alat. Ini kandidat "normal". |
| **r2_sys_a** | Daftar kategori ditaruh di instruksi pembuka. |
| **r3_query_a** | Daftar kategori ditaruh di kalimat user. |
| **r4_enum_b** | Sama seperti r1, tapi data latihnya ditambah 2.000 baris penekanan "cocokkan nama". |
| **r5_rank128_a** | Sama seperti r1, tapi buku catatannya (rank) lebih tebal: 128. |
| **r6_ep3_a** | Sama seperti r1, tapi bahan dibaca 3 kali, bukan 2. |
| **r7_uncapped** | Sama seperti r1, tapi daftar kategori tidak dibatasi 20 nama. Paling lama karena barisnya paling panjang. |
| **r8_rank128_b** | Gabungan: rank 128 + data profil B. Ini juara sementara. |

Kenapa ada yang mirip? Karena kalau semua variabel diubah sekaligus, kita
tidak tahu mana yang menyebabkan menang atau kalah. r1 vs r5 hanya beda rank;
r1 vs r4 hanya beda data; r1 vs r6 hanya beda epoch. Dengan begitu hasilnya
bisa dibaca.

---

## 4. Hasil sementara (baru tahap pertama)

Di 599 kalimat uji yang sama, setelah epoch-1:

- **r8: 13,5%** jawaban persis benar — terbaik.
- r5: 12,7%
- r2: 10,9%
- r1 dan r6: 10,5% (identik di tahap pertama, karena bentuk data dan seed-nya sama; r6 baru berbeda di tahap berikutnya)
- r4: 10,0%
- r3: 8,7%

13,5% kedengarannya kecil, tapi ingat: ini "seluruh isi catatan harus persis
benar" (jenis, nominal, item, kategori, tanggal sekaligus). Kalau dipecah,
arah uang sudah benar 88–91%. Nominal dan nama item masih jadi pekerjaan
rumah, dan itulah yang harus diperbaiki epoch-2.

Angka ini belum final. Epoch-2 bisa menaikkan, bisa juga tidak.

---

## 5. Sekarang 8 mesin itu di mana?

Per 20 Okt 20.17 WIB:

- **Sudah selesai tahap 1: 7 dari 8** (semua kecuali r7).
- **Sudah selesai sampai akhir: 0 dari 8.**

Posisi tahap 2:

- r6: 1050/1755 (paling maju)
- r3: 875/1755
- r2: 840/1755
- r1: 805/1755
- r5: 980/1755
- r4: 780/1980
- r8: 741/1980
- r7: 2170/3510 — masih tahap 1, memang paling berat

Perkiraan selesai (bisa bergeser):

- paling cepat **r6 sekitar 02.30 WIB**, lalu r5 ±03.10, r3 ±04.00,
  r2 ±04.20, r1 ±04.40
- r4 ±06.50
- **r8 ±08.05 WIB** (kandidat juara, jadi kita tunggu ini)
- **r7 ±11.20 WIB** (paling akhir)

Setelah model jadi, tiap mesin masih mengerjakan eval 599 kalimat + sapuan
uji batas daftar. Itu menambah ±30–90 menit per mesin. Jadi realistis:
**otak final bisa dipilih dan dipasang sekitar siang–sore 21 Oktober**, bukan
pagi-pagi.

---

## 6. Kalau semua sudah selesai, apa selanjutnya?

Urutannya sudah otomatis sebagian, lalu saya yang mengambil keputusan:

1. **Mesin menyelesaikan sendiri**: menggabungkan hasil latihan jadi satu file
   `.cact`, mengevaluasi 599 kalimat, dan menguji batas daftar kategori
   (N=3 sampai 20).
2. **Saya kumpulkan angkanya** dari 8 mesin, semua di set uji yang sama.
3. **Saya bandingkan dengan otak yang sekarang** (r8 epoch-1).
4. **Saya pilih pemenangnya.** Kalau tidak ada yang lebih baik dari otak
   sekarang, otak sekarang yang tetap dipakai. Tidak ada tukar otak berdasarkan
   harapan.
5. **Saya tarik file pemenang** ke laptop, cek MD5-nya (supaya yakin tidak
   rusak saat diunduh).
6. **Saya ganti** `app/src/main/assets/rank64.cact` dengan file itu.
7. **Build ulang APK**, pasang **menimpa** aplikasi lama di Redmi Note 8 Pro.
   Data lama tetap ada; tidak ada instalasi ganda.
8. **Uji ulang di HP**: 34 kalimat lama + 30 kalimat baru, lalu bandingkan
   dengan hasil hari ini. Ini yang menentukan apakah peningkatan di mesin
   benar-benar terasa di HP.
9. **Perbarui dokumen status dan commit** kalau hasilnya lebih baik.

Kalau di tengah jalan ada yang gagal (file tidak muncul, eval error, model
lebih buruk), saya laporkan apa adanya dan kita putuskan lagi. Tidak ada
otak yang dipasang tanpa angka.

---

## 7. Satu hal yang perlu kamu tahu

Otak baru **tidak memperbaiki bug aturan di aplikasi**. Empat temuan dari uji
30 kalimat tadi adalah kesalahan logika aplikasi, bukan kesalahan otak:

- "bunga tabungan 45 ribu" kebaca pengeluaran
- "ada duit 750rb" tidak bertanya masuk/keluar
- "servis ac kamar" ditolak, padahal harusnya tanya nominal
- "jajan bakso 15rb sama es teh 5rb" salah tanya arah

Keempatnya harus diperbaiki di kode aplikasi (kecil, tidak menyentuh otak).
Otak v5 paling banter memperbaiki **nama item** dan **pilihan kategori**.

---

## 8. Ringkasan satu paragraf

Aplikasi sekarang memakai otak r8 tahap pertama (63 MB, exact 14% di simulasi
aplikasi). Otak dasarnya needle3, model kecil 121 juta parameter yang sudah
pandai memanggil alat tapi belum tahu bahasa uang Indonesia dan kategori milik
user. Karena itu dilatih. Delapan mesin menjalankan delapan resep berbeda
supaya kita tidak menebak; semuanya diuji di 599 kalimat yang sama. Baru
tahap pertama yang selesai (7 dari 8 mesin), tahap kedua diperkirakan rampung
21 Oktober siang–sore. Sesudah itu: pilih yang terbaik, pasang di HP, uji
ulang 64 kalimat, dan baru dianggap selesai kalau angkanya memang lebih baik.
