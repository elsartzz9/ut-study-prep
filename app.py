from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="UT Study Prep",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Katalog kurikulum SI UT: 51 slot mata kuliah, termasuk kelompok pilihan.
# -----------------------------------------------------------------------------

KATALOG_MK_UT = [
    {"slot": 1, "kode": "STSI4101", "nama": "Pengantar Sistem Informasi", "sks": 3},
    {"slot": 2, "kode": "STSI4103", "nama": "Sistem Operasi", "sks": 3},
    {
        "slot": 3,
        "kode": "MKWN4101/02/03/04/05/07",
        "nama": "Pendidikan Agama (pilih satu)",
        "sks": 3,
        "pilihan": [
            {"kode": "MKWN4101", "nama": "Pendidikan Agama Islam"},
            {"kode": "MKWN4102", "nama": "Pendidikan Agama Katolik"},
            {"kode": "MKWN4103", "nama": "Pendidikan Agama Kristen"},
            {"kode": "MKWN4104", "nama": "Pendidikan Agama Buddha"},
            {"kode": "MKWN4105", "nama": "Pendidikan Agama Hindu"},
            {"kode": "MKWN4107", "nama": "Pendidikan Agama Khonghucu"},
        ],
    },
    {"slot": 4, "kode": "STSI4102", "nama": "Algoritma dan Pemrograman", "sks": 3},
    {"slot": 5, "kode": "STMA4112", "nama": "Matematika Dasar", "sks": 3},
    {"slot": 6, "kode": "MKWN4109", "nama": "Pendidikan Kewarganegaraan", "sks": 2},
    {"slot": 7, "kode": "STSI4105", "nama": "Basis Data", "sks": 3},
    {"slot": 8, "kode": "STSI4104", "nama": "Struktur Data", "sks": 3},
    {"slot": 9, "kode": "MKKI4201", "nama": "Pengantar Statistika", "sks": 3},
    {"slot": 10, "kode": "MKDI4201", "nama": "Bahasa Inggris", "sks": 3},
    {"slot": 11, "kode": "MKWN4108", "nama": "Bahasa Indonesia", "sks": 2},
    {"slot": 12, "kode": "MKWN4110", "nama": "Pancasila", "sks": 2},
    {"slot": 13, "kode": "STMA4113", "nama": "Aljabar Linear Elementer", "sks": 2},
    {"slot": 14, "kode": "STIK4111", "nama": "Dasar Pemrograman R", "sks": 3},
    {"slot": 15, "kode": "STSI4106", "nama": "Logika Informatika", "sks": 3},
    {"slot": 16, "kode": "STSI4201", "nama": "Pemrograman Berbasis Desktop", "sks": 3},
    {"slot": 17, "kode": "STSI4203", "nama": "Interaksi Manusia dan Komputer", "sks": 3},
    {"slot": 18, "kode": "STSI4202", "nama": "Rekayasa Perangkat Lunak", "sks": 3},
    {"slot": 19, "kode": "STSI4205", "nama": "Jaringan Komputer", "sks": 3},
    {"slot": 20, "kode": "MKDI4202", "nama": "Belajar di Era Digital", "sks": 3},
    {"slot": 21, "kode": "MKDI4203", "nama": "Kewirausahaan di Era Digital", "sks": 3},
    {"slot": 22, "kode": "STSI4204", "nama": "Analisis dan Visualisasi Data", "sks": 2},
    {"slot": 23, "kode": "STSI4208", "nama": "Analisis dan Perancangan Sistem", "sks": 3},
    {"slot": 24, "kode": "STSI4209", "nama": "Pemrograman Berbasis Web", "sks": 3},
    {"slot": 25, "kode": "STSI4206", "nama": "Proses Bisnis", "sks": 2},
    {"slot": 26, "kode": "STSI4207", "nama": "Sistem Informasi Manajemen", "sks": 3},
    {"slot": 27, "kode": "EMBS4207", "nama": "Perilaku Organisasi", "sks": 3},
    {"slot": 28, "kode": "FSSI4101", "nama": "Membaca Dasar", "sks": 3},
    {"slot": 29, "kode": "STMA4111", "nama": "Kalkulus Diferensial", "sks": 3},
    {"slot": 30, "kode": "EMBS4102", "nama": "Pengantar Bisnis", "sks": 3},
    {
        "slot": 31,
        "kode": "STSI4301/STSI4302",
        "nama": "Mata kuliah pilihan 1",
        "sks": 3,
        "pilihan": [
            {"kode": "STSI4301", "nama": "Sistem Pendukung Keputusan"},
            {"kode": "STSI4302", "nama": "Administrasi Server"},
        ],
    },
    {"slot": 32, "kode": "FSAP4102", "nama": "Teori Organisasi", "sks": 3},
    {"slot": 33, "kode": "STSI4303", "nama": "Pemrograman Berbasis Perangkat Bergerak", "sks": 3},
    {"slot": 34, "kode": "STSI4308", "nama": "Komunikasi Bisnis dan Teknis", "sks": 2},
    {
        "slot": 35,
        "kode": "STSI4307/STSI4309",
        "nama": "Mata kuliah pilihan 2",
        "sks": 3,
        "pilihan": [
            {"kode": "STSI4307", "nama": "Penambangan Data"},
            {"kode": "STSI4309", "nama": "Administrasi Jaringan"},
        ],
    },
    {"slot": 36, "kode": "STSI4306", "nama": "Arsitektur dan Perancangan Sistem Perusahaan", "sks": 3},
    {"slot": 37, "kode": "STSI4305", "nama": "Etika Profesi", "sks": 2},
    {
        "slot": 38,
        "kode": "STPL4211/MKKI4301",
        "nama": "Mata kuliah pilihan 3",
        "sks": 3,
        "pilihan": [
            {"kode": "STPL4211", "nama": "Sistem Informasi Perencanaan"},
            {"kode": "MKKI4301", "nama": "Pemberdayaan Masyarakat"},
        ],
    },
    {"slot": 39, "kode": "STSI4304", "nama": "Dasar Infrastruktur Teknologi Informasi", "sks": 2},
    {"slot": 40, "kode": "STSI4310", "nama": "Metodologi Penelitian", "sks": 3},
    {"slot": 41, "kode": "EMBS4101", "nama": "Manajemen", "sks": 4},
    {
        "slot": 42,
        "kode": "STSI4409/STSI4404",
        "nama": "Mata kuliah pilihan 4",
        "sks": 3,
        "pilihan": [
            {"kode": "STSI4409", "nama": "Gudang Data"},
            {"kode": "STSI4404", "nama": "Keamanan Jaringan"},
        ],
    },
    {"slot": 43, "kode": "STDA4101", "nama": "Pengantar Sains Data", "sks": 3},
    {"slot": 44, "kode": "STSI4403", "nama": "Manajemen Risiko dan Audit Sistem Informasi", "sks": 3},
    {"slot": 45, "kode": "STSI4402", "nama": "Tata Kelola Teknologi Informasi", "sks": 2},
    {"slot": 46, "kode": "STSI4440", "nama": "Proyek Akhir (TAPS)", "sks": 6},
    {"slot": 47, "kode": "STSI4406", "nama": "Manajemen Proyek Sistem Informasi", "sks": 2},
    {"slot": 48, "kode": "STSI4405", "nama": "Keamanan Sistem Informasi", "sks": 2},
    {"slot": 49, "kode": "STSI4407", "nama": "Manajemen Layanan Teknologi Informasi", "sks": 3},
    {"slot": 50, "kode": "STSI4408", "nama": "Bisnis Elektronik", "sks": 3},
    {"slot": 51, "kode": "EACC4207", "nama": "Sistem Informasi Akuntansi", "sks": 3},
]


