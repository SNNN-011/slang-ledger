#!/usr/bin/env python3
"""Generator dataset v5 — kontrak mesin Needle 3 + app nano-money.

TEMUAN YANG MEMICU v4 (lihat logs/step2b_think.log, LANGKAH 0d):
- mesin native MEMAKSA token <think> sebagai token pertama tiap turn, lalu model
  menulis derivasi satu baris + </think> + <tool_call>[...]</tool_call>
  (dokumen resmi "Porting Needle 3").
- dataset v3 tidak punya `reasoning` di satu baris pun (0/16470). Akibatnya model
  dipaksa keluar distribusi tiap turn: pilihan tool jatuh ke kelas mayoritas
  (catat_pengeluaran) dan kategori rusak. Terbukti: fp32 sehat (tanya 4/4,
  masuk 4/4, kosong 4/4) tapi begitu <think> dipaksa -> 0/4, 0/4, 0/4, sama
  persis dengan .cact.
- perbaikan = setiap baris WAJIB punya `reasoning` (format resmi: satu baris
  derivasi, "'kutipan dari kalimat' -> field"), yang sekaligus mengajari grounding.

PERUBAHAN v3 -> v4:
- R1: tiap baris punya `reasoning` (derivasi satu baris: dari mana tiap nilai).
- R2: tool `tanya` DIBUANG. Mesin sudah punya jalur sendiri: nominal tak disebut
  -> panggilan masuk `suppressed_calls`, jawaban app = tanya. Jadi:
    * keluar-ber-item tanpa nominal -> catat_pengeluaran TANPA `amount`
      (schema: `amount` tidak wajib, `category` wajib) = baris "partial".
    * sinyal jenis tidak disebut ("uang 200 ribu", "transfer 500 ribu", "ada
      1 juta nih") -> balas [] (kontrak mesin: tidak ada tool yang pas). App
      yang bertanya jenis, dan app juga pembaca nominalnya sendiri (AmountReader).
- R3: kategori "lainnya" diturunkan: (a) frasa TANPA nama benda yang menunjuk
  kategori langsung (makan siang/jajan/iuran/...), (b) aturan "kalau bendanya
  disebut, `item` ikut ditulis" -- jadi "bayar listrik" mengajarkan item=listrik
  sekaligus kategori=tagihan, bukan pengeluaran tanpa item.
- R4: ronde-2 (multi-turn "Konteks sebelumnya") DIBUANG: app memanggil stateless,
  1 pesan = 1 transaksi, jadi pola itu tidak pernah dipakai.
- R5: kosong (tanpa tool/kalimat negasi & batal) ~1 dari 8 baris, sesuai saran
  resmi ("include off-topic examples with answers: []; about one in eight").
- tanggal tetap seperti v3 (G1: frasa tanggal & field "date" selalu sepadan).

PERUBAHAN v4 -> v5:
- V1: tiap baris membawa DAFTAR KATEGORI MILIK USER di `system` (dua baris tambahan,
  baris tanggal tetap baris pertama) DAN daftar yang sama sebagai `enum` pada field
  `category` di skema tool baris itu. Tujuan: model belajar MENYALIN nama dari daftar
  kalau ada yang cocok, bukan mengarang. Hasil ukur v4: daftar hanya di `enum` =
  17/28, daftar di system+enum = 15/38, jadi mekanismenya ada tapi belum dilatih.
- V2: daftar keluar selalu memuat 7 kategori bawaan app (makanan..lainnya), daftar
  masuk selalu memuat gaji/investasi/freelance/lainnya; `lainnya` tidak pernah
  dihapus. Nama custom disampel per baris (0..30) dari kosakata item generator
  (sisi keluar) dan daftar kurasi (sisi masuk), lalu diacak.
- V3: ~10% baris berjawaban sengaja menghapus 1-3 nama bawaan (meniru user yang
  menghapus kategori). Akibatnya jawaban yang seharusnya bawaan itu jatuh ke
  `lainnya` -- jalur ini juga dilatih, bukan cuma jalur "cocok".
- V4: aturan remap jawaban: nama custom yang sama persis / merupakan rentetan token
  utuh di dalam `item` -> jawab nama itu; kalau tidak ada yang cocok -> kategori v4,
  dan kalau kategori v4 sudah dihapus dari daftar -> `lainnya`. Invarian: `category`
  jawaban SELALU anggota `enum` baris itu (gerbang baru).
- V5: `reasoning` menyebut jalurnya: "(ada di daftar)" vs "(tidak ada yang cocok di
  daftar)", tetap mengutip span asli kalimat.
- V6: baris jebakan baru (~1.100) yang mostly masuk bucket exp_item/masuk: near-miss
  (benda mirip tapi tidak sama -> bawaan), paksa-cocok (melatih salin nama),
  bawaan-dihapus (-> lainnya), dan daftar besar tanpa kecocokan.
- V7: kuota 15.600 (exp_item 7.000 / exp_noitem 2.000 / masuk 3.600 / partial
  1.200 / kosong 1.800). Kunci dedup & konflik jadi (query, system) karena kalimat
  yang sama dengan daftar berbeda adalah input berbeda.

PERUBAHAN v5 -> v5.1 (env):
- LIST_CAP (default 20, `0` = tanpa batas): jumlah nama per daftar kategori
  dipangkas. Daftar panjang membuat baris ~453 token rata-rata dan pelatih
  memotong di `--max-len`. Kategori jawaban + `lainnya` selalu dipertahankan.
- PROFILE A (default) = kuota 15.600 seperti v5; PROFILE B = exp_item 9.000
  (total 17.600) dengan 2.000 baris tambahan dibias ke baris cocok-daftar, supaya
  porsi cocok-daftar naik dari ~7% ke ~19%. 15.600 baris dasar identik di A & B.

Jalankan dari folder needle-nanomoney:
    .venv\\Scripts\\python.exe generate_app_dataset.py
Output: data_app/ (bisa diarahkan ke folder lain: OUT_DIR=nama_folder)
"""
import collections
import json
import os
import random
import re
from datetime import date, timedelta

import generate_dataset as G  # kosakata merchant/nominal/harga dari generator lama

SEED = int(os.environ.get("SEED", "7"))   # SEED lain = kolam eval baru (anti-bocor)
OUT = os.environ.get("OUT_DIR", "data_app")

# ---------------------------------------------------------------- v5.1: tombol
# LIST_CAP: batas jumlah nama per daftar kategori (`0` = tanpa batas). Daftar
#   panjang membuat baris ~453 token rata-rata; pelatih `needle` memotong di
#   `--max-len`, jadi panjang daftar dibatasi. Dipakai di cap_list()/apply_v5().
# PROFILE : A = kuota 15.600 (v5 sekarang). B = exp_item 9.000 -> 17.600, dengan
#   2.000 baris tambahan yang dibias ke baris benar-benar cocok-daftar.
LIST_CAP = int(os.environ.get("LIST_CAP", "20"))
PROFILE = os.environ.get("PROFILE", "A").strip().upper()
if LIST_CAP < 0:
    raise SystemExit(f"LIST_CAP harus >= 0 (0 = tanpa batas), dapat {LIST_CAP}")
if PROFILE not in ("A", "B"):
    raise SystemExit(f"PROFILE harus 'A' atau 'B', dapat {PROFILE!r}")

DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON_ID = ["januari", "februari", "maret", "april", "mei", "juni",
          "juli", "agustus", "september", "oktober", "november", "desember"]

# "dibayar" dibuang dari sini: di aplikasi kata itu penanda uang MASUK
# (harness: "dibayar klien 3 juta" = masuk), jadi jangan dipakai sebagai kata
# kerja pengeluaran.
AKSI = ["catat", "tambahin", "catetin", "catet", "input", "inputin", "masukin",
        "tulis", "noted", "note", "rekam", "simpan", "beli", "bayar", "beliin",
        "habis", "keluar", "traktir", "jajan", "ngambil", "topup", "isi", "sewa"]

# G2: hukum sinyal jenis (SUMBER TUNGGAL — dipakai juga oleh vm/data_audit.py)
OUT_SIGNALS = ["beli", "bayar", "beliin", "habis", "keluar", "jajan", "traktir",
               "dibelikan", "dipakai", "ngambil", "pengeluaran", "belanja",
               "topup", "isi", "sewa", "makan", "sarapan", "iuran", "nonton",
               "langganan", "karaoke", "rekreasi", "periksa", "tebus", "apotek",
               "klinik", "sakit", "ongkos", "biaya", "game"]
# "dibayar"/"dikasih"/"jual"/"uang" = penanda uang MASUK, bukan pengeluaran.
IN_SIGNALS = ["masuk", "dapat", "dapet", "terima", "pemasukan", "pendapatan", "cair",
              "dibayar", "dikasih", "jual", "jualan", "uang"]
OUT_RE = re.compile(r"\b(?:%s)\b" % "|".join(OUT_SIGNALS), re.I)
IN_RE = re.compile(r"\b(?:%s)\b" % "|".join(IN_SIGNALS), re.I)

EXP_NOMINALS = [
    4000, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000,
    60000, 75000, 80000, 100000, 120000, 150000, 200000, 250000, 300000,
    350000, 400000, 500000, 600000, 750000, 800000, 1000000, 1200000,
    1500000, 2000000, 2500000, 3000000, 3500000, 5000000, 6000000, 7500000,
    10000000, 15000000,
]
INC_NOMINALS = [500000, 1000000, 1500000, 2000000, 2500000, 3000000,
                5000000, 8000000, 10000000, 12000000, 15000000, 20000000]

MERCH = {k: list(dict.fromkeys(v)) for k, v in G.merchants.items()}

