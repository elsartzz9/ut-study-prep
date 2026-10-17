from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import smtplib
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st


st.set_page_config(
    page_title="UT Study Prep",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("bahasa_antarmuka", "Bahasa Indonesia")


def memakai_bahasa_inggris() -> bool:
    return st.session_state.get("bahasa_antarmuka") == "English"


def tx(indonesia: str, english: str) -> str:
    return english if memakai_bahasa_inggris() else indonesia


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

            CREATE TABLE IF NOT EXISTS ielts_practice (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                practice_type TEXT NOT NULL CHECK (practice_type IN ('Writing', 'Speaking')),
                input_text TEXT NOT NULL,
                feedback_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS language_vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL CHECK (language IN ('Mandarin', 'Vietnamese')),
                term TEXT NOT NULL,
                pronunciation TEXT NOT NULL,
                indonesian_translation TEXT NOT NULL,
                example_sentence TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE (language, term COLLATE NOCASE)
            );
            """
        )
        koneksi.execute("PRAGMA journal_mode = WAL")
        if koneksi.execute("SELECT id FROM semesters LIMIT 1").fetchone() is None:
            koneksi.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                ("Semester 1", waktu_sekarang()),
            )

        if koneksi.execute("SELECT id FROM language_vocabulary LIMIT 1").fetchone() is None:
            kosakata_awal = [
                ("Mandarin", "你好", "nǐ hǎo", "halo", "你好，很高兴认识你。", "percakapan sehari-hari"),
                ("Mandarin", "学习", "xuéxí", "belajar", "我每天学习英语。", "pendidikan"),
                ("Mandarin", "机会", "jīhuì", "kesempatan", "这是一个很好的机会。", "karier dan tujuan"),
                ("Mandarin", "坚持", "jiānchí", "tekun; bertahan", "坚持就是胜利。", "motivasi"),
                ("Vietnamese", "xin chào", "sin chào", "halo", "Xin chào, rất vui được gặp bạn.", "percakapan sehari-hari"),
                ("Vietnamese", "học tập", "hok təp", "belajar", "Tôi học tiếng Việt mỗi ngày.", "pendidikan"),
                ("Vietnamese", "cơ hội", "kə hoj", "kesempatan", "Đây là một cơ hội tốt.", "karier dan tujuan"),
                ("Vietnamese", "kiên trì", "kien trì", "tekun; gigih", "Kiên trì sẽ dẫn đến thành công.", "motivasi"),
            ]
            koneksi.executemany(
                """
                INSERT INTO language_vocabulary
                    (language, term, pronunciation, indonesian_translation,
                     example_sentence, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [(*item, waktu_sekarang()) for item in kosakata_awal],
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
        raise ValueError(tx("Tuliskan nama semester terlebih dahulu.", "Enter a semester name first."))
    with buka_db() as koneksi:
        try:
            kursor = koneksi.execute(
                "INSERT INTO semesters (name, created_at) VALUES (?, ?)",
                (nama_bersih, waktu_sekarang()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(tx("Nama semester tersebut sudah tersedia.", "That semester already exists.")) from exc
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
        raise ValueError(tx("Kode dan nama mata kuliah wajib diisi.", "Course code and name are required."))
    if kode_bersih in PENAWARAN_PER_KODE:
        raise ValueError(tx("Kode tersebut sudah ada di katalog. Pilih dari daftar katalog.", "That code is already in the catalog. Select it from the catalog list."))
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


def simpan_latihan_ielts(
    jenis: str, teks: str, hasil: dict[str, Any], penyedia: str
) -> int:
    with buka_db() as koneksi:
        kursor = koneksi.execute(
            """
            INSERT INTO ielts_practice
                (practice_type, input_text, feedback_json, provider, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                jenis,
                teks.strip(),
                json.dumps(hasil, ensure_ascii=False),
                penyedia,
                waktu_sekarang(),
            ),
        )
    return int(kursor.lastrowid)


def daftar_latihan_ielts(batas: int = 12) -> list[dict[str, Any]]:
    with buka_db() as koneksi:
        hasil = koneksi.execute(
            """
            SELECT id, practice_type, input_text, feedback_json, provider, created_at
            FROM ielts_practice
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(batas),),
        ).fetchall()
    latihan = []
    for item in hasil:
        baris = dict(item)
        try:
            baris["feedback"] = json.loads(baris.pop("feedback_json"))
        except json.JSONDecodeError:
            baris["feedback"] = {}
        latihan.append(baris)
    return latihan


def tambah_kosakata(
    bahasa: str,
    istilah: str,
    pelafalan: str,
    terjemahan: str,
    contoh: str,
    tag: str,
) -> None:
    nilai = [re.sub(r"\s+", " ", item.strip()) for item in (istilah, pelafalan, terjemahan, contoh)]
    if bahasa not in {"Mandarin", "Vietnamese"} or not all(nilai):
        raise ValueError(
            tx(
                "Bahasa, istilah, pelafalan, terjemahan, dan contoh wajib diisi.",
                "Language, term, pronunciation, translation, and example are required.",
            )
        )
    with buka_db() as koneksi:
        koneksi.execute(
            """
            INSERT INTO language_vocabulary
                (language, term, pronunciation, indonesian_translation,
                 example_sentence, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language, term) DO UPDATE SET
                pronunciation = excluded.pronunciation,
                indonesian_translation = excluded.indonesian_translation,
                example_sentence = excluded.example_sentence,
                tags = excluded.tags,
                created_at = excluded.created_at
            """,
            (bahasa, *nilai, re.sub(r"\s+", " ", tag.strip()), waktu_sekarang()),
        )


def daftar_kosakata(bahasa: str | None = None) -> list[dict[str, Any]]:
    with buka_db() as koneksi:
        if bahasa in {"Mandarin", "Vietnamese"}:
            hasil = koneksi.execute(
                """
                SELECT * FROM language_vocabulary
                WHERE language = ?
                ORDER BY term COLLATE NOCASE
                """,
                (bahasa,),
            ).fetchall()
        else:
            hasil = koneksi.execute(
                "SELECT * FROM language_vocabulary ORDER BY language, term COLLATE NOCASE"
            ).fetchall()
    return [dict(item) for item in hasil]


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
    cadangan = (
        ["concept", "application", "analysis", "process", "evaluation", "system", "data", "quality"]
        if memakai_bahasa_inggris()
        else ["konsep", "penerapan", "analisis", "proses", "evaluasi", "sistem", "data", "kualitas"]
    )
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
            tx(
                f"Hubungkan konsep {kata.title()} dengan capaian belajar {mata_kuliah['name']}.",
                f"Connect {kata.title()} to the learning outcomes for {mata_kuliah['name']}.",
            )
            for kata in kata_kunci[: 5 - len(poin_penting)]
        )

    topik_diskusi = ambil_kata_kunci(diskusi + " " + tugas, 5)
    topik_prediksi = list(dict.fromkeys(topik_diskusi + kata_kunci))[:5]
    prediksi = [
        {
            "topic": topik.title(),
            "priority": tx("Tinggi", "High") if indeks < 2 else tx("Sedang", "Medium"),
            "rationale": (
                tx(
                    "Topik muncul pada diskusi atau tugas; latih penjelasan dan penerapannya.",
                    "This topic appears in the discussion or assignment; practice explaining and applying it.",
                )
                if topik in topik_diskusi
                else tx(
                    "Topik menonjol pada materi Tuton dan layak dijadikan fokus belajar konsep.",
                    "This topic is prominent in the tutorial material and deserves focused review.",
                )
            ),
        }
        for indeks, topik in enumerate(topik_prediksi)
    ]

    flashcard = []
    for topik in kata_kunci[:6]:
        jawaban = next(
            (item for item in kalimat if topik.lower() in item.lower()),
            tx(
                f"Pelajari hubungan {topik} dengan materi {mata_kuliah['name']}.",
                f"Review how {topik} relates to {mata_kuliah['name']}.",
            ),
        )
        flashcard.append(
            {
                "front": tx(
                    f"Apa yang perlu diingat tentang {topik.title()}?",
                    f"What should you remember about {topik.title()}?",
                ),
                "back": jawaban,
            }
        )

    kuis = []
    for indeks, topik in enumerate(kata_kunci[:5]):
        sumber = next(
            (item for item in kalimat if topik.lower() in item.lower()),
            poin_penting[indeks % len(poin_penting)],
        )
        pengecoh = [kata.title() for kata in kata_kunci if kata != topik][:3]
        while len(pengecoh) < 3:
            pengecoh.append(
                (["Application", "Evaluation", "Architecture"] if memakai_bahasa_inggris() else ["Penerapan", "Evaluasi", "Arsitektur"])[len(pengecoh)]
            )
        indeks_jawaban = indeks % 4
        opsi = pengecoh[:]
        opsi.insert(indeks_jawaban, topik.title())
        kuis.append(
            {
                "question": tx(
                    f"Konsep mana yang paling sesuai dengan catatan berikut: “{sumber[:150]}”?",
                    f"Which concept best matches this note: “{sumber[:150]}”?",
                ),
                "options": opsi,
                "answer_index": indeks_jawaban,
                "explanation": tx(
                    f"Catatan tersebut paling langsung membahas {topik.title()}.",
                    f"The note most directly discusses {topik.title()}.",
                ),
            }
        )

    return {
        "summary": ringkasan,
        "key_points": poin_penting[:6],
        "exam_predictions": prediksi,
        "flashcards": flashcard,
        "quiz": kuis,
        "study_plan": (
            [
                "Read the summary once without highlighting.",
                "Recall every key point without looking at your notes.",
                "Practice the exam-focus topics with your own examples.",
                "Complete the quiz, then revisit every missed concept.",
            ]
            if memakai_bahasa_inggris()
            else [
                "Baca ringkasan sekali tanpa memberi tanda.",
                "Sebutkan kembali setiap poin penting tanpa melihat catatan.",
                "Latih topik kisi-kisi UAS dengan contoh buatan sendiri.",
                "Kerjakan kuis, lalu ulangi konsep yang masih keliru.",
            ]
        ),
    }


def buat_prompt(
    mata_kuliah: dict[str, Any], nomor_sesi: int, materi: str, diskusi: str, tugas: str
) -> str:
    sumber = tx(
        f"""MATA KULIAH: {mata_kuliah['code']} — {mata_kuliah['name']} ({mata_kuliah['credits']} SKS)
SESI TUTON: {nomor_sesi}

MATERI ATAU RINGKASAN TUTON:
{materi}

DISKUSI:
{diskusi or '(tidak diisi)'}

TUGAS:
{tugas or '(tidak diisi)'}""",
        f"""COURSE: {mata_kuliah['code']} — {mata_kuliah['name']} ({mata_kuliah['credits']} credits)
TUTORIAL SESSION: {nomor_sesi}

TUTORIAL MATERIAL OR NOTES:
{materi}

DISCUSSION:
{diskusi or '(not provided)'}

ASSIGNMENT:
{tugas or '(not provided)'}""",
    ).strip()[:30000]
    if memakai_bahasa_inggris():
        return f"""
You are a study assistant for a Universitas Terbuka Information Systems student.
Use only the supplied material and write in clear English. Never claim that a predicted topic is
guaranteed to appear on the final exam. Return only one valid JSON object with this structure:

{{
  "summary": "a concise and complete summary",
  "key_points": ["5 to 7 important points"],
  "exam_predictions": [
    {{"topic": "topic", "priority": "High or Medium", "rationale": "evidence-based reason"}}
  ],
  "flashcards": [{{"front": "question", "back": "answer"}}],
  "quiz": [
    {{"question": "multiple-choice question", "options": ["A", "B", "C", "D"],
      "answer_index": 0, "explanation": "why the answer is correct"}}
  ],
  "study_plan": ["four short study actions"]
}}

Create 5 exam-focus predictions, 6 flashcards, and 5 quiz questions. answer_index is zero-based.

{sumber}
""".strip()
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
        raise KesalahanPenyedia(tx(f"Permintaan ke layanan AI gagal: {pesan}", f"The AI provider request failed: {pesan}")) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise KesalahanPenyedia(tx(f"Layanan AI tidak dapat dihubungi: {exc}", f"The AI provider could not be reached: {exc}")) from exc



def ambil_objek_json(teks: str) -> dict[str, Any]:
    """Ambil satu objek JSON dari respons teks layanan AI."""
    hasil = teks.strip()
    if hasil.startswith("```"):
        hasil = re.sub(r"^```(?:json)?\s*|\s*```$", "", hasil, flags=re.IGNORECASE)
    awal, akhir = hasil.find("{"), hasil.rfind("}")
    if awal < 0 or akhir <= awal:
        raise KesalahanPenyedia(tx("Layanan AI tidak mengirimkan paket belajar berbentuk JSON.", "The AI provider did not return a JSON study pack."))
        raise KesalahanPenyedia(
            tx(
                "Layanan AI tidak mengirimkan JSON yang dapat dibaca.",
                "The AI provider did not return readable JSON.",
            )
        )
    try:
        data = json.loads(hasil[awal : akhir + 1])
    except json.JSONDecodeError as exc:
        raise KesalahanPenyedia(tx("Format jawaban layanan AI tidak valid. Silakan coba lagi.", "The AI provider returned invalid JSON. Please try again.")) from exc
    if not isinstance(data, dict):
        raise KesalahanPenyedia(tx("Jawaban layanan AI bukan paket belajar yang valid.", "The AI response is not a valid study pack."))
    return rapikan_paket(data)
        raise KesalahanPenyedia(
            tx(
                "Jawaban layanan AI bukan objek JSON yang valid.",
                "The AI response is not a valid JSON object.",
            )
        )
    return data


def ambil_json(teks: str) -> dict[str, Any]:
    return rapikan_paket(ambil_objek_json(teks))


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
        raise KesalahanPenyedia(tx("Jawaban layanan AI belum lengkap. Silakan buat ulang paket belajar.", "The AI response is incomplete. Please generate the study pack again."))
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
        raise KesalahanPenyedia(tx("Gemini tidak mengirimkan jawaban yang dapat dibaca.", "Gemini did not return readable output.")) from exc
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
        raise KesalahanPenyedia(tx("Groq tidak mengirimkan jawaban yang dapat dibaca.", "Groq did not return readable output.")) from exc
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
        raise KesalahanPenyedia(tx(f"Masukkan kunci API {penyedia} di bilah samping.", f"Enter your {penyedia} API key in the sidebar."))
    prompt = buat_prompt(mata_kuliah, nomor_sesi, materi, diskusi, tugas)
    if penyedia == "Google Gemini":
        return paket_gemini(prompt, kunci_api.strip(), model)
    if penyedia == "Groq":
        return paket_groq(prompt, kunci_api.strip(), model)
    raise KesalahanPenyedia(tx("Mesin belajar tidak dikenali.", "The study engine is not supported."))


def rapikan_teks_inggris(teks: str) -> str:
    hasil = re.sub(r"\s+", " ", teks.strip())
    hasil = re.sub(r"\s+([,.;:!?])", r"\1", hasil)
    hasil = re.sub(r"\bi\b", "I", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"\bim\b", "I'm", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"\bdont\b", "don't", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"\bcant\b", "can't", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"\bwont\b", "won't", hasil, flags=re.IGNORECASE)
    bagian = re.split(r"(?<=[.!?])\s+", hasil)
    return " ".join(item[:1].upper() + item[1:] if item else item for item in bagian)


def koreksi_ielts_lokal(teks: str, jenis: str) -> dict[str, Any]:
    kata = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", teks)
    jumlah_kata = len(kata)
    kata_unik = len({item.lower() for item in kata})
    rasio_unik = kata_unik / max(jumlah_kata, 1)
    penghubung = {
        "however", "therefore", "moreover", "furthermore", "although", "whereas",
        "consequently", "nevertheless", "firstly", "secondly", "finally", "because",
    }
    jumlah_penghubung = sum(1 for item in kata if item.lower() in penghubung)
    pola_kesalahan = re.findall(
        r"\b(?:im|dont|cant|wont|didnt|doesnt|isnt|arent|wasnt|werent)\b",
        teks.lower(),
    )
    kalimat = pecah_kalimat(teks)

    ambang = [45, 90, 150, 230] if jenis == "Writing" else [30, 60, 100, 160]
    band = 4.0 + sum(0.5 for nilai in ambang if jumlah_kata >= nilai)
    if rasio_unik >= 0.48 and jumlah_kata >= 80:
        band += 0.5
    if jumlah_penghubung >= 3:
        band += 0.5
    if pola_kesalahan:
        band -= 0.5
    band = max(3.5, min(7.0, round(band * 2) / 2))

    tata_bahasa = []
    if pola_kesalahan:
        tata_bahasa.append(
            tx(
                "Periksa kontraksi dan apostrof, misalnya I'm, don't, can't, dan won't.",
                "Check contractions and apostrophes, such as I'm, don't, can't, and won't.",
            )
        )
    if len(kalimat) < 3:
        tata_bahasa.append(
            tx(
                "Kembangkan gagasan menjadi beberapa kalimat lengkap dengan subjek dan predikat yang jelas.",
                "Develop the response into several complete sentences with clear subjects and verbs.",
            )
        )
    tata_bahasa.append(
        tx(
            "Periksa konsistensi tense, subject–verb agreement, artikel, dan tanda baca pada penyuntingan akhir.",
            "Check tense consistency, subject–verb agreement, articles, and punctuation during the final edit.",
        )
    )

    kosakata = [
        tx(
            f"Keragaman kosakata terdeteksi sekitar {rasio_unik:.0%}; prioritaskan ketepatan sebelum memakai kata yang terlalu rumit.",
            f"Vocabulary variety is approximately {rasio_unik:.0%}; prioritize accuracy before using overly complex words.",
        )
    ]
    if jumlah_penghubung < 3:
        kosakata.append(
            tx(
                "Tambahkan penghubung secara alami, misalnya however, therefore, atau moreover.",
                "Add linking words naturally, such as however, therefore, or moreover.",
            )
        )
    else:
        kosakata.append(
            tx(
                "Kata penghubung sudah muncul; pastikan setiap penghubung benar-benar menunjukkan hubungan logis.",
                "Linking words are present; make sure each one expresses a genuine logical relationship.",
            )
        )

    return {
        "overview": tx(
            f"Teks {jenis.lower()} berisi {jumlah_kata} kata. Mesin offline menilai kejelasan, panjang, variasi kosakata, dan penanda kohesi dasar.",
            f"This {jenis.lower()} response contains {jumlah_kata} words. The offline engine reviewed clarity, length, vocabulary variety, and basic cohesion markers.",
        ),
        "grammar_feedback": tata_bahasa,
        "vocabulary_feedback": kosakata,
        "corrected_text": rapikan_teks_inggris(teks),
        "estimated_band": band,
        "next_steps": [
            tx("Baca ulang teks dengan suara keras untuk menemukan kalimat yang janggal.", "Read the response aloud to catch awkward sentences."),
            tx("Tulis ulang satu paragraf dengan struktur yang lebih jelas.", "Rewrite one paragraph with a clearer structure."),
            tx("Bandingkan versi awal dan versi koreksi, lalu catat tiga pola kesalahan.", "Compare the original and corrected versions, then record three recurring errors."),
        ],
    }


def rapikan_koreksi_ielts(data: dict[str, Any], teks_asli: str) -> dict[str, Any]:
    def daftar(nama: str) -> list[str]:
        nilai = data.get(nama, [])
        return [str(item).strip() for item in nilai if str(item).strip()] if isinstance(nilai, list) else []

    try:
        band = float(data.get("estimated_band", 0))
    except (TypeError, ValueError):
        band = 0
    band = max(0.0, min(9.0, round(band * 2) / 2))
    hasil = {
        "overview": str(data.get("overview", "")).strip(),
        "grammar_feedback": daftar("grammar_feedback"),
        "vocabulary_feedback": daftar("vocabulary_feedback"),
        "corrected_text": str(data.get("corrected_text", "")).strip() or teks_asli.strip(),
        "estimated_band": band,
        "next_steps": daftar("next_steps"),
    }
    if not hasil["overview"] or not hasil["grammar_feedback"] or not hasil["vocabulary_feedback"]:
        raise KesalahanPenyedia(
            tx(
                "Umpan balik IELTS dari layanan AI belum lengkap. Silakan coba lagi.",
                "The AI provider returned incomplete IELTS feedback. Please try again.",
            )
        )
    return hasil


def buat_prompt_ielts(teks: str, jenis: str) -> str:
    bahasa = "Indonesian" if not memakai_bahasa_inggris() else "English"
    return f"""
You are a careful IELTS tutor. Review the English {jenis.lower()} practice below.
Return feedback in {bahasa}. Estimate an indicative IELTS band from 0 to 9 using half-band steps;
make clear through the wording that this is not an official score. Preserve the writer's meaning.
Return only one valid JSON object with this exact structure:
{{
  "overview": "brief overall assessment",
  "grammar_feedback": ["specific issue and improvement"],
  "vocabulary_feedback": ["specific lexical improvement"],
  "corrected_text": "a corrected version of the full response",
  "estimated_band": 6.0,
  "next_steps": ["three focused practice actions"]
}}

PRACTICE TEXT:
{teks.strip()[:18000]}
""".strip()


def koreksi_ielts_dengan_ai(
    penyedia: str,
    jenis: str,
    teks: str,
    kunci_api: str,
    model: str,
) -> dict[str, Any]:
    if penyedia == "Lokal (tanpa API)":
        return koreksi_ielts_lokal(teks, jenis)
    if not kunci_api.strip():
        raise KesalahanPenyedia(
            tx(
                f"Masukkan kunci API {penyedia} di bilah samping.",
                f"Enter your {penyedia} API key in the sidebar.",
            )
        )
    prompt = buat_prompt_ielts(teks, jenis)
    if penyedia == "Google Gemini":
        model_aman = urllib.parse.quote(model.strip(), safe="-_.")
        data = kirim_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_aman}:generateContent",
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
            },
            {"x-goog-api-key": kunci_api.strip()},
        )
        try:
            teks_jawaban = "".join(
                item.get("text", "")
                for item in data["candidates"][0]["content"]["parts"]
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise KesalahanPenyedia(
                tx("Gemini tidak mengirimkan koreksi yang dapat dibaca.", "Gemini did not return readable feedback.")
            ) from exc
    elif penyedia == "Groq":
        data = kirim_json(
            "https://api.groq.com/openai/v1/chat/completions",
            {
                "model": model.strip(),
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            {"Authorization": f"Bearer {kunci_api.strip()}"},
        )
        try:
            teks_jawaban = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise KesalahanPenyedia(
                tx("Groq tidak mengirimkan koreksi yang dapat dibaca.", "Groq did not return readable feedback.")
            ) from exc
    else:
        raise KesalahanPenyedia(tx("Mesin belajar tidak dikenali.", "The study engine is not supported."))
    return rapikan_koreksi_ielts(ambil_objek_json(teks_jawaban), teks)


# -----------------------------------------------------------------------------
# Tampilan dan komponen
# -----------------------------------------------------------------------------

NAMA_MK_INGGRIS = {
    "STSI4101": "Introduction to Information Systems", "STSI4103": "Operating Systems",
    "MKWN4101": "Islamic Religious Education", "MKWN4102": "Catholic Religious Education",
    "MKWN4103": "Christian Religious Education", "MKWN4104": "Buddhist Religious Education",
    "MKWN4105": "Hindu Religious Education", "MKWN4107": "Confucian Religious Education",
    "STSI4102": "Algorithms and Programming", "STMA4112": "Basic Mathematics",
    "MKWN4109": "Civic Education", "STSI4105": "Databases", "STSI4104": "Data Structures",
    "MKKI4201": "Introduction to Statistics", "MKDI4201": "English",
    "MKWN4108": "Indonesian Language", "MKWN4110": "Pancasila",
    "STMA4113": "Elementary Linear Algebra", "STIK4111": "Fundamentals of R Programming",
    "STSI4106": "Informatics Logic", "STSI4201": "Desktop-Based Programming",
    "STSI4203": "Human-Computer Interaction", "STSI4202": "Software Engineering",
    "STSI4205": "Computer Networks", "MKDI4202": "Learning in the Digital Era",
    "MKDI4203": "Entrepreneurship in the Digital Era", "STSI4204": "Data Analysis and Visualization",
    "STSI4208": "Systems Analysis and Design", "STSI4209": "Web-Based Programming",
    "STSI4206": "Business Processes", "STSI4207": "Management Information Systems",
    "EMBS4207": "Organizational Behavior", "FSSI4101": "Basic Reading",
    "STMA4111": "Differential Calculus", "EMBS4102": "Introduction to Business",
    "STSI4301": "Decision Support Systems", "STSI4302": "Server Administration",
    "FSAP4102": "Organizational Theory", "STSI4303": "Mobile-Based Programming",
    "STSI4308": "Business and Technical Communication", "STSI4307": "Data Mining",
    "STSI4309": "Network Administration", "STSI4306": "Enterprise System Architecture and Design",
    "STSI4305": "Professional Ethics", "STPL4211": "Planning Information Systems",
    "MKKI4301": "Community Empowerment", "STSI4304": "Fundamentals of IT Infrastructure",
    "STSI4310": "Research Methodology", "EMBS4101": "Management",
    "STSI4409": "Data Warehouse", "STSI4404": "Network Security",
    "STDA4101": "Introduction to Data Science", "STSI4403": "Risk Management and Information Systems Audit",
    "STSI4402": "Information Technology Governance", "STSI4440": "Capstone Project (TAPS)",
    "STSI4406": "Information Systems Project Management", "STSI4405": "Information Systems Security",
    "STSI4407": "Information Technology Service Management", "STSI4408": "E-Business",
    "EACC4207": "Accounting Information Systems",
}

NAMA_SLOT_INGGRIS = {
    3: "Religious Education (choose one)",
    31: "Elective course 1",
    35: "Elective course 2",
    38: "Elective course 3",
    42: "Elective course 4",
}

KUTIPAN_HARIAN = [
    (
        "Mimpi kuliah atau bekerja di luar negeri tidak akan mengejar Anda. Selesaikan satu sesi hari ini, lalu biarkan konsistensi membuka jalan.",
        "Your dream of studying or working abroad will not chase you. Finish one session today and let consistency open the door.",
    ),
    (
        "Tidak punya banyak privilese berarti disiplin Anda harus menjadi modal. Sulit bukan berarti mustahil.",
        "Having less privilege means discipline must become your capital. Difficult does not mean impossible.",
    ),
    (
        "Takdir jarang berubah lewat niat besar. Ia berubah lewat kebiasaan kecil yang diulang ketika Anda sedang malas.",
        "Destiny rarely changes through grand intentions. It changes through small habits repeated when you feel lazy.",
    ),
    (
        "Orang lain mungkin memulai lebih jauh di depan. Tugas Anda bukan iri—tugas Anda terus memperpendek jarak.",
        "Others may start far ahead. Your job is not to envy them; your job is to keep closing the distance.",
    ),
    (
        "Lelah itu manusiawi. Menyerahkan masa depan kepada rasa malas adalah pilihan yang terlalu mahal.",
        "Being tired is human. Handing your future to laziness is far too expensive.",
    ),
    (
        "Tidak ada penyelamat yang akan datang membawa gelar, karier, atau visa impian Anda. Mulailah dari catatan di depan Anda.",
        "No rescuer is coming with your degree, career, or dream visa. Start with the notes in front of you.",
    ),
    (
        "Satu jam belajar mungkin terasa kecil, tetapi satu jam setiap hari bisa mengubah arah hidup Anda.",
        "One hour of study may feel small, but one hour every day can change the direction of your life.",
    ),
    (
        "Anda tidak harus merasa termotivasi untuk bergerak. Bergeraklah dulu; motivasi sering menyusul setelahnya.",
        "You do not have to feel motivated before moving. Move first; motivation often follows.",
    ),
    (
        "Kesempatan ke luar negeri dibangun jauh sebelum tiket dibeli—melalui kemampuan yang Anda latih hari ini.",
        "An opportunity abroad is built long before the ticket is purchased—through the skills you practice today.",
    ),
    (
        "Kemajuan yang sunyi tetaplah kemajuan. Tidak semua kerja keras perlu terlihat untuk mengubah hidup.",
        "Quiet progress is still progress. Hard work does not need an audience to change your life.",
    ),
    (
        "Jika hidup tidak memberi Anda jalan pintas, bangun stamina untuk menempuh jalan panjang.",
        "If life gives you no shortcut, build the stamina to take the long road.",
    ),
    (
        "Versi masa depan Anda membutuhkan bukti, bukan janji. Berikan satu sesi belajar sebagai bukti hari ini.",
        "Your future self needs evidence, not promises. Give them one completed study session today.",
    ),
]

BANK_KOSAKATA_IELTS = [
    {"term": "mitigate", "meaning": "mengurangi dampak", "example": "Governments should mitigate the effects of climate change.", "tag": "Academic verb"},
    {"term": "ubiquitous", "meaning": "ada di mana-mana", "example": "Digital technology has become ubiquitous in modern education.", "tag": "Academic adjective"},
    {"term": "compelling", "meaning": "sangat meyakinkan", "example": "The report presents compelling evidence for policy reform.", "tag": "Argument"},
    {"term": "disparity", "meaning": "kesenjangan", "example": "The policy aims to reduce the disparity between urban and rural areas.", "tag": "Society"},
    {"term": "sustainable", "meaning": "berkelanjutan", "example": "Cities need sustainable transport systems to reduce pollution.", "tag": "Environment"},
    {"term": "exacerbate", "meaning": "memperburuk", "example": "Poor planning may exacerbate existing social problems.", "tag": "Cause and effect"},
    {"term": "pragmatic", "meaning": "praktis dan realistis", "example": "A pragmatic solution should balance cost and public benefit.", "tag": "Evaluation"},
    {"term": "pivotal", "meaning": "sangat penting", "example": "Teachers play a pivotal role in developing critical thinking.", "tag": "Importance"},
    {"term": "a double-edged sword", "meaning": "sesuatu yang memiliki manfaat dan risiko", "example": "Social media can be a double-edged sword for young people.", "tag": "Idiom"},
    {"term": "in the long run", "meaning": "dalam jangka panjang", "example": "Preventive healthcare saves public money in the long run.", "tag": "Idiom"},
    {"term": "bridge the gap", "meaning": "menjembatani kesenjangan", "example": "Online courses can help bridge the gap in access to education.", "tag": "Idiom"},
    {"term": "food for thought", "meaning": "bahan untuk dipikirkan", "example": "The documentary offers food for thought about consumer habits.", "tag": "Idiom"},
]


def nama_tampilan(kode: str, nama_asli: str) -> str:
    if memakai_bahasa_inggris():
        return NAMA_MK_INGGRIS.get(kode, nama_asli)
    return nama_asli


def nama_slot_katalog(item: dict[str, Any]) -> str:
    if memakai_bahasa_inggris():
        return NAMA_SLOT_INGGRIS.get(
            int(item["slot"]), NAMA_MK_INGGRIS.get(item["kode"], item["nama"])
        )
    return item["nama"]


def waktu_lokal() -> datetime:
    try:
        return datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Bangkok")))
    except Exception:
        return datetime.now(timezone.utc)


def kirim_email_belajar(
    penerima: str,
    jadwal: str,
    mata_kuliah: dict[str, Any],
    nomor_sesi: int,
    paket: dict[str, Any],
    host: str,
    port: int,
    pengguna: str,
    kata_sandi: str,
    pengirim: str,
) -> None:
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", penerima.strip()):
        raise ValueError(tx("Alamat email belum valid.", "Please enter a valid email address."))
    if not host.strip() or not pengguna.strip() or not kata_sandi:
        raise ValueError(
            tx(
                "Lengkapi host, nama pengguna, dan kata sandi SMTP di bilah samping.",
                "Complete the SMTP host, username, and password in the sidebar.",
            )
        )

    pesan = EmailMessage()
    pesan["Subject"] = tx(
        f"Ringkasan belajar UT · {mata_kuliah['code']} · Sesi {nomor_sesi}",
        f"UT study summary · {mata_kuliah['code']} · Session {nomor_sesi}",
    )
    pesan["From"] = pengirim.strip() or pengguna.strip()
    pesan["To"] = penerima.strip()
    poin = "\n".join(f"- {item}" for item in paket.get("key_points", []))
    fokus = "\n".join(
        f"- {item['topic']} ({item['priority']}): {item['rationale']}"
        for item in paket.get("exam_predictions", [])
    )
    pesan.set_content(
        tx(
            f"""Halo, Elsa!

Berikut ringkasan belajar hari ini.

Mata kuliah: {mata_kuliah['code']} — {nama_tampilan(mata_kuliah['code'], mata_kuliah['name'])}
Sesi Tuton: {nomor_sesi}

RINGKASAN
{paket['summary']}

POIN PENTING
{poin}

KISI-KISI UAS
{fokus}

JADWAL BELAJAR
{jadwal or 'Belum ditentukan'}

Tetap konsisten. Satu sesi hari ini tetap membawa Anda lebih dekat pada tujuan.
""",
            f"""Hello, Elsa!

Here is today's learning summary.

Course: {mata_kuliah['code']} — {nama_tampilan(mata_kuliah['code'], mata_kuliah['name'])}
Tutorial session: {nomor_sesi}

SUMMARY
{paket['summary']}

KEY POINTS
{poin}

FINAL-EXAM FOCUS
{fokus}

STUDY SCHEDULE
{jadwal or 'Not set'}

Stay consistent. One session today still moves you closer to your goal.
""",
        )
    )

    konteks = ssl.create_default_context()
    if int(port) == 465:
        with smtplib.SMTP_SSL(host.strip(), int(port), context=konteks, timeout=30) as server:
            server.login(pengguna.strip(), kata_sandi)
            server.send_message(pesan)
    else:
        with smtplib.SMTP(host.strip(), int(port), timeout=30) as server:
            server.ehlo()
            server.starttls(context=konteks)
            server.ehlo()
            server.login(pengguna.strip(), kata_sandi)
            server.send_message(pesan)

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

    [data-testid="stExpander"] details {
        background: var(--sand) !important;
        border: 1px solid var(--demitasse) !important;
        border-radius: 14px !important;
        overflow: hidden;
    }

    [data-testid="stExpander"] summary {
        background: var(--demitasse) !important;
    }

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary svg {
        color: var(--coconut) !important;
        fill: var(--coconut) !important;
        font-weight: 750 !important;
    }

    [data-testid="stExpanderDetails"],
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] span,
    [data-testid="stExpanderDetails"] label {
        background: var(--sand) !important;
        color: var(--demitasse) !important;
    }

    .sapaan-harian {
        background: var(--sand); border: 1px solid var(--line); border-radius: 18px;
        padding: 1.15rem 1.3rem; margin: 0 0 1.2rem;
    }
    .sapaan-harian strong { font-size: 1.1rem; color: var(--demitasse); }
    .kutipan-harian { margin-top: .55rem; line-height: 1.6; font-style: italic; }
    .petunjuk-ringkas {
        background: var(--coconut); border: 1px dashed var(--demitasse); border-radius: 12px;
        padding: .72rem .9rem; margin: .45rem 0 .85rem; color: var(--demitasse);
    }

    .kartu-tebak {
        background: var(--sand); border: 2px solid var(--demitasse); border-radius: 18px;
        padding: 1.15rem 1.25rem; margin: .5rem 0 1rem;
    }
    .prompt-tebak {
        color: var(--demitasse); font-size: clamp(1.55rem, 4vw, 2.35rem);
        font-weight: 850; margin: .65rem 0 .35rem;
    }

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
    if memakai_bahasa_inggris():
        st.session_state[f"materi_{akhiran}"] = (
            "Information systems combine people, processes, data, and technology to support operations "
            "and decision-making. Transaction processing systems record routine activities, management "
            "information systems turn operational data into reports, and decision support systems use "
            "models and analysis for semi-structured decisions. System quality, information quality, "
            "security, user adoption, and business alignment are important measures of success."
        )
        st.session_state[f"diskusi_{akhiran}"] = (
            "Compare transaction processing, management information, and decision support systems."
        )
        st.session_state[f"tugas_{akhiran}"] = (
            "Explain how information quality and user adoption affect system success."
        )
    else:
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
def pemutar_audio(teks: str, identitas: str, *, bahasa_inggris_saja: bool = False) -> None:
    teks_terenkripsi = base64.b64encode(teks.encode("utf-8")).decode("ascii")
    label_audio = tx("Pembaca audio", "Audio reader")
    label_audio = tx("Pembaca audio Inggris", "English audio reader") if bahasa_inggris_saja else tx("Pembaca audio", "Audio reader")
    label_putar = tx("▶ Putar", "▶ Play")
    label_jeda = tx("Jeda / lanjut", "Pause / resume")
    label_henti = tx("Hentikan", "Stop")
    label_id = tx("Bahasa Indonesia", "Indonesian")
    label_en = tx("Bahasa Inggris", "English")
    pilihan_bahasa = "" if bahasa_inggris_saja else (
        f'<select id="bahasa-{identitas}" style="padding:7px;border-radius:8px;border:1px solid #40342b;background:#dbd5d1;color:#40342b">'
        f'<option value="id-ID">{label_id}</option><option value="en-US">{label_en}</option></select>'
    )
    bahasa_ucapan = "'en-US'" if bahasa_inggris_saja else f"document.getElementById('bahasa-{identitas}').value"
    st.iframe(
        f"""
        <div style="font-family:Arial,sans-serif;background:#dbd5d1;border:1px solid #aa9d94;
                    border-radius:14px;padding:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;color:#40342b">
          <strong style="color:#40342b;margin-right:8px">{label_audio}</strong>
          <button id="putar-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#c8beb7;color:#40342b;cursor:pointer;font-weight:700">{label_putar}</button>
          <button id="jeda-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#dbd5d1;color:#40342b;cursor:pointer;font-weight:700">{label_jeda}</button>
          <button id="henti-{identitas}" style="border:1px solid #40342b;border-radius:999px;padding:8px 14px;background:#dbd5d1;color:#40342b;cursor:pointer;font-weight:700">{label_henti}</button>
          <select id="bahasa-{identitas}" style="padding:7px;border-radius:8px;border:1px solid #40342b;background:#dbd5d1;color:#40342b">
            <option value="id-ID">{label_id}</option><option value="en-US">{label_en}</option>
          </select>
          {pilihan_bahasa}
        </div>
        <script>
          const byteTeks = Uint8Array.from(atob('{teks_terenkripsi}'), karakter => karakter.charCodeAt(0));
          const teksBelajar = new TextDecoder().decode(byteTeks);
          const suara = window.speechSynthesis;
          let ucapan = null;
          document.getElementById('putar-{identitas}').onclick = () => {{
            suara.cancel(); ucapan = new SpeechSynthesisUtterance(teksBelajar);
            ucapan.lang = document.getElementById('bahasa-{identitas}').value;
            ucapan.lang = {bahasa_ucapan};
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
        [
            tx("Ringkasan & audio", "Summary & audio"),
            tx("Kisi-kisi UAS", "Final-exam focus"),
            tx("Flashcard", "Flashcards"),
            tx("Kuis latihan", "Practice quiz"),
        ]
    )
    with tab_ringkasan:
        st.markdown(paket["summary"])
        pemutar_audio(paket["summary"], f"{mata_kuliah['id']}-{nomor_sesi}")
        st.markdown(tx("#### Poin penting", "#### Key points"))
        for poin in paket.get("key_points", []):
            st.markdown(f"- {poin}")
        if paket.get("study_plan"):
            st.markdown(tx("#### Urutan belajar yang disarankan", "#### Suggested study sequence"))
            for indeks, tindakan in enumerate(paket["study_plan"], start=1):
                st.markdown(f"{indeks}. {tindakan}")

    with tab_kisi:
        st.caption(tx(
            "Kisi-kisi ini adalah prioritas belajar berdasarkan materi yang Anda masukkan, bukan jaminan soal UAS.",
            "These are study priorities inferred from your material, not guaranteed final-exam questions.",
        ))
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
            periksa = st.form_submit_button(tx("Periksa jawaban", "Check my answers"), type="primary")
        if periksa:
            skor = 0
            for indeks, (soal, jawaban_dipilih) in enumerate(
                zip(daftar_kuis, jawaban), start=1
            ):
                jawaban_benar = soal["options"][soal["answer_index"]]
                if jawaban_dipilih == jawaban_benar:
                    skor += 1
                    st.success(tx(f"Soal {indeks}: benar", f"Question {indeks}: correct"))
                else:
                    st.error(tx(
                        f"Soal {indeks}: jawaban yang benar adalah {jawaban_benar}",
                        f"Question {indeks}: the correct answer is {jawaban_benar}",
                    ))
                if soal.get("explanation"):
                    st.caption(soal["explanation"])
            st.metric(tx("Nilai kuis", "Quiz score"), f"{skor}/{len(daftar_kuis)}")


def tampilkan_hero() -> None:
    kicker = tx("RUANG BELAJAR SISTEM INFORMASI UT", "UT INFORMATION SYSTEMS STUDY SPACE")
    judul = tx(
        "Belajar lebih terarah, satu sesi setiap kali.",
        "Study with direction, one session at a time.",
    )
    deskripsi = tx(
        "Pilih mata kuliah, simpan bahan Tuton per sesi, lalu ubah catatan Anda menjadi ringkasan, kisi-kisi UAS, flashcard, kuis, dan audio.",
        "Choose a course, save each tutorial session, then turn your notes into summaries, exam focus, flashcards, quizzes, and audio.",
    )
    st.markdown(
        f"""
        <div class="hero-ut">
          <div class="kicker">{kicker}</div>
          <h1>{judul}</h1>
          <p>{deskripsi}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tampilkan_sapaan_harian() -> None:
    sekarang = waktu_lokal()
    jam = sekarang.hour
    if jam < 11:
        sapaan = tx("Selamat pagi", "Good morning")
    elif jam < 15:
        sapaan = tx("Selamat siang", "Good afternoon")
    elif jam < 19:
        sapaan = tx("Selamat sore", "Good evening")
    else:
        sapaan = tx("Selamat malam", "Good evening")
    kutipan = KUTIPAN_HARIAN[sekarang.date().toordinal() % len(KUTIPAN_HARIAN)]
    teks_kutipan = kutipan[1] if memakai_bahasa_inggris() else kutipan[0]
    label = tx("Reality check hari ini", "Today's reality check")
    st.markdown(
        "<div class='sapaan-harian'>"
        f"<strong>{html.escape(sapaan)}, Elsa 👋</strong>"
        f"<div class='teks-bantu'>{html.escape(label)} · {sekarang.strftime('%d %b %Y')}</div>"
        f"<div class='kutipan-harian'>“{html.escape(teks_kutipan)}”</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def kotak_petunjuk(indonesia: str, english: str) -> None:
    st.markdown(
        f"<div class='petunjuk-ringkas'>{html.escape(tx(indonesia, english))}</div>",
        unsafe_allow_html=True,
    )


def tampilkan_hasil_koreksi_ielts(hasil: dict[str, Any]) -> None:
    kolom_band, kolom_ringkas = st.columns([1, 3])
    kolom_band.metric(
        tx("Estimasi band", "Estimated band"),
        f"{float(hasil.get('estimated_band', 0)):.1f}",
    )
    kolom_ringkas.info(hasil.get("overview", ""))
    st.caption(
        tx(
            "Estimasi ini adalah panduan latihan, bukan skor resmi IELTS.",
            "This estimate is a practice guide, not an official IELTS score.",
        )
    )
    kolom_tata_bahasa, kolom_kosakata = st.columns(2)
    with kolom_tata_bahasa:
        st.markdown(tx("#### Tata bahasa", "#### Grammar feedback"))
        for item in hasil.get("grammar_feedback", []):
            st.markdown(f"- {item}")
    with kolom_kosakata:
        st.markdown(tx("#### Peningkatan kosakata", "#### Vocabulary improvements"))
        for item in hasil.get("vocabulary_feedback", []):
            st.markdown(f"- {item}")
    with st.expander(tx("Lihat versi yang dikoreksi", "View corrected version"), expanded=True):
        st.write(hasil.get("corrected_text", ""))
    if hasil.get("next_steps"):
        st.markdown(tx("#### Langkah latihan berikutnya", "#### Next practice steps"))
        for indeks, item in enumerate(hasil["next_steps"], start=1):
            st.markdown(f"{indeks}. {item}")


def tampilkan_pusat_ielts(
    penyedia: str,
    nama_penyedia: dict[str, str],
    kunci_api: str,
    model: str,
) -> None:
    with st.container(border=True):
        st.markdown(tx("### ✍️ Latihan Writing & Speaking", "### ✍️ Writing & Speaking practice"))
        kotak_petunjuk(
            "📌 Pilih jenis latihan, tempel esai atau transkrip speaking, lalu tekan Koreksi AI.",
            "📌 Choose a practice type, paste an essay or speaking transcript, then select AI Correction.",
        )
        nama_jenis = {
            "Writing": tx("Writing — esai", "Writing — essay"),
            "Speaking": tx("Speaking — transkrip latihan", "Speaking — practice transcript"),
        }
        jenis = st.selectbox(
            tx("Jenis latihan", "Practice type"),
            ["Writing", "Speaking"],
            format_func=lambda pilihan: nama_jenis[pilihan],
            key=f"jenis_latihan_ielts_{'en' if memakai_bahasa_inggris() else 'id'}",
        )
        teks_latihan = st.text_area(
            tx("Teks latihan bahasa Inggris", "English practice text"),
            height=260,
            placeholder=tx(
                "Tempel esai IELTS atau transkrip jawaban speaking Anda di sini…",
                "Paste your IELTS essay or speaking-answer transcript here…",
            ),
            key="teks_latihan_ielts",
        )
        jumlah_kata = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", teks_latihan))
        st.caption(tx(f"{jumlah_kata} kata", f"{jumlah_kata} words"))
        koreksi_diklik = st.button(
            tx("✨ Koreksi AI", "✨ AI Correction"),
            type="primary",
            width="stretch",
            key="tombol_koreksi_ielts",
        )
        if koreksi_diklik:
            if jumlah_kata < 30:
                st.error(
                    tx(
                        "Masukkan sedikitnya 30 kata agar umpan balik cukup bermakna.",
                        "Enter at least 30 words so the feedback can be meaningful.",
                    )
                )
            else:
                try:
                    with st.spinner(
                        tx(
                            f"Menganalisis latihan dengan {nama_penyedia[penyedia]}…",
                            f"Reviewing your practice with {nama_penyedia[penyedia]}…",
                        )
                    ):
                        hasil = koreksi_ielts_dengan_ai(
                            penyedia, jenis, teks_latihan, kunci_api, model
                        )
                        id_latihan = simpan_latihan_ielts(
                            jenis, teks_latihan, hasil, penyedia
                        )
                    st.session_state["hasil_koreksi_ielts"] = {
                        "id": id_latihan,
                        "jenis": jenis,
                        "hasil": hasil,
                    }
                    st.success(
                        tx(
                            "Koreksi selesai dan tersimpan di riwayat SQLite.",
                            "Your correction is complete and saved to SQLite history.",
                        )
                    )
                except KesalahanPenyedia as exc:
                    st.error(str(exc))

        hasil_aktif = st.session_state.get("hasil_koreksi_ielts")
        if hasil_aktif:
            st.markdown(tx("### Hasil koreksi", "### Correction results"))
            tampilkan_hasil_koreksi_ielts(hasil_aktif["hasil"])

    with st.container(border=True):
        st.markdown(tx("### 📚 Bank Kosakata & Idiom IELTS Academic", "### 📚 Academic IELTS Vocabulary & Idioms"))
        kotak_petunjuk(
            "📌 Pelajari arti dan contoh, lalu gunakan pembaca audio untuk menirukan pelafalan bahasa Inggris.",
            "📌 Study each meaning and example, then use the audio reader to imitate English pronunciation.",
        )
        st.dataframe(
            [
                {
                    tx("Kosakata/idiom", "Vocabulary/idiom"): item["term"],
                    tx("Arti Indonesia", "Indonesian meaning"): item["meaning"],
                    tx("Contoh", "Example"): item["example"],
                    tx("Topik", "Topic"): item["tag"],
                }
                for item in BANK_KOSAKATA_IELTS
            ],
            width="stretch",
            hide_index=True,
        )
        teks_audio = ". ".join(
            f"{item['term']}. {item['example']}" for item in BANK_KOSAKATA_IELTS
        )
        pemutar_audio(teks_audio, "bank-ielts", bahasa_inggris_saja=True)

    riwayat = daftar_latihan_ielts()
    if riwayat:
        with st.expander(tx("Riwayat latihan IELTS", "IELTS practice history")):
            for item in riwayat:
                hasil = item.get("feedback", {})
                st.markdown(
                    f"**{item['practice_type']} · Band {float(hasil.get('estimated_band', 0)):.1f}**  "
                    f"\n{item['created_at'].replace('T', ' ')[:16]} · {item['provider']}"
                )
                st.caption(item["input_text"][:220] + ("…" if len(item["input_text"]) > 220 else ""))
                st.divider()


def tampilkan_kosakata_multibahasa() -> None:
    kotak_petunjuk(
        "📌 Simpan kosakata Mandarin atau Vietnam, cari di tabel, lalu latih ingatan melalui kartu Tebak Kata.",
        "📌 Save Mandarin or Vietnamese vocabulary, explore the table, then practice with Guess the Word cards.",
    )
    nama_filter = {
        "Semua": tx("Semua bahasa", "All languages"),
        "Mandarin": "Mandarin",
        "Vietnamese": tx("Bahasa Vietnam", "Vietnamese"),
    }
    filter_bahasa = st.selectbox(
        tx("Tampilkan bahasa", "Show language"),
        ["Semua", "Mandarin", "Vietnamese"],
        format_func=lambda pilihan: nama_filter[pilihan],
        key=f"filter_kosakata_bahasa_{'en' if memakai_bahasa_inggris() else 'id'}",
    )
    kosakata = daftar_kosakata(None if filter_bahasa == "Semua" else filter_bahasa)
    st.dataframe(
        [
            {
                tx("Bahasa", "Language"): item["language"],
                tx("Kosakata", "Term"): item["term"],
                tx("Pelafalan/Pinyin", "Pronunciation/Pinyin"): item["pronunciation"],
                tx("Arti Indonesia", "Indonesian translation"): item["indonesian_translation"],
                tx("Contoh kalimat", "Example sentence"): item["example_sentence"],
                tx("Tag/Topik", "Tags/Topic"): item["tags"],
            }
            for item in kosakata
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        tx(
            f"{len(kosakata)} kosakata tersimpan permanen di SQLite.",
            f"{len(kosakata)} vocabulary entries are stored in SQLite.",
        )
    )

    pesan_kosakata = st.session_state.pop("_pesan_kosakata", None)
    if pesan_kosakata:
        st.success(pesan_kosakata)

    with st.expander(tx("Tambah kosakata baru", "Add New Vocabulary"), expanded=False):
        with st.form("form_kosakata_baru", clear_on_submit=True):
            bahasa_baru = st.selectbox(
                tx("Bahasa", "Language"), ["Mandarin", "Vietnamese"]
            )
            kolom_istilah, kolom_lafal = st.columns(2)
            istilah = kolom_istilah.text_input(
                tx("Kosakata", "Vocabulary term"),
                placeholder=tx("Contoh: 梦想", "Example: 梦想"),
            )
            pelafalan = kolom_lafal.text_input(
                tx("Pelafalan atau Pinyin", "Pronunciation or Pinyin"),
                placeholder=tx("Contoh: mèngxiǎng", "Example: mèngxiǎng"),
            )
            terjemahan = st.text_input(
                tx("Terjemahan bahasa Indonesia", "Indonesian translation"),
                placeholder=tx("Contoh: impian", "Example: impian"),
            )
            contoh = st.text_area(
                tx("Contoh kalimat", "Example sentence"),
                placeholder=tx(
                    "Masukkan satu contoh kalimat dalam bahasa target…",
                    "Enter one example sentence in the target language…",
                ),
                height=95,
            )
            tag = st.text_input(
                tx("Tag atau topik", "Tags or topic"),
                placeholder=tx("Contoh: impian, motivasi", "Example: dreams, motivation"),
            )
            tambah_diklik = st.form_submit_button(
                tx("Simpan kosakata", "Save vocabulary"), type="primary"
            )
        if tambah_diklik:
            try:
                tambah_kosakata(
                    bahasa_baru, istilah, pelafalan, terjemahan, contoh, tag
                )
                st.session_state["_pesan_kosakata"] = tx(
                    "Kosakata berhasil disimpan.", "Vocabulary saved successfully."
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown(tx("### 🧠 Tebak Kata", "### 🧠 Guess the Word"))
    if not kosakata:
        st.info(tx("Tambahkan kosakata untuk mulai bermain.", "Add vocabulary to start playing."))
        return
    kunci_indeks = f"indeks_tebak_{filter_bahasa}"
    if kunci_indeks not in st.session_state:
        st.session_state[kunci_indeks] = 0
    indeks = int(st.session_state[kunci_indeks]) % len(kosakata)
    kartu = kosakata[indeks]
    st.markdown(
        "<div class='kartu-tebak'>"
        f"<span class='label-kecil'>{html.escape(kartu['language'])}</span>"
        f"<div class='prompt-tebak'>{html.escape(kartu['indonesian_translation'])}</div>"
        f"<div class='teks-bantu'>{html.escape(kartu['example_sentence'])}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    pilihan_jawaban = st.selectbox(
        tx("Pilih kosakata yang tepat", "Choose the matching word"),
        options=[item["term"] for item in kosakata],
        index=None,
        placeholder=tx("Pilih jawaban…", "Choose an answer…"),
        key=f"jawaban_tebak_{filter_bahasa}_{indeks}_{len(kosakata)}",
    )
    kolom_periksa, kolom_lanjut, ruang = st.columns([1, 1, 3])
    if kolom_periksa.button(
        tx("Periksa jawaban", "Check answer"), key=f"periksa_tebak_{filter_bahasa}"
    ):
        if pilihan_jawaban == kartu["term"]:
            st.success(tx("Benar! Kerja bagus.", "Correct! Great work."))
        else:
            st.error(
                tx(
                    f"Jawaban yang tepat: {kartu['term']} ({kartu['pronunciation']}).",
                    f"The correct answer is {kartu['term']} ({kartu['pronunciation']}).",
                )
            )
    if kolom_lanjut.button(
        tx("Kartu berikutnya", "Next card"), key=f"lanjut_tebak_{filter_bahasa}"
    ):
        st.session_state[kunci_indeks] = (indeks + 1) % len(kosakata)
        st.rerun()


def tampilkan_hub_bahasa(
    penyedia: str,
    nama_penyedia: dict[str, str],
    kunci_api: str,
    model: str,
) -> None:
    st.markdown(
        f"""
        <div class="hero-ut">
          <div class="kicker">{html.escape(tx('PUSAT BELAJAR BAHASA', 'LANGUAGE LEARNING HUB'))}</div>
          <h1>{html.escape(tx('Linguist & IELTS Hub', 'Linguist & IELTS Hub'))}</h1>
          <p>{html.escape(tx('Latih IELTS, perluas kosakata akademik, dan bangun kebiasaan belajar Mandarin serta Vietnam.', 'Practice IELTS, expand your academic vocabulary, and build Mandarin and Vietnamese learning habits.'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tab_ielts, tab_multibahasa = st.tabs(
        [
            tx("1 · Pusat Persiapan IELTS", "1 · IELTS Prep Center"),
            tx("2 · Kosakata Multibahasa", "2 · Multilingual Vocabulary (Mandarin & Vietnamese)"),
        ]
    )
    with tab_ielts:
        tampilkan_pusat_ielts(penyedia, nama_penyedia, kunci_api, model)
    with tab_multibahasa:
        tampilkan_kosakata_multibahasa()


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
    st.selectbox(
        "Bahasa / Language",
        ["Bahasa Indonesia", "English"],
        key="bahasa_antarmuka",
    )
    st.caption(tx("Pendamping belajar SI UT", "Your UT Information Systems study companion"))
    nama_halaman = {
        "Ruang belajar": tx("Ruang belajar", "Study space"),
        "Atur semester": tx("Atur semester", "Semester setup"),
        "Katalog SI": tx("Katalog SI", "IS catalog"),
        "Linguist & IELTS Hub": "Linguist & IELTS Hub",
    }
    halaman = st.radio(
        tx("Menu utama", "Main menu"),
        ["Ruang belajar", "Atur semester", "Katalog SI"],
        ["Ruang belajar", "Atur semester", "Katalog SI", "Linguist & IELTS Hub"],
        format_func=lambda pilihan: nama_halaman[pilihan],
        index=0 if ada_mata_kuliah_aktif else 1,
        key="menu_utama",
    )
    st.divider()
    st.markdown(tx("#### Mesin ringkasan", "#### Summary engine"))
    nama_penyedia = {
        "Lokal (tanpa API)": tx("Lokal (tanpa API)", "Offline (no API key)"),
        "Google Gemini": "Google Gemini",
        "Groq": "Groq",
    }
    penyedia = st.selectbox(
        tx("Pilih mesin", "Choose an engine"),
        ["Lokal (tanpa API)", "Google Gemini", "Groq"],
        format_func=lambda pilihan: nama_penyedia[pilihan],
        help=tx(
            "Mode lokal selalu tersedia. Gemini dan Groq menggunakan kuota dari masing-masing penyedia.",
            "Offline mode is always available. Gemini and Groq use each provider's own quota.",
        ),
    )
    if penyedia == "Google Gemini":
        kunci_api = st.text_input(
            tx("Kunci API Gemini", "Gemini API key"),
            value=ambil_rahasia("GEMINI_API_KEY"),
            type="password",
            placeholder=tx("Tempel kunci API Gemini", "Paste your Gemini API key"),
            help=tx("Kunci yang diketik tidak disimpan ke SQLite.", "The key you enter is not saved to SQLite."),
        )
        model = st.text_input(tx("Model Gemini", "Gemini model"), value="gemini-2.5-flash", key="model_gemini")
        st.link_button(tx("Buka halaman kunci Gemini", "Open Gemini API keys"), "https://aistudio.google.com/app/apikey")
    elif penyedia == "Groq":
        kunci_api = st.text_input(
            tx("Kunci API Groq", "Groq API key"),
            value=ambil_rahasia("GROQ_API_KEY"),
            type="password",
            placeholder=tx("Tempel kunci API Groq", "Paste your Groq API key"),
            help=tx("Kunci yang diketik tidak disimpan ke SQLite.", "The key you enter is not saved to SQLite."),
        )
        model = st.text_input(tx("Model Groq", "Groq model"), value="llama-3.3-70b-versatile", key="model_groq")
        st.link_button(tx("Buka halaman kunci Groq", "Open Groq API keys"), "https://console.groq.com/keys")
    else:
        kunci_api, model = "", "mesin-lokal"

    with st.expander(tx("Pengaturan email (SMTP)", "Email settings (SMTP)")):
        st.caption(tx(
            "Gunakan kata sandi aplikasi, bukan kata sandi utama akun email. Data ini tidak disimpan ke SQLite.",
            "Use an app password, not your main email password. These settings are not saved to SQLite.",
        ))
        smtp_host = st.text_input(
            tx("Host SMTP", "SMTP host"),
            value=ambil_rahasia("SMTP_HOST") or "smtp.gmail.com",
            placeholder="smtp.gmail.com",
            key="smtp_host",
        )
        try:
            port_awal = int(ambil_rahasia("SMTP_PORT") or 587)
        except ValueError:
            port_awal = 587
        smtp_port = int(st.number_input(
            tx("Port SMTP", "SMTP port"), min_value=1, max_value=65535,
            value=port_awal, key="smtp_port",
        ))
        smtp_user = st.text_input(
            tx("Nama pengguna SMTP", "SMTP username"),
            value=ambil_rahasia("SMTP_USER"),
            placeholder=tx("biasanya alamat email Anda", "usually your email address"),
            key="smtp_user",
        )
        smtp_password = st.text_input(
            tx("Kata sandi aplikasi", "App password"),
            value=ambil_rahasia("SMTP_PASSWORD"),
            type="password",
            placeholder=tx("tempel kata sandi aplikasi", "paste your app password"),
            key="smtp_password",
        )
        smtp_from = st.text_input(
            tx("Alamat pengirim", "Sender address"),
            value=ambil_rahasia("SMTP_FROM") or smtp_user,
            placeholder=tx("contoh: elsa@gmail.com", "example: elsa@gmail.com"),
            key="smtp_from",
        )
    st.divider()
    st.caption(tx(f"Penyimpanan lokal: `{LOKASI_DB.name}`", f"Local storage: `{LOKASI_DB.name}`"))

tampilkan_sapaan_harian()


if halaman == "Ruang belajar":
    tampilkan_hero()

    with st.container(border=True):
        judul_langkah(
            1,
            tx("Pilih semester dan mata kuliah", "Choose a semester and course"),
            tx(
                "Buka mata kuliah aktif yang sedang Anda pelajari.",
                "Open the active course you are studying now.",
            ),
        )
        kotak_petunjuk(
            "📌 Langkah 1: Pilih semester dan mata kuliah yang sedang Anda pelajari.",
            "📌 Step 1: Choose the semester and course you are currently studying.",
        )
        kolom_semester, kolom_mata_kuliah = st.columns(2)
        semester_id = kolom_semester.selectbox(
            tx("Semester", "Semester"),
            options=list(semester_per_id),
            format_func=lambda identitas: semester_per_id[identitas]["name"],
            key="semester_belajar",
        )
        mata_kuliah_aktif = daftar_mata_kuliah(semester_id)
        if not mata_kuliah_aktif:
            kolom_mata_kuliah.selectbox(
                tx("Mata kuliah", "Course"),
                options=[tx("Belum ada mata kuliah aktif", "No active course yet")],
                disabled=True,
            )
            st.warning(
                tx(
                    "Semester ini belum memiliki mata kuliah aktif. Buka menu Atur semester untuk memilih mata kuliah.",
                    "This semester has no active courses. Open Semester setup to choose your courses.",
                )
            )
            st.stop()
        mata_kuliah_per_id = {int(item["id"]): item for item in mata_kuliah_aktif}
        mata_kuliah_id = kolom_mata_kuliah.selectbox(
            tx("Mata kuliah", "Course"),
            options=list(mata_kuliah_per_id),
            format_func=lambda identitas: (
                f"{mata_kuliah_per_id[identitas]['code']} — "
                f"{nama_tampilan(mata_kuliah_per_id[identitas]['code'], mata_kuliah_per_id[identitas]['name'])}"
            ),
            key=f"mata_kuliah_belajar_{semester_id}",
        )
        mata_kuliah = mata_kuliah_per_id[mata_kuliah_id]
        mata_kuliah_bahasa = {
            **mata_kuliah,
            "name": nama_tampilan(mata_kuliah["code"], mata_kuliah["name"]),
        }
        st.markdown(
            f"<span class='label-kecil'>{html.escape(mata_kuliah['code'])}</span>"
            f"<span class='label-kecil'>{mata_kuliah['credits']} {tx('SKS', 'credits')}</span>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        judul_langkah(
            2,
            tx("Pilih sesi dan masukkan bahan Tuton", "Choose a session and add Tuton materials"),
            tx(
                "Setiap mata kuliah menyimpan Sesi 1 sampai Sesi 8 secara terpisah.",
                "Each course stores Sessions 1 through 8 separately.",
            ),
        )
        kotak_petunjuk(
            "📌 Langkah 2: Pilih Sesi 1–8, lalu tempel bahan Tuton, diskusi, atau tugas.",
            "📌 Step 2: Choose Sessions 1–8, then paste your Tuton materials, discussion, or assignment.",
        )
        nomor_sesi = st.radio(
            tx("Sesi tutorial", "Tutorial session"),
            options=list(range(1, 9)),
            format_func=lambda nomor: tx(f"Sesi {nomor}", f"Session {nomor}"),
            horizontal=True,
            key=f"sesi_{mata_kuliah_id}",
        )
        data_sesi = ambil_sesi(mata_kuliah_id, nomor_sesi)
        akhiran = f"{mata_kuliah_id}_{nomor_sesi}"
        materi = st.text_area(
            tx("Materi atau ringkasan Tuton", "Tuton material or notes"),
            value=data_sesi["material"],
            height=240,
            placeholder=tx(
                "Tempel ringkasan modul, penjelasan Tuton, atau poin belajar di sini…",
                "Paste module notes, Tuton explanations, or key study points here…",
            ),
            key=f"materi_{akhiran}",
        )
        kolom_diskusi, kolom_tugas = st.columns(2)
        with kolom_diskusi:
            diskusi = st.text_area(
                tx("Pertanyaan diskusi", "Discussion questions"),
                value=data_sesi["discussion"],
                height=135,
                placeholder=tx(
                    "Tempel pertanyaan atau jawaban diskusi…",
                    "Paste discussion questions or answers…",
                ),
                key=f"diskusi_{akhiran}",
            )
        with kolom_tugas:
            tugas = st.text_area(
                tx("Tugas", "Assignment"),
                value=data_sesi["assignments"],
                height=135,
                placeholder=tx(
                    "Tempel instruksi atau jawaban tugas…",
                    "Paste assignment instructions or your answer…",
                ),
                key=f"tugas_{akhiran}",
            )
        tombol_simpan, tombol_contoh, ruang_kosong = st.columns([1, 1, 3])
        simpan_diklik = tombol_simpan.button(
            tx("Simpan bahan", "Save materials"), width="stretch"
        )
        tombol_contoh.button(
            tx("Isi contoh", "Load example"),
            width="stretch",
            on_click=isi_contoh,
            args=(mata_kuliah_id, nomor_sesi),
        )
        if simpan_diklik:
            simpan_catatan_sesi(mata_kuliah_id, nomor_sesi, materi, diskusi, tugas)
            st.success(
                tx(
                    f"Bahan Sesi {nomor_sesi} berhasil disimpan.",
                    f"Materials for Session {nomor_sesi} were saved.",
                )
            )

    with st.container(border=True):
        judul_langkah(
            3,
            tx("Buat ringkasan dan prediksi UAS", "Generate a summary and final-exam forecast"),
            tx(
                "Hasil akan tersimpan pada mata kuliah dan sesi yang dipilih.",
                "Your results will be saved under the selected course and session.",
            ),
        )
        kotak_petunjuk(
            "📌 Langkah 3: Buat paket belajar untuk melihat ringkasan, kisi-kisi, kuis, dan audio.",
            "📌 Step 3: Generate a study pack to see the summary, exam guide, quiz, and audio.",
        )
        buat_diklik = st.button(
            tx(
                "Buat Ringkasan & Prediksi UAS",
                "Generate Summary & Final Exam Predictions",
            ),
            type="primary",
            width="stretch",
        )
        paket = baca_paket(data_sesi)
        if buat_diklik:
            panjang_teks = len(materi.strip()) + len(diskusi.strip()) + len(tugas.strip())
            if panjang_teks < 80:
                st.error(
                    tx(
                        "Masukkan sedikitnya 80 karakter bahan Tuton agar hasilnya bermakna.",
                        "Enter at least 80 characters of Tuton material for a meaningful result.",
                    )
                )
            else:
                try:
                    with st.spinner(
                        tx(
                            f"Menyusun paket belajar dengan {nama_penyedia[penyedia]}…",
                            f"Building your study pack with {nama_penyedia[penyedia]}…",
                        )
                    ):
                        paket = buat_paket_belajar(
                            penyedia,
                            mata_kuliah_bahasa,
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
                        tx(
                            f"Paket belajar {mata_kuliah['code']} · Sesi {nomor_sesi} berhasil dibuat dan disimpan.",
                            f"Study pack for {mata_kuliah['code']} · Session {nomor_sesi} was generated and saved.",
                        )
                    )
                except KesalahanPenyedia as exc:
                    st.error(str(exc))

    if paket:
        st.markdown(tx("## Hasil belajar", "## Study results"))
        st.caption(
            tx(
                f"{mata_kuliah['code']} · Sesi {nomor_sesi} · Dibuat dengan "
                f"{nama_penyedia.get(data_sesi.get('provider') or penyedia, data_sesi.get('provider') or penyedia)}",
                f"{mata_kuliah['code']} · Session {nomor_sesi} · Generated with "
                f"{nama_penyedia.get(data_sesi.get('provider') or penyedia, data_sesi.get('provider') or penyedia)}",
            )
        )
        tampilkan_hasil(
            paket,
            mata_kuliah_bahasa,
            nomor_sesi,
            data_sesi.get("updated_at", ""),
        )

        with st.container(border=True):
            st.markdown(
                tx(
                    "### 📧 Kirim ringkasan belajar",
                    "### 📧 Email today's learning summary",
                )
            )
            kotak_petunjuk(
                "📌 Masukkan email tujuan dan jadwal belajar. Pastikan pengaturan SMTP di bilah samping sudah lengkap.",
                "📌 Enter the recipient email and your study schedule. Make sure the SMTP settings in the sidebar are complete.",
            )
            with st.form(f"form_email_{mata_kuliah_id}_{nomor_sesi}"):
                alamat_email = st.text_input(
                    tx("Email tujuan", "Email address"),
                    value="elsahaditiasitorus@gmail.com",
                    placeholder="elsahaditiasitorus@gmail.com",
                )
                jadwal_email = st.text_area(
                    tx("Jadwal atau pengingat belajar", "Study schedule or reminder"),
                    placeholder=tx(
                        "Contoh: Ulangi Sesi 3 hari Sabtu pukul 19.00 selama 45 menit.",
                        "Example: Review Session 3 on Saturday at 7:00 PM for 45 minutes.",
                    ),
                    height=110,
                )
                kirim_diklik = st.form_submit_button(
                    tx(
                        "📧 Kirim Ringkasan & Jadwal Belajar Hari Ini ke Email Saya",
                        "📧 Send Today's Learning Summary & Schedule to My Email",
                    ),
                    type="primary",
                )
            if kirim_diklik:
                try:
                    with st.spinner(tx("Mengirim email…", "Sending email…")):
                        kirim_email_belajar(
                            alamat_email,
                            jadwal_email,
                            mata_kuliah_bahasa,
                            nomor_sesi,
                            paket,
                            smtp_host,
                            smtp_port,
                            smtp_user,
                            smtp_password,
                            smtp_from,
                        )
                except (ValueError, OSError, smtplib.SMTPException) as exc:
                    st.error(
                        tx(
                            f"Email belum terkirim: {exc}",
                            f"The email could not be sent: {exc}",
                        )
                    )
                else:
                    st.success(
                        tx(
                            f"Ringkasan dan jadwal berhasil dikirim ke {alamat_email}.",
                            f"The summary and schedule were sent to {alamat_email}.",
                        )
                    )
    else:
        st.info(
            tx(
                "Hasil akan muncul di sini setelah Anda membuat paket belajar.",
                "Your results will appear here after you generate a study pack.",
            )
        )

elif halaman == "Atur semester":
    st.markdown(
        f"""
        <div class="hero-ut">
          <div class="kicker">{html.escape(tx('PENGATURAN NON-SIPAS', 'NON-SIPAS SETUP'))}</div>
          <h1>{html.escape(tx('Susun semester sesuai rencana Anda.', 'Build a semester that fits your plan.'))}</h1>
          <p>{html.escape(tx('Pilih mata kuliah aktif dari katalog SI atau tambahkan mata kuliah khusus.', 'Choose active courses from the IS catalog or add a custom course.'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kotak_petunjuk(
        "📌 Langkah 1: Masukkan nama semester baru di bawah jika belum tersedia.",
        "📌 Step 1: Enter the name of a new semester below if it is not available yet.",
    )
    semester_id = st.selectbox(
        tx("Semester yang akan diatur", "Semester to configure"),
        options=list(semester_per_id),
        format_func=lambda identitas: semester_per_id[identitas]["name"],
        key="semester_pengaturan",
    )
    with st.expander(tx("Buat semester baru", "Create a new semester")):
        with st.form("form_semester_baru", clear_on_submit=True):
            nama_semester_baru = st.text_input(
                tx("Nama semester", "Semester name"),
                placeholder=tx("Contoh: Semester 5", "Example: Semester 5"),
            )
            buat_semester_diklik = st.form_submit_button(
                tx("Buat semester", "Create semester"), type="primary"
            )
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
    metrik_satu.metric(tx("Mata kuliah aktif", "Active courses"), len(aktif))
    metrik_dua.metric(tx("Beban semester", "Semester load"), tx(f"{jumlah_sks} SKS", f"{jumlah_sks} credits"))
    metrik_tiga.metric(tx("Katalog SI", "IS catalog"), tx("51 mata kuliah", "51 courses"))

    with st.container(border=True):
        kotak_petunjuk(
            "📌 Langkah 2: Centang mata kuliah yang sedang Anda ambil.",
            "📌 Step 2: Check the courses you are currently taking.",
        )
        st.markdown(tx("### Pilih mata kuliah aktif", "### Choose active courses"))
        st.caption(
            tx(
                "Kelompok agama dan mata kuliah pilihan ditampilkan sebagai pilihan kode yang terpisah.",
                "Religion and elective groups are shown as separate course-code options.",
            )
        )
        with st.form(f"form_katalog_{semester_id}"):
            pilihan_kode = st.multiselect(
                tx("Mata kuliah semester ini", "Courses for this semester"),
                options=[item["kode"] for item in DAFTAR_PENAWARAN],
                default=kode_aktif,
                format_func=lambda kode: (
                    f"{kode} — {nama_tampilan(kode, PENAWARAN_PER_KODE[kode]['nama'])} · "
                    f"{PENAWARAN_PER_KODE[kode]['sks']} {tx('SKS', 'credits')}"
                ),
                placeholder=tx(
                    "Pilih satu atau beberapa mata kuliah",
                    "Choose one or more courses",
                ),
                key=f"pilihan_katalog_{semester_id}",
            )
            simpan_pilihan = st.form_submit_button(
                tx("Simpan mata kuliah aktif", "Save active courses"), type="primary"
            )
        if simpan_pilihan:
            sinkronkan_mata_kuliah(semester_id, pilihan_kode)
            st.success(
                tx(
                    "Daftar mata kuliah aktif berhasil disimpan.",
                    "The active course list was saved.",
                )
            )

    with st.expander(tx("Tambahkan mata kuliah khusus", "Add a custom course")):
        with st.form(f"form_mata_kuliah_khusus_{semester_id}", clear_on_submit=True):
            kolom_kode, kolom_nama, kolom_sks = st.columns([1, 2, 1])
            kode_khusus = kolom_kode.text_input(tx("Kode", "Code"), placeholder="CUSTOM01")
            nama_khusus = kolom_nama.text_input(
                tx("Nama mata kuliah", "Course name"),
                placeholder=tx("Contoh: Seminar khusus", "Example: Special seminar"),
            )
            sks_khusus = kolom_sks.number_input(
                tx("SKS", "Credits"), min_value=1, max_value=24, value=3
            )
            tambah_diklik = st.form_submit_button(
                tx("Tambahkan mata kuliah", "Add course")
            )
        if tambah_diklik:
            try:
                tambah_mata_kuliah_khusus(
                    semester_id, kode_khusus, nama_khusus, int(sks_khusus)
                )
                st.success(tx("Mata kuliah khusus berhasil ditambahkan.", "The custom course was added."))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    kotak_petunjuk(
        "📌 Langkah 3: Simpan pilihan, lalu kembali ke Ruang belajar.",
        "📌 Step 3: Save your choices, then return to Study space.",
    )
    st.markdown(tx("### Mata kuliah aktif", "### Active courses"))
    aktif = daftar_mata_kuliah(semester_id)
    if not aktif:
        st.info(tx("Belum ada mata kuliah aktif pada semester ini.", "There are no active courses in this semester yet."))
    else:
        st.dataframe(
            [
                {
                    tx("Kode", "Code"): item["code"],
                    tx("Mata kuliah", "Course"): nama_tampilan(item["code"], item["name"]),
                    tx("SKS", "Credits"): item["credits"],
                    tx("Sumber", "Source"): tx("Tambahan", "Custom") if item["is_custom"] else tx("Katalog UT", "UT catalog"),
                }
                for item in aktif
            ],
            width="stretch",
            hide_index=True,
        )
        tambahan = [item for item in aktif if item["is_custom"]]
        if tambahan:
            with st.expander(tx("Kelola mata kuliah khusus", "Manage custom courses")):
                for item in tambahan:
                    kolom_info, kolom_hapus = st.columns([5, 1])
                    kolom_info.write(
                        f"**{item['code']}** — {item['name']} "
                        f"({item['credits']} {tx('SKS', 'credits')})"
                    )
                    if kolom_hapus.button(tx("Hapus", "Delete"), key=f"hapus_{item['id']}"):
                        hapus_mata_kuliah_khusus(int(item["id"]))
                        st.rerun()

    st.download_button(
        tx("Unduh cadangan semester", "Download semester backup"),
        data=ekspor_semester(semester_id),
        file_name=f"{semester_per_id[semester_id]['name'].lower().replace(' ', '-')}-cadangan.json",
        mime="application/json",
    )

else:
elif halaman == "Katalog SI":
    st.markdown(
        f"""
        <div class="hero-ut">
          <div class="kicker">{html.escape(tx('KATALOG PROGRAM STUDI', 'DEGREE CATALOG'))}</div>
          <h1>{html.escape(tx('51 mata kuliah Sistem Informasi UT.', '51 UT Information Systems courses.'))}</h1>
          <p>{html.escape(tx('Kelompok agama dan mata kuliah pilihan tetap dihitung sebagai satu slot kurikulum.', 'Religion and elective groups each count as one curriculum slot.'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    kotak_petunjuk(
        "📌 Gunakan pencarian untuk menemukan kode atau nama mata kuliah.",
        "📌 Use the search box to find a course code or name.",
    )
    pencarian = st.text_input(
        tx("Cari kode atau nama mata kuliah", "Search by course code or name"),
        placeholder=tx("Contoh: STSI44 atau keamanan", "Example: STSI44 or security"),
    )
    kata_cari = pencarian.strip().lower()
    hasil_katalog = [
        item
        for item in KATALOG_MK_UT
        if not kata_cari
        or kata_cari in item["kode"].lower()
        or kata_cari in item["nama"].lower()
        or kata_cari in nama_slot_katalog(item).lower()
        or any(
            kata_cari in opsi["kode"].lower()
            or kata_cari in opsi["nama"].lower()
            or kata_cari in nama_tampilan(opsi["kode"], opsi["nama"]).lower()
            for opsi in item.get("pilihan", [])
        )
    ]
    metrik_satu, metrik_dua, metrik_tiga = st.columns(3)
    metrik_satu.metric(tx("Jumlah mata kuliah", "Course count"), len(KATALOG_MK_UT))
    metrik_dua.metric(tx("Hasil ditampilkan", "Results shown"), len(hasil_katalog))
    metrik_tiga.metric(tx("Total kurikulum", "Curriculum total"), tx("145 SKS", "145 credits"))
    st.dataframe(
        [
            {
                tx("No.", "No."): item["slot"],
                tx("Kode", "Code"): item["kode"],
                tx("Mata kuliah", "Course"): nama_slot_katalog(item),
                tx("SKS", "Credits"): item["sks"],
                tx("Jenis", "Type"): tx("Pilihan", "Elective") if item.get("pilihan") else tx("Wajib", "Required"),
            }
            for item in hasil_katalog
        ],
        width="stretch",
        hide_index=True,
    )
    kelompok_pilihan = [item for item in hasil_katalog if item.get("pilihan")]
    if kelompok_pilihan:
        with st.expander(tx("Lihat rincian kelompok pilihan", "View elective group details")):
            for item in kelompok_pilihan:
                st.markdown(
                    f"**{tx('Slot', 'Slot')} {item['slot']} · {nama_slot_katalog(item)}**"
                )
                for opsi in item["pilihan"]:
                    st.markdown(
                        f"- `{opsi['kode']}` — {nama_tampilan(opsi['kode'], opsi['nama'])} "
                        f"({item['sks']} {tx('SKS', 'credits')})"
                    )

else:
    tampilkan_hub_bahasa(penyedia, nama_penyedia, kunci_api, model)