def bangun_daftar_penawaran() -> list[dict[str, Any]]:
    penawaran: list[dict[str, Any]] = []
    for mata_kuliah in KATALOG_MK_UT:
        pilihan = mata_kuliah.get("pilihan")
        if pilihan:
            for opsi in pilihan:
                penawaran.append(
                    {
                        "slot": mata_kuliah["slot"],
                        "kode": opsi["kode"],
                        "nama": opsi["nama"],
                        "sks": mata_kuliah["sks"],
                    }
                )
        else:
            penawaran.append(
                {
                    "slot": mata_kuliah["slot"],
                    "kode": mata_kuliah["kode"],
                    "nama": mata_kuliah["nama"],
                    "sks": mata_kuliah["sks"],
                }
            )
    return penawaran


DAFTAR_PENAWARAN = bangun_daftar_penawaran()
PENAWARAN_PER_KODE = {item["kode"]: item for item in DAFTAR_PENAWARAN}


def validasi_katalog() -> None:
    slot = [item["slot"] for item in KATALOG_MK_UT]
    kode_penawaran = [item["kode"] for item in DAFTAR_PENAWARAN]
    if len(KATALOG_MK_UT) != 51 or slot != list(range(1, 52)):
        raise RuntimeError("Katalog SI harus berisi tepat 51 slot kurikulum.")
    if sum(int(item["sks"]) for item in KATALOG_MK_UT) != 145:
        raise RuntimeError("Jumlah SKS kurikulum harus 145.")
    if len(kode_penawaran) != len(set(kode_penawaran)):
        raise RuntimeError("Kode mata kuliah pada daftar penawaran harus unik.")


validasi_katalog()


# -----------------------------------------------------------------------------
# Penyimpanan SQLite lokal
# -----------------------------------------------------------------------------

DIREKTORI_APLIKASI = Path(__file__).resolve().parent
LOKASI_DB = Path(
    os.getenv("UT_STUDY_DB_PATH", str(DIREKTORI_APLIKASI / "ut_study_prep.db"))
)


def waktu_sekarang() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def buka_db() -> sqlite3.Connection:
    koneksi = sqlite3.connect(LOKASI_DB, timeout=15)
    koneksi.row_factory = sqlite3.Row
    koneksi.execute("PRAGMA foreign_keys = ON")
    return koneksi


def siapkan_database() -> None:
    LOKASI_DB.parent.mkdir(parents=True, exist_ok=True)
    with buka_db() as koneksi:
        koneksi.executescript(
            """
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS semester_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 24),
                is_custom INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                material TEXT NOT NULL DEFAULT '',
                discussion TEXT NOT NULL DEFAULT '',
                assignments TEXT NOT NULL DEFAULT '',
                study_pack_json TEXT,
                provider TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (semester_id, code),
                FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tutorial_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_course_id INTEGER NOT NULL,
                session_number INTEGER NOT NULL CHECK (session_number BETWEEN 1 AND 8),
                material TEXT NOT NULL DEFAULT '',
                discussion TEXT NOT NULL DEFAULT '',
                assignments TEXT NOT NULL DEFAULT '',
                study_pack_json TEXT,
                provider TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (semester_course_id, session_number),
                FOREIGN KEY (semester_course_id) REFERENCES semester_courses(id) ON DELETE CASCADE
            );
            """
        )
        koneksi.execute("PRAGMA journal_mode = WAL")
        if koneksi.execute("SELECT id FROM semesters LIMIT 1").fetchone() is None:
            koneksi.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                ("Semester 1", waktu_sekarang()),
            )

        # Migrasi aman dari versi lama: materi tingkat mata kuliah menjadi Sesi 1.
        data_lama = koneksi.execute(
            """
            SELECT id, material, discussion, assignments, study_pack_json, provider, updated_at
            FROM semester_courses
            WHERE (material <> '' OR discussion <> '' OR assignments <> '' OR study_pack_json IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM tutorial_sessions
                  WHERE tutorial_sessions.semester_course_id = semester_courses.id
              )
            """
        ).fetchall()
        for baris in data_lama:
            koneksi.execute(
                """
                INSERT INTO tutorial_sessions
                    (semester_course_id, session_number, material, discussion, assignments,
                     study_pack_json, provider, updated_at)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baris["id"],
                    baris["material"],
                    baris["discussion"],
                    baris["assignments"],
                    baris["study_pack_json"],
                    baris["provider"],
                    baris["updated_at"],
                ),
            )


def daftar_semester() -> list[dict[str, Any]]:
    with buka_db() as koneksi:
        hasil = koneksi.execute(
            "SELECT id, name, created_at FROM semesters ORDER BY id"
        ).fetchall()
    return [dict(item) for item in hasil]


def buat_semester(nama: str) -> int:
    nama_bersih = re.sub(r"\s+", " ", nama.strip())
    if not nama_bersih:
        raise ValueError("Tuliskan nama semester terlebih dahulu.")
    with buka_db() as koneksi:
        try:
            kursor = koneksi.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                (nama_bersih, waktu_sekarang()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Nama semester tersebut sudah tersedia.") from exc
    return int(kursor.lastrowid)


def daftar_mata_kuliah(
    semester_id: int, *, hanya_aktif: bool = True
) -> list[dict[str, Any]]:
    syarat = "AND active = 1" if hanya_aktif else ""
    with buka_db() as koneksi:
        hasil = koneksi.execute(
            f"""
            SELECT * FROM semester_courses
            WHERE semester_id = ? {syarat}
            ORDER BY is_custom, code
            """,
            (semester_id,),
        ).fetchall()
    return [dict(item) for item in hasil]


def sinkronkan_mata_kuliah(semester_id: int, kode_terpilih: list[str]) -> None:
    pilihan = {kode for kode in kode_terpilih if kode in PENAWARAN_PER_KODE}
    with buka_db() as koneksi:
        koneksi.execute(
            """
            UPDATE semester_courses SET active = 0, updated_at = ?
            WHERE semester_id = ? AND is_custom = 0
            """,
            (waktu_sekarang(), semester_id),
        )
        for kode in sorted(pilihan):
            mata_kuliah = PENAWARAN_PER_KODE[kode]
            koneksi.execute(
                """
                INSERT INTO semester_courses
                    (semester_id, code, name, credits, is_custom, active, updated_at)
                VALUES (?, ?, ?, ?, 0, 1, ?)
                ON CONFLICT(semester_id, code) DO UPDATE SET
                    name = excluded.name,
                    credits = excluded.credits,
                    active = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    semester_id,
                    kode,
                    mata_kuliah["nama"],
                    mata_kuliah["sks"],
                    waktu_sekarang(),
                ),
            )


def tambah_mata_kuliah_khusus(
    semester_id: int, kode: str, nama: str, sks: int
) -> None:
    kode_bersih = re.sub(r"[^A-Z0-9_-]", "", kode.upper().strip())
    nama_bersih = re.sub(r"\s+", " ", nama.strip())
    if not kode_bersih or not nama_bersih:
        raise ValueError("Kode dan nama mata kuliah wajib diisi.")
    if kode_bersih in PENAWARAN_PER_KODE:
        raise ValueError("Kode tersebut sudah ada di katalog. Pilih dari daftar katalog.")
    with buka_db() as koneksi:
        koneksi.execute(
            """
            INSERT INTO semester_courses
                (semester_id, code, name, credits, is_custom, active, updated_at)
            VALUES (?, ?, ?, ?, 1, 1, ?)
            ON CONFLICT(semester_id, code) DO UPDATE SET
                name = excluded.name,
                credits = excluded.credits,
                is_custom = 1,
                active = 1,
                updated_at = excluded.updated_at
            """,
            (semester_id, kode_bersih, nama_bersih, int(sks), waktu_sekarang()),
        )