# R6: kosakata item UMUM (nama barang, bukan merchant). Contoh wajib user
# ("beli es 5k", "beli bensin 50rbu") memakai kata benda, jadi `item` harus
# terlatih untuk kata benda juga -- kalau tidak, model cuma hafal 110 merchant.
ITEM_UMUM = {
    "makanan": ["es", "es teh", "kopi", "nasi", "mie", "roti", "gorengan",
                "snack", "telur", "susu", "air mineral", "tahu", "tempe", "bakso",
                "sate", "nasi goreng", "kerupuk"],
    "transportasi": ["bensin", "parkir", "tol", "tarif tol", "ojek", "angkot",
                     "tiket bus", "tiket kereta", "tambal ban", "tiket"],
    "tagihan": ["token listrik", "listrik", "kuota", "pulsa", "air", "gas",
                "iuran sampah", "iuran keamanan", "wifi", "bpjs", "sewa kos", "kos",
                "gopay", "ovo", "dana", "shopeepay", "linkaja"],
    "kesehatan": ["obat", "vitamin", "masker", "vaksin", "periksa gigi",
                  "tes lab", "perban", "plester"],
    "hiburan": ["tiket nonton", "langganan film", "tiket konser", "tiket bioskop"],
    "belanja": ["baju", "sepatu", "sabun", "sampo", "deterjen", "tas", "celana",
                "minyak goreng", "perabot", "sprei", "handuk", "baterai"],
    "lainnya": ["rokok", "kado", "donasi"],
}
MERCH = {k: list(dict.fromkeys(MERCH[k] + ITEM_UMUM.get(k, []))) for k in MERCH}
# G6: satu item = satu kategori. Kalau nama yang sama muncul di dua kategori,
# kategori pertama yang menang -- kalau tidak, ada kalimat yang sama dengan dua
# jawaban beda (generator akan menolaknya sebagai KONFLIK).
_SEEN_ITEM = {}
for _k in list(MERCH):
    _keep = []
    for _m in MERCH[_k]:
        if _m.lower() in _SEEN_ITEM:
            continue
        _SEEN_ITEM[_m.lower()] = _k
        _keep.append(_m)
    MERCH[_k] = _keep
ENUM = list(MERCH.keys()) + ["gaji", "investasi", "freelance"]

# ------------------------------------------------------------------ v5: kategori user
# Kategori bawaan app. Ini WAJIB ada di tiap daftar (kecuali ~10% baris yang
# sengaja kehilangan 1-3 nama untuk melatih jalur "bawaan dihapus -> lainnya").
DEFAULT_KELUAR = ["makanan", "transportasi", "belanja", "tagihan", "hiburan",
                  "kesehatan", "lainnya"]
DEFAULT_MASUK = ["gaji", "investasi", "freelance", "lainnya"]

# Nama custom sisi keluar = SEMUA nama item yang sudah ada di kosakata generator
# (huruf kecil, sesuai format daftar yang dibekukan) + beberapa nama realistis.
# Deterministik (di-sort) supaya sampel per baris reproducible.
_EXTRA_KELUAR = [
    "es krim", "susu kucing", "servis motor", "cuci motor", "uang jajan",
    "jajan anak", "susu bayi", "nasi padang", "kopi susu", "minuman",
    "lauk pauk", "kotak amal", "uang sekolah", "sedekah", "zakat",
    "cicilan motor", "arisan", "sabun cuci", "perlengkapan mandi",
    "obat kucing", "pasir kucing", "buku tulis", "alat tulis", "sewa motor",
    "parkir motor", "kado ultah", "uang duka", "traktir teman", "jajan pasar",
    "fotokopi", "laundry", "potong rambut", "servis ac", "gas elpiji",
    "air galon", "paket data", "langganan musik", "topup game", "donasi online",
    "iuran sekolah", "uang keamanan", "bayar tukang", "obat nyamuk",
    "vitamin anak", "masker wajah", "sabun mandi", "pasta gigi",
]
CUSTOM_KELUAR = sorted(dict.fromkeys(
    [m.lower() for ml in MERCH.values() for m in ml] + _EXTRA_KELUAR))
CUSTOM_KELUAR = [c for c in CUSTOM_KELUAR if c not in DEFAULT_KELUAR]

# Nama custom sisi masuk: daftar kurasi, nama yang wajar dipakai user.
CUSTOM_MASUK = sorted(dict.fromkeys([
    "bonus", "thr", "klien", "jual", "uang jajan", "transfer", "sampingan",
    "komisi", "upah", "honor", "lembur", "dividen", "cashback", "refund",
    "bantuan", "kiriman", "arisan", "tunjangan", "insentif", "jasa", "tips",
    "donasi", "hadiah", "hibah", "proyek", "omzet", "dagangan", "gajian",
    "bunga bank", "capital gain", "reksadana", "sewa", "uang saku",
    "uang bulanan", "uang ibu", "uang ayah", "warisan", "pesangon", "royalti",
    "beasiswa",
]))
CUSTOM_MASUK = [c for c in CUSTOM_MASUK if c not in DEFAULT_MASUK]

# Nama custom -> kategori v4 asal merchant-nya (untuk baris tambahan profil B).
# Pada baris cocok-daftar kategori jawaban DIGANTI nama custom itu, jadi peta ini
# hanya menjaga agar baris tetap wajar kalau ditelusuri manual.
CUSTOM_CAT = {}
for _cat, _ml in MERCH.items():
    for _m in _ml:
        CUSTOM_CAT.setdefault(_m.lower(), _cat)
for _m in _EXTRA_KELUAR:
    CUSTOM_CAT.setdefault(_m, "lainnya")

# target kuota v5 (total 15.600; +1.100 baris untuk jebakan kategori).
# BASE_QUOTA = komposisi beku; PROFILE B hanya menambah exp_item (+2.000).
BASE_QUOTA = {"exp_item": 7000, "exp_noitem": 2000, "masuk": 3600,
              "partial": 1200, "kosong": 1800}
QUOTA_TARGETS = dict(BASE_QUOTA)
if PROFILE == "B":
    # 2.000 baris tambahan, sengaja dibias ke baris cocok-daftar (lihat hit_rows).
    QUOTA_TARGETS["exp_item"] += 2000

# source pemasukan -> kategori (sesuai kategori default app: Gaji/Investasi/Freelance/Lainnya)
INCOME_CAT_GIVEN = {}
for s in ["gaji", "THR", "tunjangan", "bonus", "insentif", "komisi", "gajian",
          "lembur", "upah", "honor"]:
    INCOME_CAT_GIVEN[s] = "gaji"
for s in ["dividen", "bunga bank", "sewa", "capital gain", "reksadana"]:
    INCOME_CAT_GIVEN[s] = "investasi"
for s in ["freelance", "project", "proyek", "jualan", "dagangan", "sampingan", "omzet",
          "klien", "bos", "perusahaan", "pelanggan", "customer"]:
    INCOME_CAT_GIVEN[s] = "freelance"
INC_SOURCES = list(dict.fromkeys(
    G.sumber_income + ["gajian", "lembur", "upah", "honor", "proyek", "sampingan",
                       "omzet", "uang jajan", "klien", "bos", "perusahaan",
                       "pelanggan", "customer"]))
# R6: sumber yang boleh dipakai TANPA kata kerja ("gajian 5jt", "bonus 2 juta").
# "transfer"/"uang saku" sengaja TIDAK di sini: "transfer 500 ribu" & "uang 200
# ribu" harus tetap ambigu (app yang bertanya), lihat AMBIG_TPL.
BARE_INC_SOURCES = ["gajian", "gaji", "bonus", "THR", "tunjangan", "honor", "lembur",
                    "upah", "insentif", "komisi", "dividen", "bunga bank", "cashback",
                    "refund", "kiriman", "donasi", "hadiah", "hibah"]
# Sinyal masuk versi audit harus mengenali bentuk tanpa kata kerja: di
# "upah 8 juta" satu-satunya penanda arah adalah kata sumbernya sendiri.
IN_SIGNALS += [w for w in BARE_INC_SOURCES if w not in IN_SIGNALS]
IN_RE = re.compile(r"\b(?:%s)\b" % "|".join(IN_SIGNALS), re.I)


def income_cat(source):
    return INCOME_CAT_GIVEN.get(source, "lainnya")


# R6: tempat untuk template "{a} {m} di {t}" supaya kalimat seperti "beli obat di
# apotek" (kalimat uji 20) ada di distribusi. Tempat TIDAK masuk jawaban; yang
# jadi `item` tetap bendanya.
TEMPAT = ["toko", "warung", "minimarket", "pasar", "mall", "apotek", "klinik",
          "bengkel", "kantor", "stasiun"]

ITEM_TPL = [
    "{a} {m} {n}", "{a} {n} {m}", "{a} {m} seharga {n}", "{a} pengeluaran {n} buat {m}",
    "uang keluar {n} di {m}", "keluar {n} untuk {m}", "habis {n} buat {m}", "belanja {m} {n}",
    "{m} {n}", "bayar {m} {n}", "jajan di {m} {n}", "{a} {n} di {m}",
    "{a} {m} {n} {d}", "{a} {m} {d} {n}", "{a} {n} {d} di {m}", "{d} {a} {m} {n}",
    "beli {m} {d} {n}", "{a} {d} beli {m} {n}", "bayar {m} {d} {n}", "{a} {n} {m} {d}",
    "bayar {m} sebesar {n}", "habis {n} di {m}", "{a} {m} aja {n}", "habis {n} buat {m} {d}",
    "{a} {m} di {t} {n}", "{a} {m} di {t} {n} {d}",
]
NO_ITEM_TPL = [
    "catat pengeluaran {n}", "habis {n}", "keluar {n}", "uang keluar {n}",
    "catetin pengeluaran {n}", "pengeluaran {n}", "catat pengeluaran {n} {d}",
    "habis {n} {d}", "{d} catat pengeluaran {n}", "uang keluar {n} {d}",
    "bayar {n}", "bayar {n} {d}",
]

