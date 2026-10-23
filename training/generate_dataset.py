#!/usr/bin/env python3
"""Generator dataset nano money untuk fine-tune Needle.
Dijalankan dengan: uv run generate_dataset.py
"""
import json
import random
from datetime import datetime, timedelta

random.seed(42)

# ============================================================
# KOMPONEN KALIMAT
# ============================================================

# Merchant lokal (sesuai kategori)
# G6: satu merchant = satu kategori. Indomaret/Alfamart hanya di "belanja".
merchants = {
    "makanan": ["warteg", "Kopi Kenangan", "Kopken", "Starbucks", "warung bakso", "Gacoan", "Ayam Geprek Bensu", "Solaria", "HokBen", "KFC", "McD", "JCO", "Dunkin", "Yoshinoya", "Bakso Malang", "Mie Ayam", "Seblak", "Sate Taichan", "Martabak", "Pecel Lele", "Nasi Padang", "Dimsum", "Seblak", "Bakmie"],
    "transportasi": ["Gojek", "Grab", "SPBU Pertamina", "SPBU Shell", "SPBU Total", "Pertamini", "Maxim", "Indriver", "Bengkel", "JNE", "J&T", "SiCepat", "Anterin", "Paxel"],
    "hiburan": ["Netflix", "Spotify", "YouTube Premium", "Disney+", "Vidio", "Bioskop XXI", "CGV", "Game Topup", "Steam", "PS Store", "Nintendo eShop", "Genflix", "WeTV", "Viu", "Iflix", "Loket", "Tiket.com", "Traveloka"],
    "tagihan": ["PLN", "PDAM", "Indihome", "Telkomsel", "XL", "Tri", "Smartfren", "BPJS", "Pulsa", "Gas LPG", "Air Galon", "Iuran RT", "Iuran RW", "Listrik", "Wifi", "Kuota", "Internet"],
    "kesehatan": ["Apotek", "Apotek K-24", "Apotek Kimia Farma", "Dokter", "Klinik", "Rumah Sakit", "Bidan", "Lab", "Vitamin", "Obat", "Masker", "Hand Sanitizer", "Tes Covid"],
    "belanja": ["Indomaret", "Alfamart", "Alfamidi", "Superindo", "Giant", "Hypermart", "Lotte Mart", "Transmart", "Ramayana", "Matahari", "Erafone", "iBox", "Electronic City", "Bhinneka", "Blibli", "Tokopedia", "Shopee", "Lazada", "Bukalapak"],
    "lainnya": ["Toko", "Warung", "Pasar", "Mall", "Online Shop", "e-Commerce"],
}

# Aksi user
aksi_tambah = [
    "catat", "tambahin", "catetin", "input", "tulis", "log", "noted", "save", "masukin", "kasih tau", "cerita", "aku",
    "habis", "beli", "bayar", "keluar", "dipakai", "dibayar", "dibelikan", "traktir", "ngambil",
    "catet", "masukkan", "inputin", "tambah", "note", "rekam", "simpan",
]

aksi_query = [
    "pengeluaran", "habis", "belanja", "konsumsi", "total",
    "berapa", "gimana", "gimana", "bagaimana", "cek", "liat", "lihat", "lapor", "rangkum",
]

periode = {
    "hari_ini": ["hari ini", "sehari", "hari ini", "tgl ini", "tanggal ini", "daily", "harian"],
    "minggu_ini": ["minggu ini", "sepekan", "7 hari terakhir", "mingguan", "weekly", "seminggu", "pekan ini"],
    "bulan_ini": ["bulan ini", "sebulan", "30 hari terakhir", "bulanan", "monthly", "sebulan terakhir", "bulan"],
}

# Sumber pemasukan
sumber_income = [
    "gaji", "THR", "tunjangan", "bonus", "insentif", "komisi", "freelance", "project", "jualan", "dagangan",
    "hadiah", "uang saku", "kasbon", "cashback", "dividen", "bunga bank", "sewa", "refund", "pengembalian dana",
    "uang saku orang tua", "transfer", "kiriman", "donasi", "hibah", "grant", "pajak refund", "asuransi",
]