def hapus_mata_kuliah_khusus(mata_kuliah_id: int) -> None:
    with buka_db() as koneksi:
        koneksi.execute(
            "DELETE FROM semester_courses WHERE id = ? AND is_custom = 1",
            (mata_kuliah_id,),
        )


def ambil_sesi(mata_kuliah_id: int, nomor_sesi: int) -> dict[str, Any]:
    with buka_db() as koneksi:
        hasil = koneksi.execute(
            """
            SELECT * FROM tutorial_sessions
            WHERE semester_course_id = ? AND session_number = ?
            """,
            (mata_kuliah_id, nomor_sesi),
        ).fetchone()
    if hasil:
        return dict(hasil)
    return {
        "id": None,
        "semester_course_id": mata_kuliah_id,
        "session_number": nomor_sesi,
        "material": "",
        "discussion": "",
        "assignments": "",
        "study_pack_json": None,
        "provider": None,
        "updated_at": "",
    }


def simpan_catatan_sesi(
    mata_kuliah_id: int,
    nomor_sesi: int,
    materi: str,
    diskusi: str,
    tugas: str,
) -> None:
    with buka_db() as koneksi:
        koneksi.execute(
            """
            INSERT INTO tutorial_sessions
                (semester_course_id, session_number, material, discussion,
                 assignments, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(semester_course_id, session_number) DO UPDATE SET
                material = excluded.material,
                discussion = excluded.discussion,
                assignments = excluded.assignments,
                updated_at = excluded.updated_at
            """,
            (mata_kuliah_id, nomor_sesi, materi, diskusi, tugas, waktu_sekarang()),
        )


def simpan_paket_belajar(
    mata_kuliah_id: int,
    nomor_sesi: int,
    materi: str,
    diskusi: str,
    tugas: str,
    paket: dict[str, Any],
    penyedia: str,
) -> None:
    with buka_db() as koneksi:
        koneksi.execute(
            """
            INSERT INTO tutorial_sessions
                (semester_course_id, session_number, material, discussion,
                 assignments, study_pack_json, provider, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(semester_course_id, session_number) DO UPDATE SET
                material = excluded.material,
                discussion = excluded.discussion,
                assignments = excluded.assignments,
                study_pack_json = excluded.study_pack_json,
                provider = excluded.provider,
                updated_at = excluded.updated_at
            """,
            (
                mata_kuliah_id,
                nomor_sesi,
                materi,
                diskusi,
                tugas,
                json.dumps(paket, ensure_ascii=False),
                penyedia,
                waktu_sekarang(),
            ),
        )


def ekspor_semester(semester_id: int) -> str:
    semester = next(item for item in daftar_semester() if item["id"] == semester_id)
    mata_kuliah = daftar_mata_kuliah(semester_id, hanya_aktif=False)
    with buka_db() as koneksi:
        for item in mata_kuliah:
            sesi = koneksi.execute(
                """
                SELECT session_number, material, discussion, assignments,
                       study_pack_json, provider, updated_at
                FROM tutorial_sessions
                WHERE semester_course_id = ?
                ORDER BY session_number
                """,
                (item["id"],),
            ).fetchall()
            item["sesi_tuton"] = [dict(baris) for baris in sesi]
    hasil = {
        "aplikasi": "UT Study Prep",
        "versi": 3,
        "diekspor_pada": waktu_sekarang(),
        "semester": semester,
        "mata_kuliah": mata_kuliah,
    }
    return json.dumps(hasil, ensure_ascii=False, indent=2)


siapkan_database()


# -----------------------------------------------------------------------------
# Mesin ringkasan, prediksi UAS, flashcard, dan kuis
# -----------------------------------------------------------------------------

KATA_UMUM = {
    "adalah", "agar", "akan", "atau", "bagi", "bahwa", "dalam", "dapat", "dari",
    "dengan", "jika", "juga", "karena", "kepada", "lebih", "maka", "pada", "para",
    "sebagai", "sebuah", "serta", "sudah", "tersebut", "untuk", "yang", "about",
    "after", "again", "being", "each", "have", "into", "their", "there", "these",
    "through", "were", "will", "with", "your", "the", "and", "from", "that",
    "then", "than", "when", "where", "which", "while", "what", "over",
}


class KesalahanPenyedia(RuntimeError):
    pass


def pecah_kalimat(teks: str) -> list[str]:
    ringkas = re.sub(r"[ \t]+", " ", teks.replace("\r", " ")).strip()
    bagian = re.split(r"(?<=[.!?])\s+|\n+|(?:^|\s)[•*-]\s+", ringkas)
    return [item.strip(" -•\t") for item in bagian if len(item.strip()) >= 28]


def ambil_kata_kunci(teks: str, batas: int = 12) -> list[str]:
    kata = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}", teks.lower())
    hitung = Counter(item for item in kata if item not in KATA_UMUM and not item.isdigit())
    return [item for item, _ in hitung.most_common(batas)]


def paket_belajar_lokal(
    mata_kuliah: dict[str, Any], materi: str, diskusi: str, tugas: str
) -> dict[str, Any]:
    gabungan = "\n".join(item for item in (materi, diskusi, tugas) if item.strip())
    kalimat = pecah_kalimat(gabungan) or [gabungan.strip()]
    kata_kunci = ambil_kata_kunci(gabungan, 14)
    cadangan = ["konsep", "penerapan", "analisis", "proses", "evaluasi", "sistem", "data", "kualitas"]
    for kata in cadangan:
        if len(kata_kunci) >= 8:
            break
        if kata not in kata_kunci:
            kata_kunci.append(kata)

    frekuensi = Counter(
        re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}", gabungan.lower())
    )
    peringkat = sorted(
        enumerate(kalimat),
        key=lambda pasangan: sum(
            frekuensi[kata] for kata in re.findall(r"\w+", pasangan[1].lower())
        )
        / math.sqrt(max(len(pasangan[1].split()), 1)),
        reverse=True,
    )[: min(5, len(kalimat))]
    kalimat_ringkasan = [kalimat[indeks] for indeks, _ in sorted(peringkat)]
    ringkasan = " ".join(kalimat_ringkasan)

    poin_penting = kalimat_ringkasan[:6]
    if len(poin_penting) < 5:
        poin_penting.extend(
            f"Hubungkan konsep {kata.title()} dengan capaian belajar {mata_kuliah['name']}."
            for kata in kata_kunci[: 5 - len(poin_penting)]
        )

    topik_diskusi = ambil_kata_kunci(diskusi + " " + tugas, 5)
    topik_prediksi = list(dict.fromkeys(topik_diskusi + kata_kunci))[:5]
    prediksi = [
        {
            "topic": topik.title(),
            "priority": "Tinggi" if indeks < 2 else "Sedang",
            "rationale": (
                "Topik muncul pada diskusi atau tugas; latih penjelasan dan penerapannya."
                if topik in topik_diskusi
                else "Topik menonjol pada materi Tuton dan layak dijadikan fokus belajar konsep."
            ),
        }
        for indeks, topik in enumerate(topik_prediksi)
    ]

    flashcard = []
    for topik in kata_kunci[:6]:
        jawaban = next(
            (item for item in kalimat if topik.lower() in item.lower()),
            f"Pelajari hubungan {topik} dengan materi {mata_kuliah['name']}.",
        )
        flashcard.append(
            {"front": f"Apa yang perlu diingat tentang {topik.title()}?", "back": jawaban}
        )

    kuis = []
    for indeks, topik in enumerate(kata_kunci[:5]):
        sumber = next(
            (item for item in kalimat if topik.lower() in item.lower()),
            poin_penting[indeks % len(poin_penting)],
        )
        pengecoh = [kata.title() for kata in kata_kunci if kata != topik][:3]
        while len(pengecoh) < 3:
            pengecoh.append(["Penerapan", "Evaluasi", "Arsitektur"][len(pengecoh)])
        indeks_jawaban = indeks % 4
        opsi = pengecoh[:]
        opsi.insert(indeks_jawaban, topik.title())
        kuis.append(
            {
                "question": f"Konsep mana yang paling sesuai dengan catatan berikut: “{sumber[:150]}”?",
                "options": opsi,
                "answer_index": indeks_jawaban,
                "explanation": f"Catatan tersebut paling langsung membahas {topik.title()}.",
            }
        )

    return {
        "summary": ringkasan,
        "key_points": poin_penting[:6],
        "exam_predictions": prediksi,
        "flashcards": flashcard,
        "quiz": kuis,
        "study_plan": [
            "Baca ringkasan sekali tanpa memberi tanda.",
            "Sebutkan kembali setiap poin penting tanpa melihat catatan.",
            "Latih topik kisi-kisi UAS dengan contoh buatan sendiri.",
            "Kerjakan kuis, lalu ulangi konsep yang masih keliru.",
        ],
    }