# R3: kalimat tanpa item yang TETAP menunjuk satu kategori. Frasa "jajan"/"belanja"
# pindah ke sini (di v3 mereka ada di NO_ITEM_TPL dengan kategori "lainnya", jadi
# sinyalnya saling bertabrakan). Tujuannya: kategori dilatih, bukan ditebak.
NOITEM_CAT = {
    "makanan": ["makan siang {n}", "makan malam {n}", "sarapan {n}", "jajan {n}",
                "makan di luar {n}", "jajan bareng {n}",
                "jajan {n} {d}", "makan siang {n} {d}"],
    "transportasi": ["biaya transport {n}", "ongkos perjalanan {n}",
                     "ongkos pulang {n}", "biaya transport {n} {d}"],
    "tagihan": ["iuran {n}", "bayar tagihan {n}", "bayar cicilan {n}",
                "iuran {n} {d}", "bayar tagihan {n} {d}"],
    "kesehatan": ["ke apotek {n}", "ke klinik {n}", "ke rumah sakit {n}",
                  "periksa dokter {n}", "tebus resep {n}", "ke apotek {n} {d}"],
    "hiburan": ["nonton {n}", "langganan {n}", "karaoke {n}", "main game {n}",
                "rekreasi {n}", "nonton {n} {d}"],
    "belanja": ["belanja bulanan {n}", "belanja online {n}", "belanja harian {n}",
                "belanja bulanan {n} {d}"],
    # frasa tanpa benda & tanpa penunjuk kategori -> kategori "lainnya" (default app).
    # Tanpa ember ini, kalimat seperti "keluar 50rb" tidak ada di data sama sekali.
    "lainnya": NO_ITEM_TPL,
}
INC_TPL = [
    "dapat {s} {n}", "terima {s} {n}", "masuk {s} {n}", "{s} masuk {n}", "dapet {s} {n}",
    "pemasukan {s} {n}", "uang masuk {n} dari {s}", "dapat {s} senilai {n}",
    "dapat {s} {n} {d}", "{d} dapat {s} {n}", "terima {s} {n} {d}", "{s} masuk {n} {d}",
    "uang masuk {n} dari {s} {d}", "{d} terima {s} {n}",
    "cair {s} {n}", "{s} cair {n}", "baru terima {s} {n}", "dapat {s} total {n}",
    "uang {s} {n}", "dibayar {s} {n}", "uang {s} {n} {d}", "dibayar {s} {n} {d}",
]
# R6: pemasukan tanpa sumber yang disebut ("dikasih uang 1 juta") -> kategori
# "lainnya", tanpa `item` (tidak ada benda yang bisa dikutip).
TANPA_SUMBER_TPL = [
    "dikasih uang {n}", "dikasih duit {n}", "dapat uang {n}", "dikasih uang {n} {d}",
    "dapat uang dari orang tua {n}", "dikasih uang sama ibu {n}",
]
# R6: menjual barang ("jual hp bekas 1,2 juta") -> catat_masuk, item = barangnya,
# kategori "freelance" (pemasukan bukan gaji).
JUAL_TPL = [
    "jual {m} {n}", "jual {m} {d} {n}", "{n} dari jual {m}", "jualan {m} {n}",
    "jual {m} aja {n}",
]
JUAL_ITEM = ["hp", "hp bekas", "laptop", "motor", "sepeda", "tv", "kulkas", "ac",
             "kipas", "meja", "kursi", "handphone"]

# R7: "pola inti" -- kombinasi kata kerja x item yang HARUS ada di data. Kombinasi
# acak bisa saja tidak terambil (peluangnya kecil), padahal pola inilah yang dipakai
# pengguna sehari-hari. Ini POLA, bukan kalimat uji: nominal + tanggal tetap acak,
# jadi model tetap harus membaca nominalnya sendiri.
CORE_ITEM = [
    ("makanan", "bakso", "beli", "{a} {m} {n}", None),
    ("makanan", "nasi goreng", None, "{m} {n}", None),
    ("makanan", "kopi", "jajan", "{a} {m} {n}", None),
    ("makanan", "es teh", "beli", None, None),
    ("transportasi", "bensin", "isi", "{a} {m} {n}", None),
    ("transportasi", "bensin", "beli", None, None),
    ("transportasi", "tiket bus", "beli", None, None),
    ("tagihan", "listrik", "bayar", "bayar {m} {n}", None),
    ("tagihan", "wifi", "bayar", None, None),
    ("tagihan", "gopay", "topup", "{a} {m} {n}", None),
    ("tagihan", "pulsa", "isi", "{a} {m} {n}", None),
    ("tagihan", "sewa kos", "bayar", None, None),
    ("tagihan", "bpjs", "bayar", None, None),
    ("belanja", "baju", "beli", None, None),
    ("belanja", "sepatu", "beli", None, None),
    ("kesehatan", "obat", "beli", "{a} {m} di {t} {n}", "apotek"),
    ("hiburan", "tiket bioskop", "beli", None, None),
    ("lainnya", "rokok", "beli", None, None),
]
CORE_PARTIAL = [
    ("tagihan", "kos", None, "bayar {m}", None),
    ("tagihan", "wifi", None, "bayar {m}", None),
    ("transportasi", "ojek", None, "ongkos {m}", None),
    ("belanja", "baju", None, "beli {m}", None),
    ("belanja", "iBox", None, "bayar {m}", None),
    ("makanan", "kopi", None, "jajan di {m}", None),
    ("kesehatan", "obat", "beli", "{a} {m} di {t}", "apotek"),
]
CORE_MASUK = [
    ("gaji", "terima {s} {n}"),
    ("bonus", "dapat {s} {n}"),
    ("klien", "dibayar {s} {n}"),
    ("kiriman", "uang {s} {n}"),
    ("cashback", "{s} masuk {n}"),
]
# gerbang: pasangan kata kunci ini harus benar-benar ada di data akhir
CORE_CHECK = [("isi", "bensin"), ("topup", "gopay"), ("bayar", "listrik"),
              ("beli", "bakso"), ("beli", "nasi goreng"), ("jajan", "kopi"),
              ("beli", "obat"), ("bayar", "kos"), ("ongkos", "ojek"),
              ("bayar", "iBox"), ("beli", "baju"), ("beli", "sepatu"),
              ("bayar", "wifi"), ("bayar", "bpjs"), ("beli", "tiket bioskop"),
              ("beli", "rokok"), ("terima", "gaji"), ("dapat", "bonus"),
              ("dibayar", "klien"), ("uang", "kiriman"), ("cashback", "masuk")]
# R6: bentuk tanpa kata kerja ("gajian 5jt", "bonus 2 juta") -- hanya untuk sumber
# yang arahnya tidak ambigu (BARE_INC_SOURCES).
BARE_INC_TPL = ["{s} {n}", "{s} {n} {d}", "{d} {s} {n}"]
# R2: keluar ber-item TANPA nominal -> panggilan catat_pengeluaran tanpa `amount`
# (mesin masih akan menyaring bila model tetap mengarang nominal -> suppressed_calls).
PARTIAL_TPL = [
    "beli {m}", "bayar {m}", "jajan di {m}", "catat pengeluaran buat {m}",
    "habis buat {m}", "catat {m}", "ongkos {m}", "beli {m} {d}", "bayar {m} {d}",
    "jajan di {m} {d}", "beli di {m}", "bayar ke {m}", "catat pengeluaran di {m}",
    "{a} {m} di {t}", "{a} {m} di {t} {d}",
]
# R6: pemasukan tanpa nominal ("terima transfer") -> catat_masuk tanpa `amount`.
PARTIAL_INC_TPL = [
    "terima {s}", "dapat {s}", "dapet {s}", "{s} masuk", "terima {s} {d}",
    "dapat {s} {d}", "{s} masuk {d}", "masuk {s}",
]
# R2: sinyal jenis tidak disebut -> TIDAK ada tool yang pas -> balas [] (kontrak
# mesin). App yang bertanya jenis, karena app sudah membaca nominalnya sendiri
# (AmountReader). Dulu ini baris tanya(type).
AMBIG_TPL = [
    "catat {n}", "transaksi {n}", "{n}", "tambah {n}", "input {n}", "catet {n}",
    "catat transaksi {n}", "input transaksi {n}", "catat {n} {d}", "transaksi {n} {d}",
    "masukin {n}", "tulis {n}", "nyatat {n}", "nyatet {n}", "tolong catat {n}",
    "masukin {n} {d}", "tulis {n} {d}", "nyatat {n} {d}",
    "uang {n}", "uang {n} {d}", "transfer {n}", "transfer {n} {d}",
    "ada {n}", "ada {n} nih", "{n} nih",
]
OFF_TOPIC = [
    "apa itu blockchain", "ceritakan lelucon dong", "cuaca hari ini gimana", "siapa presiden Indonesia",
    "jelaskan teori relativitas", "bagaimana cara membuat website", "apa itu machine learning",
    "rekomendasi film bagus dong", "siapa penemu lampu", "apa ibu kota Jepang",
    "bagaimana cara menanam padi", "apa itu kecerdasan buatan", "ceritakan dong",
    "hari ini tanggal berapa", "jam berapa sekarang", "apa arti hidup",
    "tolong bantu aku", "apa yang harus aku lakukan", "bagaimana cara jadi kaya",
    "apa itu cryptocurrency", "jelaskan apa itu NFT", "apa itu metaverse",
    "siapa artis favorit kamu", "apa makanan terenak", "di mana lokasi terbaik",
    "bagaimana cara belajar coding", "apa itu python", "apa itu javascript",
    "siapa pencipta facebook", "apa itu google", "apa itu microsoft",
    "rekomendasi lagu bagus dong", "apa lagu terbaru", "siapa penyanyi terkenal",
    "halo", "hai", "pagi", "malam", "terima kasih", "makasih", "assalamualaikum",
    "apa kabar", "kamu siapa", "kamu bisa apa", "bantuan", "menu", "panduan",
    "saldo saya berapa", "cek saldo dong", "berapa pengeluaran bulan ini",
    "berapa total pengeluaran aku", "apa isi dompet digital", "lihat riwayat",
    "tampilkan laporan bulan ini", "berapa sisa uang aku",
]

