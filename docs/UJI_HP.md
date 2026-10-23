# Uji di HP — Mode AI Lokal

Tujuan: memutuskan **cukup atau tidak** model lokal yang sudah dipasang. Bukan
menguji kecantikan jawaban, hanya 4 hal:

1. masuk/keluar benar?
2. nama item benar?
3. nominal benar?
4. kategori wajar (masuk akal untuk transaksi itu)?

Aturan tanggal: **semua transaksi tercatat pada tanggal hari ini**, apa pun kata
di kalimatnya. Jadi kalimat "kemarin" tidak diuji di sini.

Cara pakai: pasang APK, buka tab chat, pilih chip **AI Lokal**, lalu ketik 30
kalimat di bawah satu per satu. Catat hasilnya di kolom kosong.

Hasil dialog konfirmasi ("Mau catat ini?") yang dibaca — sebelum menekan
"Ya, Simpan".

---

## A. Pengeluaran dengan nominal jelas (8)

| # | Kalimat | Jenis | Item | Nominal | Kategori |
|---|---------|-------|------|---------|----------|
| 1 | beli bakso 25 ribu | | | | |
| 2 | nasi goreng 15000 | | | | |
| 3 | bayar listrik 350 ribu | | | | |
| 4 | isi bensin 100rb | | | | |
| 5 | belanja bulanan 1,5 juta | | | | |
| 6 | topup gopay 50 ribu | | | | |
| 7 | jajan kopi 18rb | | | | |
| 8 | sewa kos 2 juta | | | | |

## B. Uang masuk (6)

| # | Kalimat | Jenis | Item | Nominal | Kategori |
|---|---------|-------|------|---------|----------|
| 9 | terima gaji 5 juta | | | | |
| 10 | dapat bonus 2 juta | | | | |
| 11 | jual hp bekas 1,2 juta | | | | |
| 12 | cashback 35 ribu masuk | | | | |
| 13 | dibayar klien 3 juta | | | | |
| 14 | uang kiriman ibu 500 ribu | | | | |

## C. Nominal tidak disebut — harus BERTANYA, bukan mengarang (6)

| # | Kalimat | Model bertanya? | Pertanyaannya soal apa (nominal/jenis)? | Kalau dijawab "50 ribu", hasilnya benar? |
|---|---------|-----------------|------------------------------------------|------------------------------------------|
| 15 | bayar iBox | | | |
| 16 | beli baju | | | |
| 17 | bayar kos | | | |
| 18 | ongkos ojek | | | |
| 19 | terima transfer | | | |
| 20 | beli obat di apotek | | | |

Catatan: model yang **tidak** bertanya di sini (langsung mengarang nominal) tetap
dihitung salah, karena user diminta mengonfirmasi angka yang tidak pernah ia
sebut.

## D. Jenis transaksi ambigu — harus BERTANYA (3)

| # | Kalimat | Model bertanya soal jenis? | Kalau dijawab, benar? |
|---|---------|----------------------------|-----------------------|
| 21 | uang 200 ribu | | |
| 22 | transfer 500 ribu | | |
| 23 | ada 1 juta nih | | |

## E. Bukan transaksi — harus ditolak (4)

| # | Kalimat | Ditolak dengan sopan? |
|---|---------|-----------------------|
| 24 | apa kabar bot? | |
| 25 | cuaca hari ini bagus ya | |
| 26 | makasih ya | |
| 27 | cara hemat uang gimana? | |

## F. Kalimat campur / sulit (3)

| # | Kalimat | Jenis | Item | Nominal | Kategori |
|---|---------|-------|------|---------|----------|
| 28 | bayar tagihan wifi 300rb sama beli pulsa 25 ribu | | | | |
| 29 | kemarin beli sepatu 800 ribu | | | | |
| 30 | dikasih uang sama ayah 1 juta buat bayar kuliah | | | | |

---

## Cara menghitung hasil

Dari 27 kalimat transaksi (A, B, D, F):

- hitung berapa kalimat yang **jenisnya** benar
- berapa yang **itemnya** benar (boleh kosong kalau memang tidak ada itemnya)
- berapa yang **nominalnya** benar
- berapa yang **kategorinya** wajar
- dari 9 kalimat yang seharusnya bertanya (C, D), berapa yang benar bertanya

Keputusan:

- **Semua di atas 70%** → pemasangan sudah cukup, lanjut poles di sisi aplikasi.
- **Nominal/jenis > 70% tapi tanya < 50%** → latih ulang **fokus `tanya`** (data
  nominal/jenis diacak, 50:50, kalimat lebih beragam). Perkiraan ±8 jam kerja VM.
- **Nominal juga di bawah 70%** → ada yang salah di pemasangan (model/prompt
  prefix/tokenizer), periksa dulu sebelum latih ulang: jangan buang 8 jam.

Yang perlu dilaporkan: tabel terisi + versi APK. Kalimat yang salah **tulis apa
adanya**, jangan disaring — daftar salah itu bahan latih ulang berikutnya.

## Pemasangan APK (untuk catatan)

```
adb install -r app-debug.apk
```