def buat_prompt(
    mata_kuliah: dict[str, Any], nomor_sesi: int, materi: str, diskusi: str, tugas: str
) -> str:
    sumber = f"""
MATA KULIAH: {mata_kuliah['code']} — {mata_kuliah['name']} ({mata_kuliah['credits']} SKS)
SESI TUTON: {nomor_sesi}

MATERI ATAU RINGKASAN TUTON:
{materi}

DISKUSI:
{diskusi or '(tidak diisi)'}

TUGAS:
{tugas or '(tidak diisi)'}
""".strip()[:30000]
    return f"""
Anda adalah pendamping belajar mahasiswa Sistem Informasi Universitas Terbuka.
Gunakan hanya bahan yang diberikan. Gunakan bahasa Indonesia yang jelas. Jangan pernah menyatakan
bahwa prediksi pasti keluar pada UAS. Kembalikan hanya satu objek JSON valid dengan susunan berikut:

{{
  "summary": "ringkasan padat dan lengkap",
  "key_points": ["5 sampai 7 poin penting"],
  "exam_predictions": [
    {{"topic": "topik", "priority": "Tinggi atau Sedang", "rationale": "alasan berbasis materi"}}
  ],
  "flashcards": [{{"front": "pertanyaan", "back": "jawaban"}}],
  "quiz": [
    {{"question": "soal pilihan ganda", "options": ["A", "B", "C", "D"],
      "answer_index": 0, "explanation": "alasan jawaban benar"}}
  ],
  "study_plan": ["empat langkah belajar singkat"]
}}

Buat 5 prediksi topik UAS, 6 flashcard, dan 5 soal kuis. answer_index dimulai dari nol.

{sumber}
""".strip()


def kirim_json(
    alamat: str, muatan: dict[str, Any], kepala: dict[str, str]
) -> dict[str, Any]:
    permintaan = urllib.request.Request(
        alamat,
        data=json.dumps(muatan).encode("utf-8"),
        headers={"Content-Type": "application/json", **kepala},
        method="POST",
    )
    try:
        with urllib.request.urlopen(permintaan, timeout=60) as tanggapan:
            return json.loads(tanggapan.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            rincian = json.loads(exc.read().decode("utf-8"))
            pesan = rincian.get("error", {}).get("message") or str(rincian)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pesan = f"HTTP {exc.code}"
        raise KesalahanPenyedia(f"Permintaan ke layanan AI gagal: {pesan}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise KesalahanPenyedia(f"Layanan AI tidak dapat dihubungi: {exc}") from exc


def ambil_json(teks: str) -> dict[str, Any]:
    hasil = teks.strip()
    if hasil.startswith("```"):
        hasil = re.sub(r"^```(?:json)?\s*|\s*```$", "", hasil, flags=re.IGNORECASE)
    awal, akhir = hasil.find("{"), hasil.rfind("}")
    if awal < 0 or akhir <= awal:
        raise KesalahanPenyedia("Layanan AI tidak mengirimkan paket belajar berbentuk JSON.")
    try:
        data = json.loads(hasil[awal : akhir + 1])
    except json.JSONDecodeError as exc:
        raise KesalahanPenyedia("Format jawaban layanan AI tidak valid. Silakan coba lagi.") from exc
    if not isinstance(data, dict):
        raise KesalahanPenyedia("Jawaban layanan AI bukan paket belajar yang valid.")
    return rapikan_paket(data)


def rapikan_paket(paket: dict[str, Any]) -> dict[str, Any]:
    ringkasan = str(paket.get("summary", "")).strip()
    poin = [str(item).strip() for item in paket.get("key_points", []) if str(item).strip()]
    prediksi = []
    for item in paket.get("exam_predictions", []):
        if isinstance(item, dict) and item.get("topic"):
            prediksi.append(
                {
                    "topic": str(item["topic"]).strip(),
                    "priority": str(item.get("priority", "Sedang")).strip(),
                    "rationale": str(item.get("rationale", "Pelajari konsep ini kembali.")).strip(),
                }
            )
    flashcard = []
    for item in paket.get("flashcards", []):
        if isinstance(item, dict):
            depan = str(item.get("front", "")).strip()
            belakang = str(item.get("back", "")).strip()
            if depan and belakang:
                flashcard.append({"front": depan, "back": belakang})
    kuis = []
    for item in paket.get("quiz", []):
        if not isinstance(item, dict):
            continue
        opsi = [str(opsi_item).strip() for opsi_item in item.get("options", [])]
        try:
            indeks_jawaban = int(item.get("answer_index", 0))
        except (TypeError, ValueError):
            indeks_jawaban = 0
        if item.get("question") and len(opsi) == 4 and 0 <= indeks_jawaban < 4:
            kuis.append(
                {
                    "question": str(item["question"]).strip(),
                    "options": opsi,
                    "answer_index": indeks_jawaban,
                    "explanation": str(item.get("explanation", "")).strip(),
                }
            )
    rencana = [str(item).strip() for item in paket.get("study_plan", []) if str(item).strip()]
    if not ringkasan or len(poin) < 3 or len(prediksi) < 2 or len(flashcard) < 3 or len(kuis) < 3:
        raise KesalahanPenyedia("Jawaban layanan AI belum lengkap. Silakan buat ulang paket belajar.")
    return {
        "summary": ringkasan,
        "key_points": poin[:8],
        "exam_predictions": prediksi[:6],
        "flashcards": flashcard[:8],
        "quiz": kuis[:6],
        "study_plan": rencana[:6],
    }


def paket_gemini(prompt: str, kunci_api: str, model: str) -> dict[str, Any]:
    model_aman = urllib.parse.quote(model.strip(), safe="-_.")
    data = kirim_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_aman}:generateContent",
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.25, "responseMimeType": "application/json"},
        },
        {"x-goog-api-key": kunci_api},
    )
    try:
        bagian = data["candidates"][0]["content"]["parts"]
        teks = "".join(item.get("text", "") for item in bagian)
    except (KeyError, IndexError, TypeError) as exc:
        raise KesalahanPenyedia("Gemini tidak mengirimkan jawaban yang dapat dibaca.") from exc
    return ambil_json(teks)