# R5: negasi/batal -> [] (alasan derivasi dibedakan dari off-topic biasa)
NEGASI = [
    "jangan catat beli es", "jangan catat ini", "batal catat kemarin",
    "batalin dong", "salah catat nih", "hapus yang tadi",
    "cancel transaksi terakhir", "jangan masukin pengeluaran ini",
    "bukan pengeluaran kok", "gausah catat", "ga usah dicatat",
    "jangan simpan yang tadi", "batalkan input terakhir",
]

STATS = collections.Counter()


def make_tools():
    def trx(name):
        return {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer"},
                    "category": {"type": "string"},
                    "item": {"type": "string"},
                    "date": {"type": "string"},
                },
                # R2: `amount` TIDAK wajib supaya model bisa menulis panggilan
                # separuh (item ada, nominal tidak disebut) tanpa mengarang angka.
                "required": ["category"],
            },
        }

    return [trx("catat_pengeluaran"), trx("catat_masuk")]


TOOLS = make_tools()


def tools_with_enum(keluar, masuk):
    """Skema tool PER BARIS: daftar kategori user masuk ke `enum` `category`.

    `make_tools()`/`TOOLS` sengaja tetap TANPA enum karena tools.json dipakai
    vm/step3b/step3c yang menyuntik enum-nya sendiri. Baris latih memakai
    versi ini supaya daftar di `system` dan `enum` selalu sama persis.
    """
    tools = make_tools()
    tools[0]["parameters"]["properties"]["category"] = {
        "type": "string", "enum": list(keluar)}
    tools[1]["parameters"]["properties"]["category"] = {
        "type": "string", "enum": list(masuk)}
    return tools


def make_anchor(rng):
    d = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 729))
    hm = f"{rng.randrange(0, 24):02d}:{rng.randrange(0, 60):02d}"
    return d, hm


def date_fact(d, hm):
    return f"date: {d.isoformat()} {DAY_ABBR[d.weekday()]} {hm}"


def date_variants(anchor, offset):
    """Frasa tanggal yang, di lihat dari anchor, pasti menunjuk ke ref yang sama."""
    ref = anchor + timedelta(days=offset)
    out = []
    if offset == 0:
        out += ["hari ini", "tadi", "sekarang"]
    elif offset == -1:
        out += ["kemarin", "kmrn", "kemaren"]
    elif offset == -2:
        out += ["kemarin lusa", "2 hari lalu"]
    elif offset == 1:
        out += ["besok"]
    elif offset == 2:
        out += ["besok lusa", "lusa"]
    if offset <= -3:
        out += [f"{abs(offset)} hari lalu", f"{abs(offset)} hari yang lalu"]
    if offset >= 3:
        out += [f"{offset} hari lagi"]
    if ref.year == anchor.year and ref.month == anchor.month:
        out += [f"tanggal {ref.day}", f"tgl {ref.day}"]
    if ref.year == anchor.year:
        out += [f"{ref.day} {MON_ID[ref.month - 1]}",
                f"tgl {ref.day} {MON_ID[ref.month - 1]}",
                f"{ref.day}/{ref.month:02d}", f"{ref.day}-{ref.month:02d}"]
    out += [ref.isoformat(), f"{ref.day}/{ref.month:02d}/{ref.year}"]
    return ref, out


SUF_FORM = re.compile(r"\d(?:[.,]\d+)?\s*(?:jutaan|juta|jta|jt|reibuan|reibu|ribuan|rbuan|ribu|rebu|rbu|rb|k)\b", re.I)


def pick_nominal(rng, v=None, forms=None, p_suffix=0.45):
    """G4: campur bentuk singkatan (rb/ribu/jt/juta/...) dengan bentuk penuh."""
    if forms is None:
        forms = G.format_nominal(v)
    suf = [f for f in forms if SUF_FORM.search(f)]
    full = [f for f in forms if not SUF_FORM.search(f)]
    if suf and rng.random() < p_suffix:
        STATS["nom_suffix"] += 1
        return rng.choice(suf)
    if full:
        STATS["nom_full"] += 1
        return rng.choice(full)
    return rng.choice(forms)


def choose_tpl_date(rng, pool, p_date, off_lo, off_hi, anchor):
    """G1: cabang tanggal HANYA untuk template ber-{d}; tanpa cabang -> template
    tanpa {d} (kalau pool cuma punya versi {d}, {d} dibiarkan kosong = "")."""
    with_d = [t for t in pool if "{d}" in t]
    without_d = [t for t in pool if "{d}" not in t]
    if with_d and rng.random() < p_date:
        ref, forms = date_variants(anchor, rng.randint(off_lo, off_hi))
        return rng.choice(with_d), rng.choice(forms), ref.isoformat()
    if without_d:
        return rng.choice(without_d), "", None
    return rng.choice(pool), "", None


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(s):
    return _TOKEN_RE.findall(s.lower())


def custom_hits(item, customs):
    """Nama custom yang cocok dengan `item`: sama persis atau rentetan token utuh.

    Contoh: item \"susu kucing\" cocok dengan custom \"kucing\" dan
    \"susu kucing\"; item \"kopi susu\" cocok dengan \"kopi\". Yang dikembalikan
    sudah diurutkan: token terpanjang menang, lalu karakter terpanjang, lalu
    urutan di daftar (deterministik).
    """
    hay = _tokens(item)
    hits = []
    for idx, c in enumerate(customs):
        need = _tokens(c)
        if not need or len(need) > len(hay):
            continue
        if any(hay[i:i + len(need)] == need
               for i in range(len(hay) - len(need) + 1)):
            hits.append((c, idx))
    if not hits:
        return []
    hits.sort(key=lambda h: (-len(_tokens(h[0])), -len(h[0]), h[1]))
    return [c for c, _ in hits]


def sample_n_custom(rng):
    """Sebaran jumlah nama custom per baris (0..30), sesuai rencana v5."""
    x = rng.random()
    if x < 0.25:
        return 0
    if x < 0.40:
        return rng.randint(1, 3)
    if x < 0.70:
        return rng.randint(4, 8)
    if x < 0.90:
        return rng.randint(9, 15)
    return rng.randint(16, 30)


def sample_lists(rng, side):
    """Daftar keluar/masuk untuk satu baris. `side` = sisi jawaban (atau None).

    ~10% baris berjawaban kehilangan 1-3 nama bawaan (bukan `lainnya`) supaya
    model belajar jatuh ke `lainnya` saat kategorinya sudah dihapus user.
    """
    keluar = list(DEFAULT_KELUAR)
    masuk = list(DEFAULT_MASUK)
    keluar += rng.sample(CUSTOM_KELUAR, sample_n_custom(rng))
    masuk += rng.sample(CUSTOM_MASUK, sample_n_custom(rng))
    rng.shuffle(keluar)
    rng.shuffle(masuk)
    if side and rng.random() < 0.10:
        pool = [d for d in (DEFAULT_KELUAR if side == "keluar" else DEFAULT_MASUK)
                if d != "lainnya"]
        rem = set(rng.sample(pool, min(len(pool), rng.randint(1, 3))))
        if side == "keluar":
            keluar = [c for c in keluar if c not in rem]
        else:
            masuk = [c for c in masuk if c not in rem]
    return keluar, masuk


def cap_list(rng, names, keep, cap):
    """Batasi panjang daftar kategori ke `cap` nama (`cap <= 0` = tanpa batas).

    Nama di `keep` (kategori jawaban + `lainnya`) TIDAK pernah dibuang; sisa nama
    dipangkas acak (deterministik lewat `rng`) supaya distribusi "nama yang tidak
    dipakai" tidak bias. Urutan nama di daftar dipertahankan.
    """
    if cap <= 0 or len(names) <= cap:
        return names
    keep = {k for k in keep if k in names}
    if len(keep) > cap:
        raise RuntimeError(f"LIST_CAP={cap} lebih kecil dari nama wajib {sorted(keep)}")
    drop = [c for c in names if c not in keep]
    removed = set(rng.sample(drop, len(names) - cap))
    return [c for c in names if c not in removed]


def system_v5(date_line, keluar, masuk):
    """Format `system` yang DIBEKUKAN: baris tanggal + dua baris kategori."""
    return (date_line + "\n"
            + "kategori keluar: " + "|".join(keluar) + "\n"
            + "kategori masuk: " + "|".join(masuk))


def parse_lists(system):
    """Baca balik dua baris daftar dari `system` (dipakai audit + gerbang)."""
    keluar, masuk = [], []
    for ln in (system or "").splitlines():
        low = ln.strip().lower()
        if low.startswith("kategori keluar:"):
            val = ln.split(":", 1)[1].strip()
            keluar = val.split("|") if val else []
        elif low.startswith("kategori masuk:"):
            val = ln.split(":", 1)[1].strip()
            masuk = val.split("|") if val else []
    return keluar, masuk