# ============================================================
# GENERATOR KALIMAT NOMINAL
# ============================================================

def format_nominal(value):
    """Generate variasi penulisan nominal yang bisa user ketik."""
    formats = []
    
    # Jutaan (1jt, 1.5jt, 2jt, 2.5jt, dst) — PRIORITAS, cek dulu sebelum ribuan
    if value >= 1000000:
        # Cek apakah value kelipatan juta (1jt, 2jt, 5jt)
        if value % 1000000 == 0:
            juta = value // 1000000
            if juta > 0:
                # Untuk juta >= 10, pakai "15 juta" bukan "15jt" (lebih jelas)
                if juta >= 10:
                    formats.append(f"{juta} juta")
                    formats.append(f"Rp {juta} juta")
                    formats.append(f"{juta}000000")
                    formats.append(f"{juta}.000.000")
                    formats.append(f"Rp {juta}.000.000")
                else:
                    formats.append(f"{juta} juta")
                    formats.append(f"{juta}jt")
                    formats.append(f"{juta} jt")
                    formats.append(f"{juta} jta")
                    formats.append(f"{juta} jutaan")
                    formats.append(f"Rp {juta}jt")
                    formats.append(f"Rp {juta} juta")
                    formats.append(f"Rp {juta} jta")
                    formats.append(f"{juta}000000")
                    formats.append(f"{juta}.000.000")
                    formats.append(f"Rp {juta}.000.000")
                    formats.append(f"Rp{juta}jt")
                    formats.append(f"{juta}.000.000,-")
                    formats.append(f"Rp. {juta}.000.000")
        # Format desimal (1,5jt, 2,5jt, dst) — value bukan kelipatan juta
        # CATATAN v3: gaya Indonesia = koma desimal ("2,5jt"). Bentuk gabungan
        # ("2.5.000.000", "2.5000000") dulu bug (terbaca 2,5 juta) — diganti
        # bentuk penuh yang benar ("2500000", "2.500.000").
        else:
            juta_desimal = value / 1000000
            juta_id = f"{juta_desimal:g}".replace(".", ",")
            full_plain = f"{value}"
            full_dot = f"{value:,}".replace(",", ".")
            formats.append(f"{juta_id} juta")
            formats.append(f"{juta_id}jt")
            formats.append(f"{juta_id} jt")
            formats.append(f"{juta_id} jta")
            formats.append(f"{juta_id} jutaan")
            formats.append(f"Rp {juta_id}jt")
            formats.append(f"Rp {juta_id} juta")
            formats.append(f"Rp {juta_id} jta")
            formats.append(full_plain)
            formats.append(full_dot)
            formats.append(f"Rp {full_dot}")
            formats.append(f"Rp{juta_id}jt")
            formats.append(f"{full_dot},-")
            formats.append(f"Rp. {full_dot}")
    
    # Ratusan ribu (100rb, 150rb, dst)
    if value >= 100000 and value % 1000 == 0 and value < 1000000:
        ratus_ribu = value // 1000
        formats.append(f"{ratus_ribu} ribu")
        formats.append(f"{ratus_ribu}k")
        formats.append(f"{ratus_ribu}rb")
        formats.append(f"{ratus_ribu}rbuan")
        formats.append(f"Rp {ratus_ribu}rb")
        formats.append(f"Rp {ratus_ribu}.000")
        formats.append(f"{ratus_ribu}.000")
        formats.append(f"{ratus_ribu} rebu")
        formats.append(f"{ratus_ribu} reibuan")
        formats.append(f"Rp. {ratus_ribu}.000")
        formats.append(f"{ratus_ribu} k")
    
    # Ribuan (5rb, 15rb, 50rb, dst) — untuk value < 100000
    if value >= 1000 and value % 1000 == 0 and value < 100000:
        ribu = value // 1000
        formats.append(f"{ribu} ribu")
        formats.append(f"{ribu}k")
        formats.append(f"{ribu}rb")
        formats.append(f"{ribu}rbuan")
        formats.append(f"{ribu} rbu")
        formats.append(f"Rp {ribu}rb")
        formats.append(f"Rp {ribu}.000")
        formats.append(f"Rp{ribu}rb")
        formats.append(f"{value:,}".replace(",", "."))
        formats.append(f"{ribu} rebu")
        formats.append(f"{ribu} reibuan")
        formats.append(f"{ribu}.000")
        formats.append(f"Rp {ribu} ribu")
        formats.append(f"Rp {ribu} rebu")
        formats.append(f"Rp {ribu} reibu")
        formats.append(f"{ribu}000")
        formats.append(f"Rp{ribu}000")
        formats.append(f"{ribu}.000,-")
        formats.append(f"Rp. {ribu}.000")
        formats.append(f"Rp. {ribu}.000,-")
        formats.append(f"{ribu} k")
    
    # Full number
    formats.append(f"{value}")
    formats.append(f"{value:,}".replace(",", "."))
    formats.append(f"Rp {value:,}".replace(",", "."))
    formats.append(f"Rp{value}")
    formats.append(f"Rp. {value}")
    formats.append(f"Rp. {value:,}".replace(",", "."))
    formats.append(f"{value},-")
    formats.append(f"Rp. {value},-")
    
    return formats