def paket_groq(prompt: str, kunci_api: str, model: str) -> dict[str, Any]:
    data = kirim_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": model.strip(),
            "messages": [
                {"role": "system", "content": "Berikan hanya JSON valid sesuai format yang diminta."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        },
        {"Authorization": f"Bearer {kunci_api}"},
    )
    try:
        teks = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise KesalahanPenyedia("Groq tidak mengirimkan jawaban yang dapat dibaca.") from exc
    return ambil_json(teks)


def buat_paket_belajar(
    penyedia: str,
    mata_kuliah: dict[str, Any],
    nomor_sesi: int,
    materi: str,
    diskusi: str,
    tugas: str,
    kunci_api: str,
    model: str,
) -> dict[str, Any]:
    if penyedia == "Lokal (tanpa API)":
        return paket_belajar_lokal(mata_kuliah, materi, diskusi, tugas)
    if not kunci_api.strip():
        raise KesalahanPenyedia(f"Masukkan kunci API {penyedia} di bilah samping.")
    prompt = buat_prompt(mata_kuliah, nomor_sesi, materi, diskusi, tugas)
    if penyedia == "Google Gemini":
        return paket_gemini(prompt, kunci_api.strip(), model)
    if penyedia == "Groq":
        return paket_groq(prompt, kunci_api.strip(), model)
    raise KesalahanPenyedia("Mesin belajar tidak dikenali.")


# -----------------------------------------------------------------------------
# Tampilan dan komponen
# -----------------------------------------------------------------------------

CSS_APLIKASI = """
<style>
    :root {
        --demitasse: #40342b;
        --coconut: #f0ede5;
        --sand: #dbd5d1;
        --sand-dark: #c8beb7;
        --line: #aa9d94;
    }

    html, body, .stApp, [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] p, [data-testid="stAppViewContainer"] span,
    [data-testid="stAppViewContainer"] label, [data-testid="stAppViewContainer"] div,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] div {
        color: var(--demitasse) !important;
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background: var(--coconut) !important;
    }

    [data-testid="stHeader"] { background: rgba(240, 237, 229, .92) !important; }
    [data-testid="stSidebar"] {
        background: var(--sand) !important;
        border-right: 1px solid var(--line) !important;
    }

    h1, h2, h3, h4, h5, h6,
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        color: var(--demitasse) !important;
        letter-spacing: -0.025em;
    }

    input, textarea, [data-baseweb="select"] > div,
    [data-baseweb="base-input"], [data-testid="stTextInputRootElement"],
    [data-testid="stTextAreaRootElement"] {
        background: var(--sand) !important;
        color: var(--demitasse) !important;
        border-color: var(--line) !important;
    }

    input::placeholder, textarea::placeholder {
        color: #6e6259 !important;
        opacity: 1 !important;
    }

    [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"],
    [role="option"], [data-baseweb="tag"] {
        background: var(--sand) !important;
        color: var(--demitasse) !important;
    }

    [role="option"]:hover, [aria-selected="true"] {
        background: var(--sand-dark) !important;
        color: var(--demitasse) !important;
    }

    .stButton > button, .stDownloadButton > button,
    [data-testid="stLinkButton"] a {
        background: var(--sand) !important;
        color: var(--demitasse) !important;
        border: 1px solid var(--demitasse) !important;
        border-radius: 12px !important;
        font-weight: 750 !important;
        box-shadow: none !important;
    }

    .stButton > button:hover, .stDownloadButton > button:hover,
    [data-testid="stLinkButton"] a:hover {
        background: var(--sand-dark) !important;
        color: var(--demitasse) !important;
        border-color: var(--demitasse) !important;
    }

    button[kind="primary"], .stButton > button[kind="primary"] {
        background: var(--sand-dark) !important;
        color: var(--demitasse) !important;
        border: 2px solid var(--demitasse) !important;
    }

    [data-testid="stMetric"] {
        background: var(--sand) !important;
        border: 1px solid var(--line) !important;
        border-radius: 16px !important;
        padding: .85rem 1rem !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--sand) !important;
        border-color: var(--line) !important;
        border-radius: 18px !important;
    }

    [data-testid="stAlert"] {
        background: var(--sand) !important;
        color: var(--demitasse) !important;
        border: 1px solid var(--line) !important;
    }

    [data-testid="stTabs"] button, [data-testid="stTabs"] button p {
        color: var(--demitasse) !important;
        font-weight: 700 !important;
    }

    [data-testid="stTabs"] [aria-selected="true"] {
        background: transparent !important;
        border-bottom-color: var(--demitasse) !important;
    }

    [data-testid="stRadio"] label, [data-testid="stCheckbox"] label,
    [data-testid="stSelectbox"] label, [data-testid="stTextInput"] label,
    [data-testid="stTextArea"] label, [data-testid="stNumberInput"] label {
        color: var(--demitasse) !important;
        font-weight: 650 !important;
    }

    svg { color: var(--demitasse) !important; fill: currentColor; }
    a { color: var(--demitasse) !important; text-decoration-thickness: 1px; }
    hr { border-color: var(--line) !important; }

    .hero-ut {
        background: var(--sand);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1.55rem 1.65rem;
        margin: .2rem 0 1.25rem;
    }

    .hero-ut h1 { margin: .2rem 0 .35rem; font-size: clamp(2rem, 5vw, 3.25rem); }
    .hero-ut p { margin: 0; max-width: 780px; font-size: 1.02rem; line-height: 1.65; }
    .kicker { font-size: .76rem; font-weight: 850; letter-spacing: .15em; text-transform: uppercase; }

    .langkah {
        display: flex; align-items: center; gap: .75rem; margin-bottom: .75rem;
    }

    .nomor-langkah {
        width: 2.15rem; height: 2.15rem; display: inline-flex; align-items: center;
        justify-content: center; border: 2px solid var(--demitasse); border-radius: 50%;
        color: var(--demitasse); font-weight: 850; flex: 0 0 auto;
    }

    .judul-langkah { font-size: 1.18rem; font-weight: 800; color: var(--demitasse); }
    .subjudul-langkah { font-size: .88rem; color: var(--demitasse); opacity: .82; }

    .label-kecil {
        display: inline-block; padding: .28rem .65rem; border: 1px solid var(--demitasse);
        border-radius: 999px; color: var(--demitasse); font-size: .78rem; font-weight: 750;
        margin: .15rem .3rem .15rem 0;
    }

    .kotak-prediksi {
        background: var(--sand); border: 1px solid var(--line); border-left: 5px solid var(--demitasse);
        padding: .9rem 1rem; border-radius: 10px 16px 16px 10px; margin: .6rem 0;
    }

    .kartu-flash {
        min-height: 150px; background: var(--sand); border: 1px solid var(--line);
        border-radius: 16px; padding: 1rem; margin-bottom: .85rem;
    }

    .teks-bantu { font-size: .9rem; line-height: 1.55; opacity: .86; }

    @media (max-width: 700px) {
        .hero-ut { padding: 1.15rem; border-radius: 16px; }
        .hero-ut h1 { font-size: 2rem; }
    }
</style>
"""