def row(system, query, answers, reasoning, meta=None):
    """Satu contoh latih.

    R1: `reasoning` = derivasi satu baris ala Needle, format resmi
    "'kutipan dari kalimat' -> field [nilai]" dipisah "; ". Mesin native menulis
    baris ini di dalam <think>...</think> sebelum <tool_call>...</tool_call>, dan
    loss latihan mencakup baris derivasi itu. Data v3 tidak punya field ini ->
    model dipaksa keluar distribusi tiap turn (lihat LANGKAH 0d).

    `meta` = info sementara untuk apply_v5 (sisi, item, kutipan, baris category
    asli). Dibuang sebelum ditulis; tidak pernah masuk JSONL.
    """
    r = {"system": system, "tools": TOOLS,
         "query": " ".join(query.split()), "answers": answers,
         "reasoning": " ".join(reasoning.split())}
    if meta:
        r["_meta"] = meta
    return r


def span(nilai):
    """Kutipan span asli dari kalimat user untuk derivasi."""
    return f"'{nilai}'"


def fill(tpl, **kw):
    return " ".join(tpl.format(**kw).split())


def row_bucket(r):
    """Klasifikasi baris untuk kuota v4 (dipakai generator + vm/data_audit.py)."""
    if not r["answers"]:
        return "kosong"
    a = r["answers"][0]
    args = a.get("arguments") or {}
    if a["name"] == "catat_pengeluaran":
        if "amount" not in args:
            return "partial"
        return "exp_item" if "item" in args else "exp_noitem"
    if a["name"] == "catat_masuk":
        return "masuk"
    return "kosong"


# ------------------------------------------------------------------ pembangun baris
def tpl_span(tpl):
    """Frasa tetap template (slot dikosongkan) = span nyata di kalimat user.

    Dipakai untuk mengutip *pemicu* di derivasi: \"'bayar listrik' -> category
    'tagihan'\". Untuk template yang isinya cuma slot (\"{n}\") hasilnya kosong.
    """
    t = tpl
    for s in ("n", "d", "s", "m", "a", "t"):
        t = t.replace("{" + s + "}", " ")
    return " ".join(t.split())


def trig(tpl, verb=None):
    """Kutipan pemicu yang BENAR-BENAR ada di kalimat.

    Kalau template memakai slot kata kerja ({a}) -> kutip kata kerjanya; kalau
    tidak -> frasa tetap template ("bayar {m} {n}" -> 'bayar'); template yang
    isinya cuma slot ("{m} {n}") tidak punya pemicu -> kosong.
    """
    if verb and "{a}" in tpl:
        return verb
    return tpl_span(tpl)


def mk_exp_item(rng, category, merchant, nominal, verb=None, tpl=None, tempat=None):
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, [tpl] if tpl else ITEM_TPL, 0.35, -6, 3, a)
    verb = verb or rng.choice(AKSI)
    tempat = tempat or rng.choice(TEMPAT)
    n = pick_nominal(rng, nominal)
    q = fill(tpl, a=verb, m=merchant, n=n, d=d, t=tempat)
    args = {"amount": nominal, "category": category, "item": merchant}
    pemicu = trig(tpl, verb)
    cat_line = f"{span(merchant)} -> category {span(category)}"
    why = [f"{span(pemicu)} -> catat_pengeluaran" if pemicu else "catat_pengeluaran requested",
           f"{span(n)} -> amount {nominal}",
           f"{span(merchant)} -> item", cat_line]
    if "{t}" in tpl:
        why.append(f"{span(tempat)} -> place, not part of the call")
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_pengeluaran", "arguments": args}], "; ".join(why),
               {"side": "keluar", "cat": category, "item": merchant,
                "quote": merchant, "line": cat_line})


def mk_exp_noitem(rng, category, nominal):
    """R3: keluar tanpa item. Bila frasanya menunjuk kategori (NOITEM_CAT) maka
    kategori itu yang dipakai; sisa frasa generik -> \"lainnya\"."""
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    pool = NOITEM_CAT.get(category) or NO_ITEM_TPL
    tpl, d, date_str = choose_tpl_date(rng, pool, 0.35, -6, 3, a)
    n = pick_nominal(rng, nominal)
    q = fill(tpl, n=n, d=d)
    args = {"amount": nominal, "category": category}
    sig = tpl_span(tpl)
    cat_line = (f"{span(sig)} -> category {span(category)}" if sig
                else "category 'lainnya' by default (no item, no category signal)")
    why = []
    if sig:
        why.append(f"{span(sig)} -> catat_pengeluaran")
    why.append(f"{span(n)} -> amount {nominal}")
    why.append("no item named")
    why.append(cat_line)
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_pengeluaran", "arguments": args}], "; ".join(why),
               {"side": "keluar", "cat": category, "item": None,
                "quote": sig or category, "line": cat_line})


def mk_masuk(rng, source, nominal, tpl=None):
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    pool = INC_TPL + (BARE_INC_TPL if source in BARE_INC_SOURCES else [])
    tpl, d, date_str = choose_tpl_date(rng, [tpl] if tpl else pool, 0.35, -5, 1, a)
    n = pick_nominal(rng, nominal)
    q = fill(tpl, s=source, n=n, d=d)
    cat = income_cat(source)
    args = {"amount": nominal, "category": cat, "item": source}
    sig = tpl_span(tpl)
    cat_line = f"{span(source)} -> category {span(cat)}"
    why = [f"{span(sig)} -> catat_masuk" if sig else f"{span(source)} -> catat_masuk",
           f"{span(n)} -> amount {nominal}", f"{span(source)} -> item",
           cat_line]
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_masuk", "arguments": args}], "; ".join(why),
               {"side": "masuk", "cat": cat, "item": source,
                "quote": source, "line": cat_line})


def mk_partial(rng, category, merchant, verb=None, tpl=None, tempat=None):
    """R2: keluar ber-item TANPA nominal -> panggilan tanpa `amount`.

    App memakai ini untuk bertanya nominal (nominal dibaca dulu dari kalimat oleh
    AmountReader; panggilan ini pasangan itemnya). Bila model keliru mengarang
    nominal, gate grounding mesin menyaringnya ke `suppressed_calls`.
    """
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, [tpl] if tpl else PARTIAL_TPL, 0.30, -6, 3, a)
    verb = verb or rng.choice(AKSI)
    tempat = tempat or rng.choice(TEMPAT)
    q = fill(tpl, a=verb, m=merchant, d=d, t=tempat)
    args = {"category": category, "item": merchant}
    sig = trig(tpl, verb)
    cat_line = f"{span(merchant)} -> category {span(category)}"
    why = [f"{span(sig)} -> catat_pengeluaran" if sig else "catat_pengeluaran requested",
           f"{span(merchant)} -> item", "amount not named", cat_line]
    if "{t}" in tpl:
        why.append(f"{span(tempat)} -> place, not part of the call")
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_pengeluaran", "arguments": args}], "; ".join(why),
               {"side": "keluar", "cat": category, "item": merchant,
                "quote": merchant, "line": cat_line})


def mk_ambigu(rng):
    """R2: nominal disebut, sinyal jenis TIDAK disebut -> balas [] .

    Kontrak mesin: permintaan yang tidak dilayani tool mana pun = list kosong.
    App yang bertanya "masuk atau keluar?" memakai AmountReader-nya sendiri
    (kalimat tanpa nominal -> app menolak sebagai bukan_transaksi). Dulu ini
    baris tanya(type); `tanya` dibuang karena app bisa memutuskan sendiri.
    """
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, AMBIG_TPL, 0.25, -6, 3, a)
    hid = rng.choice(EXP_NOMINALS)
    n = pick_nominal(rng, forms=[f for f in G.format_nominal(hid) if not f.startswith("Rp")])
    q = fill(tpl, n=n, d=d)
    why = [f"{span(n)} -> amount {hid}",
           "no expense/income signal, no tool fits",
           "returning no call"]
    if date_str:
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [], "; ".join(why))


def mk_partial_masuk(rng, source):
    """R6: pemasukan TANPA nominal ("terima transfer") -> catat_masuk tanpa `amount`."""
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, PARTIAL_INC_TPL, 0.30, -5, 1, a)
    q = fill(tpl, s=source, d=d)
    cat = income_cat(source)
    args = {"category": cat, "item": source}
    sig = tpl_span(tpl)
    cat_line = f"{span(source)} -> category {span(cat)}"
    why = [f"{span(sig)} -> catat_masuk" if sig else "catat_masuk requested",
           f"{span(source)} -> item", "amount not named", cat_line]
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_masuk", "arguments": args}], "; ".join(why),
               {"side": "masuk", "cat": cat, "item": source,
                "quote": source, "line": cat_line})


def mk_masuk_jual(rng, barang, nominal):
    """R6: menjual barang -> catat_masuk, `item` = barang yang dijual."""
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, JUAL_TPL, 0.30, -5, 1, a)
    n = pick_nominal(rng, nominal)
    q = fill(tpl, m=barang, n=n, d=d)
    args = {"amount": nominal, "category": "freelance", "item": barang}
    cat_line = f"{span(barang)} -> category 'freelance'"
    why = [f"{span(tpl_span(tpl) or 'jual')} -> catat_masuk",
           f"{span(n)} -> amount {nominal}", f"{span(barang)} -> item",
           cat_line]
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_masuk", "arguments": args}], "; ".join(why),
               {"side": "masuk", "cat": "freelance", "item": barang,
                "quote": barang, "line": cat_line})