# ============================================================
# GENERATOR TANGGAL
# ============================================================

def format_tanggal_relatif(ref_date):
    """Generate variasi penulisan tanggal relatif ke hari ini."""
    today = datetime.now().date()
    formats = []
    
    # Relative
    if ref_date == today:
        formats.extend(["hari ini", "tgl ini", "tanggal ini", "today", "sekarang", "ini"])
    elif ref_date == today - timedelta(days=1):
        formats.extend(["kemarin", "yesterday", "kmrn", "kemaren", "1 hari lalu", "sehari lalu", "tgl kemarin", "tanggal kemarin"])
    elif ref_date == today - timedelta(days=2):
        formats.extend(["2 hari lalu", "dua hari lalu", "kemarin lusa", "lusa", "2 hari yg lalu", "2hr lalu"])
    elif ref_date == today + timedelta(days=1):
        formats.extend(["besok", "tomorrow", "bsw", "1 hari lagi", "sehari lagi", "besoknya", "tgl besok"])
    elif ref_date == today + timedelta(days=2):
        formats.extend(["lusa", "besok lusa", "2 hari lagi", "dua hari lagi", "2hr lagi"])
    
    # Tanggal spesifik
    day = ref_date.day
    month_id = ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"]
    month_en = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    month_num = f"{ref_date.month:02d}"
    
    formats.extend([
        f"tanggal {day}",
        f"tgl {day}",
        f"tgl {day} {month_id[ref_date.month-1]}",
        f"tanggal {day} {month_id[ref_date.month-1]}",
        f"{day} {month_id[ref_date.month-1]}",
        f"{day}/{month_num}",
        f"{day}/{month_num}/{ref_date.year}",
        f"{day}-{month_num}",
        f"{ref_date.isoformat()}",
        f"{day} {month_en[ref_date.month-1]}",
        f"{day}/{month_num}/{str(ref_date.year)[2:]}",
        f"pada {day} {month_id[ref_date.month-1]}",
        f"hari {day} {month_id[ref_date.month-1]}",
    ])
    
    return formats

# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_dataset():
    examples = []
    today = datetime.now().date()
    
    # Nominal nominal yang umum
    nominals = [
        4000, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000,
        60000, 75000, 80000, 100000, 120000, 150000, 200000, 250000, 300000,
        350000, 400000, 500000, 600000, 750000, 800000, 1000000, 1200000,
        1500000, 2000000, 2500000, 3000000, 3500000, 5000000, 6000000, 7500000,
        10000000, 15000000,
    ]
    
    for category, merchant_list in merchants.items():
        for merchant in merchant_list:
            for nominal in nominals:
                # 30% dengan tanggal, 70% tanpa
                use_date = random.random() < 0.3
                
                if use_date:
                    # Random hari ini - 3 sampai hari ini + 3
                    offset = random.randint(-3, 3)
                    ref_date = today + timedelta(days=offset)
                    date_fmts = format_tanggal_relatif(ref_date)
                    date_str = ref_date.isoformat()
                else:
                    date_fmts = [""]
                    date_str = ""
                
                for date_fmt in date_fmts[:3]:  # ambil 3 variasi tanggal per entry
                    # Variasi penulisan nominal
                    nominal_fmts = format_nominal(nominal)
                    for nominal_fmt in nominal_fmts[:3]:  # ambil 3 variasi nominal
                        # Template kalimat
                        aksi = random.choice(aksi_tambah)
                        
                        # Template dasar
                        templates = [
                            f"{aksi} {nominal_fmt} {merchant}",
                            f"{aksi} {merchant} {nominal_fmt}",
                            f"{aksi} {merchant} seharga {nominal_fmt}",
                            f"beli {merchant} {nominal_fmt}",
                            f"bayar {merchant} {nominal_fmt}",
                            f"jajan {merchant} {nominal_fmt}",
                            f"{aksi} pengeluaran {nominal_fmt} buat {merchant}",
                            f"uang keluar {nominal_fmt} di {merchant}",
                            f"keluar {nominal_fmt} untuk {merchant}",
                            f"{merchant} {nominal_fmt}",
                            f"habis {nominal_fmt} buat {merchant}",
                            f"belanja {merchant} {nominal_fmt}",
                        ]
                        
                        # Tambah tanggal di tengah kalimat
                        if date_fmt:
                            templates_with_date = [
                                f"{aksi} {merchant} {nominal_fmt} {date_fmt}",
                                f"{aksi} {merchant} {date_fmt} {nominal_fmt}",
                                f"{aksi} {nominal_fmt} {date_fmt} di {merchant}",
                                f"{aksi} {nominal_fmt} {merchant} {date_fmt}",
                                f"{date_fmt} {aksi} {merchant} {nominal_fmt}",
                                f"{aksi} {date_fmt} beli {merchant} {nominal_fmt}",
                                f"beli {merchant} {date_fmt} {nominal_fmt}",
                                f"bayar {merchant} {date_fmt} {nominal_fmt}",
                                f"jajan {merchant} {date_fmt} {nominal_fmt}",
                                f"uang keluar {nominal_fmt} di {merchant} {date_fmt}",
                            ]
                            templates.extend(templates_with_date)
                        
                        template = random.choice(templates)
                        
                        # Clean up double spaces
                        query = " ".join(template.split())
                        
                        # Build arguments — date hanya masuk kalau template-nya memang mengandung tanggal
                        args = {"amount": nominal, "category": category}
                        if merchant and category != "lainnya":
                            args["merchant"] = merchant
                        if date_str and date_fmt and date_fmt in query:
                            args["date"] = date_str
                        
                        examples.append({
                            "query": query,
                            "answers": [{"name": "add_expense", "arguments": args}]
                        })
    
    # ============================================================
    # INCOME EXAMPLES
    # ============================================================
    for source in sumber_income:
        for nominal in [500000, 1000000, 1500000, 2000000, 2500000, 3000000, 5000000, 8000000, 10000000, 12000000, 15000000, 20000000]:
            for nominal_fmt in format_nominal(nominal)[:3]:
                # 30% dengan tanggal
                use_date = random.random() < 0.3
                if use_date:
                    offset = random.randint(-30, 0)
                    ref_date = today + timedelta(days=offset)
                    date_str = ref_date.isoformat()
                    date_fmt = random.choice(format_tanggal_relatif(ref_date))
                else:
                    date_str = ""
                    date_fmt = ""
                
                templates = [
                    f"dapat {source} {nominal_fmt}",
                    f"terima {source} {nominal_fmt}",
                    f"masuk {source} {nominal_fmt}",
                    f"{source} masuk {nominal_fmt}",
                    f"dapet {source} {nominal_fmt}",
                    f"dapat bonus {source} {nominal_fmt}",
                    f"income {source} {nominal_fmt}",
                    f"pemasukan {source} {nominal_fmt}",
                    f"uang masuk {nominal_fmt} dari {source}",
                    f"dapat {source} senilai {nominal_fmt}",
                ]
                if date_fmt:
                    templates.extend([
                        f"dapat {source} {nominal_fmt} {date_fmt}",
                        f"{date_fmt} dapat {source} {nominal_fmt}",
                        f"terima {source} {nominal_fmt} {date_fmt}",
                        f"{source} masuk {nominal_fmt} {date_fmt}",
                    ])
                
                template = random.choice(templates)
                query = " ".join(template.split())
                
                args = {"amount": nominal, "source": source}
                if date_str and date_fmt and date_fmt in query:
                    args["date"] = date_str
                
                examples.append({
                    "query": query,
                    "answers": [{"name": "add_income", "arguments": args}]
                })
    
    # ============================================================
    # QUERY EXAMPLES
    # ============================================================
    for period_key, period_variants in periode.items():
        for period_fmt in period_variants:
            for category in [None, "makanan", "transportasi", "hiburan", "tagihan", "kesehatan", "belanja"]:
                if category:
                    cat_str = f" {category}"
                else:
                    cat_str = ""
                
                templates = [
                    f"pengeluaran{cat_str} {period_fmt} berapa",
                    f"total{cat_str} {period_fmt} berapa",
                    f"habis berapa{cat_str} {period_fmt}",
                    f"cek pengeluaran{cat_str} {period_fmt}",
                    f"lihat total{cat_str} {period_fmt}",
                    f"rangkuman pengeluaran{cat_str} {period_fmt}",
                    f"berapa{cat_str} yang keluar {period_fmt}",
                    f"lapor pengeluaran{cat_str} {period_fmt}",
                    f"pengeluaran{cat_str} {period_fmt}",
                    f"total{cat_str} {period_fmt}",
                    f"aku habis berapa{cat_str} {period_fmt}",
                    f"cek{cat_str} {period_fmt}",
                ]
                
                for template in templates:
                    query = " ".join(template.split())
                    args = {"period": period_key}
                    if category:
                        args["category"] = category
                    
                    examples.append({
                        "query": query,
                        "answers": [{"name": "query_expenses", "arguments": args}]
                    })
    
    # ============================================================
    # DELETE EXAMPLES
    # ============================================================
    delete_keywords = ["bakso", "gojek", "kopi", "bensin", "listrik", "parkir", "nasi", "goreng", "baju", "obat", "Netflix", "pulsa", "bengkel", "es", "teh", "jeruk"]
    for kw in delete_keywords:
        templates = [
            f"hapus catatan {kw}",
            f"hapus {kw}",
            f"hapus transaksi {kw}",
            f"delete {kw}",
            f"cancel {kw}",
            f"hapus pengeluaran {kw}",
            f"hapus {kw} tadi",
            f"hapus {kw} kemarin",
            f"hapus catatan {kw} tadi",
            f"batalkan {kw}",
            f"hapus {kw} yang tadi",
            f"delete transaksi {kw}",
        ]
        for template in templates:
            query = " ".join(template.split())
            examples.append({
                "query": query,
                "answers": [{"name": "delete_expense", "arguments": {"keyword": kw}}]
            })
    
    # ============================================================
    # SET BUDGET EXAMPLES
    # ============================================================
    for category in ["makanan", "transportasi", "hiburan", "tagihan", "kesehatan", "belanja"]:
        for nominal in [500000, 800000, 1000000, 1500000, 2000000, 2500000, 3000000]:
            for nominal_fmt in format_nominal(nominal)[:2]:
                templates = [
                    f"set budget {category} {nominal_fmt}",
                    f"budget {category} {nominal_fmt}",
                    f"atur anggaran {category} {nominal_fmt}",
                    f"limit {category} {nominal_fmt}",
                    f"plafon {category} {nominal_fmt}",
                    f"batasi {category} {nominal_fmt}",
                    f"set budget bulanan {category} {nominal_fmt}",
                    f"budget {category} per bulan {nominal_fmt}",
                    f"buat budget {category} {nominal_fmt}",
                ]
                for template in templates:
                    query = " ".join(template.split())
                    examples.append({
                        "query": query,
                        "answers": [{"name": "set_budget", "arguments": {"category": category, "amount": nominal}}]
                    })
    
    # ============================================================
    # MULTI-CALL EXAMPLES
    # ============================================================
    multi_templates = [
        ("catat beli bensin 30rb sama parkir 5rb", [
            {"name": "add_expense", "arguments": {"amount": 30000, "category": "transportasi"}},
            {"name": "add_expense", "arguments": {"amount": 5000, "category": "transportasi"}},
        ]),
        ("beli bakso 15rb sama es teh 5rb", [
            {"name": "add_expense", "arguments": {"amount": 15000, "category": "makanan"}},
            {"name": "add_expense", "arguments": {"amount": 5000, "category": "makanan"}},
        ]),
        ("habis 50rb buat bensin dan 25rb buat parkir", [
            {"name": "add_expense", "arguments": {"amount": 50000, "category": "transportasi"}},
            {"name": "add_expense", "arguments": {"amount": 25000, "category": "transportasi"}},
        ]),
        ("catat makan 30rb sama bensin 50rb", [
            {"name": "add_expense", "arguments": {"amount": 30000, "category": "makanan"}},
            {"name": "add_expense", "arguments": {"amount": 50000, "category": "transportasi"}},
        ]),
        ("beli pulpen 5rb sama buku 25rb", [
            {"name": "add_expense", "arguments": {"amount": 5000, "category": "lainnya"}},
            {"name": "add_expense", "arguments": {"amount": 25000, "category": "lainnya"}},
        ]),
        ("catat beli gas 22rb sama pulsa 25rb", [
            {"name": "add_expense", "arguments": {"amount": 22000, "category": "tagihan"}},
            {"name": "add_expense", "arguments": {"amount": 25000, "category": "tagihan"}},
        ]),
        ("habis 100rb buat gojek dan 50rb buat makan", [
            {"name": "add_expense", "arguments": {"amount": 100000, "category": "transportasi"}},
            {"name": "add_expense", "arguments": {"amount": 50000, "category": "makanan"}},
        ]),
        ("bayar listrik 350rb sama internet 300rb", [
            {"name": "add_expense", "arguments": {"amount": 350000, "category": "tagihan"}},
            {"name": "add_expense", "arguments": {"amount": 300000, "category": "tagihan"}},
        ]),
        ("catat beli baju 85rb sama celana 120rb", [
            {"name": "add_expense", "arguments": {"amount": 85000, "category": "belanja"}},
            {"name": "add_expense", "arguments": {"amount": 120000, "category": "belanja"}},
        ]),
        ("habis 45rb buat obat dan 30rb buat vitamin", [
            {"name": "add_expense", "arguments": {"amount": 45000, "category": "kesehatan"}},
            {"name": "add_expense", "arguments": {"amount": 30000, "category": "kesehatan"}},
        ]),
    ]
    
    for query, answers in multi_templates:
        examples.append({"query": query, "answers": answers})
    
    # ============================================================
    # OFF-TOPIC EXAMPLES (harus return [])
    # ============================================================
    off_topic = [
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
    ]
    
    for q in off_topic:
        examples.append({"query": q, "answers": []})
    
    return examples

if __name__ == "__main__":
    examples = generate_dataset()
    print(f"Total examples: {len(examples)}")
    
    # Shuffle
    random.shuffle(examples)
    
    # Split 80/10/10
    n = len(examples)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)
    
    train = examples[:train_end]
    validation = examples[train_end:val_end]
    test = examples[val_end:]
    
    # Write files
    with open("data/train.jsonl", "w", encoding="utf-8") as f:
        for ex in train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    with open("data/validation.jsonl", "w", encoding="utf-8") as f:
        for ex in validation:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    with open("data/test.jsonl", "w", encoding="utf-8") as f:
        for ex in test:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    print(f"Train: {len(train)}")
    print(f"Validation: {len(validation)}")
    print(f"Test: {len(test)}")