CONTOH_MATERI = """Sistem informasi menggabungkan manusia, proses, data, dan teknologi untuk
mendukung operasi serta pengambilan keputusan. Sistem pemrosesan transaksi mencatat kegiatan rutin,
sedangkan sistem informasi manajemen mengubah data operasional menjadi laporan. Sistem pendukung
keputusan memakai model dan analisis data untuk keputusan semi-terstruktur. Kualitas sistem, kualitas
informasi, keamanan, penerimaan pengguna, dan keselarasan bisnis menjadi ukuran penting keberhasilan."""


def ambil_rahasia(nama: str) -> str:
    try:
        nilai = st.secrets.get(nama, "")
    except (FileNotFoundError, AttributeError):
        nilai = ""
    return str(nilai or os.getenv(nama, ""))


def baca_paket(data_sesi: dict[str, Any]) -> dict[str, Any] | None:
    isi = data_sesi.get("study_pack_json")
    if not isi:
        return None
    try:
        return json.loads(isi)
    except json.JSONDecodeError:
        return None


def isi_contoh(mata_kuliah_id: int, nomor_sesi: int) -> None:
    akhiran = f"{mata_kuliah_id}_{nomor_sesi}"
    st.session_state[f"materi_{akhiran}"] = CONTOH_MATERI
    st.session_state[f"diskusi_{akhiran}"] = (
        "Bandingkan sistem pemrosesan transaksi, sistem informasi manajemen, dan sistem pendukung keputusan."
    )
    st.session_state[f"tugas_{akhiran}"] = (
        "Jelaskan pengaruh kualitas informasi dan penerimaan pengguna terhadap keberhasilan sistem."
    )