def mk_masuk_tanpa_sumber(rng, nominal):
    """R6: pemasukan tanpa sumber ("dikasih uang 1 juta") -> tanpa `item`."""
    a, hm = make_anchor(rng)
    sysf = date_fact(a, hm)
    tpl, d, date_str = choose_tpl_date(rng, TANPA_SUMBER_TPL, 0.30, -5, 1, a)
    n = pick_nominal(rng, nominal)
    q = fill(tpl, n=n, d=d)
    args = {"amount": nominal, "category": "lainnya"}
    sig = tpl_span(tpl)
    cat_line = "no source named, category 'lainnya'"
    why = [f"{span(sig or 'dikasih uang')} -> catat_masuk",
           f"{span(n)} -> amount {nominal}", cat_line]
    if date_str:
        args["date"] = date_str
        why.append(f"{span(d)} -> date {date_str}")
    return row(sysf, q, [{"name": "catat_masuk", "arguments": args}], "; ".join(why),
               {"side": "masuk", "cat": "lainnya", "item": None,
                "quote": sig or "dikasih uang", "line": cat_line})


def mk_kosong(rng, topic, why=None):
    a, hm = make_anchor(rng)
    return row(date_fact(a, hm), topic, [],
               why or "no declared tool fits, returning no call")


# ------------------------------------------------------------------ v5: remap + jebakan
def apply_v5(rng, r):
    """Pasang daftar kategori per baris, enum-nya, lalu remap kategori jawaban.

    Aturan (dibekukan):
      - nama custom yang cocok dengan `item` (sama persis / rentetan token utuh)
        -> jawab nama itu apa adanya;
      - kalau tidak ada yang cocok -> kategori v4, TAPI kalau kategori itu sudah
        dihapus dari daftar -> `lainnya`;
      - `category` jawaban tidak pernah keluar dari daftar (`enum`) baris ini.
    `reasoning` menyebut jalurnya dan tetap mengutip span asli kalimat.
    """
    m = r.pop("_meta", None)
    date_line = r["system"]
    side = m["side"] if m else None
    force = m.get("force") if m else None
    if force:
        keluar, masuk = list(force[0]), list(force[1])
    else:
        keluar, masuk = sample_lists(rng, side)
    if not m or not m.get("line"):
        # Baris kosong: tidak ada kategori jawaban, cukup jaga `lainnya` + cap.
        keluar = cap_list(rng, keluar, {"lainnya"}, LIST_CAP)
        masuk = cap_list(rng, masuk, {"lainnya"}, LIST_CAP)
        r["system"] = system_v5(date_line, keluar, masuk)
        r["tools"] = tools_with_enum(keluar, masuk)
        r["_path"] = "kosong"
        return r

    lst = keluar if side == "keluar" else masuk
    defaults = DEFAULT_KELUAR if side == "keluar" else DEFAULT_MASUK
    customs = [c for c in lst if c not in defaults]
    item = m.get("item")
    hits = custom_hits(item, customs) if item else []
    if hits:
        new_cat, path = hits[0], "hit"
    elif m["cat"] in lst:
        new_cat = m["cat"]
        path = "lainnya" if new_cat == "lainnya" else "default"
    else:
        new_cat, path = "lainnya", "lainnya_dihapus"

    # Cap daftar DULU-an setelah kategori jawaban ditentukan, supaya kategori itu
    # dijamin ikut dipertahankan (butuh tetap ADA di daftar/enum).
    if side == "keluar":
        keluar = cap_list(rng, keluar, {new_cat, "lainnya"}, LIST_CAP)
        masuk = cap_list(rng, masuk, {"lainnya"}, LIST_CAP)
    else:
        masuk = cap_list(rng, masuk, {new_cat, "lainnya"}, LIST_CAP)
        keluar = cap_list(rng, keluar, {"lainnya"}, LIST_CAP)
    r["system"] = system_v5(date_line, keluar, masuk)
    r["tools"] = tools_with_enum(keluar, masuk)

    q = m.get("quote") or item or ""
    if path == "hit":
        newline = f"{span(q)} -> category '{new_cat}' (ada di daftar)"
    else:
        newline = f"{span(q)} -> category '{new_cat}' (tidak ada yang cocok di daftar)"
    r["reasoning"] = r["reasoning"].replace(m["line"], newline)
    r["answers"][0]["arguments"]["category"] = new_cat
    r["_path"] = path
    return r


def _force_exp(keluar_extra, drop=()):
    """Daftar keluar paksa untuk baris jebakan (masuk tetap bawaan)."""
    return ([d for d in DEFAULT_KELUAR if d not in drop] + list(keluar_extra),
            list(DEFAULT_MASUK))


def _force_masuk(masuk_extra, drop=()):
    return (list(DEFAULT_KELUAR),
            [d for d in DEFAULT_MASUK if d not in drop] + list(masuk_extra))


def mk_exp_trap(rng, category, item, customs, drop=()):
    """Baris keluar dengan daftar paksa (untuk near-miss / paksa-cocok / dihapus)."""
    r = mk_exp_item(rng, category, item, rng.choice(EXP_NOMINALS))
    keluar, masuk = _force_exp(customs, drop)
    rng.shuffle(keluar)
    r["_meta"]["force"] = (keluar, masuk)
    return r


def mk_masuk_trap(rng, source, customs, drop=()):
    """Baris masuk dengan daftar paksa."""
    r = mk_masuk(rng, source, rng.choice(INC_NOMINALS))
    keluar, masuk = _force_masuk(customs, drop)
    rng.shuffle(masuk)
    r["_meta"]["force"] = (keluar, masuk)
    return r


# Pasangan near-miss: benda di kalimat SENGAJA tidak sama dengan nama di daftar.
NEAR_MISS_EXP = [
    ("makanan", "nasi goreng", ["nasi padang", "es krim"]),
    ("makanan", "kopi", ["teh", "es krim"]),
    ("makanan", "es teh", ["es krim", "kopi susu"]),
    ("makanan", "mie", ["bakso", "sate"]),
    ("transportasi", "bensin", ["bbm", "pertalite"]),
    ("transportasi", "tiket bus", ["tiket kereta", "tiket konser"]),
    ("transportasi", "parkir", ["tarif tol", "bensin"]),
    ("tagihan", "listrik", ["pulsa", "wifi"]),
    ("tagihan", "kuota", ["pulsa", "paket data"]),
    ("tagihan", "wifi", ["listrik", "air galon"]),
    ("kesehatan", "obat", ["vitamin", "masker"]),
    ("kesehatan", "vitamin", ["obat", "periksa gigi"]),
    ("belanja", "susu bayi", ["kucing", "susu kucing"]),
    ("belanja", "baju", ["sepatu", "celana"]),
    ("belanja", "sabun", ["sampo", "deterjen"]),
    ("hiburan", "tiket bioskop", ["tiket konser", "langganan film"]),
    ("lainnya", "rokok", ["korek", "kado"]),
]
# Baris paksa-cocok: daftar memuat nama benda itu sendiri (melatih menyalin).
HIT_EXP = [
    ("makanan", "kopi", ["kopi"]),
    ("transportasi", "bensin", ["bensin"]),
    ("makanan", "susu kucing", ["susu kucing", "kucing"]),
    ("makanan", "es krim", ["es krim"]),
    ("transportasi", "servis motor", ["servis motor", "cuci motor"]),
    ("tagihan", "pulsa", ["pulsa"]),
    ("tagihan", "token listrik", ["token listrik", "listrik"]),
    ("belanja", "susu bayi", ["susu bayi"]),
    ("belanja", "baju", ["baju"]),
    ("kesehatan", "obat", ["obat"]),
    ("hiburan", "tiket bioskop", ["tiket bioskop"]),
    ("lainnya", "rokok", ["rokok"]),
]
NEAR_MISS_MASUK = [
    ("gajian", ["bonus", "klien"]),
    ("gaji", ["upah", "honor"]),
    ("bonus", ["thr", "komisi"]),
    ("klien", ["pelanggan", "jasa"]),
    ("cashback", ["refund", "dividen"]),
    ("kiriman", ["transfer", "bantuan"]),
    ("jualan", ["jual", "omzet"]),
]


def exp_traps(rng):
    """~1.000 baris jebakan sisi keluar (mostly bucket exp_item)."""
    out = []
    # 300 near-miss: daftar memuat benda terkait tapi TIDAK sama -> bawaan.
    for i in range(300):
        cat, item, customs = NEAR_MISS_EXP[i % len(NEAR_MISS_EXP)]
        out.append(mk_exp_trap(rng, cat, item, customs))
    # 300 paksa-cocok: nama benda ADA di daftar -> jawab nama itu.
    for i in range(300):
        cat, item, customs = HIT_EXP[i % len(HIT_EXP)]
        out.append(mk_exp_trap(rng, cat, item, customs))
    # 200 bawaan dihapus (tanpa nama cocok) -> lainnya.
    for i in range(200):
        cat = rng.choice([d for d in DEFAULT_KELUAR if d != "lainnya"])
        item = rng.choice(MERCH[cat])
        out.append(mk_exp_trap(rng, cat, item, [], drop=(cat,)))
    # 200 daftar besar tanpa kecocokan -> bawaan (menguji list size besar).
    for _ in range(200):
        cat, ml = rng.choice(list(MERCH.items()))
        item = rng.choice(ml)
        safe = [c for c in CUSTOM_KELUAR if not custom_hits(item, [c])]
        customs = rng.sample(safe, rng.randint(8, 20))
        out.append(mk_exp_trap(rng, cat, item, customs))
    return out


def masuk_traps(rng):
    """~100 baris jebakan sisi masuk."""
    out = []
    for i in range(50):
        src = rng.choice([s for s in INC_SOURCES if s.lower() not in DEFAULT_MASUK])
        out.append(mk_masuk_trap(rng, src, [src.lower()]))
    for i in range(30):
        src, customs = NEAR_MISS_MASUK[i % len(NEAR_MISS_MASUK)]
        out.append(mk_masuk_trap(rng, src, customs))
    for i in range(20):
        src = rng.choice([s for s in INC_SOURCES if income_cat(s) == "gaji"])
        out.append(mk_masuk_trap(rng, src, [], drop=(income_cat(src),)))
    return out


def build_quota(rng, target, cands):
    if len(cands) < target:
        raise RuntimeError(f"kandidat kurang: {len(cands)} < {target}")
    return rng.sample(cands, target)


# ------------------------------------------------------------------ profil B
HIT_ITEM_SUFFIX = ["langganan", "bulanan", "toko", "online", "lagi", "aja"]


def mk_hit_row(rng, name):
    """Baris exp_item yang DIJAMIN cocok-daftar: `name` (nama custom) ada di daftar.

    Dipakai profil B untuk menaikkan porsi cocok-daftar. `name` dimasukkan ke
    daftar paksa keluar lewat `_meta["force"]`, dan `item` dibuat memuat `name`
    (sama persis / dengan akhiran). Nama custom lain yang kebetulan cocok
    disaring, supaya `name`-lah yang jadi jawaban.
    """
    cat = CUSTOM_CAT.get(name, "lainnya")
    v = rng.random()
    if v < 0.55:
        item = name
    elif v < 0.80:
        item = f"{name} {rng.choice(HIT_ITEM_SUFFIX)}"
    else:
        item = name.title()
    r = mk_exp_item(rng, cat, item, rng.choice(EXP_NOMINALS))
    safe = [c for c in CUSTOM_KELUAR if c != name and not custom_hits(item, [c])]
    extra = rng.sample(safe, min(len(safe), rng.randint(0, 6)))
    keluar = list(dict.fromkeys(list(DEFAULT_KELUAR) + [name] + extra))
    rng.shuffle(keluar)
    r["_meta"]["force"] = (keluar, list(DEFAULT_MASUK))
    return r


def hit_rows(rng, count):
    """`count` baris ber-bias cocok-daftar (profil B).

    Kandidat dibuat 2x lalu disampel (kolisi (query, system) hampir nol, tapi
    biar aman). Kalau pool nyata kurang dari `count`, kembalikan apa adanya --
    jumlah nyata dilaporkan lewat statistik.
    """
    pool = [c for c in CUSTOM_KELUAR if c not in DEFAULT_KELUAR]
    cands = [mk_hit_row(rng, rng.choice(pool)) for _ in range(count * 2)]
    if len(cands) < count:
        return cands
    return rng.sample(cands, count)


def gen(rng):
    STATS.clear()
    ex = []

    # ---------------- exp_item 7.000: keluar ber-item + nominal, termasuk ~1.000
    # baris jebakan kategori (near-miss / paksa-cocok / bawaan dihapus / tanpa cocok)
    traps = exp_traps(rng)
    cands = [mk_exp_item(rng, cat, m, nom)
             for cat, ml in MERCH.items() for m in ml
             for nom in EXP_NOMINALS for _ in range(3)]
    item_rows = build_quota(rng, BASE_QUOTA["exp_item"] - len(traps), cands)
    core = [mk_exp_item(rng, c, m, rng.choice(EXP_NOMINALS), verb=v, tpl=t, tempat=tp)
            for c, m, v, t, tp in CORE_ITEM]
    item_rows[:len(core)] = core
    item_rows += traps
    ex.extend(item_rows)

    # ---------------- exp_noitem 2.000: frasa tanpa item yang menunjuk kategori (R3)
    cands = [mk_exp_noitem(rng, cat, nom)
             for cat, tpls in NOITEM_CAT.items() if tpls
             for nom in EXP_NOMINALS
             for _ in range(16 if cat == "lainnya" else 24)]
    ex.extend(build_quota(rng, QUOTA_TARGETS["exp_noitem"], cands))

    # ---------------- masuk 3.600 = 3.200 bentuk sumber + 300 bentuk R6 + 100 jebakan
    # (150 tanpa nominal, 100 jual barang, 50 tanpa sumber)
    masuk_trap_rows = masuk_traps(rng)
    cands = [mk_masuk(rng, s, nom) for s in INC_SOURCES
             for nom in INC_NOMINALS for _ in range(10)]
    masuk_rows = build_quota(rng, QUOTA_TARGETS["masuk"] - 300 - len(masuk_trap_rows), cands)
    core = [mk_masuk(rng, s, rng.choice(INC_NOMINALS), tpl=t) for s, t in CORE_MASUK]
    masuk_rows[:len(core)] = core
    masuk_rows += masuk_trap_rows
    masuk_rows += [mk_partial_masuk(rng, rng.choice(INC_SOURCES)) for _ in range(150)]
    masuk_rows += [mk_masuk_jual(rng, rng.choice(JUAL_ITEM), rng.choice(INC_NOMINALS))
                   for _ in range(100)]
    masuk_rows += [mk_masuk_tanpa_sumber(rng, rng.choice(INC_NOMINALS))
                   for _ in range(50)]
    ex.extend(masuk_rows)

    # ---------------- partial 1.200: item ada, nominal tidak disebut (R2)
    cands = [mk_partial(rng, cat, m)
             for cat, ml in MERCH.items() for m in ml for _ in range(18)]
    part_rows = build_quota(rng, QUOTA_TARGETS["partial"], cands)
    core = [mk_partial(rng, c, m, verb=v, tpl=t, tempat=tp)
            for c, m, v, t, tp in CORE_PARTIAL]
    part_rows[:len(core)] = core
    ex.extend(part_rows)

    # ---------------- kosong 1.800 (R5 ~1 dari 8) = negasi + ambigu + di luar topik
    n_neg, n_amb = 300, 600
    cands = [mk_kosong(rng, t, "request negates the entry, returning no call")
             for t in NEGASI for _ in range(40)]
    ex.extend(build_quota(rng, n_neg, cands))
    cands = [mk_ambigu(rng) for _ in range(2800)]
    ex.extend(build_quota(rng, n_amb, cands))
    cands = [mk_kosong(rng, t) for t in OFF_TOPIC for _ in range(30)]
    ex.extend(build_quota(rng, QUOTA_TARGETS["kosong"] - n_neg - n_amb, cands))

    # ---------------- profil B: baris tambahan ber-bias cocok-daftar.
    # rng TERPISAH supaya 15.600 baris dasar tetap identik dengan profil A
    # (hanya baris tambahan ini yang berbeda).
    extra_hit = QUOTA_TARGETS["exp_item"] - BASE_QUOTA["exp_item"]
    if extra_hit > 0:
        ex.extend(hit_rows(random.Random(SEED + 11), extra_hit))

    # ---------------- v5: pasang daftar kategori + enum + remap jawaban per baris
    ex = [apply_v5(rng, r) for r in ex]

    return ex