def judul_langkah(nomor: int, judul: str, penjelasan: str) -> None:
    st.markdown(
        "<div class='langkah'>"
        f"<span class='nomor-langkah'>{nomor}</span>"
        "<div>"
        f"<div class='judul-langkah'>{html.escape(judul)}</div>"
        f"<div class='subjudul-langkah'>{html.escape(penjelasan)}</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def pemutar_audio(teks: str, identitas: str) -> None:
    teks_terenkripsi = base64.b64encode(teks.encode("utf-8")).decode("ascii")
    st.iframe(
        f"""
        <div style="font-family:Arial,sans-serif;background:#dbd5d1;border:1px solid #aa9d94;
                    border-radius:14px;padding:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;color:#40342b">
          <strong style="color:#40342b;margin-right:8px">Pembaca audio</strong>
          <button id="putar-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#c8beb7;color:#40342b;cursor:pointer;font-weight:700">▶ Putar</button>
          <button id="jeda-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#dbd5d1;color:#40342b;cursor:pointer;font-weight:700">Jeda / lanjut</button>
          <button id="henti-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#dbd5d1;color:#40342b;cursor:pointer;font-weight:700">Hentikan</button>
          <select id="bahasa-{identitas}" style="padding:7px;border-radius:8px;border:1px solid #40342b;background:#dbd5d1;color:#40342b">
            <option value="id-ID">Bahasa Indonesia</option><option value="en-US">Bahasa Inggris</option>
          </select>
        </div>
        <script>
          const byteTeks = Uint8Array.from(atob('{teks_terenkripsi}'), karakter => karakter.charCodeAt(0));
          const teksBelajar = new TextDecoder().decode(byteTeks);
          const suara = window.speechSynthesis;
          let ucapan = null;
          document.getElementById('putar-{identitas}').onclick = () => {{
            suara.cancel(); ucapan = new SpeechSynthesisUtterance(teksBelajar);
            ucapan.lang = document.getElementById('bahasa-{identitas}').value;
            ucapan.rate = 0.95; suara.speak(ucapan);
          }};
          document.getElementById('jeda-{identitas}').onclick = () => suara.paused ? suara.resume() : suara.pause();
          document.getElementById('henti-{identitas}').onclick = () => suara.cancel();
        </script>
        """,
        height=88,
    )


def tampilkan_hasil(
    paket: dict[str, Any], mata_kuliah: dict[str, Any], nomor_sesi: int, diperbarui: str
) -> None:
    tab_ringkasan, tab_kisi, tab_flash, tab_kuis = st.tabs(
        ["Ringkasan & audio", "Kisi-kisi UAS", "Flashcard", "Kuis latihan"]
    )
    with tab_ringkasan:
        st.markdown(paket["summary"])
        pemutar_audio(paket["summary"], f"{mata_kuliah['id']}-{nomor_sesi}")
        st.markdown("#### Poin penting")
        for poin in paket.get("key_points", []):
            st.markdown(f"- {poin}")
        if paket.get("study_plan"):
            st.markdown("#### Urutan belajar yang disarankan")
            for indeks, tindakan in enumerate(paket["study_plan"], start=1):
                st.markdown(f"{indeks}. {tindakan}")

    with tab_kisi:
        st.caption(
            "Kisi-kisi ini adalah prioritas belajar berdasarkan materi yang Anda masukkan, bukan jaminan soal UAS."
        )
        for prediksi in paket.get("exam_predictions", []):
            st.markdown(
                "<div class='kotak-prediksi'>"
                f"<strong>{html.escape(prediksi['topic'])}</strong> "
                f"<span class='label-kecil'>{html.escape(prediksi['priority'])}</span><br>"
                f"<span class='teks-bantu'>{html.escape(prediksi['rationale'])}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    with tab_flash:
        kartu = paket.get("flashcards", [])
        kolom = st.columns(2)
        for indeks, item in enumerate(kartu):
            with kolom[indeks % 2]:
                st.markdown(
                    "<div class='kartu-flash'>"
                    f"<strong>{html.escape(item['front'])}</strong><hr>"
                    f"<span class='teks-bantu'>{html.escape(item['back'])}</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    with tab_kuis:
        daftar_kuis = paket.get("quiz", [])
        kunci_formulir = re.sub(r"[^A-Za-z0-9_-]", "", diperbarui)
        with st.form(f"form_kuis_{mata_kuliah['id']}_{nomor_sesi}_{kunci_formulir}"):
            jawaban: list[str | None] = []
            for indeks, soal in enumerate(daftar_kuis):
                jawaban.append(
                    st.radio(
                        f"{indeks + 1}. {soal['question']}",
                        soal["options"],
                        index=None,
                        key=f"kuis_{mata_kuliah['id']}_{nomor_sesi}_{indeks}_{kunci_formulir}",
                    )
                )
            periksa = st.form_submit_button("Periksa jawaban", type="primary")
        if periksa:
            skor = 0
            for indeks, (soal, jawaban_dipilih) in enumerate(
                zip(daftar_kuis, jawaban), start=1
            ):
                jawaban_benar = soal["options"][soal["answer_index"]]
                if jawaban_dipilih == jawaban_benar:
                    skor += 1
                    st.success(f"Soal {indeks}: benar")
                else:
                    st.error(f"Soal {indeks}: jawaban yang benar adalah {jawaban_benar}")
                if soal.get("explanation"):
                    st.caption(soal["explanation"])
            st.metric("Nilai kuis", f"{skor}/{len(daftar_kuis)}")


def tampilkan_hero() -> None:
    st.markdown(
        """
        <div class="hero-ut">
          <div class="kicker">RUANG BELAJAR SISTEM INFORMASI UT</div>
          <h1>Belajar lebih terarah, satu sesi setiap kali.</h1>
          <p>Pilih mata kuliah, simpan bahan Tuton per sesi, lalu ubah catatan Anda menjadi ringkasan, kisi-kisi UAS, flashcard, kuis, dan audio.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(CSS_APLIKASI, unsafe_allow_html=True)
daftar_semester_tersedia = daftar_semester()
semester_per_id = {item["id"]: item for item in daftar_semester_tersedia}
ada_mata_kuliah_aktif = any(
    daftar_mata_kuliah(item["id"]) for item in daftar_semester_tersedia
)
semester_baru = st.session_state.pop("_semester_baru", None)
if semester_baru in semester_per_id:
    st.session_state["semester_belajar"] = semester_baru
    st.session_state["semester_pengaturan"] = semester_baru


with st.sidebar:
    st.markdown("## UT Study Prep")
    st.caption("Pendamping belajar SI UT")
    halaman = st.radio(
        "Menu utama",
        ["Ruang belajar", "Atur semester", "Katalog SI"],
        index=0 if ada_mata_kuliah_aktif else 1,
        key="menu_utama",
    )
    st.divider()
    st.markdown("#### Mesin ringkasan")
    penyedia = st.selectbox(
        "Pilih mesin",
        ["Lokal (tanpa API)", "Google Gemini", "Groq"],
        help="Mode lokal selalu tersedia. Gemini dan Groq menggunakan kuota dari masing-masing penyedia.",
    )
    if penyedia == "Google Gemini":
        kunci_api = st.text_input(
            "Kunci API Gemini",
            value=ambil_rahasia("GEMINI_API_KEY"),
            type="password",
            help="Kunci yang diketik tidak disimpan ke SQLite.",
        )
        model = st.text_input("Model Gemini", value="gemini-2.5-flash", key="model_gemini")
        st.link_button("Buka halaman kunci Gemini", "https://aistudio.google.com/app/apikey")
    elif penyedia == "Groq":
        kunci_api = st.text_input(
            "Kunci API Groq",
            value=ambil_rahasia("GROQ_API_KEY"),
            type="password",
            help="Kunci yang diketik tidak disimpan ke SQLite.",
        )
        model = st.text_input("Model Groq", value="llama-3.3-70b-versatile", key="model_groq")
        st.link_button("Buka halaman kunci Groq", "https://console.groq.com/keys")
    else:
        kunci_api, model = "", "mesin-lokal"
    st.divider()
    st.caption(f"Penyimpanan lokal: `{LOKASI_DB.name}`")


if halaman == "Ruang belajar":
    tampilkan_hero()

    with st.container(border=True):
        judul_langkah(
            1,
            "Pilih semester dan mata kuliah",
            "Buka mata kuliah aktif yang sedang Anda pelajari.",
        )
        kolom_semester, kolom_mata_kuliah = st.columns(2)
        semester_id = kolom_semester.selectbox(
            "Semester",
            options=list(semester_per_id),
            format_func=lambda identitas: semester_per_id[identitas]["name"],
            key="semester_belajar",
        )
        mata_kuliah_aktif = daftar_mata_kuliah(semester_id)
        if not mata_kuliah_aktif:
            kolom_mata_kuliah.selectbox(
                "Mata kuliah",
                options=["Belum ada mata kuliah aktif"],
                disabled=True,
            )
            st.warning(
                "Semester ini belum memiliki mata kuliah aktif. Buka menu Atur semester untuk memilih mata kuliah."
            )
            st.stop()
        mata_kuliah_per_id = {int(item["id"]): item for item in mata_kuliah_aktif}
        mata_kuliah_id = kolom_mata_kuliah.selectbox(
            "Mata kuliah",
            options=list(mata_kuliah_per_id),
            format_func=lambda identitas: (
                f"{mata_kuliah_per_id[identitas]['code']} — {mata_kuliah_per_id[identitas]['name']}"
            ),
            key=f"mata_kuliah_belajar_{semester_id}",
        )
        mata_kuliah = mata_kuliah_per_id[mata_kuliah_id]
        st.markdown(
            f"<span class='label-kecil'>{html.escape(mata_kuliah['code'])}</span>"
            f"<span class='label-kecil'>{mata_kuliah['credits']} SKS</span>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        judul_langkah(
            2,
            "Pilih sesi dan masukkan bahan Tuton",
            "Setiap mata kuliah menyimpan Sesi 1 sampai Sesi 8 secara terpisah.",
        )
        nomor_sesi = st.radio(
            "Sesi tutorial",
            options=list(range(1, 9)),
            format_func=lambda nomor: f"Sesi {nomor}",
            horizontal=True,
            key=f"sesi_{mata_kuliah_id}",
        )
        data_sesi = ambil_sesi(mata_kuliah_id, nomor_sesi)
        akhiran = f"{mata_kuliah_id}_{nomor_sesi}"
        materi = st.text_area(
            "Materi atau ringkasan Tuton",
            value=data_sesi["material"],
            height=240,
            placeholder="Tempel ringkasan modul, penjelasan Tuton, atau poin belajar di sini…",
            key=f"materi_{akhiran}",
        )
        kolom_diskusi, kolom_tugas = st.columns(2)
        with kolom_diskusi:
            diskusi = st.text_area(
                "Pertanyaan diskusi",
                value=data_sesi["discussion"],
                height=135,
                placeholder="Tempel pertanyaan atau jawaban diskusi…",
                key=f"diskusi_{akhiran}",
            )
        with kolom_tugas:
            tugas = st.text_area(
                "Tugas",
                value=data_sesi["assignments"],
                height=135,
                placeholder="Tempel instruksi atau jawaban tugas…",
                key=f"tugas_{akhiran}",
            )
        tombol_simpan, tombol_contoh, ruang_kosong = st.columns([1, 1, 3])
        simpan_diklik = tombol_simpan.button("Simpan bahan", width="stretch")
        tombol_contoh.button(
            "Isi contoh",
            width="stretch",
            on_click=isi_contoh,
            args=(mata_kuliah_id, nomor_sesi),
        )
        if simpan_diklik:
            simpan_catatan_sesi(mata_kuliah_id, nomor_sesi, materi, diskusi, tugas)
            st.success(f"Bahan Sesi {nomor_sesi} berhasil disimpan.")

    with st.container(border=True):
        judul_langkah(
            3,
            "Buat ringkasan dan prediksi UAS",
            "Hasil akan tersimpan pada mata kuliah dan sesi yang dipilih.",
        )
        buat_diklik = st.button(
            "Buat Ringkasan & Prediksi UAS",
            type="primary",
            width="stretch",
        )
        paket = baca_paket(data_sesi)
        if buat_diklik:
            panjang_teks = len(materi.strip()) + len(diskusi.strip()) + len(tugas.strip())
            if panjang_teks < 80:
                st.error("Masukkan sedikitnya 80 karakter bahan Tuton agar hasilnya bermakna.")
            else:
                try:
                    with st.spinner(f"Menyusun paket belajar dengan {penyedia}…"):
                        paket = buat_paket_belajar(
                            penyedia,
                            mata_kuliah,
                            nomor_sesi,
                            materi,
                            diskusi,
                            tugas,
                            kunci_api,
                            model,
                        )
                    simpan_paket_belajar(
                        mata_kuliah_id,
                        nomor_sesi,
                        materi,
                        diskusi,
                        tugas,
                        paket,
                        penyedia,
                    )
                    data_sesi = ambil_sesi(mata_kuliah_id, nomor_sesi)
                    st.success(
                        f"Paket belajar {mata_kuliah['code']} · Sesi {nomor_sesi} berhasil dibuat dan disimpan."
                    )
                except KesalahanPenyedia as exc:
                    st.error(str(exc))

    if paket:
        st.markdown("## Hasil belajar")
        st.caption(
            f"{mata_kuliah['code']} · Sesi {nomor_sesi} · Dibuat dengan {data_sesi.get('provider') or penyedia}"
        )
        tampilkan_hasil(
            paket,
            mata_kuliah,
            nomor_sesi,
            data_sesi.get("updated_at", ""),
        )
    else:
        st.info("Hasil akan muncul di sini setelah Anda membuat paket belajar.")

elif halaman == "Atur semester":
    st.markdown(
        """
        <div class="hero-ut">
          <div class="kicker">PENGATURAN NON-SIPAS</div>
          <h1>Susun semester sesuai rencana Anda.</h1>
          <p>Pilih mata kuliah aktif dari katalog SI atau tambahkan mata kuliah khusus.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    semester_id = st.selectbox(
        "Semester yang akan diatur",
        options=list(semester_per_id),
        format_func=lambda identitas: semester_per_id[identitas]["name"],
        key="semester_pengaturan",
    )
    with st.expander("Buat semester baru"):
        with st.form("form_semester_baru", clear_on_submit=True):
            nama_semester_baru = st.text_input("Nama semester", placeholder="Contoh: Semester 5")
            buat_semester_diklik = st.form_submit_button("Buat semester", type="primary")
        if buat_semester_diklik:
            try:
                id_baru = buat_semester(nama_semester_baru)
                st.session_state["_semester_baru"] = id_baru
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    seluruh_mata_kuliah = daftar_mata_kuliah(semester_id, hanya_aktif=False)
    kode_aktif = [
        item["code"] for item in seluruh_mata_kuliah if not item["is_custom"] and item["active"]
    ]
    aktif = [item for item in seluruh_mata_kuliah if item["active"]]
    jumlah_sks = sum(int(item["credits"]) for item in aktif)
    metrik_satu, metrik_dua, metrik_tiga = st.columns(3)
    metrik_satu.metric("Mata kuliah aktif", len(aktif))
    metrik_dua.metric("Beban semester", f"{jumlah_sks} SKS")
    metrik_tiga.metric("Katalog SI", "51 mata kuliah")

    with st.container(border=True):
        st.markdown("### Pilih mata kuliah aktif")
        st.caption("Kelompok agama dan mata kuliah pilihan ditampilkan sebagai pilihan kode yang terpisah.")
        with st.form(f"form_katalog_{semester_id}"):
            pilihan_kode = st.multiselect(
                "Mata kuliah semester ini",
                options=[item["kode"] for item in DAFTAR_PENAWARAN],
                default=kode_aktif,
                format_func=lambda kode: (
                    f"{kode} — {PENAWARAN_PER_KODE[kode]['nama']} · {PENAWARAN_PER_KODE[kode]['sks']} SKS"
                ),
                key=f"pilihan_katalog_{semester_id}",
            )
            simpan_pilihan = st.form_submit_button("Simpan mata kuliah aktif", type="primary")
        if simpan_pilihan:
            sinkronkan_mata_kuliah(semester_id, pilihan_kode)
            st.success("Daftar mata kuliah aktif berhasil disimpan.")

    with st.expander("Tambahkan mata kuliah khusus"):
        with st.form(f"form_mata_kuliah_khusus_{semester_id}", clear_on_submit=True):
            kolom_kode, kolom_nama, kolom_sks = st.columns([1, 2, 1])
            kode_khusus = kolom_kode.text_input("Kode", placeholder="KHUSUS01")
            nama_khusus = kolom_nama.text_input("Nama mata kuliah")
            sks_khusus = kolom_sks.number_input("SKS", min_value=1, max_value=24, value=3)
            tambah_diklik = st.form_submit_button("Tambahkan mata kuliah")
        if tambah_diklik:
            try:
                tambah_mata_kuliah_khusus(
                    semester_id, kode_khusus, nama_khusus, int(sks_khusus)
                )
                st.success("Mata kuliah khusus berhasil ditambahkan.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("### Mata kuliah aktif")
    aktif = daftar_mata_kuliah(semester_id)
    if not aktif:
        st.info("Belum ada mata kuliah aktif pada semester ini.")
    else:
        st.dataframe(
            [
                {
                    "Kode": item["code"],
                    "Mata kuliah": item["name"],
                    "SKS": item["credits"],
                    "Sumber": "Tambahan" if item["is_custom"] else "Katalog UT",
                }
                for item in aktif
            ],
            width="stretch",
            hide_index=True,
        )
        tambahan = [item for item in aktif if item["is_custom"]]
        if tambahan:
            with st.expander("Kelola mata kuliah khusus"):
                for item in tambahan:
                    kolom_info, kolom_hapus = st.columns([5, 1])
                    kolom_info.write(
                        f"**{item['code']}** — {item['name']} ({item['credits']} SKS)"
                    )
                    if kolom_hapus.button("Hapus", key=f"hapus_{item['id']}"):
                        hapus_mata_kuliah_khusus(int(item["id"]))
                        st.rerun()

    st.download_button(
        "Unduh cadangan semester",
        data=ekspor_semester(semester_id),
        file_name=f"{semester_per_id[semester_id]['name'].lower().replace(' ', '-')}-cadangan.json",
        mime="application/json",
    )

else:
    st.markdown(
        """
        <div class="hero-ut">
          <div class="kicker">KATALOG PROGRAM STUDI</div>
          <h1>51 mata kuliah Sistem Informasi UT.</h1>
          <p>Kelompok agama dan mata kuliah pilihan tetap dihitung sebagai satu slot kurikulum.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    pencarian = st.text_input(
        "Cari kode atau nama mata kuliah",
        placeholder="Contoh: STSI44 atau keamanan",
    )
    kata_cari = pencarian.strip().lower()
    hasil_katalog = [
        item
        for item in KATALOG_MK_UT
        if not kata_cari
        or kata_cari in item["kode"].lower()
        or kata_cari in item["nama"].lower()
        or any(
            kata_cari in opsi["kode"].lower() or kata_cari in opsi["nama"].lower()
            for opsi in item.get("pilihan", [])
        )
    ]
    metrik_satu, metrik_dua, metrik_tiga = st.columns(3)
    metrik_satu.metric("Jumlah mata kuliah", len(KATALOG_MK_UT))
    metrik_dua.metric("Hasil ditampilkan", len(hasil_katalog))
    metrik_tiga.metric("Total kurikulum", "145 SKS")
    st.dataframe(
        [
            {
                "No.": item["slot"],
                "Kode": item["kode"],
                "Mata kuliah": item["nama"],
                "SKS": item["sks"],
                "Jenis": "Pilihan" if item.get("pilihan") else "Wajib",
            }
            for item in hasil_katalog
        ],
        width="stretch",
        hide_index=True,
    )
    kelompok_pilihan = [item for item in hasil_katalog if item.get("pilihan")]
    if kelompok_pilihan:
        with st.expander("Lihat rincian kelompok pilihan"):
            for item in kelompok_pilihan:
                st.markdown(f"**Slot {item['slot']} · {item['nama']}**")
                for opsi in item["pilihan"]:
                    st.markdown(f"- `{opsi['kode']}` — {opsi['nama']} ({item['sks']} SKS)")