def main():
    rng = random.Random(SEED)
    ex = gen(rng)

    # ------------------------------------------------- dedup + larangan konflik (G6)
    seen = {}
    kept = []
    dup = 0
    for r in ex:
        key = (r["query"], r["system"])
        val = json.dumps(r["answers"], sort_keys=True, ensure_ascii=False)
        if key in seen:
            if seen[key] == val:
                dup += 1
                continue
            raise RuntimeError(f"KONFLIK (query,system) sama: {r['query'][:90]!r}")
        seen[key] = val
        kept.append(r)
    ex = kept
    # Konflik sejati = (query, system) sama tapi jawaban beda BUKAN cuma di field
    # date. Kunci wajib (query, system): kalimat sama dengan daftar kategori
    # berbeda adalah input berbeda (v5), jadi jawaban berbeda itu sah.
    def ans_sig(answers):
        out = []
        for a in answers:
            args = a.get("arguments") or {}
            rest = tuple(sorted((k, v) for k, v in args.items() if k != "date"))
            out.append((a.get("name"), rest, "date" in args))
        return tuple(out)
    qmap = collections.defaultdict(set)
    for r in ex:
        qmap[(r["query"], r["system"])].add(ans_sig(r["answers"]))
    konf = [q for q, s in qmap.items() if len(s) > 1]
    if konf:
        raise RuntimeError(f"KONFLIK (query,system) (jawaban beda selain date): {konf[:3]}")

    # R7: gerbang pola inti -- kombinasi kata kerja x item wajib ada di data.
    hilang = [f"{v} {m}" for v, m in CORE_CHECK
              if not any(v.lower() in r["query"].lower() and m.lower() in r["query"].lower()
                         for r in ex)]
    if hilang:
        raise RuntimeError(f"pola inti hilang: {hilang}")

    # gerbang: `amount` hanya boleh ada kalau nominalnya BENAR-BENAR disebut.
    # Kalau tidak, model belajar mengarang nominal (dan app jadi salah catat).
    # Arah sebaliknya tidak digerbang: kalimat boleh memuat tanggal (angka)
    # tanpa nominal -- itu justru alasan AmountReader butuh penjaga tanggal.
    tanpa_angka = [r["query"] for r in ex
                   if r["answers"]
                   and "amount" in (r["answers"][0].get("arguments") or {})
                   and not re.search(r"[0-9]", r["query"])]
    if tanpa_angka:
        raise RuntimeError(f"amount tanpa nominal di kalimat: {tanpa_angka[:3]}")

    # ---------------- GATE A (v5): daftar di system == enum tool, category anggota enum
    for r in ex:
        lines = r["system"].split("\n")
        if len(lines) != 3 or not lines[0].startswith("date: ") \
                or not lines[1].startswith("kategori keluar: ") \
                or not lines[2].startswith("kategori masuk: "):
            raise RuntimeError(f"format system v5 salah: {r['system'][:90]!r}")
        keluar, masuk = parse_lists(r["system"])
        if not keluar or not masuk or "lainnya" not in keluar or "lainnya" not in masuk:
            raise RuntimeError(f"daftar kategori kosong/tanpa lainnya: {r['system'][:90]!r}")
        if len(set(keluar)) != len(keluar) or len(set(masuk)) != len(masuk):
            raise RuntimeError(f"nama kategori duplikat: {r['system'][:90]!r}")
        if LIST_CAP > 0 and (len(keluar) > LIST_CAP or len(masuk) > LIST_CAP):
            raise RuntimeError(
                f"daftar melebihi LIST_CAP={LIST_CAP} "
                f"(keluar {len(keluar)}, masuk {len(masuk)}): {r['query'][:60]!r}")
        if r["tools"] != tools_with_enum(keluar, masuk):
            raise RuntimeError(f"enum != daftar system: {r['query'][:60]!r}")
        if not r["answers"]:
            continue
        a = r["answers"][0]
        cat = (a.get("arguments") or {}).get("category")
        enum = keluar if a.get("name") == "catat_pengeluaran" else masuk
        if cat not in enum:
            raise RuntimeError(f"category '{cat}' bukan anggota enum: {r['query'][:60]!r}")

    # ---------------- GATE B (v5): >= 1.800 baris tanpa kecocokan kategori user
    n_kat = sum(1 for r in ex if r["answers"])
    no_match = sum(1 for r in ex
                   if r.get("_path") in ("default", "lainnya", "lainnya_dihapus"))
    if no_match < 1800:
        raise RuntimeError(f"baris tanpa cocok cuma {no_match} (< 1800)")
    same_item_cat = sum(
        1 for r in ex if r["answers"]
        and (r["answers"][0].get("arguments") or {}).get("item")
        == (r["answers"][0].get("arguments") or {}).get("category"))
    pc = collections.Counter(r.get("_path") for r in ex)
    # `_path` hanya untuk statistik; jangan pernah ikut ditulis ke JSONL.
    for r in ex:
        r.pop("_path", None)

    rng.shuffle(ex)

    n = len(ex)
    # split TERSTRATIFIKASI per bucket kuota: tiap file mempertahankan
    # proporsi target §8.1 persis (gate kuota audit dijamin lolos, dan
    # distribusi test = distribusi training).
    groups = collections.defaultdict(list)
    for r in ex:
        groups[row_bucket(r)].append(r)
    train, validation, test = [], [], []
    for rows in groups.values():
        nt, nv = round(len(rows) * 0.8), round(len(rows) * 0.1)
        train += rows[:nt]
        validation += rows[nt:nt + nv]
        test += rows[nt + nv:]
    rng.shuffle(train)
    rng.shuffle(validation)
    rng.shuffle(test)

    os.makedirs(os.path.join(OUT, "exp"), exist_ok=True)

    def dump(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump(os.path.join(OUT, "train.jsonl"), train)
    dump(os.path.join(OUT, "validation.jsonl"), validation)
    dump(os.path.join(OUT, "test.jsonl"), test)
    finetune = train + validation
    dump(os.path.join(OUT, "finetune.jsonl"), finetune)
    with open(os.path.join(OUT, "tools.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(TOOLS, separators=(",", ":"), ensure_ascii=False))

    rng2 = random.Random(1234)
    quick1000 = rng2.sample(finetune, 1000)
    dump(os.path.join(OUT, "exp", "quick1000.jsonl"), quick1000)
    rng3 = random.Random(5)
    shards = quick1000[:]
    rng3.shuffle(shards)
    for i in range(5):
        dump(os.path.join(OUT, "exp", f"shard{i + 1}.jsonl"), shards[i * 200:(i + 1) * 200])

    rng4 = random.Random(99)
    off_test = [r for r in test if not r["answers"]]
    other_test = [r for r in test if r["answers"]]
    eval_rows = off_test + rng4.sample(other_test, min(280, len(other_test)))
    rng4.shuffle(eval_rows)
    dump(os.path.join(OUT, "exp", "eval.jsonl"), eval_rows)

    # eval1000: sampel terstratifikasi 1000 baris dari test (paritas eval E5/E1)
    rng5 = random.Random(1000)
    tgroups = collections.defaultdict(list)
    for r in test:
        tgroups[row_bucket(r)].append(r)
    eval1000 = []
    skala = 1000.0 / max(1, len(test))
    for rows in tgroups.values():
        eval1000 += rng5.sample(rows, max(1, round(len(rows) * skala)))
    rng5.shuffle(eval1000)
    dump(os.path.join(OUT, "exp", "eval1000.jsonl"), eval1000)

    # ------------------------------------------------------------------ statistik
    bucket = collections.Counter(row_bucket(r) for r in ex)
    print(f"out dir     : {OUT}")
    print(f"profil      : {PROFILE} (target total {sum(QUOTA_TARGETS.values())}) "
          f"| LIST_CAP {LIST_CAP if LIST_CAP else '0 (tanpa batas)'}")
    qup = len({r["query"] for r in ex})
    print(f"total       : {n} (target {sum(QUOTA_TARGETS.values())}, drop dedup {dup}, "
          f"konflik 0, date-dup {n - qup})")
    print("kuota v5    :")
    for b in ("exp_item", "exp_noitem", "masuk", "partial", "kosong"):
        got, tgt = bucket.get(b, 0), QUOTA_TARGETS[b]
        dev = (got - tgt) / tgt * 100
        flag = "OK" if abs(dev) <= 10 else "!!"
        print(f"  {b:<13} {got:>6} / {tgt:>6}  ({dev:+5.1f}%) {flag}")
    suff = STATS["nom_suffix"] + STATS["nom_full"]
    if suff:
        print(f"bentuk nom  : singkatan {STATS['nom_suffix']} / total {suff} "
              f"({STATS['nom_suffix'] / suff * 100:.1f}%)")
    print(f"split       : train {len(train)} / valid {len(validation)} / test {len(test)}")
    tanpa_why = sum(1 for r in ex if not r.get("reasoning"))
    pj = [len(r["reasoning"]) for r in ex if r.get("reasoning")]
    print(f"reasoning   : kosong {tanpa_why} (harus 0) | rata-rata {sum(pj) // max(1, len(pj))} char "
          f"| terpanjang {max(pj) if pj else 0}")
    print(f"tool        : {[t['name'] for t in TOOLS]} | required(pengeluaran) "
          f"{TOOLS[0]['parameters']['required']}")
    kat = collections.Counter((r["answers"][0]["arguments"].get("category")
                               if r["answers"] else "(kosong)") for r in ex)
    print(f"kategori    : {dict(kat.most_common(15))}")
    # ---- statistik v5 (jalur kategori + sebaran ukuran daftar)
    if n_kat:
        print(f"kategori v5 : cocok-daftar {pc.get('hit', 0)} ({pc.get('hit', 0) / n_kat * 100:.1f}%)"
              f" | bawaan {pc.get('default', 0)} ({pc.get('default', 0) / n_kat * 100:.1f}%)"
              f" | lainnya-dihapus {pc.get('lainnya_dihapus', 0)}"
              f" ({pc.get('lainnya_dihapus', 0) / n_kat * 100:.1f}%)"
              f" | lainnya-bawaan {pc.get('lainnya', 0)}")
    print(f"tanpa cocok : {no_match} (gate >=1800) | category==item {same_item_cat} "
          f"({same_item_cat / max(1, n_kat) * 100:.2f}%)")
    sizes = collections.Counter(len(parse_lists(r["system"])[0]) - len(DEFAULT_KELUAR)
                                for r in ex)
    grp = collections.Counter()
    for k, v in sizes.items():
        grp["0" if k <= 0 else "1-3" if k <= 3 else "4-8" if k <= 8
            else "9-15" if k <= 15 else "16-20" if k <= 20 else "21+"] += v
    tail = f" 21+={grp['21+']}" if grp["21+"] else ""
    print(f"ukuran daftar keluar (di atas 7 bawaan): "
          f"0={grp['0']} 1-3={grp['1-3']} 4-8={grp['4-8']} 9-15={grp['9-15']} 16-20={grp['16-20']}{tail}")
    msz = collections.Counter(len(parse_lists(r["system"])[1]) - len(DEFAULT_MASUK)
                              for r in ex)
    mgrp = collections.Counter()
    for k, v in msz.items():
        mgrp["0" if k <= 0 else "1-3" if k <= 3 else "4-8" if k <= 8
             else "9-15" if k <= 15 else "16-20" if k <= 20 else "21+"] += v
    mtail = f" 21+={mgrp['21+']}" if mgrp["21+"] else ""
    print(f"ukuran daftar masuk  (di atas 4 bawaan): "
          f"0={mgrp['0']} 1-3={mgrp['1-3']} 4-8={mgrp['4-8']} 9-15={mgrp['9-15']} 16-20={mgrp['16-20']}{mtail}")
    print(f"pakai date  : {sum(1 for r in ex if r['answers'] and 'date' in r['answers'][0].get('arguments', {}))}")
    print(f"pakai item  : {sum(1 for r in ex if r['answers'] and 'item' in r['answers'][0].get('arguments', {}))}")
    print(f"query unik  : {len({r['query'] for r in ex})}")
    print(f"pola inti   : {len(CORE_CHECK)}/{len(CORE_CHECK)} ada (kata kerja x item)")
    print(f"query terpanjang: {max(len(r['query']) for r in ex)} char")
    for p in ["train.jsonl", "validation.jsonl", "test.jsonl", "finetune.jsonl",
              "exp/quick1000.jsonl", "exp/shard1.jsonl", "exp/eval.jsonl",
              "exp/eval1000.jsonl", "tools.json"]:
        print(f"  {p:<24} {os.path.getsize(os.path.join(OUT, p)):>9,} B")


if __name__ == "__main__":
    main()
