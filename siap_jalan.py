"""
Aplikasi SIAP JALAN - Sistem Informasi Administrasi Perjalanan Dinas (V10 - Multi Tujuan & Kop Setda)
Dibuat dengan Python (Flask) + SQLite + Tailwind CSS (Frontend)
"""

import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import DictLoader

app = Flask(__name__)
app.config['SECRET_KEY'] = 'siap-jalan-rahasia-123-v10'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///siapjalan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# STREAMING_CHUNK:Database Models
class User(db.Model):
    """Tabel untuk Admin Login"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class MasterPegawai(db.Model):
    """Tabel Master Data Pegawai"""
    __tablename__ = 'master_pegawai'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(50), nullable=False)
    jenis_nip = db.Column(db.String(20), default='NIP.') # Tambahan NIP / NIPPPK / Non ASN
    pangkat = db.Column(db.String(100), nullable=False)
    jabatan = db.Column(db.String(100), nullable=False)

class MasterTtdSpt(db.Model):
    """Tabel Master Penandatangan SPT"""
    __tablename__ = 'master_ttd_spt'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(50), nullable=False)
    pangkat = db.Column(db.String(100), nullable=False)
    jabatan = db.Column(db.String(100), nullable=False)

class MasterTtdSpd(db.Model):
    """Tabel Master Penandatangan SPD"""
    __tablename__ = 'master_ttd_spd'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(50), nullable=False)
    pangkat = db.Column(db.String(100), nullable=False)
    jabatan = db.Column(db.String(100), nullable=False)

class MasterTtdKwitansi(db.Model):
    """Tabel Master Penandatangan Kwitansi (PPTK / Bendahara)"""
    __tablename__ = 'master_ttd_kwitansi'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(50), nullable=False)
    pangkat = db.Column(db.String(100), nullable=True)
    jabatan = db.Column(db.String(100), nullable=False)

class SPT(db.Model):
    """Tabel Induk untuk Surat Perintah Tugas (Data Perjalanan)"""
    __tablename__ = 'spt'
    id = db.Column(db.Integer, primary_key=True)
    no_spt = db.Column(db.String(50), nullable=False)
    jenis_spt = db.Column(db.String(20), default='biasa') # biasa, kadis_bupati, kadis_sekda
    dasar_surat = db.Column(db.Text, nullable=True) # JSON String untuk Multi Dasar Surat
    maksud_tugas = db.Column(db.Text, nullable=False) # Diubah ke Text untuk Multi Maksud Tugas JSON
    tempat_berangkat = db.Column(db.String(100), default='Kotabaru')
    tempat_tujuan = db.Column(db.Text, nullable=False) # JSON Struktur Baru: [{"kota": "A", "tgl_tiba": "...", "tgl_berangkat": "..."}, ...]
    tanggal_spt = db.Column(db.Date, nullable=True) # Tanggal Pembuatan / Penetapan Dokumen
    tanggal_berangkat = db.Column(db.Date, nullable=False)
    tanggal_kembali = db.Column(db.Date, nullable=False)
    kendaraan = db.Column(db.String(50), nullable=False)
    
    pejabat_pemberi_perintah = db.Column(db.String(100), nullable=False)
    tingkat_biaya = db.Column(db.String(10), nullable=False)
    instansi_pembebanan = db.Column(db.String(255), nullable=False)
    akun_pembebanan = db.Column(db.String(100), nullable=False)
    
    # Penandatangan SPT
    ttd_spt_nama = db.Column(db.String(100), nullable=False)
    ttd_spt_jabatan = db.Column(db.String(100), nullable=False)
    ttd_spt_pangkat = db.Column(db.String(100), nullable=False)
    ttd_spt_nip = db.Column(db.String(50), nullable=False)

    # Penandatangan SPD
    ttd_spd_nama = db.Column(db.String(100), nullable=False)
    ttd_spd_jabatan = db.Column(db.String(100), nullable=False)
    ttd_spd_pangkat = db.Column(db.String(100), nullable=False)
    ttd_spd_nip = db.Column(db.String(50), nullable=False)
    
    # Custom Form Laporan
    laporan_kepada = db.Column(db.String(100), nullable=True)
    laporan_dari = db.Column(db.String(100), nullable=True)
    laporan_tanggal = db.Column(db.Date, nullable=True)
    laporan_hal = db.Column(db.String(255), nullable=True)
    laporan_nama_kegiatan = db.Column(db.Text, nullable=True)
    laporan_waktu_tanggal = db.Column(db.String(100), nullable=True)
    laporan_waktu_tujuan = db.Column(db.String(255), nullable=True)
    hasil_laporan = db.Column(db.Text, nullable=True) # Disimpan sebagai JSON list untuk >1 kegiatan
    laporan_kesimpulan = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now)

    pegawais = db.relationship('PegawaiTugas', backref='spt', cascade="all, delete-orphan")

    @property
    def lama_hari(self):
        if self.tanggal_kembali and self.tanggal_berangkat:
            delta = self.tanggal_kembali - self.tanggal_berangkat
            days = delta.days + 1
            return days if days > 0 else 0
        return 0

class PegawaiTugas(db.Model):
    """Tabel Anak untuk Data Pegawai dan Keuangan Individu"""
    __tablename__ = 'pegawai_tugas'
    id = db.Column(db.Integer, primary_key=True)
    spt_id = db.Column(db.Integer, db.ForeignKey('spt.id'), nullable=False)
    no_spd = db.Column(db.String(50), nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(50), nullable=False)
    jenis_nip = db.Column(db.String(20), default='NIP.') # Status (NIP/NIPPPK)
    jabatan = db.Column(db.String(100), nullable=False)
    pangkat = db.Column(db.String(100), nullable=False)
    
    # Penandatangan Kwitansi Individu (PA, PPTK, Bendahara)
    pa_nama = db.Column(db.String(100), nullable=True)
    pa_nip = db.Column(db.String(50), nullable=True)
    pa_jabatan = db.Column(db.String(100), nullable=True)

    pptk_nama = db.Column(db.String(100), nullable=True)
    pptk_nip = db.Column(db.String(50), nullable=True)
    pptk_jabatan = db.Column(db.String(100), nullable=True)
    
    bendahara_nama = db.Column(db.String(100), nullable=True)
    bendahara_nip = db.Column(db.String(50), nullable=True)
    bendahara_jabatan = db.Column(db.String(100), nullable=True)

    # Metadata Kuitansi Dinamis
    kwitansi_jenis = db.Column(db.String(20), default='GU')
    kwitansi_kode_sub = db.Column(db.String(100), default='1.04.01.2.06.0009')
    kwitansi_kode_rek = db.Column(db.String(100), default='5.1.02.04.001.0001')
    kwitansi_tahun = db.Column(db.String(10), nullable=True)
    kwitansi_tanggal = db.Column(db.Date, nullable=True) # Tambahan Tanggal Kwitansi
    
    pengeluaran_riil_tanggal = db.Column(db.Date, nullable=True) # Tanggal Pengeluaran Riil

    rincian_biayas = db.relationship('RincianBiaya', backref='pegawai', cascade="all, delete-orphan")
    pengeluaran_riils = db.relationship('PengeluaranRiil', backref='pegawai', cascade="all, delete-orphan")

    @property
    def grand_total(self):
        if self.rincian_biayas:
            return sum(r.jumlah for r in self.rincian_biayas)
        return 0

    @property
    def total_pengeluaran_riil(self):
        if self.pengeluaran_riils:
            return sum(r.jumlah for r in self.pengeluaran_riils)
        return 0

class RincianBiaya(db.Model):
    """Tabel Rincian Biaya per Pegawai"""
    __tablename__ = 'rincian_biaya'
    id = db.Column(db.Integer, primary_key=True)
    pegawai_id = db.Column(db.Integer, db.ForeignKey('pegawai_tugas.id'), nullable=False)
    perincian = db.Column(db.String(255), nullable=False)
    jumlah = db.Column(db.Integer, default=0)
    keterangan = db.Column(db.String(100), nullable=True)

class PengeluaranRiil(db.Model):
    """Tabel Pengeluaran Riil (Tanpa Bukti) per Pegawai"""
    __tablename__ = 'pengeluaran_riil'
    id = db.Column(db.Integer, primary_key=True)
    pegawai_id = db.Column(db.Integer, db.ForeignKey('pegawai_tugas.id'), nullable=False)
    uraian = db.Column(db.String(255), nullable=False)
    jumlah = db.Column(db.Integer, default=0)

# STREAMING_CHUNK:Filters and Base Setup
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.template_filter('from_json')
def from_json_filter(value):
    if not value: return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return data
        return [str(data)]
    except:
        return [value]

@app.template_filter('rupiah')
def rupiah_format(value):
    try:
        return f"Rp {int(value):,}".replace(',', '.')
    except (ValueError, TypeError):
        return "Rp 0"

@app.template_filter('tanggal')
def tanggal_format(value):
    if not value: return '-'
    
    # Handle string input for parsing back to date object
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return value # return raw string if format not matched
            
    bulan = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    return f"{value.day} {bulan[value.month]} {value.year}"

@app.template_filter('tanggal_range')
def tanggal_range_format(tgl1, tgl2):
    if not tgl1 or not tgl2: return '-'
    bulan = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    if tgl1.month == tgl2.month and tgl1.year == tgl2.year:
        if tgl1.day == tgl2.day:
            return f"{tgl1.day} {bulan[tgl1.month]} {tgl1.year}"
        return f"{tgl1.day} s/d {tgl2.day} {bulan[tgl1.month]} {tgl1.year}"
    elif tgl1.year == tgl2.year:
        return f"{tgl1.day} {bulan[tgl1.month]} s/d {tgl2.day} {bulan[tgl2.month]} {tgl1.year}"
    else:
        return f"{tgl1.day} {bulan[tgl1.month]} {tgl1.year} s/d {tgl2.day} {bulan[tgl2.month]} {tgl2.year}"

@app.template_filter('terbilang')
def terbilang(n):
    try:
        n = int(n)
    except:
        return ""
        
    if n < 0:
        return "Minus " + terbilang(abs(n))
        
    angka = ["", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]
    if n == 0: return "Nol"
    if n < 12: return angka[n]
    elif n < 20: return terbilang(n - 10) + " Belas"
    elif n < 100: return terbilang(n // 10) + " Puluh" + (" " + terbilang(n % 10) if n % 10 != 0 else "")
    elif n < 200: return "Seratus" + (" " + terbilang(n - 100) if n - 100 != 0 else "")
    elif n < 1000: return terbilang(n // 100) + " Ratus" + (" " + terbilang(n % 100) if n % 100 != 0 else "")
    elif n < 2000: return "Seribu" + (" " + terbilang(n - 1000) if n - 1000 != 0 else "")
    elif n < 1000000: return terbilang(n // 1000) + " Ribu" + (" " + terbilang(n % 1000) if n % 1000 != 0 else "")
    elif n < 1000000000: return terbilang(n // 1000000) + " Juta" + (" " + terbilang(n % 1000000) if n % 1000000 != 0 else "")
    else: return str(n)


TEMPLATE_DICT = {}

# STREAMING_CHUNK:Base Layout
TEMPLATE_DICT['base.html'] = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SIAP JALAN - {{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-100 min-h-screen font-sans text-slate-800">
    <nav class="bg-blue-800 text-white shadow-lg">
        <div class="max-w-1xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <div class="flex items-center gap-3">
                    <i class="fas fa-plane-departure text-2xl"></i>
                    <span class="font-bold text-xl tracking-wider">SIAP JALAN - Sistem Informasi Administrasi Perjalanan Dinas</span>
                </div>
                <div class="flex gap-2 items-center">
                    {% if session.get('logged_in') %}
                        <a href="{{ url_for('index') }}" class="px-4 py-2 rounded-md text-sm font-medium bg-blue-700 hover:bg-blue-600 transition shadow-sm"><i class="fas fa-home mr-1"></i> Dashboard</a>
                        
                        <div class="relative group z-50">
                            <button class="px-4 py-2 rounded-md text-sm font-medium bg-green-600 hover:bg-green-500 transition shadow-sm inline-flex items-center">
                                <i class="fas fa-plus mr-1"></i> Buat SPT <i class="fas fa-chevron-down ml-1 text-xs"></i>
                            </button>
                            <div class="absolute left-0 mt-0 w-48 bg-white rounded-md shadow-lg py-1 hidden group-hover:block border border-gray-100">
                                <a href="{{ url_for('create', type='kadis') }}" class="block px-4 py-2 text-sm text-purple-700 font-bold hover:bg-green-50 border-b border-gray-100"><i class="fas fa-user-tie mr-1"></i> SPT Khusus Kadis</a>
                                <a href="{{ url_for('create') }}" class="block px-4 py-2 text-sm text-green-700 font-bold hover:bg-green-50"><i class="fas fa-users mr-1"></i> SPT Pegawai Biasa</a>
                            </div>
                        </div>
                        
                        <div class="relative group z-50">
                            <button class="px-4 py-2 rounded-md text-sm font-medium bg-blue-700 hover:bg-blue-600 transition shadow-sm inline-flex items-center">
                                <i class="fas fa-database mr-1"></i> Master Data <i class="fas fa-chevron-down ml-1 text-xs"></i>
                            </button>
                            <div class="absolute left-0 mt-0 w-48 bg-white rounded-md shadow-lg py-1 hidden group-hover:block border border-gray-100">
                                <a href="{{ url_for('master_pegawai') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 border-b border-gray-100"><i class="fas fa-users mr-1"></i> Data Pegawai</a>
                                <a href="{{ url_for('master_ttd_spt') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 border-b border-gray-100"><i class="fas fa-signature mr-1"></i> TTD SPT</a>
                                <a href="{{ url_for('master_ttd_spd') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 border-b border-gray-100"><i class="fas fa-file-signature mr-1"></i> TTD SPD</a>
                                <a href="{{ url_for('master_ttd_kwitansi') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-blue-50"><i class="fas fa-pen-nib mr-1"></i> TTD Kwitansi</a>
                            </div>
                        </div>

                        <a href="{{ url_for('change_password') }}" class="ml-2 px-3 py-2 rounded-md text-sm font-medium bg-slate-700 hover:bg-slate-600 transition shadow-sm" title="Ubah Password"><i class="fas fa-key"></i></a>
                        <a href="{{ url_for('logout') }}" class="ml-1 px-3 py-2 rounded-md text-sm font-medium text-red-200 hover:text-white hover:bg-red-700 transition" title="Keluar"><i class="fas fa-sign-out-alt"></i></a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{% if category == 'error' %}bg-red-100 border-red-500 text-red-700{% else %}bg-green-100 border-green-500 text-green-700{% endif %} border-l-4 p-4 rounded shadow-sm mb-6 flex items-center">
                <i class="{% if category == 'error' %}fas fa-exclamation-circle{% else %}fas fa-check-circle{% endif %} mr-2 text-lg"></i> {{ message }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </main>
</body>
</html>
"""

# STREAMING_CHUNK:Auth Login
TEMPLATE_DICT['login.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-md mx-auto mt-10 bg-white rounded-xl shadow-2xl overflow-hidden border border-gray-100">
    <div class="bg-blue-50 p-6 text-center border-b border-gray-200">
        <div class="flex justify-center items-center gap-6 mb-4">
            <img src="/logo.png" alt="Logo Daerah" class="h-20 w-auto object-contain">
            <img src="/app_logo.png" alt="Logo Aplikasi" class="h-20 w-auto object-contain">
        </div>
        <h2 class="text-xl font-bold text-blue-900 uppercase tracking-wide">SIAP JALAN</h2>
        <p class="text-sm font-semibold text-gray-700 mt-1">Sistem Informasi Administrasi Perjalanan Dinas</p>
        <p class="text-xs text-gray-500 mt-1">Dinas Perumahan Rakyat, Permukiman dan Pertanahan</p>
    </div>
    
    <div class="p-8">
        <h3 class="text-center text-gray-600 font-bold mb-6">Silakan Masuk</h3>
        <form method="POST" action="">
            <div class="mb-5">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Username</label>
                <div class="relative">
                    <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400"><i class="fas fa-user"></i></span>
                    <input type="text" name="username" required class="w-full border border-gray-300 rounded-md py-2.5 pl-10 pr-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition" placeholder="Masukkan username">
                </div>
            </div>
            <div class="mb-6">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Password</label>
                <div class="relative">
                    <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400"><i class="fas fa-lock"></i></span>
                    <input type="password" name="password" required class="w-full border border-gray-300 rounded-md py-2.5 pl-10 pr-3 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition" placeholder="Masukkan password">
                </div>
            </div>
            <button type="submit" class="w-full bg-blue-700 text-white font-bold py-3 px-4 rounded-md hover:bg-blue-600 transition shadow-md flex justify-center items-center gap-2">
                <i class="fas fa-sign-in-alt"></i> Masuk
            </button>
        </form>
    </div>
</div>
{% endblock %}
"""

TEMPLATE_DICT['change_password.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-md mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2"><i class="fas fa-key text-slate-700"></i> Ubah Password Admin</h2>
    <form method="POST" action="">
        <div class="mb-4">
            <label class="block text-sm font-bold text-gray-700 mb-1">Password Lama</label>
            <input type="password" name="old_password" required class="w-full border border-gray-300 p-2.5 rounded focus:border-blue-500 outline-none">
        </div>
        <div class="mb-4">
            <label class="block text-sm font-bold text-gray-700 mb-1">Password Baru</label>
            <input type="password" name="new_password" required class="w-full border border-gray-300 p-2.5 rounded focus:border-blue-500 outline-none">
        </div>
        <div class="mb-6">
            <label class="block text-sm font-bold text-gray-700 mb-1">Konfirmasi Password Baru</label>
            <input type="password" name="confirm_password" required class="w-full border border-gray-300 p-2.5 rounded focus:border-blue-500 outline-none">
        </div>
        <div class="flex justify-end gap-2">
            <a href="{{ url_for('index') }}" class="px-4 py-2 bg-gray-200 rounded font-semibold hover:bg-gray-300">Batal</a>
            <button type="submit" class="px-4 py-2 bg-blue-700 text-white rounded font-semibold shadow hover:bg-blue-600"><i class="fas fa-save"></i> Simpan Password</button>
        </div>
    </form>
</div>
{% endblock %}
"""

# STREAMING_CHUNK:Master Data Pages
TEMPLATE_DICT['master_index.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="mb-6 flex justify-between items-center">
    <h2 class="text-2xl font-bold">{{ title }}</h2>
    <a href="{{ add_url }}" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-500 transition"><i class="fas fa-plus mr-1"></i> Tambah Data</a>
</div>
<div class="bg-white shadow rounded-lg overflow-hidden border border-gray-200">
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">No</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nama</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status & NIP</th>
                <th class="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pangkat / Gol.</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jabatan</th>
                <th class="px-0 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-36">Aksi</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
            {% for item in items %}
            <tr class="hover:bg-slate-50 transition">
                <td class="px-2 py-4 whitespace-nowrap text-sm text-gray-900">{{ loop.index }}</td>
                <td class="px-0 py-4 whitespace-nowrap text-sm font-bold text-gray-900">{{ item.nama }}</td>
                <td class="px-0 py-4 whitespace-nowrap text-sm text-gray-600">
                    {% if item.jenis_nip %}
                        <span class="bg-blue-100 text-blue-800 text-[10px] font-bold px-2 py-0.5 rounded mr-1">{{ item.jenis_nip }}</span>
                    {% endif %}
                    {{ item.nip }}
                </td>
                <td class="px-2 py-4 whitespace-nowrap text-sm text-gray-600">{{ item.pangkat }}</td>
                <td class="px-0 py-4 whitespace-nowrap text-sm text-gray-600">{{ item.jabatan }}</td>
                <td class="px-0 py-4 whitespace-nowrap text-center text-sm font-medium">
                    <a href="{{ edit_url_base }}/{{ item.id }}" class="text-amber-600 hover:text-amber-900 mr-3" title="Edit"><i class="fas fa-edit text-lg"></i></a>
                    <a href="{{ delete_url_base }}/{{ item.id }}" onclick="return confirm('Hapus data ini?')" class="text-red-600 hover:text-red-900" title="Hapus"><i class="fas fa-trash text-lg"></i></a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="0" class="px-6 py-8 text-center text-gray-500 italic">Belum ada data master.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

TEMPLATE_DICT['master_form.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-3xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center justify-between mb-6 border-b pb-4">
        <h2 class="text-2xl font-bold text-gray-800">{{ title }}</h2>
        <a href="{{ back_url }}" class="text-gray-500 hover:text-gray-700 font-semibold"><i class="fas fa-times"></i> Batal</a>
    </div>

    <form method="POST" action="">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div class="col-span-2">
                <label class="block text-sm font-bold text-gray-700 mb-1">Nama Lengkap & Gelar</label>
                <input type="text" name="nama" value="{{ item.nama if item else '' }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500">
            </div>
            
            <div>
                <label class="block text-sm font-bold text-gray-700 mb-1">Status (NIP / NIPPPK)</label>
                <select name="jenis_nip" class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold">
                    <option value="NIP." {% if item and item.jenis_nip == 'NIP.' %}selected{% endif %}>PNS (NIP.)</option>
                    <option value="NIPPPK." {% if item and item.jenis_nip == 'NIPPPK.' %}selected{% endif %}>PPPK (NIPPPK.)</option>
                    <option value="-" {% if item and item.jenis_nip == '-' %}selected{% endif %}>Non-ASN (-)</option>
                </select>
            </div>

            <div>
                <label class="block text-sm font-bold text-gray-700 mb-1">Nomor (Identitas)</label>
                <input type="text" name="nip" value="{{ item.nip if item else '' }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500">
            </div>
            <div>
                <label class="block text-sm font-bold text-gray-700 mb-1">Pangkat / Golongan</label>
                <input type="text" name="pangkat" value="{{ item.pangkat if item else '' }}" class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500">
            </div>
            <div class="col-span-2">
                <label class="block text-sm font-bold text-gray-700 mb-1">Jabatan</label>
                <input type="text" name="jabatan" value="{{ item.jabatan if item else '' }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500">
            </div>
        </div>
        <div class="flex justify-end pt-4 border-t border-gray-200">
            <button type="submit" class="bg-blue-700 text-white px-6 py-2.5 rounded-md font-bold hover:bg-blue-600 shadow flex items-center"><i class="fas fa-save mr-2"></i> Simpan Master Data</button>
        </div>
    </form>
</div>
{% endblock %}
"""

# STREAMING_CHUNK:Dashboard UI
TEMPLATE_DICT['index.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
    <h2 class="text-2xl font-bold">Dashboard Perjalanan Dinas</h2>
    <div class="flex items-center gap-2 w-full md:w-auto">
        <form action="" method="GET" class="relative w-full md:w-80">
            <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400"><i class="fas fa-search"></i></span>
            <input type="text" name="q" value="{{ request.args.get('q', '') }}" placeholder="Cari tujuan, maksud, nama, no spt..." class="w-full border border-gray-300 rounded-md py-2 pl-10 pr-10 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition shadow-sm text-sm">
            {% if request.args.get('q') %}
            <a href="{{ url_for('index') }}" class="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-red-600 transition" title="Hapus Pencarian"><i class="fas fa-times"></i></a>
            {% endif %}
        </form>
        <div class="relative group z-50">
            <button class="bg-green-600 text-white px-4 py-2 rounded shadow hover:bg-green-500 transition whitespace-nowrap font-semibold text-sm inline-flex items-center">
                <i class="fas fa-plus mr-1"></i> Buat SPT <i class="fas fa-chevron-down ml-1 text-xs"></i>
            </button>
            <div class="absolute right-0 mt-0 w-48 bg-white rounded-md shadow-lg py-1 hidden group-hover:block border border-gray-100">
                <a href="{{ url_for('create', type='kadis') }}" class="block px-4 py-2 text-sm text-purple-700 font-bold hover:bg-green-50 border-b border-gray-100"><i class="fas fa-user-tie mr-1"></i> SPT Khusus Kepala Dinas</a>
                <a href="{{ url_for('create') }}" class="block px-4 py-2 text-sm text-green-700 font-bold hover:bg-green-50"><i class="fas fa-users mr-1"></i> SPT Pegawai Biasa</a>
            </div>
        </div>
    </div>
</div>
<div class="bg-white shadow rounded-lg overflow-hidden border border-gray-200">
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">No</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-40">Nomor SPT</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-40">Tujuan</th>
                <th class="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">Tanggal</th>
                <th class="px-0 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Maksud Tugas</th>
                <th class="px-0 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-40">Aksi</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
            {% for spt in spts %}
            <tr class="hover:bg-slate-50 transition">
                <td class="px-2 py-4 whitespace-nowrap text-sm text-gray-900">{{ loop.index }}</td>
                <td class="px-0 py-4 whitespace-nowrap text-sm text-blue-700 font-bold">
                    000.1.2.3/{{ spt.no_spt }}/{% if spt.jenis_spt in ['kadis_bupati', 'kadis_sekda'] %}SETDA{% else %}DPRPP{% endif %}
                </td>
                <td class="px-0 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                    {% set tujuans = spt.tempat_tujuan|from_json %}
                    {% if tujuans|length > 0 %}
                        {% if tujuans[0] is string %}
                            {{ tujuans|join(', ') }}
                        {% else %}
                            {% for t in tujuans %}
                                {{ t.kota }}{% if not loop.last %}, {% endif %}
                            {% endfor %}
                        {% endif %}
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td class="px-2 py-4 whitespace-nowrap text-sm text-gray-900">{{ spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }}</td>
                <td class="px-0 py-4 text-sm text-gray-900">
                    {% set maksuds = spt.maksud_tugas|from_json %}
                    <div class="truncate max-w-sm" title="{{ maksuds|join(', ') }}">
                        {% if spt.jenis_spt != 'biasa' %}<span class="bg-purple-100 text-purple-800 text-[10px] font-bold px-2 py-0.5 rounded mr-1">KADIS</span>{% endif %}
                        {{ maksuds|join(', ') }}
                    </div>
                </td>
                <td class="px-0 py-4 whitespace-nowrap text-center text-sm font-medium">
                    <a href="{{ url_for('detail', id=spt.id) }}" class="text-blue-600 hover:text-blue-900 mr-1 px-2 py-1 rounded hover:bg-blue-100 transition"><i class="fas fa-folder-open"></i> Detail</a>
                    <a href="{{ url_for('edit', id=spt.id) }}" class="text-amber-600 hover:text-amber-900 mr-1 px-2 py-1 rounded hover:bg-amber-100 transition"><i class="fas fa-edit"></i> Edit</a>
                    <a href="{{ url_for('delete_spt', id=spt.id) }}" onclick="return confirm('Yakin ingin menghapus data ini beserta seluruh pegawai dan kuitansinya secara permanen?')" class="text-red-600 hover:text-red-900 px-2 py-1 rounded hover:bg-red-100 transition"><i class="fas fa-trash"></i> Hapus</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" class="px-6 py-8 text-center text-gray-500 italic">Belum ada data perjalanan dinas yang dibuat.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

# ... existing code ...
# STREAMING_CHUNK:SPT Create Form
TEMPLATE_DICT['form.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-6xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center gap-3 mb-6 border-b pb-4">
        {% if request.args.get('type') == 'kadis' %}
        <i class="fas fa-crown text-3xl text-purple-600"></i>
        <h2 class="text-2xl font-bold text-gray-800">Buat Surat Perintah Tugas (Khusus Kepala Dinas)</h2>
        {% else %}
        <i class="fas fa-file-signature text-3xl text-green-600"></i>
        <h2 class="text-2xl font-bold text-gray-800">Buat Surat Perintah Tugas (SPT Pegawai)</h2>
        {% endif %}
    </div>

    <form method="POST" action="{{ url_for('create', type=request.args.get('type', 'biasa')) }}">
        
        {% if request.args.get('type') == 'kadis' %}
            <div class="mb-6 bg-purple-50 p-5 rounded border border-purple-200">
                <h3 class="text-lg font-bold text-purple-800 mb-2"><i class="fas fa-cog mr-2"></i>Pengaturan Format Surat Khusus</h3>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pilih Penandatangan & Kop Surat</label>
                <select name="jenis_spt" id="jenis_spt_selector" class="w-full border border-purple-300 p-2.5 rounded outline-none focus:border-purple-500 font-bold text-purple-900 cursor-pointer" onchange="updateSuffix()">
                    <option value="kadis_bupati">Kop Bupati (Ditandatangani Bupati / Wakil Bupati)</option>
                    <option value="kadis_sekda">Kop Sekretariat Daerah (Ditandatangani Sekretaris Daerah)</option>
                </select>
            </div>
        {% else %}
            <input type="hidden" name="jenis_spt" value="biasa" id="jenis_spt_selector">
        {% endif %}

        <!-- Section 1: Data Utama SPT -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-green-500 pl-3">Data Utama Perjalanan</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="col-span-2 md:col-span-1">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Nomor SPT <span class="text-red-500">*</span></label>
                <div class="flex items-stretch">
                    <span class="bg-gray-100 border border-gray-300 border-r-0 rounded-l px-3 flex items-center text-gray-600 text-sm font-bold">NOMOR: 000.1.2.3/</span>
                    <input type="text" name="no_spt" required class="w-full border border-gray-300 p-2.5 outline-none focus:border-green-500 text-center font-bold" placeholder="No. SPT">
                    <span id="spt_suffix" class="bg-gray-100 border border-gray-300 border-l-0 rounded-r px-3 flex items-center text-gray-600 text-sm font-bold">{% if request.args.get('type') == 'kadis' %}/SETDA{% else %}/DPRPP{% endif %}</span>
                </div>
            </div>
            <div class="col-span-2 md:col-span-1">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Pembuatan SPT <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_spt" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500">
            </div>
            <div class="col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tempat Berangkat Utama <span class="text-red-500">*</span></label>
                <input type="text" name="tempat_berangkat" value="Kotabaru" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Berangkat (Awal) <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_berangkat" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Kembali (Akhir) <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_kembali" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500">
            </div>
            <div class="col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Alat Angkut / Kendaraan <span class="text-red-500">*</span></label>
                <input type="text" name="kendaraan" required placeholder="Contoh: Darat - Udara" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500">
            </div>
        </div>
        
        <!-- Section: Dynamic Maksud & Tujuan -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-green-500 pl-3">Tujuan & Maksud Tugas</h3>
        
        <label class="block text-sm font-semibold text-gray-700 mb-1">Daftar Tempat Tujuan <span class="text-red-500">*</span></label>
        <p class="text-xs text-gray-500 mb-2">Tanggal Tiba dan Berangkat ini khusus digunakan untuk mengisi Rincian Belakang SPD (Romawi I s.d IV).</p>
        <div id="tujuan-container" class="space-y-3 mb-4">
            <div class="flex flex-col md:flex-row gap-2 tujuan-row bg-green-50 p-3 rounded border border-green-100">
                <div class="w-full md:w-2/5">
                    <label class="text-xs font-bold text-gray-600">Kota/Tempat Tujuan</label>
                    <input type="text" name="tujuan_kota[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500" placeholder="Contoh: Banjarmasin">
                </div>
                <div class="w-full md:w-1/4">
                    <label class="text-xs font-bold text-gray-600">Tanggal Tiba</label>
                    <input type="date" name="tujuan_tiba[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500">
                </div>
                <div class="w-full md:w-1/4">
                    <label class="text-xs font-bold text-gray-600">Tanggal Berangkat</label>
                    <input type="date" name="tujuan_berangkat[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500">
                </div>
                <div class="flex items-end pb-1">
                    <button type="button" onclick="if(document.querySelectorAll('.tujuan-row').length > 1) this.closest('.tujuan-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
                </div>
            </div>
        </div>
        <button type="button" onclick="addTujuan()" class="mb-6 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Kota Tujuan
        </button>

        <label class="block text-sm font-semibold text-gray-700 mb-1">Maksud Tugas <span class="text-red-500">*</span></label>
        <div id="maksud-container" class="space-y-3 mb-4">
            <div class="flex gap-2 maksud-row">
                <textarea name="maksud_tugas[]" required rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500" placeholder="Contoh: Menghadiri rapat koordinasi..."></textarea>
                <button type="button" onclick="if(document.querySelectorAll('.maksud-row').length > 1) this.closest('.maksud-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
        </div>
        <button type="button" onclick="addMaksud()" class="mb-8 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Maksud Tugas
        </button>

        <!-- Section: Dasar Surat -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-green-500 pl-3">Dasar Surat Perintah Tugas</h3>
        <div id="dasar-container" class="space-y-3 mb-4">
            <div class="flex gap-2 dasar-row">
                <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500" required>Peraturan Presiden Republik Indonesia Nomor 33 Tahun 2020 tentang Standar Harga Satuan Regional.</textarea>
                <button type="button" onclick="this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
            <div class="flex gap-2 dasar-row">
                <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500" required>Perbup Nomor 55 Tahun 2023 tentang perjalanan Dinas bagi Pejabat Negara, Pimpinan dan Anggota Dewan Perwakilan Rakyat Daerah, Pegawai Aparatur Sipil Negara, Tenaga non ASN dan Pihak Lain.</textarea>
                <button type="button" onclick="this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
            <div class="flex gap-2 dasar-row">
                <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500" required>Dokumen Pelaksanaan Anggaran Dinas Perumahan Rakyat Permukiman dan Pertanahan Tahun Anggaran 2026</textarea>
                <button type="button" onclick="this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
        </div>
        <button type="button" onclick="addDasar()" class="mb-8 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Dasar Surat
        </button>

        <!-- Section 2: Administrasi SPD -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-blue-500 pl-3 mt-8">Administrasi Anggaran (Untuk Cetak SPD)</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-blue-50 p-5 rounded border border-blue-100">
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pejabat Pemberi Perintah</label>
                <input type="text" name="pejabat_pemberi_perintah" value="H. Akhmad Rozain, S.Ag, M.M" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tingkat Biaya Perjalanan Dinas</label>
                <input type="text" name="tingkat_biaya" value="-" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pembebanan Anggaran: a. Instansi</label>
                <input type="text" name="instansi_pembebanan" value="Dinas Perumahan Rakyat, Permukiman dan Pertanahan" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pembebanan Anggaran: b. Akun</label>
                <input type="text" name="akun_pembebanan" value="5.1.02.04.001.00001" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500">
            </div>
        </div>

        <!-- Section 3: Penandatangan SPT -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-indigo-500 pl-3 mt-8">Pejabat Penandatangan SPT</h3>
        <div class="mb-4">
            <select class="w-full border border-indigo-300 bg-indigo-50 text-indigo-800 font-bold p-2.5 rounded outline-none cursor-pointer" onchange="fillTtdData(this, 'spt')">
                <option value='{"nama":"", "nip":"", "pangkat":"", "jabatan":""}'>-- Pilih Penandatangan SPT dari Master Data --</option>
                {% for t in ttd_spts %}
                <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "pangkat":"{{t.pangkat}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-indigo-50 p-5 rounded border border-indigo-100">
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Jabatan TTD SPT</label>
                <input type="text" id="spt_jabatan" name="ttd_spt_jabatan" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Nama Pejabat</label>
                <input type="text" id="spt_nama" name="ttd_spt_nama" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pangkat / Golongan</label>
                <input type="text" id="spt_pangkat" name="ttd_spt_pangkat" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">NIP Pejabat</label>
                <input type="text" id="spt_nip" name="ttd_spt_nip" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500">
            </div>
        </div>

        <!-- Section 4: Penandatangan SPD -->
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-purple-500 pl-3 mt-8">Pejabat Penandatangan SPD (Depan & Belakang)</h3>
        <div class="mb-4">
            <select class="w-full border border-purple-300 bg-purple-50 text-purple-800 font-bold p-2.5 rounded outline-none cursor-pointer" onchange="fillTtdData(this, 'spd')">
                <option value='{"nama":"", "nip":"", "pangkat":"", "jabatan":""}'>-- Pilih Penandatangan SPD dari Master Data --</option>
                {% for t in ttd_spds %}
                <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "pangkat":"{{t.pangkat}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-purple-50 p-5 rounded border border-purple-100">
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Jabatan TTD SPD</label>
                <input type="text" id="spd_jabatan" name="ttd_spd_jabatan" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Nama Pejabat</label>
                <input type="text" id="spd_nama" name="ttd_spd_nama" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pangkat / Golongan</label>
                <input type="text" id="spd_pangkat" name="ttd_spd_pangkat" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">NIP Pejabat</label>
                <input type="text" id="spd_nip" name="ttd_spd_nip" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500">
            </div>
        </div>

        <!-- Section 5: Daftar Pegawai -->
        <div class="mb-4 flex justify-between items-end border-b border-gray-200 pb-3 mt-10">
            <h3 class="text-xl font-bold text-gray-800"><i class="fas fa-users mr-2 text-blue-600"></i>Daftar Pegawai yang Ditugaskan</h3>
            <button type="button" onclick="addPegawai()" class="bg-blue-600 text-white px-4 py-2 rounded text-sm font-bold hover:bg-blue-500 transition shadow"><i class="fas fa-user-plus mr-1"></i> Tambah Pegawai</button>
        </div>
        
        <div id="pegawai-container" class="space-y-4 mb-8">
            <div class="pegawai-row bg-slate-50 p-5 rounded-md border border-slate-200 shadow-sm">
                <!-- Dropdown Pilih Pegawai -->
                <div class="mb-4 pb-4 border-b border-gray-200">
                    <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none font-semibold text-blue-700 cursor-pointer" onchange="fillPegawaiData(this)">
                        <option value='{"nama":"", "nip":"", "jenis_nip":"NIP.", "pangkat":"", "jabatan":""}'>-- Pilih Pegawai dari Master Data --</option>
                        {% for p in pegawais %}
                        <option value='{"nama":"{{p.nama}}", "nip":"{{p.nip}}", "jenis_nip":"{{p.jenis_nip or 'NIP.'}}", "pangkat":"{{p.pangkat}}", "jabatan":"{{p.jabatan}}"}'>{{ p.nama }}</option>
                        {% endfor %}
                    </select>
                </div>
                <!-- Inputs Pegawai dengan col-span fix -->
                <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div class="md:col-span-4">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">No. SPD</label>
                        <div class="flex items-stretch">
                            <span class="bg-gray-200 border border-gray-300 border-r-0 rounded-l px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">000.1.2.3/</span>
                            <input type="text" name="no_spd[]" required class="w-full min-w-[3rem] border border-gray-300 p-2 text-sm outline-none text-center font-bold" placeholder="No. SPD">
                            <span class="bg-gray-200 border border-gray-300 border-l-0 rounded-r px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">/DPRPP/2026</span>
                        </div>
                    </div>
                    <div class="md:col-span-3">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Nama Lengkap</label>
                        <input type="text" name="nama[]" required class="peg-nama w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                    </div>
                    <div class="md:col-span-2">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Status</label>
                        <select name="jenis_nip[]" required class="peg-jenis-nip w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                            <option value="NIP.">NIP.</option>
                            <option value="NIPPPK.">NIPPPK.</option>
                            <option value="-">-</option>
                        </select>
                    </div>
                    <div class="md:col-span-3">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Nomor (NIP)</label>
                        <input type="text" name="nip[]" required class="peg-nip w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                    </div>
                    <div class="md:col-span-6">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Pangkat / Golongan</label>
                        <input type="text" name="pangkat[]" required class="peg-pangkat w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                    </div>
                    <div class="md:col-span-6">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Jabatan</label>
                        <input type="text" name="jabatan[]" required class="peg-jabatan w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                    </div>
                </div>
            </div>
        </div>

        <div class="flex justify-end pt-4 border-t border-gray-200">
            <button type="submit" class="bg-green-700 text-white px-8 py-3 rounded-md font-bold hover:bg-green-600 text-lg shadow-lg transition flex items-center"><i class="fas fa-save mr-2"></i> Simpan & Buat Dokumen</button>
        </div>
    </form>
</div>

<script>
function updateSuffix() {
    var sel = document.getElementById('jenis_spt_selector');
    var suffix = document.getElementById('spt_suffix');
    if(sel && suffix) {
        if(sel.value === 'kadis_bupati' || sel.value === 'kadis_sekda') {
            suffix.innerHTML = '/SETDA';
        } else {
            suffix.innerHTML = '/DPRPP';
        }
    }
}

function fillTtdData(selectElement, type) {
    try {
        const data = JSON.parse(selectElement.value);
        document.getElementById(type + '_nama').value = data.nama;
        document.getElementById(type + '_nip').value = data.nip;
        document.getElementById(type + '_pangkat').value = data.pangkat;
        document.getElementById(type + '_jabatan').value = data.jabatan;
    } catch (e) {}
}

function fillPegawaiData(selectElement) {
    try {
        const data = JSON.parse(selectElement.value);
        const row = selectElement.closest('.pegawai-row');
        row.querySelector('.peg-nama').value = data.nama;
        row.querySelector('.peg-jenis-nip').value = data.jenis_nip || 'NIP.';
        row.querySelector('.peg-nip').value = data.nip;
        row.querySelector('.peg-pangkat').value = data.pangkat;
        row.querySelector('.peg-jabatan').value = data.jabatan;
    } catch (e) {}
}

function addMaksud() {
    const container = document.getElementById('maksud-container');
    const row = document.createElement('div');
    row.className = 'flex gap-2 maksud-row';
    row.innerHTML = `
        <textarea name="maksud_tugas[]" required rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500" placeholder="Contoh: Menghadiri rapat koordinasi..."></textarea>
        <button type="button" onclick="this.closest('.maksud-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
    `;
    container.appendChild(row);
}

function addTujuan() {
    const container = document.getElementById('tujuan-container');
    const row = document.createElement('div');
    row.className = 'flex flex-col md:flex-row gap-2 tujuan-row bg-green-50 p-3 rounded border border-green-100';
    row.innerHTML = `
        <div class="w-full md:w-2/5">
            <label class="text-xs font-bold text-gray-600">Kota/Tempat Tujuan</label>
            <input type="text" name="tujuan_kota[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500" placeholder="Contoh: Banjarmasin">
        </div>
        <div class="w-full md:w-1/4">
            <label class="text-xs font-bold text-gray-600">Tanggal Tiba</label>
            <input type="date" name="tujuan_tiba[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500">
        </div>
        <div class="w-full md:w-1/4">
            <label class="text-xs font-bold text-gray-600">Tanggal Berangkat</label>
            <input type="date" name="tujuan_berangkat[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500">
        </div>
        <div class="flex items-end pb-1">
            <button type="button" onclick="this.closest('.tujuan-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
        </div>
    `;
    container.appendChild(row);
}

function addDasar() {
    const container = document.getElementById('dasar-container');
    const row = document.createElement('div');
    row.className = 'flex gap-2 dasar-row';
    row.innerHTML = `
        <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-green-500" required placeholder="Masukkan dasar surat baru..."></textarea>
        <button type="button" onclick="this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
    `;
    container.appendChild(row);
}

function addPegawai() {
    const container = document.getElementById('pegawai-container');
    const row = document.createElement('div');
    row.className = 'pegawai-row bg-slate-50 p-5 rounded-md border border-slate-200 shadow-sm mt-4';
    const selectHtml = document.querySelector('.pegawai-row select').innerHTML;
    row.innerHTML = `
        <div class="mb-4 pb-4 border-b border-gray-200 flex gap-2 items-center">
            <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none font-semibold text-blue-700 cursor-pointer" onchange="fillPegawaiData(this)">
                ${selectHtml}
            </select>
            <button type="button" onclick="this.closest('.pegawai-row').remove()" class="bg-red-100 text-red-600 border border-red-200 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition whitespace-nowrap"><i class="fas fa-trash-alt"></i></button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
            <div class="md:col-span-4">
                <label class="block text-xs font-semibold text-gray-600 mb-1">No. SPD</label>
                <div class="flex items-stretch">
                    <span class="bg-gray-200 border border-gray-300 border-r-0 rounded-l px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">000.1.2.3/</span>
                    <input type="text" name="no_spd[]" required class="w-full min-w-[3rem] border border-gray-300 p-2 text-sm outline-none text-center font-bold">
                    <span class="bg-gray-200 border border-gray-300 border-l-0 rounded-r px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">/DPRPP/2026</span>
                </div>
            </div>
            <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">Nama Lengkap</label><input type="text" name="nama[]" required class="peg-nama w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500"></div>
            <div class="md:col-span-2">
                <label class="block text-xs font-semibold text-gray-600 mb-1">Status</label>
                <select name="jenis_nip[]" required class="peg-jenis-nip w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500">
                    <option value="NIP.">NIP.</option>
                    <option value="NIPPPK.">NIPPPK.</option>
                    <option value="-">-</option>
                </select>
            </div>
            <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">Nomor (NIP)</label><input type="text" name="nip[]" required class="peg-nip w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500"></div>
            <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Pangkat</label><input type="text" name="pangkat[]" required class="peg-pangkat w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500"></div>
            <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Jabatan</label><input type="text" name="jabatan[]" required class="peg-jabatan w-full border border-gray-300 rounded p-2 text-sm outline-none focus:border-blue-500"></div>
        </div>
    `;
    container.appendChild(row);
}
</script>
{% endblock %}
"""

# STREAMING_CHUNK:SPT Edit Form
TEMPLATE_DICT['edit.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-6xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center justify-between mb-6 border-b pb-4">
        <div class="flex items-center gap-3">
            <i class="fas fa-edit text-3xl text-amber-500"></i>
            <h2 class="text-2xl font-bold text-gray-800">Edit Surat Perintah Tugas (SPT)</h2>
        </div>
        <a href="{{ url_for('index') }}" class="text-gray-500 hover:text-gray-700 font-semibold transition"><i class="fas fa-times"></i> Batal</a>
    </div>

    <form method="POST" action="">
        
        {% if spt.jenis_spt != 'biasa' %}
            <div class="mb-6 bg-purple-50 p-5 rounded border border-purple-200">
                <h3 class="text-lg font-bold text-purple-800 mb-2"><i class="fas fa-cog mr-2"></i>Pengaturan Format Surat Khusus</h3>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Pilih Penandatangan & Kop Surat</label>
                <select name="jenis_spt" id="jenis_spt_selector" class="w-full border border-purple-300 p-2.5 rounded outline-none focus:border-purple-500 font-bold text-purple-900 cursor-pointer" onchange="updateSuffix()">
                    <option value="kadis_bupati" {% if spt.jenis_spt == 'kadis_bupati' %}selected{% endif %}>Kop BUPATI (Ditandatangani Bupati / Wakil Bupati)</option>
                    <option value="kadis_sekda" {% if spt.jenis_spt == 'kadis_sekda' %}selected{% endif %}>Kop SEKRETARIAT DAERAH (Ditandatangani Sekretaris Daerah)</option>
                </select>
            </div>
        {% else %}
            <input type="hidden" name="jenis_spt" value="biasa" id="jenis_spt_selector">
        {% endif %}

        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-amber-500 pl-3">Data Utama Perjalanan</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="col-span-2 md:col-span-1">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Nomor SPT <span class="text-red-500">*</span></label>
                <div class="flex items-stretch">
                    <span class="bg-gray-100 border border-gray-300 border-r-0 rounded-l px-3 flex items-center text-gray-600 text-sm font-bold">NOMOR: 000.1.2.3/</span>
                    <input type="text" name="no_spt" value="{{ spt.no_spt }}" required class="w-full border border-gray-300 p-2.5 outline-none focus:border-amber-500 text-center font-bold">
                    <span id="spt_suffix" class="bg-gray-100 border border-gray-300 border-l-0 rounded-r px-3 flex items-center text-gray-600 text-sm font-bold">{% if spt.jenis_spt in ['kadis_bupati', 'kadis_sekda'] %}/SETDA{% else %}/DPRPP{% endif %}</span>
                </div>
            </div>
            <div class="col-span-2 md:col-span-1">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Pembuatan SPT <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_spt" value="{{ spt.tanggal_spt.strftime('%Y-%m-%d') if spt.tanggal_spt else spt.created_at.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">
            </div>
            <div class="col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tempat Berangkat Utama <span class="text-red-500">*</span></label>
                <input type="text" name="tempat_berangkat" value="{{ spt.tempat_berangkat }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Berangkat (Awal) <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_berangkat" value="{{ spt.tanggal_berangkat.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Kembali (Akhir) <span class="text-red-500">*</span></label>
                <input type="date" name="tanggal_kembali" value="{{ spt.tanggal_kembali.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">
            </div>
            <div class="col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Alat Angkut / Kendaraan <span class="text-red-500">*</span></label>
                <input type="text" name="kendaraan" value="{{ spt.kendaraan }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">
            </div>
        </div>
        
        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-amber-500 pl-3">Tujuan & Maksud Tugas</h3>
        
        <label class="block text-sm font-semibold text-gray-700 mb-1">Daftar Tempat Tujuan <span class="text-red-500">*</span></label>
        <p class="text-xs text-gray-500 mb-2">Tanggal Tiba dan Berangkat ini khusus digunakan untuk mengisi Rincian Belakang SPD (Romawi I s.d IV).</p>
        <div id="tujuan-container" class="space-y-3 mb-4">
            {% set tujuans = spt.tempat_tujuan|from_json %}
            {% for t in tujuans %}
            <div class="flex flex-col md:flex-row gap-2 tujuan-row bg-green-50 p-3 rounded border border-green-100">
                <div class="w-full md:w-2/5">
                    <label class="text-xs font-bold text-gray-600">Kota/Tempat Tujuan</label>
                    <input type="text" name="tujuan_kota[]" value="{{ t.kota if t is mapping else t }}" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500">
                </div>
                <div class="w-full md:w-1/4">
                    <label class="text-xs font-bold text-gray-600">Tanggal Tiba</label>
                    <input type="date" name="tujuan_tiba[]" value="{{ t.tgl_tiba if t is mapping else spt.tanggal_berangkat.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500">
                </div>
                <div class="w-full md:w-1/4">
                    <label class="text-xs font-bold text-gray-600">Tanggal Berangkat</label>
                    <input type="date" name="tujuan_berangkat[]" value="{{ t.tgl_berangkat if t is mapping else spt.tanggal_kembali.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500">
                </div>
                <div class="flex items-end pb-1">
                    <button type="button" onclick="if(document.querySelectorAll('.tujuan-row').length > 1) this.closest('.tujuan-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
                </div>
            </div>
            {% endfor %}
        </div>
        <button type="button" onclick="addTujuan()" class="mb-6 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Kota Tujuan
        </button>

        <label class="block text-sm font-semibold text-gray-700 mb-1">Maksud Tugas <span class="text-red-500">*</span></label>
        <div id="maksud-container" class="space-y-3 mb-4">
            {% set maksuds = spt.maksud_tugas|from_json %}
            {% for m in maksuds %}
            <div class="flex gap-2 maksud-row">
                <textarea name="maksud_tugas[]" required rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500">{{ m }}</textarea>
                <button type="button" onclick="if(document.querySelectorAll('.maksud-row').length > 1) this.closest('.maksud-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
            {% endfor %}
        </div>
        <button type="button" onclick="addMaksud()" class="mb-8 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Maksud Tugas
        </button>

        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-amber-500 pl-3">Dasar Surat Perintah Tugas</h3>
        <div id="dasar-container" class="space-y-3 mb-4">
            {% set dasars = spt.dasar_surat|from_json %}
            {% for d in dasars %}
            <div class="flex gap-2 dasar-row">
                <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500" required>{{ d }}</textarea>
                <button type="button" onclick="if(document.querySelectorAll('.dasar-row').length > 1) this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
            </div>
            {% endfor %}
        </div>
        <button type="button" onclick="addDasar()" class="mb-8 text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            <i class="fas fa-plus"></i> Tambah Dasar Surat
        </button>

        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-blue-500 pl-3 mt-8">Administrasi Anggaran</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-blue-50 p-5 rounded border border-blue-100">
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Pejabat Pemberi Perintah</label><input type="text" name="pejabat_pemberi_perintah" value="{{ spt.pejabat_pemberi_perintah }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Tingkat Biaya</label><input type="text" name="tingkat_biaya" value="{{ spt.tingkat_biaya }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Instansi Pembebanan</label><input type="text" name="instansi_pembebanan" value="{{ spt.instansi_pembebanan }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Akun Pembebanan</label><input type="text" name="akun_pembebanan" value="{{ spt.akun_pembebanan }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-blue-500"></div>
        </div>

        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-indigo-500 pl-3 mt-8">Pejabat Penandatangan SPT</h3>
        <div class="mb-4">
            <select class="w-full border border-indigo-300 bg-indigo-50 text-indigo-800 font-bold p-2.5 rounded outline-none cursor-pointer" onchange="fillTtdData(this, 'spt')">
                <option value='{"nama":"", "nip":"", "pangkat":"", "jabatan":""}'>-- Ganti Penandatangan SPT --</option>
                {% for t in ttd_spts %}
                <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "pangkat":"{{t.pangkat}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-indigo-50 p-5 rounded border border-indigo-100">
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Jabatan</label><input type="text" id="spt_jabatan" name="ttd_spt_jabatan" value="{{ spt.ttd_spt_jabatan }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Nama</label><input type="text" id="spt_nama" name="ttd_spt_nama" value="{{ spt.ttd_spt_nama }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Pangkat</label><input type="text" id="spt_pangkat" name="ttd_spt_pangkat" value="{{ spt.ttd_spt_pangkat }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">NIP</label><input type="text" id="spt_nip" name="ttd_spt_nip" value="{{ spt.ttd_spt_nip }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-indigo-500"></div>
        </div>

        <h3 class="text-lg font-bold text-gray-800 mb-4 border-l-4 border-purple-500 pl-3 mt-8">Pejabat Penandatangan SPD</h3>
        <div class="mb-4">
            <select class="w-full border border-purple-300 bg-purple-50 text-purple-800 font-bold p-2.5 rounded outline-none cursor-pointer" onchange="fillTtdData(this, 'spd')">
                <option value='{"nama":"", "nip":"", "pangkat":"", "jabatan":""}'>-- Ganti Penandatangan SPD --</option>
                {% for t in ttd_spds %}
                <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "pangkat":"{{t.pangkat}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-purple-50 p-5 rounded border border-purple-100">
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Jabatan</label><input type="text" id="spd_jabatan" name="ttd_spd_jabatan" value="{{ spt.ttd_spd_jabatan }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Nama</label><input type="text" id="spd_nama" name="ttd_spd_nama" value="{{ spt.ttd_spd_nama }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">Pangkat</label><input type="text" id="spd_pangkat" name="ttd_spd_pangkat" value="{{ spt.ttd_spd_pangkat }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500"></div>
            <div><label class="block text-sm font-semibold text-gray-700 mb-1">NIP</label><input type="text" id="spd_nip" name="ttd_spd_nip" value="{{ spt.ttd_spd_nip }}" required class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-purple-500"></div>
        </div>

        <div class="mb-4 flex justify-between items-end border-b border-gray-200 pb-3 mt-10">
            <h3 class="text-xl font-bold text-gray-800"><i class="fas fa-users mr-2 text-amber-600"></i>Daftar Pegawai</h3>
            <button type="button" onclick="addPegawai()" class="bg-blue-600 text-white px-4 py-2 rounded text-sm font-bold hover:bg-blue-500 shadow"><i class="fas fa-user-plus mr-1"></i> Tambah Pegawai</button>
        </div>
        
        <div id="pegawai-container" class="space-y-4 mb-8">
            <select id="master_pegawai_select" class="hidden">
                <option value='{"nama":"", "nip":"", "jenis_nip":"NIP.", "pangkat":"", "jabatan":""}'>-- Ganti Pegawai --</option>
                {% for p in pegawais %}
                <option value='{"nama":"{{p.nama}}", "nip":"{{p.nip}}", "jenis_nip":"{{p.jenis_nip or 'NIP.'}}", "pangkat":"{{p.pangkat}}", "jabatan":"{{p.jabatan}}"}'>{{ p.nama }}</option>
                {% endfor %}
            </select>

            {% for peg in spt.pegawais %}
            <div class="pegawai-row bg-slate-50 p-5 rounded-md border border-slate-200 shadow-sm mt-4">
                <input type="hidden" name="pegawai_id[]" value="{{ peg.id }}">
                <div class="mb-4 pb-4 border-b border-gray-200 flex gap-2 items-center">
                    <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none font-semibold text-amber-700 cursor-pointer" onchange="fillPegawaiData(this)">
                        <option value='{"nama":"", "nip":"", "jenis_nip":"NIP.", "pangkat":"", "jabatan":""}'>-- Ganti Pegawai dari Master --</option>
                        {% for p in pegawais %}
                        <option value='{"nama":"{{p.nama}}", "nip":"{{p.nip}}", "jenis_nip":"{{p.jenis_nip or 'NIP.'}}", "pangkat":"{{p.pangkat}}", "jabatan":"{{p.jabatan}}"}'>{{ p.nama }}</option>
                        {% endfor %}
                    </select>
                    {% if loop.index > 1 %}
                    <button type="button" onclick="this.closest('.pegawai-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white"><i class="fas fa-trash-alt"></i></button>
                    {% endif %}
                </div>
                <!-- Layout Grid Diperbarui: 12 span -->
                <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div class="md:col-span-4">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">No. SPD</label>
                        <div class="flex items-stretch">
                            <span class="bg-gray-200 border border-gray-300 border-r-0 rounded-l px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">000.1.2.3/</span>
                            <input type="text" name="no_spd[]" value="{{ peg.no_spd }}" required class="w-full min-w-[3rem] border border-gray-300 p-2 text-sm outline-none text-center font-bold">
                            <span class="bg-gray-200 border border-gray-300 border-l-0 rounded-r px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">/DPRPP/2026</span>
                        </div>
                    </div>
                    <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">Nama</label><input type="text" name="nama[]" value="{{ peg.nama }}" required class="peg-nama w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
                    <div class="md:col-span-1">
                        <label class="block text-xs font-semibold text-gray-600 mb-1">Status</label>
                        <select name="jenis_nip[]" required class="peg-jenis-nip w-full border border-gray-300 rounded p-2 text-sm outline-none">
                            <option value="NIP." {% if peg.jenis_nip == 'NIP.' %}selected{% endif %}>NIP.</option>
                            <option value="NIPPPK." {% if peg.jenis_nip == 'NIPPPK.' %}selected{% endif %}>NIPPPK.</option>
                            <option value="-" {% if peg.jenis_nip == '-' %}selected{% endif %}>-</option>
                        </select>
                    </div>
                    <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">NIP</label><input type="text" name="nip[]" value="{{ peg.nip }}" required class="peg-nip w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
                    <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Pangkat</label><input type="text" name="pangkat[]" value="{{ peg.pangkat }}" required class="peg-pangkat w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
                    <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Jabatan</label><input type="text" name="jabatan[]" value="{{ peg.jabatan }}" required class="peg-jabatan w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
                </div>
            </div>
            {% endfor %}
        </div>
        <div class="flex justify-end pt-4 border-t border-gray-200">
            <button type="submit" class="bg-amber-600 text-white px-8 py-3 rounded-md font-bold hover:bg-amber-500 shadow-lg flex items-center"><i class="fas fa-save mr-2"></i> Update Dokumen</button>
        </div>
    </form>
</div>
<script>
function updateSuffix() {
    var sel = document.getElementById('jenis_spt_selector');
    var suffix = document.getElementById('spt_suffix');
    if(sel && suffix) {
        if(sel.value === 'kadis_bupati' || sel.value === 'kadis_sekda') {
            suffix.innerHTML = '/SETDA';
        } else {
            suffix.innerHTML = '/DPRPP';
        }
    }
}
function fillTtdData(selectElement, type) {
    try {
        const data = JSON.parse(selectElement.value);
        document.getElementById(type + '_nama').value = data.nama;
        document.getElementById(type + '_nip').value = data.nip;
        document.getElementById(type + '_pangkat').value = data.pangkat;
        document.getElementById(type + '_jabatan').value = data.jabatan;
    } catch (e) {}
}
function fillPegawaiData(selectElement) {
    try {
        const data = JSON.parse(selectElement.value);
        const row = selectElement.closest('.pegawai-row');
        row.querySelector('.peg-nama').value = data.nama;
        row.querySelector('.peg-jenis-nip').value = data.jenis_nip || 'NIP.';
        row.querySelector('.peg-nip').value = data.nip;
        row.querySelector('.peg-pangkat').value = data.pangkat;
        row.querySelector('.peg-jabatan').value = data.jabatan;
    } catch (e) {}
}
function addMaksud() {
    const container = document.getElementById('maksud-container');
    const row = document.createElement('div');
    row.className = 'flex gap-2 maksud-row';
    row.innerHTML = `
        <textarea name="maksud_tugas[]" required rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500" placeholder="Contoh: Menghadiri rapat koordinasi..."></textarea>
        <button type="button" onclick="this.closest('.maksud-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
    `;
    container.appendChild(row);
}
function addTujuan() {
    const container = document.getElementById('tujuan-container');
    const row = document.createElement('div');
    row.className = 'flex flex-col md:flex-row gap-2 tujuan-row bg-green-50 p-3 rounded border border-green-100';
    row.innerHTML = `
        <div class="w-full md:w-2/5">
            <label class="text-xs font-bold text-gray-600">Kota/Tempat Tujuan</label>
            <input type="text" name="tujuan_kota[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500" placeholder="Contoh: Banjarmasin">
        </div>
        <div class="w-full md:w-1/4">
            <label class="text-xs font-bold text-gray-600">Tanggal Tiba</label>
            <input type="date" name="tujuan_tiba[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500">
        </div>
        <div class="w-full md:w-1/4">
            <label class="text-xs font-bold text-gray-600">Tanggal Berangkat</label>
            <input type="date" name="tujuan_berangkat[]" required class="w-full border border-gray-300 rounded p-2 outline-none focus:border-amber-500">
        </div>
        <div class="flex items-end pb-1">
            <button type="button" onclick="this.closest('.tujuan-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
        </div>
    `;
    container.appendChild(row);
}
function addDasar() {
    const container = document.getElementById('dasar-container');
    const row = document.createElement('div');
    row.className = 'flex gap-2 dasar-row';
    row.innerHTML = `
        <textarea name="dasar_surat[]" rows="2" class="w-full border border-gray-300 rounded p-2.5 outline-none focus:border-amber-500" required placeholder="Masukkan dasar surat baru..."></textarea>
        <button type="button" onclick="this.closest('.dasar-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash-alt"></i></button>
    `;
    container.appendChild(row);
}
function addPegawai() {
    const container = document.getElementById('pegawai-container');
    const row = document.createElement('div');
    row.className = 'pegawai-row bg-slate-50 p-5 rounded-md border border-slate-200 shadow-sm mt-4';
    const selectHtml = document.getElementById('master_pegawai_select').innerHTML;
    row.innerHTML = `
        <input type="hidden" name="pegawai_id[]" value="">
        <div class="mb-4 pb-4 border-b border-gray-200 flex gap-2 items-center">
            <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none font-semibold text-amber-700 cursor-pointer" onchange="fillPegawaiData(this)">
                ${selectHtml}
            </select>
            <button type="button" onclick="this.closest('.pegawai-row').remove()" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-500 hover:text-white"><i class="fas fa-trash-alt"></i></button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
            <div class="md:col-span-4">
                <label class="block text-xs font-semibold text-gray-600 mb-1">No. SPD</label>
                <div class="flex items-stretch">
                    <span class="bg-gray-200 border border-gray-300 border-r-0 rounded-l px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">000.1.2.3/</span>
                    <input type="text" name="no_spd[]" required class="w-full min-w-[3rem] border border-gray-300 p-2 text-sm outline-none text-center font-bold">
                    <span class="bg-gray-200 border border-gray-300 border-l-0 rounded-r px-2 flex items-center text-gray-600 text-[10px] font-bold whitespace-nowrap">/DPRPP/2026</span>
                </div>
            </div>
            <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">Nama</label><input type="text" name="nama[]" required class="peg-nama w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
            <div class="md:col-span-1">
                <label class="block text-xs font-semibold text-gray-600 mb-1">Status</label>
                <select name="jenis_nip[]" required class="peg-jenis-nip w-full border border-gray-300 rounded p-2 text-sm outline-none">
                    <option value="NIP.">NIP.</option>
                    <option value="NIPPPK.">NIPPPK.</option>
                    <option value="-">-</option>
                </select>
            </div>
            <div class="md:col-span-3"><label class="block text-xs font-semibold text-gray-600 mb-1">NIP</label><input type="text" name="nip[]" required class="peg-nip w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
            <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Pangkat</label><input type="text" name="pangkat[]" required class="peg-pangkat w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
            <div class="md:col-span-6"><label class="block text-xs font-semibold text-gray-600 mb-1">Jabatan</label><input type="text" name="jabatan[]" required class="peg-jabatan w-full border border-gray-300 rounded p-2 text-sm outline-none"></div>
        </div>
    `;
    container.appendChild(row);
}
</script>
{% endblock %}
"""

# STREAMING_CHUNK:Detail and Info Pages
TEMPLATE_DICT['detail.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="mb-4 flex justify-between items-center">
    <h2 class="text-2xl font-bold flex items-center gap-2"><i class="fas fa-folder-open text-blue-700"></i> Detail Dokumen Perjalanan</h2>
    <a href="{{ url_for('index') }}" class="text-blue-600 hover:text-blue-800 font-semibold transition"><i class="fas fa-arrow-left mr-1"></i> Kembali ke Dashboard</a>
</div>

<div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-6">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 border-b pb-4 gap-4">
        <div>
            <h3 class="text-xl font-bold text-gray-800">Informasi Surat Tugas</h3>
            <p class="text-sm text-gray-500 mt-1"><i class="fas fa-hashtag"></i> ID Referensi: {{ spt.id }} | Ditetapkan: {{ spt.tanggal_spt|tanggal if spt.tanggal_spt else spt.created_at|tanggal }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
            <a href="{{ url_for('print_spt', id=spt.id) }}" target="_blank" class="bg-blue-600 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-blue-700 shadow transition flex items-center gap-1"><i class="fas fa-print"></i> Cetak SPT</a>
            {% if spt.laporan_nama_kegiatan %}
            <a href="{{ url_for('laporan', id=spt.id) }}" class="bg-indigo-100 text-indigo-700 border border-indigo-300 px-4 py-2 rounded text-sm font-semibold hover:bg-indigo-200 transition flex items-center gap-1"><i class="fas fa-edit"></i> Edit Laporan Utama</a>
            {% else %}
            <a href="{{ url_for('laporan', id=spt.id) }}" class="bg-indigo-600 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-indigo-700 shadow transition flex items-center gap-1"><i class="fas fa-file-signature"></i> Buat Laporan Utama</a>
            {% endif %}
        </div>
    </div>
    
    <div class="bg-slate-50 p-4 rounded border border-slate-100">
        <table class="w-full text-sm">
            <tr><td class="w-48 py-1.5 text-gray-600 font-bold align-top">Maksud Tugas</td><td class="w-4 align-top py-1.5">:</td><td class="py-1.5 text-gray-800 align-top">
                {% if spt.jenis_spt != 'biasa' %}<span class="bg-purple-100 text-purple-800 text-[10px] font-bold px-2 py-0.5 rounded mr-1">KADIS</span>{% endif %}
                {% set maksuds = spt.maksud_tugas|from_json %}
                {{ maksuds|join(', ') }}
            </td></tr>
            <tr><td class="py-1.5 text-gray-600 font-bold align-top">Tujuan</td><td class="align-top py-1.5">:</td><td class="py-1.5 text-gray-800 align-top">
                {% set tujuans = spt.tempat_tujuan|from_json %}
                {% if tujuans|length > 0 %}
                    {% if tujuans[0] is string %}
                        {{ tujuans|join(', ') }}
                    {% else %}
                        {% for t in tujuans %}
                            {{ t.kota }}{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    {% endif %}
                {% else %}
                    -
                {% endif %} 
                (Dari: {{ spt.tempat_berangkat }})
            </td></tr>
            <tr><td class="py-1.5 text-gray-600 font-bold align-top">Tanggal & Durasi</td><td class="align-top py-1.5">:</td><td class="py-1.5 text-gray-800 align-top">{{ spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }} <span class="bg-yellow-200 text-yellow-800 px-2 py-0.5 rounded text-xs font-bold ml-2">{{ spt.lama_hari }} Hari</span></td></tr>
            <tr><td class="py-1.5 text-gray-600 font-bold align-top">Kendaraan</td><td class="align-top py-1.5">:</td><td class="py-1.5 text-gray-800 align-top">{{ spt.kendaraan }}</td></tr>
        </table>
    </div>
</div>

<h3 class="text-xl font-bold mb-4 text-gray-800 flex items-center gap-2"><i class="fas fa-user-tie text-blue-700"></i> Daftar Pegawai & Dokumen Individu (SPD / Kuitansi / Laporan)</h3>
<div class="grid grid-cols-1 gap-4">
    {% for peg in spt.pegawais %}
    <div class="bg-white p-5 rounded-lg shadow-sm border-l-4 border-blue-600 flex flex-col lg:flex-row justify-between items-center gap-4 hover:shadow-md transition">
        <div class="w-full lg:w-1/3">
            <p class="font-bold text-lg text-gray-900 mb-1">{{ loop.index }}. {{ peg.nama }}</p>
            <p class="text-sm text-gray-600 font-mono mb-1"><i class="far fa-id-badge w-4"></i> {{ peg.jenis_nip or 'NIP.' }} {{ peg.nip }}</p>
            <p class="text-sm text-gray-600"><i class="fas fa-briefcase w-4"></i> {{ peg.jabatan }} <span class="text-gray-400">|</span> {{ peg.pangkat }}</p>
        </div>
        <div class="w-full lg:w-1/4 lg:text-center bg-gray-50 p-2 rounded border border-gray-100">
            <p class="text-xs text-gray-500 font-bold uppercase tracking-wider mb-1">Total Biaya Perjalanan</p>
            {% if peg.grand_total > 0 %}
                <p class="text-xl font-black text-green-700">{{ peg.grand_total|rupiah }}</p>
            {% else %}
                <p class="text-sm font-semibold text-red-500 italic">Belum diinput</p>
            {% endif %}
        </div>
        <div class="w-full lg:w-auto flex flex-wrap gap-2 justify-start lg:justify-end mt-4 lg:mt-0">
            <!-- SPD & Laporan Group -->
            <div class="flex gap-1 border-r border-gray-200 pr-2 mr-1">
                <a href="{{ url_for('print_spd', peg_id=peg.id) }}" target="_blank" class="bg-teal-600 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-teal-700 shadow transition flex items-center gap-1"><i class="fas fa-file-invoice"></i> SPD</a>
                {% if spt.laporan_nama_kegiatan %}
                <a href="{{ url_for('print_laporan', peg_id=peg.id) }}" target="_blank" class="bg-indigo-600 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-indigo-700 shadow transition flex items-center gap-1"><i class="fas fa-print"></i> Laporan</a>
                {% endif %}
            </div>

            <!-- Keuangan Group -->
            <div class="flex gap-1">
                <a href="{{ url_for('kwitansi', peg_id=peg.id) }}" class="bg-yellow-500 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-yellow-600 shadow transition flex items-center gap-1"><i class="fas fa-calculator"></i> Kuitansi</a>
                {% if peg.grand_total > 0 %}
                <a href="{{ url_for('print_kwitansi', peg_id=peg.id) }}" target="_blank" class="bg-orange-600 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-orange-700 shadow transition flex items-center gap-1"><i class="fas fa-print"></i> Cetak</a>
                {% endif %}
                
                <a href="{{ url_for('pengeluaran_riil', peg_id=peg.id) }}" class="bg-blue-500 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-blue-600 shadow transition flex items-center gap-1 ml-1"><i class="fas fa-pencil-alt"></i> P. Riil</a>
                {% if peg.total_pengeluaran_riil > 0 %}
                <a href="{{ url_for('print_pengeluaran_riil', peg_id=peg.id) }}" target="_blank" class="bg-indigo-600 text-white px-3 py-2 rounded text-sm font-semibold hover:bg-indigo-700 shadow transition flex items-center gap-1"><i class="fas fa-print"></i> Cetak</a>
                {% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

TEMPLATE_DICT['print_base.html'] = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Cetak Dokumen - {{ title }}</title>
    <style>
        @media print {
            body { background-color: white !important; -webkit-print-color-adjust: exact; }
            .no-print { display: none !important; }
            .page-break { page-break-before: always; }
            @page { margin: 1.5cm; }
        }
        body { font-family: Arial; color: black; line-height: 1.3; }
        table { border-collapse: collapse; }
        .w-full { width: 100%; }
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .text-justify { text-align: justify; }
        .font-bold { font-weight: bold; }
        .italic { font-style: italic; }
        .uppercase { text-transform: uppercase; }
        .capitalize { text-transform: capitalize; }
        .border-black { border: 1px solid black; }
        .p-1 { padding: 4px; }
        .p-2 { padding: 8px; }
        .align-top { vertical-align: top; }
        .leading-tight { line-height: 1.1; }
        .mb-4 { margin-bottom: 16px; }
        .mb-6 { margin-bottom: 24px; }
        .mt-4 { margin-top: 16px; }
    </style>
</head>
<body style="background-color: #f3f4f6; margin: 0; padding: 20px;">
    <div style="max-width: 800px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); position: relative; min-height: 100vh;" class="print-container">
        
        {% if not hide_base_kop %}
        <!-- Reusable Kop Surat dengan Logo -->
        <div class="kop-surat mb-6">
            <table class="w-full" style="margin-bottom: -5px;">
                <tr>
                    <td style="width: 100px; text-align: center; vertical-align: middle;">
                        <img src="/logo.png" alt="Logo Daerah" style="width: 95px; height: auto; margin: 0 auto;">
                    </td>
                    <td style="text-align: center; vertical-align: middle; padding-right: 2px;">
                        <h1 style="font-size: 14pt; text-transform: uppercase; margin: 0; line-height: 1;">PEMERINTAH DAERAH KABUPATEN KOTABARU</h1>
                        <h2 style="font-size: 18pt; font-weight: bold; text-transform: uppercase; margin: 4px 0 0 0; line-height: 1.1;">DINAS PERUMAHAN RAKYAT, PERMUKIMAN<br>DAN PERTANAHAN</h2>
                        <p style="font-size: 8pt; margin: 4px 0 0 0; line-height: 1;">Jl. Meranti Kuning No.3 Desa Sebelimbingan, Pulaulaut Utara, Kotabaru - Kalimantan Selatan 72114<br>
                        Website : dprpp.kotabarukab.go.id, Email : <span style="color: #1d4ed8; text-decoration: underline;">dprpp@kotabarukab.go.id</span></p>
                    </td>
                </tr>
            </table>
            <div style="width: 100%; border-bottom: 4px solid black; padding-bottom: 2px;"></div>
            <div style="width: 100%; border-bottom: 1px solid black; margin-top: 2px;"></div>
        </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </div>
    <button onclick="window.print()" class="no-print" style="position: fixed; bottom: 40px; right: 40px; background: #2563eb; color: white; padding: 12px 24px; border-radius: 9999px; border: none; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">Cetak</button>
</body>
<style>
@media print {
    body { background-color: white !important; padding: 0 !important; }
    .print-container { box-shadow: none !important; padding: 0 !important; max-width: 100% !important; min-height: 0 !important; }
}
</style>
</html>
"""

TEMPLATE_DICT['print_spt.html'] = """
{% extends "print_base.html" %}
{% block content %}

{% if spt.jenis_spt == 'kadis_bupati' %}
    <!-- BUPATI KOTABARU KOP & LAYOUT -->
    <style>
        .footer-bupati { position: absolute; bottom: 10mm; left: 15mm; right: 15mm; text-align: center; font-size: 8pt; border-top: 1px solid black; padding-top: 5px; }
        @media print { .footer-bupati { position: fixed; } }
    </style>
    <div class="text-center mb-6 mt-4">
        <h1 style="font-size: 16pt; font-weight: bold; margin-bottom: 20px; letter-spacing: 2px;">BUPATI KOTABARU</h1>
        <h3 class="font-bold uppercase" style="font-size: 14pt; margin-bottom: 4px;">SURAT PERINTAH TUGAS</h3>
        <p style="font-size: 11pt; margin: 0;">NOMOR: 000.1.2.3/{{ spt.no_spt }}/SETDA</p>
    </div>
{% elif spt.jenis_spt == 'kadis_sekda' %}
    <!-- SEKDA KOP & LAYOUT -->
    <div class="kop-surat mb-6">
        <table class="w-full" style="margin-bottom: -5px;">
            <tr>
                <td style="width: 100px; text-align: center; vertical-align: middle;">
                    <img src="/logo.png" alt="Logo Daerah" style="width: 75px; height: auto; margin: 0 auto;">
                </td>
                <td style="text-align: center; vertical-align: middle; padding-right: 2px;">
                    <h1 style="font-size: 14pt; text-transform: uppercase; margin: 0; line-height: 1;">PEMERINTAH DAERAH KABUPATEN KOTABARU</h1>
                    <h2 style="font-size: 20pt; font-weight: bold; text-transform: uppercase; margin: 4px 0 0 0; line-height: 1.1;">SEKRETARIAT DAERAH</h2>
                    <p style="font-size: 8pt; margin: 4px 0 0 0; line-height: 1;">Jl. Meranti Kuning No.3 Desa Sebelimbingan, Pulaulaut Utara, Kotabaru - Kalimantan Selatan 72114<br>
                    Website: kotabarukab.go.id, Email: setda@kotabarukab.go.id</p>
                </td>
            </tr>
        </table>
        <div style="width: 100%; border-bottom: 4px solid black; padding-bottom: 2px;"></div>
        <div style="width: 100%; border-bottom: 1px solid black; margin-top: 2px;"></div>
    </div>
    <div class="text-center mb-6">
        <h3 class="font-bold uppercase" style="font-size: 14pt; margin-bottom: 4px;">SURAT PERINTAH TUGAS</h3>
        <p style="font-size: 11pt; margin: 0;">NOMOR: 000.1.2.3/{{ spt.no_spt }}/SETDA</p>
    </div>
{% else %}
    <!-- BIASA KOP & LAYOUT -->
    <div class="text-center mb-6">
        <h3 class="font-bold uppercase" style="font-size: 14pt; margin-bottom: 2px;">SURAT PERINTAH TUGAS</h3>
        <p style="font-size: 11pt; margin: 0;">NOMOR: 000.1.2.3/{{ spt.no_spt }}/DPRPP</p>
    </div>
{% endif %}

<div class="text-justify" style="font-size: 11pt;">
    <table class="w-full mb-4">
        <tr>
            <td class="align-top" style="width: 80px; padding: 4px 0;">Dasar</td>
            <td class="align-top" style="width: 15px; padding: 4px 0;">:</td>
            <td class="align-top" style="padding: 4px 0;">
                <ol style="margin: 0; padding-left: 20px;">
                    {% set dasars = spt.dasar_surat|from_json %}
                    {% for d in dasars %}
                    <li>{{ d }}</li>
                    {% else %}
                    <li>Peraturan Presiden Republik Indonesia Nomor 33 Tahun 2020 tentang Standar Harga Satuan Regional.</li>
                    <li>Perbup Nomor 55 Tahun 2023 tentang perjalanan Dinas bagi Pejabat Negara, Pimpinan dan Anggota Dewan Perwakilan Rakyat Daerah, Pegawai Aparatur Sipil Negara, Tenaga non ASN dan Pihak Lain.</li>
                    <li>Dokumen Pelaksanaan Anggaran Dinas Perumahan Rakyat Permukiman dan Pertanahan Tahun Anggaran {{ spt.tanggal_berangkat.year }}.</li>
                    {% endfor %}
                </ol>
            </td>
        </tr>
    </table>

    <div class="text-center mb-4 mt-6 uppercase" style="letter-spacing: 2px;">MEMERINTAHKAN</div>

    <table class="w-full mb-4">
        <tr>
            <td class="align-top" style="width: 80px; padding: 4px 0;">Kepada</td>
            <td class="align-top" style="width: 15px; padding: 4px 0;">:</td>
            <td class="align-top" style="padding: 4px 0;">
                {% for peg in spt.pegawais %}
                <table class="w-full" style="margin-bottom: 12px;">
                    <tr>
                        <td class="align-top" style="width: 20px;">{% if spt.pegawais|length > 1 %}{{ loop.index }}.{% endif %}</td>
                        <td style="width: 100px;">Nama</td>
                        <td style="width: 15px;">:</td>
                        <td>{{ peg.nama }}</td>
                    </tr>
                    <tr>
                        <td></td>
                        <td>Pangkat/Gol.</td>
                        <td>:</td>
                        <td>{{ peg.pangkat }}</td>
                    </tr>
                    <tr>
                        <td></td>
                        <td>{{ peg.jenis_nip or 'NIP.' }}</td>
                        <td>:</td>
                        <td>{{ peg.nip }}</td>
                    </tr>
                    <tr>
                        <td></td>
                        <td>Jabatan</td>
                        <td>:</td>
                        <td>{{ peg.jabatan }}</td>
                    </tr>
                </table>
                {% endfor %}
            </td>
        </tr>
        <tr>
            <td class="align-top" style="padding: 8px 0;">Untuk</td>
            <td class="align-top" style="padding: 8px 0;">:</td>
            <td class="align-top text-justify" style="padding: 8px 0;">
                {% set maksuds = spt.maksud_tugas|from_json %}
                {% if maksuds|length > 1 %}
                    Dinas, dalam rangka:
                    <ol style="margin: 0; padding-left: 20px;">
                    {% for m in maksuds %}
                        <li>{{ m }}</li>
                    {% endfor %}
                    </ol>
                {% else %}
                    Dinas, dalam rangka {{ maksuds[0] }}
                {% endif %}
            </td>
        </tr>
        <tr>
            <td class="align-top" style="padding: 4px 0;">Waktu dan<br>Tempat</td>
            <td class="align-top" style="padding: 4px 0;">:</td>
            <td class="align-top" style="padding: 4px 0;">
                {% set tujuans = spt.tempat_tujuan|from_json %}
                {% if tujuans|length > 0 %}
                    {% if tujuans[0] is string %}
                        <!-- Fallback untuk data lama -->
                        {{ spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }} ke {{ tujuans|join(', ') }}.
                    {% else %}
                        <!-- Data baru menggunakan JSON Objek -->
                        {{ spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }} ke 
                        {% for t in tujuans %}
                            {{ t.kota }}{% if not loop.last %}, {% endif %}
                        {% endfor %}.
                    {% endif %}
                {% else %}
                    -
                {% endif %}
            </td>
        </tr>
    </table>
</div>

<div style="margin-top: 32px; display: flex; justify-content: flex-end; font-size: 11pt;">
    <div style="width: 320px;">
        <table class="w-full" style="margin-bottom: 8px;">
            <tr><td style="width: 90px; padding: 2px 0;">Ditetapkan di</td><td style="padding: 2px 0;">: Kotabaru</td></tr>
            <tr><td style="padding: 2px 0;">Pada tanggal</td><td style="padding: 2px 0;">: {{ spt.tanggal_spt|tanggal if spt.tanggal_spt else spt.created_at|tanggal }}</td></tr>
        </table>
        <p style="margin-top: 8px; margin-bottom: 80px;">{{ spt.ttd_spt_jabatan }},</p>
        <p style="margin: 0;">{{ spt.ttd_spt_nama }}</p>
        
        {% if spt.jenis_spt in ['kadis_bupati', 'kadis_sekda'] %}
            {% if spt.ttd_spt_pangkat and spt.ttd_spt_pangkat != '-' %}<p style="margin: 0;">{{ spt.ttd_spt_pangkat }}</p>{% endif %}
            {% if spt.ttd_spt_nip and spt.ttd_spt_nip != '-' %}<p style="margin: 0;">NIP. {{ spt.ttd_spt_nip }}</p>{% endif %}
        {% else %}
            <p style="margin: 0;">{{ spt.ttd_spt_pangkat }}</p>
            <p style="margin: 0;">NIP. {{ spt.ttd_spt_nip }}</p>
        {% endif %}
    </div>
</div>

{% if spt.jenis_spt == 'kadis_bupati' %}
<div class="footer-bupati">
    Alamat Kantor: Jl. Meranti Kuning No. 3 Desa Sebelimbingan, Pulaulaut Utara, Kotabaru - Kalimantan Selatan 72114<br>
    Website: kotabarukab.go.id, Email: setda@kotabarukab.go.id
</div>
{% endif %}

{% endblock %}
"""

TEMPLATE_DICT['print_spd.html'] = """
{% extends "print_base.html" %}
{% block content %}
{% set tujuans = spt.tempat_tujuan|from_json %}
{% set count_tujuan = tujuans|length %}

{# Deteksi apakah ini format lama (string kota) atau format baru (dict dengan tgl_tiba dan tgl_berangkat) #}
{% set is_new_format = count_tujuan > 0 and tujuans[0] is mapping %}

<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; font-size: 11pt;">
    <div style="width: 50%;"></div>
    <div style="width: 50%;">
        <table class="w-full">
            <tr><td style="width: 60px;">Nomor</td><td>: 000.1.2.3/{{ peg.no_spd }}/DPRPP/{{ spt.tanggal_berangkat.year }}</td></tr>
        </table>
    </div>
</div>

<h3 class="font-bold text-center uppercase" style="font-size: 14pt; text-decoration: underline; letter-spacing: 2px; margin-bottom: 16px;">SURAT PERJALANAN DINAS (SPD)</h3>

<table class="w-full border-black leading-tight" style="font-size: 11pt;">
    <tr>
        <td class="border-black p-1 text-center align-top" style="width: 30px;">1.</td>
        <td class="border-black p-1 align-top" style="width: 45%;">Pejabat yang memberi Perintah</td>
        <td class="border-black p-1 align-top">{{ spt.pejabat_pemberi_perintah }}</td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">2.</td>
        <td class="border-black p-1 align-top">Nama / {{ peg.jenis_nip or 'NIP.' }} Pegawai yang diperintah</td>
        <td class="border-black p-1 align-top">{{ peg.nama }} / {{ peg.nip }}</td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">3.</td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">Pangkat dan Golongan menurut PP No. 15 Tahun 2019</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">Jabatan</td></tr>
                <tr><td class="p-1 align-top">c.</td><td class="p-1 align-top" style="padding-left:0;">Tingkat Biaya Perjalanan Dinas</td></tr>
            </table>
        </td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">{{ peg.pangkat }}</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">{{ peg.jabatan }}</td></tr>
                <tr><td class="p-1 align-top">c.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.tingkat_biaya }}</td></tr>
            </table>
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">4.</td>
        <td class="border-black p-1 align-top">Maksud Perjalanan Dinas</td>
        <td class="border-black p-1 text-justify align-top">
            {% set maksuds = spt.maksud_tugas|from_json %}
            {% if maksuds|length > 1 %}
                <ol style="margin: 0; padding-left: 15px;">
                {% for m in maksuds %}
                    <li>{{ m }}</li>
                {% endfor %}
                </ol>
            {% else %}
                {{ maksuds[0] }}
            {% endif %}
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">5.</td>
        <td class="border-black p-1 align-top">Alat angkut yang dipergunakan</td>
        <td class="border-black p-1 align-top">{{ spt.kendaraan }}</td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">6.</td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">Tempat berangkat</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">Tempat tujuan</td></tr>
            </table>
        </td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.tempat_berangkat }}</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">
                    {% if is_new_format %}
                        {% for t in tujuans %}
                            {{ t.kota }}{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    {% else %}
                        {{ tujuans|join(', ') }}
                    {% endif %}
                </td></tr>
            </table>
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">7.</td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">Lamanya Perjalanan Dinas</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">Tanggal berangkat</td></tr>
                <tr><td class="p-1 align-top">c.</td><td class="p-1 align-top" style="padding-left:0;">Tanggal harus Kembali/tiba di tempat baru</td></tr>
            </table>
        </td>
        <td class="border-black align-top" style="padding: 0;">
            <table class="w-full">
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.lama_hari }} ({{ spt.lama_hari|terbilang|lower }}) hari</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.tanggal_berangkat|tanggal }}</td></tr>
                <tr><td class="p-1 align-top">c.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.tanggal_kembali|tanggal }}</td></tr>
            </table>
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">8.</td>
        <td class="border-black align-top" style="padding: 0; height: 100%;">
            <table class="w-full" style="height: 100%;">
                <tr><td class="p-1 align-top" style="border-bottom: 1px solid black; height: 20px;">Pengikut : Nama</td></tr>
                <tr><td class="p-1 align-top">1.<br>2.<br>3.</td></tr>
            </table>
        </td>
        <td class="border-black align-top" style="padding: 0; height: 100%;">
            <table class="w-full" style="height: 100%;">
                <tr>
                    <td class="p-1 text-center align-top" style="width: 50%; border-bottom: 1px solid black; border-right: 1px solid black; height: 20px;">Tanggal Lahir</td>
                    <td class="p-1 text-center align-top" style="width: 50%; border-bottom: 1px solid black;">Keterangan</td>
                </tr>
                <tr>
                    <td class="p-1 align-top" style="border-right: 1px solid black;">&nbsp;<br>&nbsp;<br>&nbsp;</td>
                    <td class="p-1 align-top"></td>
                </tr>
            </table>
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">9.</td>
        <td class="border-black align-top" style="padding: 0; height: 100%;">
            <table class="w-full" style="height: 100%;">
                <tr><td colspan="2" class="p-1 align-top" style="border-bottom: 1px solid black; height: 20px;">Pembebanan Anggaran</td></tr>
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">Instansi</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">Akun</td></tr>
            </table>
        </td>
        <td class="border-black align-top" style="padding: 0; height: 100%;">
            <table class="w-full" style="height: 100%;">
                <tr><td colspan="2" class="p-1 align-top" style="border-bottom: 1px solid black; height: 20px;">&nbsp;</td></tr>
                <tr><td class="p-1 align-top" style="width: 25px;">a.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.instansi_pembebanan }}</td></tr>
                <tr><td class="p-1 align-top">b.</td><td class="p-1 align-top" style="padding-left:0;">{{ spt.akun_pembebanan }}</td></tr>
            </table>
        </td>
    </tr>
    <tr>
        <td class="border-black p-1 text-center align-top">10.</td>
        <td class="border-black p-1 align-top">Keterangan lain-lain</td>
        <td class="border-black p-1 align-top"></td>
    </tr>
</table>

<div style="margin-top: 16px; display: flex; justify-content: flex-end; font-size: 11pt;">
    <div style="width: 280px; text-align: left; line-height: 1.2;">
        <p style="margin: 0;">Dikeluarkan di Kotabaru</p>
        <p style="margin: 0 0 16px 0;">Tanggal {{ spt.tanggal_spt|tanggal if spt.tanggal_spt else spt.created_at|tanggal }}</p>
        <p class="font-bold" style="margin: 0 0 80px 0;">{{ spt.ttd_spd_jabatan }},</p>
        <p class="font-bold" style="text-decoration: underline; margin: 0;">{{ spt.ttd_spd_nama }}</p>
        <p style="margin: 0;">{{ spt.ttd_spd_pangkat }}</p>
        <p style="margin: 0;">NIP. {{ spt.ttd_spd_nip }}</p>
    </div>
</div>

<div class="page-break"></div>
<!-- ================= HALAMAN BELAKANG SPD ================= -->

<table class="w-full border-black leading-tight" style="font-size: 10pt; margin-top: 16px;">
    <!-- ROMAWI I -->
    <tr>
        <td class="border-black p-0 align-top" style="width: 50%; height: 100%;">
             <table class="w-full" style="height: 100%;"><tr><td class="p-2"></td></tr></table>
        </td>
        <td class="border-black p-2 align-top" style="width: 50%; height: 100%;">
            <table class="w-full">
                <tr><td class="align-top" style="width: 25px;">I.</td><td style="width: 110px;">Berangkat dari<br>(Tempat Kedudukan)</td><td>: {{ spt.tempat_berangkat }}</td></tr>
                <tr><td></td><td>Ke</td><td>: 
                    {% if is_new_format %}{{ tujuans[0].kota if count_tujuan > 0 else '' }}{% else %}{{ tujuans[0] if count_tujuan > 0 else '' }}{% endif %}
                </td></tr>
                <tr><td></td><td>Pada Tanggal</td><td>: {{ spt.tanggal_berangkat|tanggal }}</td></tr>
            </table>
            <div class="text-center" style="margin-top: 16px;">
                <p class="uppercase" style="margin: 0;">{{ spt.ttd_spd_jabatan }},</p>
                <p class="font-bold uppercase" style="text-decoration: underline; margin: 60px 0 0 0;">{{ spt.ttd_spd_nama }}</p>
                <p style="margin: 0;">NIP. {{ spt.ttd_spd_nip }}</p>
            </div>
        </td>
    </tr>

    <!-- ROMAWI II -->
    <tr>
        <td class="border-black p-2 align-top" style="width: 50%; border-right: 1px solid black;">
            <table class="w-full">
                <tr><td class="align-top" style="width: 25px;">II.</td><td style="width: 100px;">Tiba di</td><td>: 
                    {% if is_new_format %}{{ tujuans[0].kota if count_tujuan > 0 else '' }}{% else %}{{ tujuans[0] if count_tujuan > 0 else '' }}{% endif %}
                </td></tr>
                <tr><td></td><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[0].tgl_tiba|tanggal if count_tujuan > 0 else '..........................' }}
                    {% else %}
                        {% if count_tujuan == 1 %}{{ spt.tanggal_berangkat|tanggal }}{% else %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
        </td>
        <td class="border-black p-2 align-top" style="width: 50%;">
            <table class="w-full">
                <tr><td style="width: 110px;">Berangkat dari</td><td>: 
                    {% if is_new_format %}{{ tujuans[0].kota if count_tujuan > 0 else '' }}{% else %}{{ tujuans[0] if count_tujuan > 0 else '' }}{% endif %}
                </td></tr>
                <tr><td>Ke</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[1].kota if count_tujuan > 1 else spt.tempat_berangkat }}
                    {% else %}
                        {{ tujuans[1] if count_tujuan > 1 else spt.tempat_berangkat }}
                    {% endif %}
                </td></tr>
                <tr><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[0].tgl_berangkat|tanggal if count_tujuan > 0 else '..........................' }}
                    {% else %}
                        {% if count_tujuan == 1 %}{{ spt.tanggal_kembali|tanggal }}{% else %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
        </td>
    </tr>

    <!-- ROMAWI III -->
    <tr>
        <td class="border-black p-2 align-top" style="width: 50%; height: 120px; border-right: 1px solid black;">
            <table class="w-full">
                <tr><td class="align-top" style="width: 25px;">III.</td><td style="width: 100px;">Tiba di</td><td>: 
                    {% if is_new_format %}{{ tujuans[1].kota if count_tujuan > 1 else '' }}{% else %}{{ tujuans[1] if count_tujuan > 1 else '' }}{% endif %}
                </td></tr>
                <tr><td></td><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[1].tgl_tiba|tanggal if count_tujuan > 1 else '..........................' }}
                    {% else %}
                        {% if count_tujuan > 1 %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            {% if count_tujuan > 1 %}
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
            {% endif %}
        </td>
        <td class="border-black p-2 align-top" style="width: 50%; height: 120px;">
            <table class="w-full">
                <tr><td style="width: 110px;">Berangkat from</td><td>: 
                    {% if is_new_format %}{{ tujuans[1].kota if count_tujuan > 1 else '' }}{% else %}{{ tujuans[1] if count_tujuan > 1 else '' }}{% endif %}
                </td></tr>
                <tr><td>Ke</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[2].kota if count_tujuan > 2 else (spt.tempat_berangkat if count_tujuan == 2 else '') }}
                    {% else %}
                        {{ tujuans[2] if count_tujuan > 2 else (spt.tempat_berangkat if count_tujuan == 2 else '') }}
                    {% endif %}
                </td></tr>
                <tr><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[1].tgl_berangkat|tanggal if count_tujuan > 1 else '..........................' }}
                    {% else %}
                        {% if count_tujuan > 1 %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            {% if count_tujuan > 1 %}
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
            {% endif %}
        </td>
    </tr>

    <!-- ROMAWI IV -->
    <tr>
        <td class="border-black p-2 align-top" style="width: 50%; height: 120px; border-right: 1px solid black;">
            <table class="w-full">
                <tr><td class="align-top" style="width: 25px;">IV.</td><td style="width: 100px;">Tiba di</td><td>: 
                    {% if is_new_format %}{{ tujuans[2].kota if count_tujuan > 2 else '' }}{% else %}{{ tujuans[2] if count_tujuan > 2 else '' }}{% endif %}
                </td></tr>
                <tr><td></td><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[2].tgl_tiba|tanggal if count_tujuan > 2 else '..........................' }}
                    {% else %}
                        {% if count_tujuan > 2 %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            {% if count_tujuan > 2 %}
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
            {% endif %}
        </td>
        <td class="border-black p-2 align-top" style="width: 50%; height: 120px;">
            <table class="w-full">
                <tr><td style="width: 110px;">Berangkat dari</td><td>: 
                    {% if is_new_format %}{{ tujuans[2].kota if count_tujuan > 2 else '' }}{% else %}{{ tujuans[2] if count_tujuan > 2 else '' }}{% endif %}
                </td></tr>
                <tr><td>Ke</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[3].kota if count_tujuan > 3 else (spt.tempat_berangkat if count_tujuan == 3 else '') }}
                    {% else %}
                        {{ tujuans[3] if count_tujuan > 3 else (spt.tempat_berangkat if count_tujuan == 3 else '') }}
                    {% endif %}
                </td></tr>
                <tr><td>Pada Tanggal</td><td>: 
                    {% if is_new_format %}
                        {{ tujuans[2].tgl_berangkat|tanggal if count_tujuan > 2 else '..........................' }}
                    {% else %}
                        {% if count_tujuan > 2 %}..........................{% endif %}
                    {% endif %}
                </td></tr>
            </table>
            {% if count_tujuan > 2 %}
            <div class="text-center" style="margin-top: 16px;">
                <p style="margin: 0;">....................................,</p>
                <p class="font-bold" style="margin: 60px 0 0 0;">(...................................)</p>
                <p style="margin: 0;">NIP. ...............................</p>
            </div>
            {% endif %}
        </td>
    </tr>

    <!-- ROMAWI V -->
    <tr>
        <td class="border-black p-2 align-top" style="width: 50%; border-right: 1px solid black;"></td>
        <td class="border-black p-2 align-top" style="width: 50%;">
            <table class="w-full">
                <tr><td class="align-top" style="width: 25px;">V.</td><td style="width: 110px;">Tiba Kembali di</td><td>: {{ spt.tempat_berangkat }}</td></tr>
                <tr><td></td><td>Pada Tanggal</td><td>: {{ spt.tanggal_kembali|tanggal }}</td></tr>
            </table>
            <p class="text-justify" style="margin: 8px 0;">Telah diperiksa, dengan keterangan bahwa perjalanan tersebut diatas benar dilakukan atas perintahnya dan semata-mata untuk kepentingan jabatan dalam waktu yang sesingkat-singkatnya.</p>
            <div class="text-center" style="margin-top: 8px;">
                <p class=style="margin: 0;">{{ spt.ttd_spd_jabatan }},</p>
                <p class="font-bold" style="text-decoration: underline; margin: 60px 0 0 0;">{{ spt.ttd_spd_nama }}</p>
                <p style="margin: 0;">NIP. {{ spt.ttd_spd_nip }}</p>
            </div>
        </td>
    </tr>
    <tr>
        <td colspan="2" class="border-black p-2">
            <strong>VI. Catatan Lain-lain</strong><br><br>
        </td>
    </tr>
    <tr>
        <td colspan="2" class="border-black p-2 text-justify">
            <strong>VII. PERHATIAN:</strong><br>
            PPK yang menerbitkan SPD, pegawai yang melakukan perjalanan dinas, para pejabat yang mengesahkan tanggal berangkat/tiba, serta bendahara pengeluaran bertanggung jawab berdasarkan peraturan-peraturan Keuangan Negara apabila negara menderita rugi akibat kesalahan, kelalaian dan kealpaannya.
        </td>
    </tr>
</table>
{% endblock %}
"""

# STREAMING_CHUNK:Financial Input Form
TEMPLATE_DICT['form_kwitansi.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center gap-3 mb-6 border-b pb-4">
        <i class="fas fa-money-check-alt text-3xl text-yellow-600"></i>
        <h2 class="text-2xl font-bold text-gray-800">Rincian Biaya Individu: {{ peg.nama }}</h2>
    </div>
    
    <div class="bg-blue-50 p-4 rounded mb-8 text-sm text-blue-800 border flex flex-col md:flex-row justify-between md:items-center gap-4">
        <div>
            <strong>Pangkat / Gol:</strong> {{ peg.pangkat }}<br>
            <strong>Lama Perjalanan:</strong> {{ peg.spt.lama_hari }} Hari 
            (Tujuan: 
                {% set tujuans = peg.spt.tempat_tujuan|from_json %}
                {% if tujuans|length > 0 %}
                    {% if tujuans[0] is string %}
                        {{ tujuans|join(', ') }}
                    {% else %}
                        {% for t in tujuans %}
                            {{ t.kota }}{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    {% endif %}
                {% else %}
                    -
                {% endif %} 
            )
        </div>
        <a href="{{ url_for('detail', id=peg.spt_id) }}" class="px-4 py-2 bg-white border border-blue-300 text-blue-700 rounded hover:bg-blue-100 transition font-semibold text-center"><i class="fas fa-arrow-left mr-1"></i> Kembali ke Detail</a>
    </div>

    <form method="POST" action="" id="kwitansiForm">
        <!-- TAMBAHAN: INFORMASI ANGGARAN & TANGGAL -->
        <h3 class="text-lg font-bold text-gray-700 mb-4">Informasi Anggaran & Kuitansi</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 bg-gray-50 p-5 rounded border border-gray-200">
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">UP / GU / TU / LS</label>
                <select name="kwitansi_jenis" class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700 cursor-pointer">
                    <option value="UP" {% if peg.kwitansi_jenis == 'UP' %}selected{% endif %}>UP</option>
                    <option value="GU" {% if peg.kwitansi_jenis == 'GU' or not peg.kwitansi_jenis %}selected{% endif %}>GU</option>
                    <option value="TU" {% if peg.kwitansi_jenis == 'TU' %}selected{% endif %}>TU</option>
                    <option value="LS" {% if peg.kwitansi_jenis == 'LS' %}selected{% endif %}>LS</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tahun Anggaran</label>
                <input type="text" name="kwitansi_tahun" value="{{ peg.kwitansi_tahun or peg.spt.tanggal_berangkat.year }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Kuitansi</label>
                <input type="date" name="kwitansi_tanggal" value="{{ peg.kwitansi_tanggal.strftime('%Y-%m-%d') if peg.kwitansi_tanggal else peg.spt.tanggal_kembali.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700">
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Kode Sub.Kegiatan</label>
                <input type="text" name="kwitansi_kode_sub" value="{{ peg.kwitansi_kode_sub or '1.04.01.2.06.0009' }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700">
            </div>
            <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Kode Rekening</label>
                <input type="text" name="kwitansi_kode_rek" value="{{ peg.kwitansi_kode_rek or '5.1.02.04.001.0001' }}" required class="w-full border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700">
            </div>
        </div>

        <h3 class="text-lg font-bold text-gray-700 mb-4">Komponen Perincian Biaya</h3>
        
        <div class="overflow-x-auto mb-4">
            <table class="w-full border-collapse border border-gray-300 text-sm">
                <thead>
                    <tr class="bg-gray-50">
                        <th class="border border-gray-300 p-3 w-12 text-center text-gray-700">No</th>
                        <th class="border border-gray-300 p-3 text-left text-gray-700">Perincian Biaya</th>
                        <th class="border border-gray-300 p-3 text-left w-48 text-gray-700">Jumlah (Rp)</th>
                        <th class="border border-gray-300 p-3 text-left w-48 text-gray-700">Keterangan</th>
                        <th class="border border-gray-300 p-3 w-16 text-center text-gray-700">Aksi</th>
                    </tr>
                </thead>
                <tbody id="rincian-body"></tbody>
            </table>
        </div>
        <button type="button" onclick="addRow()" class="text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
            Tambah Komponen Biaya
        </button>

        <h3 class="text-lg font-bold text-gray-700 mb-4 mt-10 border-t pt-6">Pejabat Penandatangan Kuitansi</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <!-- PENGGUNA ANGGARAN (PA) -->
            <div class="bg-blue-50 p-4 rounded border border-blue-100 shadow-sm">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Pengguna Anggaran (Mengetahui)</label>
                <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none mb-4 cursor-pointer font-semibold text-blue-700 shadow-sm focus:border-blue-500" onchange="fillKwitansiTtd(this, 'pa')">
                    <option value='{"nama":"", "nip":"", "jabatan":""}'>-- Pilih PA dari Master Data --</option>
                    {% for t in ttd_kwitansis %}
                    <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                    {% endfor %}
                </select>
                <input type="text" id="pa_jabatan" name="pa_jabatan" value="{{ peg.pa_jabatan or '' }}" placeholder="Jabatan PA" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none focus:border-blue-500">
                <input type="text" id="pa_nama" name="pa_nama" value="{{ peg.pa_nama or '' }}" placeholder="Nama PA" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none font-bold focus:border-blue-500">
                <input type="text" id="pa_nip" name="pa_nip" value="{{ peg.pa_nip or '' }}" placeholder="NIP PA" required class="w-full border border-gray-300 p-2 rounded outline-none focus:border-blue-500">
            </div>

            <!-- PPTK -->
            <div class="bg-indigo-50 p-4 rounded border border-indigo-100 shadow-sm">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Pejabat Pelaksana Teknis Kegiatan (PPTK)</label>
                <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none mb-4 cursor-pointer font-semibold text-indigo-700 shadow-sm focus:border-indigo-500" onchange="fillKwitansiTtd(this, 'pptk')">
                    <option value='{"nama":"", "nip":"", "jabatan":""}'>-- Pilih PPTK dari Master Data --</option>
                    {% for t in ttd_kwitansis %}
                    <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                    {% endfor %}
                </select>
                <input type="text" id="pptk_jabatan" name="pptk_jabatan" value="{{ peg.pptk_jabatan or '' }}" placeholder="Jabatan PPTK" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none focus:border-indigo-500">
                <input type="text" id="pptk_nama" name="pptk_nama" value="{{ peg.pptk_nama or '' }}" placeholder="Nama PPTK" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none font-bold focus:border-indigo-500">
                <input type="text" id="pptk_nip" name="pptk_nip" value="{{ peg.pptk_nip or '' }}" placeholder="NIP PPTK" required class="w-full border border-gray-300 p-2 rounded outline-none focus:border-indigo-500">
            </div>
            
            <!-- BENDAHARA -->
            <div class="bg-teal-50 p-4 rounded border border-teal-100 shadow-sm">
                <label class="block text-sm font-semibold text-gray-700 mb-2">Bendahara Pengeluaran (Lunas Dibayar)</label>
                <select class="w-full border border-gray-300 bg-white p-2 rounded outline-none mb-4 cursor-pointer font-semibold text-teal-700 shadow-sm focus:border-teal-500" onchange="fillKwitansiTtd(this, 'bendahara')">
                    <option value='{"nama":"", "nip":"", "jabatan":""}'>-- Pilih Bendahara dari Master --</option>
                    {% for t in ttd_kwitansis %}
                    <option value='{"nama":"{{t.nama}}", "nip":"{{t.nip}}", "jabatan":"{{t.jabatan}}"}'>{{ t.nama }} - {{ t.jabatan }}</option>
                    {% endfor %}
                </select>
                <input type="text" id="bendahara_jabatan" name="bendahara_jabatan" value="{{ peg.bendahara_jabatan or '' }}" placeholder="Jabatan Bendahara" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none focus:border-teal-500">
                <input type="text" id="bendahara_nama" name="bendahara_nama" value="{{ peg.bendahara_nama or '' }}" placeholder="Nama Bendahara" required class="w-full border border-gray-300 p-2 rounded mb-2 outline-none font-bold focus:border-teal-500">
                <input type="text" id="bendahara_nip" name="bendahara_nip" value="{{ peg.bendahara_nip or '' }}" placeholder="NIP Bendahara" required class="w-full border border-gray-300 p-2 rounded outline-none focus:border-teal-500">
            </div>
        </div>

        <div class="bg-slate-50 p-6 rounded-lg border border-slate-200 mt-8">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6">
                <h3 class="text-gray-600 font-bold text-xl uppercase tracking-wider">Total Jumlah:</h3>
                <span id="total-text" class="text-4xl font-black text-blue-600 mt-2 md:mt-0">Rp 0</span>
            </div>
            <div>
                <label class="block text-gray-600 font-bold mb-2">Terbilang:</label>
                <input type="text" id="terbilang-text" readonly class="w-full bg-white border border-gray-300 rounded-md p-3 text-gray-700 font-semibold outline-none shadow-sm" placeholder="Terisi otomatis...">
            </div>
        </div>
        
        <div class="mt-8 flex justify-end pt-4 border-t">
            <button type="submit" class="px-8 py-3 bg-yellow-600 text-white rounded-md font-bold text-lg hover:bg-yellow-700 transition shadow-lg flex items-center gap-2"><i class="fas fa-save"></i> Simpan Data Keuangan</button>
        </div>
    </form>
</div>

<script>
const existingData = [
    {% for r in peg.rincian_biayas %}
    { perincian: "{{ r.perincian }}", jumlah: {{ r.jumlah }}, keterangan: "{{ r.keterangan or '' }}" }{% if not loop.last %},{% endif %}
    {% endfor %}
];
const tbody = document.getElementById('rincian-body');

function renderRows() {
    tbody.innerHTML = '';
    if (existingData.length === 0) existingData.push({ perincian: '', jumlah: 0, keterangan: '' });
    existingData.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="border border-gray-300 p-2 text-center font-bold text-gray-600">${index + 1}</td>
            <td class="border border-gray-300 p-2"><input type="text" name="perincian[]" value="${item.perincian}" required placeholder="Contoh: Uang Harian Selama 3 Hari" class="w-full p-2 border border-gray-200 rounded outline-none focus:border-blue-500"></td>
            <td class="border border-gray-300 p-2"><input type="number" name="jumlah[]" value="${item.jumlah}" required min="0" oninput="hitungTotal()" class="jumlah-input w-full p-2 border border-gray-200 rounded outline-none focus:border-blue-500 text-right"></td>
            <td class="border border-gray-300 p-2"><input type="text" name="keterangan[]" value="${item.keterangan}" placeholder="-" class="w-full p-2 border border-gray-200 rounded outline-none focus:border-blue-500"></td>
            <td class="border border-gray-300 p-2 text-center"><button type="button" onclick="removeRow(${index})" class="text-red-500 border border-red-500 hover:bg-red-50 px-3 py-1 rounded transition"><i class="fas fa-minus"></i></button></td>
        `;
        tbody.appendChild(tr);
    });
    hitungTotal();
}
function addRow() { existingData.push({ perincian: '', jumlah: 0, keterangan: '' }); renderRows(); }
function removeRow(index) { if (existingData.length > 1) { existingData.splice(index, 1); renderRows(); } else { alert("Minimal harus ada 1 komponen biaya!"); } }
function hitungTotal() {
    let total = 0;
    document.querySelectorAll('.jumlah-input').forEach(input => total += parseInt(input.value) || 0);
    document.getElementById('total-text').innerText = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(total);
    document.getElementById('terbilang-text').value = terbilang(total) + " Rupiah.";
}
function terbilang(angka){
    angka=parseInt(angka);
    if(isNaN(angka)||angka<0)return "";
    if(angka===0)return "Nol";
    var bilangan=["","Satu","Dua","Tiga","Empat","Lima","Enam","Tujuh","Delapan","Sembilan","Sepuluh","Sebelas"];
    if(angka<12){
        return bilangan[angka];
    }else if(angka<20){
        return terbilang(angka-10)+" Belas";
    }else if(angka<100){
        return terbilang(Math.floor(angka/10))+" Puluh"+(angka%10?" "+terbilang(angka%10):"");
    }else if(angka<200){
        return "Seratus"+(angka%100?" "+terbilang(angka-100):"");
    }else if(angka<1000){
        return terbilang(Math.floor(angka/100))+" Ratus"+(angka%100?" "+terbilang(angka%100):"");
    }else if(angka<2000){
        return "Seribu"+(angka%1000?" "+terbilang(angka-1000):"");
    }else if(angka<1000000){
        return terbilang(Math.floor(angka/1000))+" Ribu"+(angka%1000?" "+terbilang(angka%1000):"");
    }else if(angka<1000000000){
        return terbilang(Math.floor(angka/1000000))+" Juta"+(angka%1000000?" "+terbilang(angka%1000000):"");
    }else if(angka<1000000000000){
        return terbilang(Math.floor(angka/1000000000))+" Miliar"+(angka%1000000000?" "+terbilang(angka%1000000000):"");
    }else if(angka<1000000000000000){
        return terbilang(Math.floor(angka/1000000000000))+" Triliun"+(angka%1000000000000?" "+terbilang(angka%1000000000000):"");
    }
    return "";
}
function fillKwitansiTtd(selectElement, type) {
    try {
        const data = JSON.parse(selectElement.value);
        document.getElementById(type + '_nama').value = data.nama;
        document.getElementById(type + '_nip').value = data.nip;
        document.getElementById(type + '_jabatan').value = data.jabatan;
    } catch (e) {}
}
renderRows();
</script>
{% endblock %}
"""

# STREAMING_CHUNK:Print Kwitansi Template
TEMPLATE_DICT['print_kwitansi.html'] = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Cetak Kuitansi - {{ peg.nama }}</title>
    <style>
        @media print {
            @page { size: A4 portrait; margin: 10mm 15mm; }
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background-color: white; }
            .no-print { display: none !important; }
            .page-break { page-break-before: always; }
            .sheet { box-shadow: none !important; margin: 0 !important; padding: 0 !important; }
        }
        body { font-family: Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px 0; }
        .no-print { text-align: center; margin-bottom: 20px; }
        .btn-print { padding: 10px 20px; background-color: #2563eb; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        
        .sheet { 
            background: white; 
            width: 210mm; 
            margin: 0 auto 20px auto; 
            padding: 10mm 15mm; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
            font-size: 11pt; color: black; line-height: 1.4; 
        }
        
        .top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; position: relative; }
        .identity { width: 330px; font-size: 10pt; }
        .identity div { display: flex; margin-bottom: 2px; }
        .identity b { width: 140px; font-weight: normal; }
        .identity span { width: 15px; text-align: center; }
        .identity em { font-style: normal; }
        
        h1.kuitansi-h1 { position: absolute; left: 50%; transform: translateX(-50%); top: 0; font-size: 20pt; font-weight: bold; letter-spacing: 5px; margin: 0; text-decoration: underline; }
        
        .box { border: 1px solid black; width: 250px; font-size: 10pt; }
        .box-title { text-align: center; border-bottom: 1px solid black; padding: 1px; }
        .book-row { display: flex; padding: 2px 5px; }
        .book-row span:first-child { width: 90px; }
        .book-row span:nth-child(2) { width: 60px; }
        .book-row b { width: 15px; font-weight: normal; text-align: center; }
        .book-row em { flex: 1; }
        
        .line { display: flex; font-size: 11pt; margin-bottom: 10px; }
        .line > span { width: 160px; }
        .line > b { width: 15px; font-weight: normal; text-align: center; }
        .line > div { flex: 1; }
        .justify { text-align: justify; }
        .capitalize { text-transform: capitalize; }
        
        .middle { display: flex; justify-content: space-between; margin-top: 15px; font-size: 11pt; }
        .amount { width: 35%; }
        .amount-row { display: flex; padding: 2px; }
        .amount-row:first-child { border: 0px solid black; border-bottom: none; }
        .amount-row:nth-child(2) { border-left: 0px solid black; border-right: 0px solid black; }
        .amount-row.total { border: 0px solid black; }
        .amount-label { width: 130px; }
        .amount-row.total .amount-label { font-weight: normal; }
        .amount-row span:nth-child(2) { width: 20px; text-align: center; }
        .amount-row span:nth-child(3) { width: 30px; }
        .amount-value { flex: 1; text-align: right; }
        
        .receiver { width: 45%; }
        .center { text-align: center; margin-top: 5px; }
        .receiver hr { border: none; border-top: 1px solid black; margin: 0 0 10px 0; }
        .receiver-data div { display: flex; margin-bottom: 4px; }
        .receiver-data span { width: 140px; }
        .receiver-data b { width: 15px; font-weight: normal; text-align: center; }
        .receiver-data em { font-style: normal; flex: 1; }
        
        .signatures { display: flex; justify-content: space-between; margin-top: 30px; font-size: 11pt; }
        .signatures div { width: 32%; text-align: center; }

        .kop-rincian-wrapper { margin-bottom: 24px; }
        .kop-table { width: 100%; margin-bottom: -10px; }
        .kop-table td { vertical-align: middle; }
        .kop-border-thick { width: 100%; border-bottom: 4px solid black; padding-bottom: 2px; }
        .kop-border-thin { width: 100%; border-bottom: 1px solid black; margin-top: 2px; }
        
        .rincian-title { font-weight: bold; font-size: 14pt; text-align: center; text-transform: uppercase; text-decoration: underline; margin-bottom: 24px; }
        
        .meta-table { width: 100%; margin-bottom: 16px; font-size: 11pt; }
        .meta-table td { padding: 4px 0; }
        
        .rincian-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 11pt; }
        .rincian-table th, .rincian-table td { border: 1px solid black; padding: 8px; vertical-align: top; }
        .rincian-table th { text-align: center; font-weight: bold; }
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .font-bold { font-weight: bold; }
        
        .rincian-ttd { display: flex; justify-content: space-between; margin-top: 16px; font-size: 11pt; }
        .rincian-ttd-box { width: 250px; }
    </style>
</head>
<body>
    <div class="no-print">
        <button class="btn-print" onclick="window.print()">Cetak Kuitansi / PDF</button>
    </div>

    <div class="sheet">
        <div class="top">
            <div class="identity">
                <div><b>UP/GU/TU/LS</b><span>:</span><em>{{ peg.kwitansi_jenis or 'GU' }}</em></div>
                <div><b>Kode Sub.Kegiatan</b><span>:</span><em>{{ peg.kwitansi_kode_sub or '1.04.01.2.06.0009' }}</em></div>
                <div><b>Kode Rekening</b><span>:</span><em>{{ peg.kwitansi_kode_rek or '5.1.02.04.001.0001' }}</em></div>
                <div><b>Tahun Anggaran</b><span>:</span><em>{{ peg.kwitansi_tahun or spt.tanggal_berangkat.year }}</em></div>
            </div>
            
            <h1 class="kuitansi-h1">KUITANSI</h1>
            
            <div class="box">
                <div class="box-title">Sudah dibayar dan dibukukan</div>
                <div class="book-row"><span class="paid-date">Tgl.</span><span>BKU No.</span><b>:</b><em></em></div>
                <div class="book-row"><span></span><span>BKP No.</span><b>:</b><em></em></div>
            </div>
        </div>

        <div class="line"><span>Terima dari</span><b>:</b><div>Bendahara Pengeluaran Dinas Perumahan Rakyat, Permukiman dan Pertanahan Kabupaten Kotabaru</div></div>
        <div class="line"><span>Banyaknya Uang</span><b>:</b><div><strong><i class="capitalize">{{ peg.grand_total|terbilang }} Rupiah.</i></strong></div></div>
        <div class="line">
            <span>Untuk Pembayaran</span><b>:</b>
            <div class="justify">
                {% set maksuds = spt.maksud_tugas|from_json %}
                {% set tujuans = spt.tempat_tujuan|from_json %}
                Biaya Perjalanan Dinas An. <strong>{{ peg.nama }}</strong> ke 
                {% if tujuans|length > 0 %}
                    {% if tujuans[0] is string %}
                        {{ tujuans|join(', ') }}
                    {% else %}
                        {% for t in tujuans %}
                            {{ t.kota }}{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    {% endif %}
                {% else %}
                    -
                {% endif %}
                pada Tanggal {{ spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }} dalam rangka {{ maksuds|join('; ') }} Berdasarkan SPD Nomor: 000.1.2.3/{{ peg.no_spd }}/DPRPP/{{ spt.tanggal_berangkat.year }}. Sub Kegiatan Penyelenggaraan Rapat Koordinasi dan Konsultasi SKPD. Bukti Surat Tugas Terlampir.
            </div>
        </div>

        <div class="middle">
            <div class="amount">
                <div class="amount-row"><span class="amount-label"><b>TERBILANG</b></span><span>:</span><span>Rp</span><span class="amount-value">{{ peg.grand_total|rupiah|replace('Rp ', '') }}</span></div>
                <div class="amount-row"><span class="amount-label"></span><span>:</span><span>Rp</span><span class="amount-value">0,00</span></div>
                <div class="amount-row total"><span class="amount-label">Jumlah dibayar</span><span>:</span><span>Rp</span><span class="amount-value">{{ peg.grand_total|rupiah|replace('Rp ', '') }}</span></div>
            </div>
            <div class="receiver">
                Kotabaru, {{ peg.kwitansi_tanggal|tanggal if peg.kwitansi_tanggal else spt.tanggal_kembali|tanggal }}<br>
                <div class="center">Yang menerima</div><br><br><hr>
                <div class="receiver-data">
                    <div><span>Nama</span><b>:</b><em>{{ peg.nama }}</em></div>
                    <div><span>Pangkat/Gol.Ruang</span><b>:</b><em>{{ peg.pangkat }}</em></div>
                    <div><span>Jabatan</span><b>:</b><em>{{ peg.jabatan }}</em></div>
                    <div><span>Alamat</span><b>:</b><em>Kotabaru</em></div>
                </div>
            </div>
        </div>

        <div class="signatures">
            <div>
                Mengetahui;<br>{{ peg.pa_jabatan or 'Pengguna Anggaran' }}<br><br><br><br>
                <b><u>{{ peg.pa_nama or '...................................' }}</u></b><br>NIP. {{ peg.pa_nip or '...................................' }}
            </div>
            <div>
                Setuju bayar<br>{{ peg.pptk_jabatan or 'Pejabat Pelaksana Teknis Kegiatan (PPTK)' }}<br><br><br>
                <b><u>{{ peg.pptk_nama or '...................................' }}</u></b><br>NIP. {{ peg.pptk_nip or '...................................' }}
            </div>
            <div>
                Lunas dibayar : ..........................<br>{{ peg.bendahara_jabatan or 'Bendahara Pengeluaran' }}<br><br><br><br>
                <b><u>{{ peg.bendahara_nama or '...................................' }}</u></b><br>NIP. {{ peg.bendahara_nip or '...................................' }}
            </div>
        </div>
    </div>

    <!-- Pemisah Halaman Saat Print -->
    <div class="page-break"></div>

    <div class="sheet">
        <div class="kop-rincian-wrapper">
            <table class="kop-table">
                <tr>
                    <td style="width: 100px; text-align: center;">
                        <img src="/logo.png" alt="Logo Daerah" style="width: 95px; height: auto; margin: 0 auto;">
                    </td>
                    <td style="text-align: center; vertical-align: middle; padding-right: 2px;">
                        <h1 style="font-size: 14pt; text-transform: uppercase; margin: 0; line-height: 1;">PEMERINTAH DAERAH KABUPATEN KOTABARU</h1>
                        <h2 style="font-size: 18pt; font-weight: bold; text-transform: uppercase; margin: 4px 0 0 0; line-height: 1.1;">DINAS PERUMAHAN RAKYAT, PERMUKIMAN<br>DAN PERTANAHAN</h2>
                        <p style="font-size: 8pt; margin: 4px 0 0 0; line-height: 1;">Jl. Meranti Kuning No.3 Desa Sebelimbingan, Pulaulaut Utara, Kotabaru - Kalimantan Selatan 72114<br>
                        Website : dprpp.kotabarukab.go.id, Email : <span style="color: #1d4ed8; text-decoration: underline;">dprpp@kotabarukab.go.id</span></p>
                    </td>
                </tr>
            </table>
            <div class="kop-border-thick"></div>
            <div class="kop-border-thin"></div>
        </div>

        <div class="rincian-title">RINCIAN BIAYA PERJALANAN DINAS</div>
        
        <table class="meta-table">
            <tr><td style="width: 150px;">Lampiran SPD Nomor</td><td style="width: 15px;">:</td><td>000.1.2.3/{{ peg.no_spd }}/DPRPP/{{ spt.tanggal_berangkat.year }}</td></tr>
            <tr><td>Tanggal</td><td>:</td><td>{{ spt.tanggal_berangkat|tanggal }}</td></tr>
        </table>

        <table class="rincian-table">
            <tr>
                <th style="width: 40px;">No.</th>
                <th>Perincian Biaya</th>
                <th style="width: 150px;">Jumlah (Rp)</th>
                <th style="width: 150px;">Keterangan</th>
            </tr>
            {% for rb in peg.rincian_biayas %}
            <tr>
                <td class="text-center">{{ loop.index }}</td>
                <td>{{ rb.perincian }}</td>
                <td class="text-right">{{ rb.jumlah|rupiah|replace('Rp ', '') }}</td>
                <td class="text-center">{{ rb.keterangan or '' }}</td>
            </tr>
            {% endfor %}
            <tr>
                <td class="text-center font-bold" colspan="2">Jumlah</td>
                <td class="text-right font-bold">{{ peg.grand_total|rupiah|replace('Rp ', '') }}</td>
                <td></td>
            </tr>
            <tr>
                <td colspan="4">
                    Terbilang : <span class="capitalize">{{ peg.grand_total|terbilang }} Rupiah.</span>
                </td>
            </tr>
        </table>

        <div class="rincian-ttd">
            <div class="rincian-ttd-box">
                <br><br>
                <p style="margin: 0 0 4px 0;">Telah dibayar sejumlah</p>
                <p class="font-bold" style="margin: 0 0 16px 0;">{{ peg.grand_total|rupiah|replace('Rp ', '') }}</p>
                <p style="margin: 0;">{{ peg.bendahara_jabatan or 'Bendahara Pengeluaran' }}</p>
                <p class="font-bold uppercase" style="text-decoration: underline; margin: 60px 0 0 0;">{{ peg.bendahara_nama or '...................................' }}</p>
                <p style="margin: 0;">NIP. {{ peg.bendahara_nip or '...................................' }}</p>
            </div>
            <div class="rincian-ttd-box">
                <p style="margin: 0 0 16px 0;">Kotabaru, {{ peg.kwitansi_tanggal|tanggal if peg.kwitansi_tanggal else spt.tanggal_kembali|tanggal }}</p>
                <p style="margin: 0 0 4px 0;">Telah menerima jumlah uang sebesar</p>
                <p class="font-bold" style="margin: 0 0 16px 0;">{{ peg.grand_total|rupiah|replace('Rp ', '') }}</p>
                <p style="margin: 0;">Yang Menerima,</p>
                <p class="font-bold uppercase" style="text-decoration: underline; margin: 60px 0 0 0;">{{ peg.nama }}</p>
                <p style="margin: 0;">{{ peg.jenis_nip or 'NIP.' }} {{ peg.nip }}</p>
            </div>
        </div> 

            </div>         
        </div>
        
    </div>
</body>
</html>
"""

TEMPLATE_DICT['form_laporan.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center gap-3 mb-6 border-b pb-4">
        <i class="fas fa-clipboard-check text-3xl text-green-600"></i>
        <h2 class="text-2xl font-bold text-gray-800">Laporan Hasil Perjalanan Dinas</h2>
    </div>
    
    <form method="POST" action="">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div><label class="block text-sm font-bold text-gray-700 mb-1">Kepada</label><input type="text" name="laporan_kepada" value="{{ spt.laporan_kepada or 'Kepala Dinas' }}" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500"></div>
            <div><label class="block text-sm font-bold text-gray-700 mb-1">Dari</label><input type="text" name="laporan_dari" value="{{ spt.laporan_dari or 'Sekretaris' }}" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500"></div>
            <div><label class="block text-sm font-bold text-gray-700 mb-1">Tanggal Laporan</label><input type="date" name="laporan_tanggal" value="{{ spt.laporan_tanggal.strftime('%Y-%m-%d') if spt.laporan_tanggal else spt.tanggal_kembali.strftime('%Y-%m-%d') }}" required class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500"></div>
            <div><label class="block text-sm font-bold text-gray-700 mb-1">Hal</label><input type="text" name="laporan_hal" value="{{ spt.laporan_hal or 'Laporan Perjalanan Dinas' }}" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500"></div>
        </div>

        <h3 class="font-bold text-gray-800 mb-2 border-l-4 border-green-500 pl-2">A. Dasar</h3>
        <p class="text-sm text-gray-600 mb-4 bg-gray-50 p-2 rounded border">Nomor SPT dan SPD akan otomatis terisi berdasarkan data sistem pada saat dicetak.</p>

        <h3 class="font-bold text-gray-800 mb-2 border-l-4 border-green-500 pl-2">B. Nama Kegiatan</h3>
        <textarea name="laporan_nama_kegiatan" rows="2" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500 mb-4">{{ spt.laporan_nama_kegiatan or 'DPA SKPD Dinas Perumahan Rakyat, Permukiman dan Pertanahan Kab. Kotabaru (1.04.01.2.06.0009) Sub Kegiatan Penyelenggaraan Rapat Koordinasi dan Konsultasi SKPD.' }}</textarea>

        <h3 class="font-bold text-gray-800 mb-2 border-l-4 border-green-500 pl-2">C. Waktu dan Tempat</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div><label class="block text-sm font-bold text-gray-700 mb-1">Tanggal Pelaksanaan</label><input type="text" name="laporan_waktu_tanggal" value="{{ spt.laporan_waktu_tanggal or spt.tanggal_berangkat|tanggal_range(spt.tanggal_kembali) }}" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500"></div>
            <div>
                <label class="block text-sm font-bold text-gray-700 mb-1">Tujuan</label>
                {% set tujuans = spt.tempat_tujuan|from_json %}
                {% if tujuans|length > 0 %}
                    {% if tujuans[0] is string %}
                        {% set default_tujuan = tujuans|join(', ') %}
                    {% else %}
                        {% set default_tujuan_list = [] %}
                        {% for t in tujuans %}
                            {% set _ = default_tujuan_list.append(t.kota) %}
                        {% endfor %}
                        {% set default_tujuan = default_tujuan_list|join(', ') %}
                    {% endif %}
                {% else %}
                    {% set default_tujuan = '-' %}
                {% endif %}
                <input type="text" name="laporan_waktu_tujuan" value="{{ spt.laporan_waktu_tujuan or default_tujuan }}" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500">
            </div>
        </div>

        <div class="flex justify-between items-center mb-2">
            <h3 class="font-bold text-gray-800 border-l-4 border-green-500 pl-2">D. Hasil Kegiatan</h3>
            <button type="button" onclick="addHasil()" class="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200 transition"><i class="fas fa-plus"></i> Tambah Poin</button>
        </div>
        <div id="hasil-container" class="space-y-3 mb-6">
            {% set hasils = spt.hasil_laporan|from_json %}
            {% for h in hasils %}
            <div class="flex gap-2 hasil-row">
                <textarea name="hasil_kegiatan[]" rows="3" class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500" required>{{ h }}</textarea>
                <button type="button" onclick="if(document.querySelectorAll('.hasil-row').length > 1) this.closest('.hasil-row').remove()" class="bg-red-50 text-red-500 px-3 rounded border border-red-200 hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash"></i></button>
            </div>
            {% else %}
            <div class="flex gap-2 hasil-row">
                <textarea name="hasil_kegiatan[]" rows="3" class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500" placeholder="Tuliskan hasil kegiatan disini..." required></textarea>
                <button type="button" onclick="if(document.querySelectorAll('.hasil-row').length > 1) this.closest('.hasil-row').remove()" class="bg-red-50 text-red-500 px-3 rounded border border-red-200 hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash"></i></button>
            </div>
            {% endfor %}
        </div>

        <h3 class="font-bold text-gray-800 mb-2 border-l-4 border-green-500 pl-2">E. Kesimpulan dan Saran</h3>
        <textarea name="laporan_kesimpulan" rows="4" class="w-full border border-gray-300 p-2 rounded outline-none focus:border-green-500 mb-6" placeholder="Tuliskan kesimpulan dan saran...">{{ spt.laporan_kesimpulan or 'Berisi kesimpulan sasaran' }}</textarea>

        <div class="flex justify-end gap-3 pt-4 border-t">
            <a href="{{ url_for('detail', id=spt.id) }}" class="px-5 py-2.5 bg-gray-200 text-gray-800 rounded font-bold hover:bg-gray-300 transition">Batal</a>
            <button type="submit" class="px-6 py-2.5 bg-green-700 text-white rounded font-bold shadow-md"><i class="fas fa-save"></i> Simpan Laporan</button>
        </div>
    </form>
</div>
<script>
function addHasil() {
    const container = document.getElementById('hasil-container');
    const row = document.createElement('div');
    row.className = 'flex gap-2 hasil-row';
    row.innerHTML = `
        <textarea name="hasil_kegiatan[]" rows="3" class="w-full border border-gray-300 rounded p-2 outline-none focus:border-green-500" placeholder="Tambahkan poin hasil kegiatan..." required></textarea>
        <button type="button" onclick="this.closest('.hasil-row').remove()" class="bg-red-50 text-red-500 px-3 rounded border border-red-200 hover:bg-red-500 hover:text-white transition"><i class="fas fa-trash"></i></button>
    `;
    container.appendChild(row);
}
</script>
{% endblock %}
"""

TEMPLATE_DICT['print_laporan.html'] = """
{% extends "print_base.html" %}
{% block content %}
<h3 class="font-bold text-center uppercase" style="font-size: 14pt; text-decoration: underline; letter-spacing: 2px; margin-top: 8px; margin-bottom: 24px;">LAPORAN PERJALANAN DINAS</h3>
<div style="font-size: 11pt;">
    <table class="w-full mb-6">
        <tr><td style="width: 100px; padding: 4px 0;">Kepada Yth</td><td style="width: 15px; padding: 4px 0;">:</td><td style="padding: 4px 0;">{{ spt.laporan_kepada }}</td></tr>
        <tr><td style="padding: 4px 0;">Dari</td><td style="padding: 4px 0;">:</td><td style="padding: 4px 0;">{{ spt.laporan_dari }}</td></tr>
        <tr><td style="padding: 4px 0;">Tanggal</td><td style="padding: 4px 0;">:</td><td style="padding: 4px 0;">{{ spt.laporan_tanggal|tanggal if spt.laporan_tanggal else spt.tanggal_kembali|tanggal }}</td></tr>
        <tr><td style="padding: 4px 0;">Hal</td><td style="padding: 4px 0;">:</td><td style="padding: 4px 0;">{{ spt.laporan_hal }}</td></tr>
    </table>

    <p class="font-bold" style="margin: 16px 0 8px 0;">A. DASAR</p>
    <div style="margin-left: 16px; margin-bottom: 16px;">
        <table class="w-full">
            <tr><td class="align-top" style="width: 110px;">No. Surat Tugas</td><td class="align-top" style="width: 15px;">:</td><td>000.1.2.3/{{ spt.no_spt }}/{% if spt.jenis_spt in ['kadis_bupati', 'kadis_sekda'] %}SETDA{% else %}DPRPP{% endif %} Tanggal Surat Tugas: {{ spt.tanggal_spt|tanggal if spt.tanggal_spt else spt.created_at|tanggal }}</td></tr>
            <tr><td class="align-top">No. SPD</td><td class="align-top">:</td>
                <td>
                    000.1.2.3/{{ peg.no_spd }}/DPRPP/{{ spt.tanggal_berangkat.year }} An. {{ peg.nama }}
                </td>
            </tr>
        </table>
    </div>

    <p class="font-bold" style="margin: 16px 0 8px 0;">B. NAMA KEGIATAN</p>
    <div class="text-justify" style="margin-left: 16px; margin-bottom: 16px;">
        {{ spt.laporan_nama_kegiatan }}
    </div>

    <p class="font-bold" style="margin: 16px 0 8px 0;">C. WAKTU DAN TEMPAT KEGIATAN</p>
    <div style="margin-left: 16px; margin-bottom: 16px;">
        <table class="w-full">
            <tr><td class="align-top" style="width: 110px;">Tanggal</td><td class="align-top" style="width: 15px;">:</td><td>{{ spt.laporan_waktu_tanggal }}</td></tr>
            <tr><td class="align-top">Tujuan</td><td class="align-top">:</td><td>{{ spt.laporan_waktu_tujuan }}</td></tr>
        </table>
    </div>

    <p class="font-bold" style="margin: 16px 0 8px 0;">D. HASIL KEGIATAN</p>
    <div class="text-justify" style="margin-left: 16px; margin-bottom: 16px;">
        <ol style="margin: 0; padding-left: 20px;">
            {% set hasils = spt.hasil_laporan|from_json %}
            {% for h in hasils %}
            <li style="margin-bottom: 8px; line-height: 1.5;">{{ h }}</li>
            {% endfor %}
        </ol>
    </div>

    <p class="font-bold" style="margin: 16px 0 8px 0;">E. KESIMPULAN DAN SARAN</p>
    <div class="text-justify" style="margin-left: 16px; margin-bottom: 40px; white-space: pre-wrap; line-height: 1.5;">{{ spt.laporan_kesimpulan }}</div>

    <div style="display: flex; justify-content: space-between; align-items: flex-start;"><br><br><br>
        <div style="width: 45%;"><br><br><br>
            <p style="margin-bottom: 24px; font-weight: bold;">YANG MEMBUAT LAPORAN</p>
            <table class="w-full">
                <tr>
                    <td class="align-top" style="width: 20px;">1)</td>
                    <td class="align-top">
                        {{ peg.nama }}<br>
                        {{ peg.jenis_nip or 'NIP.' }} {{ peg.nip }}
                    </td>
                </tr>
            </table>
        </div>
        <div style="width: 45%; text-align: left;">
            <table style="margin-bottom: 24px;">
                <tr><td style="width: 90px;">Dibuat di</td><td>: <span style="text-decoration: underline;">Kotabaru</span></td></tr>
                <tr><td>Pada Tanggal</td><td>: {{ spt.laporan_tanggal|tanggal if spt.laporan_tanggal else spt.tanggal_kembali|tanggal }}</td></tr>
            </table>
            <br><br>
            <p class="font-bold" style="margin-top: 24px;">( ................................... )</p>
        </div>
    </div>
</div>
{% endblock %}
"""

TEMPLATE_DICT['form_pengeluaran_riil.html'] = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto bg-white p-8 rounded-lg shadow border border-gray-200">
    <div class="flex items-center gap-3 mb-6 border-b pb-4">
        <i class="fas fa-receipt text-3xl text-blue-600"></i>
        <h2 class="text-2xl font-bold text-gray-800">Daftar Pengeluaran Riil: {{ peg.nama }}</h2>
    </div>
    
    <div class="bg-blue-50 p-4 rounded mb-6 text-sm text-blue-800 border">
        <p>Form ini digunakan untuk mencatat pengeluaran yang <strong>tidak memiliki bukti kuitansi/tiket resmi</strong> (contoh: 30% penginapan tanpa bill, transport darat non-tiket).</p>
    </div>

    <form method="POST" action="">
        <div class="mb-6 bg-gray-50 p-5 rounded border border-gray-200">
            <label class="block text-sm font-semibold text-gray-700 mb-1">Tanggal Dokumen Pengeluaran Riil</label>
            <input type="date" name="pengeluaran_riil_tanggal" value="{{ peg.pengeluaran_riil_tanggal.strftime('%Y-%m-%d') if peg.pengeluaran_riil_tanggal else peg.spt.tanggal_kembali.strftime('%Y-%m-%d') }}" required class="w-full md:w-1/3 border border-gray-300 p-2.5 rounded outline-none focus:border-blue-500 font-semibold text-gray-700">
            <p class="text-xs text-gray-500 mt-1">Biarkan default (Tanggal Kembali) jika tidak ada perubahan.</p>
        </div>

        <div class="overflow-x-auto mb-4">
            <table class="w-full border-collapse border border-gray-300 text-sm">
                <thead>
                    <tr class="bg-gray-50">
                        <th class="border border-gray-300 p-3 w-12 text-center text-gray-700">No</th>
                        <th class="border border-gray-300 p-3 text-left text-gray-700">Uraian Pengeluaran (Bisa ketik rumus, cth: Biaya Penginapan 30% x 1 Malam)</th>
                        <th class="border border-gray-300 p-3 text-left w-48 text-gray-700">Jumlah (Rp)</th>
                        <th class="border border-gray-300 p-3 w-16 text-center text-gray-700">Aksi</th>
                    </tr>
                </thead>
                <tbody id="riil-body"></tbody>
            </table>
        </div>
        
        <div class="flex justify-between items-center mb-8 border-b pb-6">
            <button type="button" onclick="addRow()" class="text-blue-600 border border-blue-500 bg-blue-50 px-4 py-2 rounded hover:bg-blue-100 transition text-sm font-semibold flex items-center gap-2">
                <i class="fas fa-plus"></i> Tambah Uraian
            </button>
            <div class="text-right">
                <span class="text-gray-600 font-bold uppercase mr-3">Total:</span>
                <span id="total-text" class="text-2xl font-black text-blue-600">Rp 0</span>
            </div>
        </div>

        <div class="flex justify-end gap-3 pt-4">
            <a href="{{ url_for('detail', id=peg.spt_id) }}" class="px-5 py-2.5 bg-gray-200 text-gray-800 rounded font-bold hover:bg-gray-300 transition">Batal</a>
            <button type="submit" class="px-6 py-2.5 bg-blue-700 text-white rounded font-bold shadow-md"><i class="fas fa-save mr-2"></i> Simpan P. Riil</button>
        </div>
    </form>
</div>

<script>
const existingData = [
    {% for pr in peg.pengeluaran_riils %}
    { uraian: "{{ pr.uraian|replace('"', '\\"') }}", jumlah: {{ pr.jumlah }} }{% if not loop.last %},{% endif %}
    {% endfor %}
];
const tbody = document.getElementById('riil-body');

function renderRows() {
    tbody.innerHTML = '';
    if (existingData.length === 0) existingData.push({ uraian: '', jumlah: 0 });
    existingData.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="border border-gray-300 p-2 text-center font-bold text-gray-600">${index + 1}</td>
            <td class="border border-gray-300 p-2"><input type="text" name="uraian[]" value="${item.uraian}" required placeholder="Contoh: Biaya Penginapan 3.316.000 x 30% x 1 Malam" class="w-full p-2 border border-gray-200 rounded outline-none focus:border-blue-500"></td>
            <td class="border border-gray-300 p-2"><input type="number" name="jumlah[]" value="${item.jumlah}" required min="0" oninput="hitungTotal()" class="jumlah-input w-full p-2 border border-gray-200 rounded outline-none focus:border-blue-500 text-right"></td>
            <td class="border border-gray-300 p-2 text-center"><button type="button" onclick="removeRow(${index})" class="text-red-500 border border-red-500 hover:bg-red-50 px-3 py-1 rounded transition"><i class="fas fa-minus"></i></button></td>
        `;
        tbody.appendChild(tr);
    });
    hitungTotal();
}
function addRow() { existingData.push({ uraian: '', jumlah: 0 }); renderRows(); }
function removeRow(index) { if (existingData.length > 1) { existingData.splice(index, 1); renderRows(); } }
function hitungTotal() {
    let total = 0;
    document.querySelectorAll('.jumlah-input').forEach(input => total += parseInt(input.value) || 0);
    document.getElementById('total-text').innerText = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(total);
}
renderRows();
</script>
{% endblock %}
"""

TEMPLATE_DICT['print_pengeluaran_riil.html'] = """
{% extends "print_base.html" %}
{% block content %}
<style>
    .kop-surat { display: none; } /* Form pengeluaran riil ini biasanya tidak pakai KOP surat */
</style>
<div style="padding-top: 20px;">
    <h3 class="text-center font-bold" style="font-size: 14pt; text-decoration: underline; margin-bottom: 24px; letter-spacing: 1px;">DAFTAR PENGELUARAN RIIL</h3>
    
    <div style="font-size: 11pt;">
        <p style="margin-bottom: 8px;">Yang bertandatangan di bawah ini:</p>
        <table style="margin-left: 20px; margin-bottom: 16px;">
            <tr><td style="width: 100px; padding: 2px 0;">Nama</td><td style="width: 15px;">:</td><td>{{ peg.nama }}</td></tr>
            <tr><td style="padding: 2px 0;">{{ peg.jenis_nip or 'NIP' }}</td><td>:</td><td>{{ peg.nip }}</td></tr>
            <tr><td style="padding: 2px 0;">Jabatan</td><td>:</td><td>{{ peg.jabatan }}</td></tr>
        </table>
        
        <p class="text-justify" style="margin-bottom: 10px; line-height: 1.5;">Berdasarkan Surat Perjalanan Dinas (SPD) Nomor: 000.1.2.3/{{ peg.no_spd }}/DPRPP/{{ spt.tanggal_berangkat.year }}, Tanggal {{ spt.tanggal_spt|tanggal if spt.tanggal_spt else spt.created_at|tanggal }}, dengan ini kami menyatakan dengan sesungguhnya bahwa :</p>
        
        <div style="display: flex; margin-bottom: 12px; line-height: 1.5;">
            <div style="width: 25px;">1.</div>
            <div class="text-justify" style="flex: 1;">
                Biaya transport dan/atau biaya penginapan sebagaimana tercantum dalam uraian di bawah ini yang tidak dapat diperoleh bukti-bukti pengeluarannya, meliputi:
            </div>
        </div>
        
        <table style="width: 90%; margin: 0 auto 16px 25px; border-collapse: collapse;">
            <tr>
                <th style="border: 1px solid black; padding: 6px; width: 40px; text-align: center;">No.</th>
                <th style="border: 1px solid black; padding: 6px; text-align: center;">Uraian</th>
                <th style="border: 1px solid black; padding: 6px; width: 150px; text-align: center;">Jumlah</th>
            </tr>
            {% for pr in peg.pengeluaran_riils %}
            <tr>
                <td style="border: 1px solid black; padding: 6px; text-align: center;">{{ loop.index }}.</td>
                <td style="border: 1px solid black; padding: 6px;">{{ pr.uraian }}</td>
                <td style="border: 1px solid black; padding: 6px; text-align: right;">Rp. {{ pr.jumlah|rupiah|replace('Rp ', '') }}</td>
            </tr>
            {% endfor %}
            <tr>
                <td colspan="2" style="border: 1px solid black; padding: 6px; text-align: center; font-weight: bold;">Jumlah</td>
                <td style="border: 1px solid black; padding: 6px; text-align: right; font-weight: bold;">Rp. {{ peg.total_pengeluaran_riil|rupiah|replace('Rp ', '') }}</td>
            </tr>
        </table>
        
        <div style="display: flex; margin-bottom: 16px; line-height: 1.5;">
            <div style="width: 25px;">2.</div>
            <div class="text-justify" style="flex: 1;">
                Jumlah uang tersebut pada angka 1 di atas benar-benar dikeluarkan dan digunakan untuk pelaksanaan Perjalanan Dinas dimaksud dan apabila di kemudian hari terdapat kelebihan atas pembayaran, saya bersedia untuk menyetorkan kelebihan tersebut ke Kas Daerah.
            </div>
        </div>
        
        <p class="text-justify" style="margin-bottom: 40px; line-height: 1.5;">Demikian daftar pengeluaran riil ini Saya buat dengan sebenarnya, untuk dipergunakan sebagaimana mestinya.</p>
        
        <div style="display: flex; justify-content: flex-end;">
            <div style="width: 300px; text-align: left;">
                <p style="margin: 0 0 4px 0;">Kotabaru, {{ peg.pengeluaran_riil_tanggal|tanggal if peg.pengeluaran_riil_tanggal else spt.tanggal_kembali|tanggal }}</p>
                <p style="margin: 0 0 16px 0;">Pelaksana Perjalanan Dinas,</p><br>
                
                <div style="margin-top: 10px; margin-bottom: 10px; border: 1px solid black; width: 80px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 8pt; color: gray; text-align: center; letter-spacing: 0.5px; padding: 2px;">
                    Materai<br>Rp.10.000
                </div>
                
                <p class="font-bold" style="text-decoration: underline; margin: 0;">({{ peg.nama }})</p>
                <p style="margin: 0;">{{ peg.jenis_nip or 'NIP.' }} {{ peg.nip }}</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

app.jinja_loader = DictLoader(TEMPLATE_DICT)

# STREAMING_CHUNK:App Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['logged_in'] = True
            flash('Selamat datang di Dashboard SIAP JALAN!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah!', 'error')
    return render_template('login.html', title="Login")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Anda telah berhasil keluar.', 'success')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        user = User.query.filter_by(username='admin').first()
        old_pass = request.form['old_password']
        new_pass = request.form['new_password']
        conf_pass = request.form['confirm_password']
        
        if not check_password_hash(user.password_hash, old_pass):
            flash('Password lama salah!', 'error')
        elif new_pass != conf_pass:
            flash('Konfirmasi password baru tidak cocok!', 'error')
        else:
            user.password_hash = generate_password_hash(new_pass)
            db.session.commit()
            flash('Password berhasil diubah!', 'success')
            return redirect(url_for('index'))
            
    return render_template('change_password.html', title="Ubah Password")

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'logo.png')

@app.route('/app_logo.png')
def serve_app_logo():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'logo_2.png')

@app.route('/master/pegawai')
@login_required
def master_pegawai():
    items = MasterPegawai.query.all()
    return render_template('master_index.html', title="Master Data Pegawai", items=items, 
                           add_url=url_for('master_pegawai_form'), edit_url_base='/master/pegawai/form', delete_url_base='/master/pegawai/delete')

@app.route('/master/pegawai/form', defaults={'id': None}, methods=['GET', 'POST'])
@app.route('/master/pegawai/form/<int:id>', methods=['GET', 'POST'])
@login_required
def master_pegawai_form(id):
    item = MasterPegawai.query.get(id) if id else None
    if request.method == 'POST':
        if not item:
            item = MasterPegawai()
            db.session.add(item)
        item.nama = request.form['nama']
        item.jenis_nip = request.form.get('jenis_nip', 'NIP.') # Handle NIP type
        item.nip = request.form['nip']
        item.pangkat = request.form['pangkat']
        item.jabatan = request.form['jabatan']
        db.session.commit()
        flash('Data Pegawai berhasil disimpan!', 'success')
        return redirect(url_for('master_pegawai'))
    return render_template('master_form.html', title="Form Data Pegawai", item=item, back_url=url_for('master_pegawai'))

@app.route('/master/pegawai/delete/<int:id>')
@login_required
def master_pegawai_delete(id):
    item = MasterPegawai.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Data Pegawai berhasil dihapus!', 'success')
    return redirect(url_for('master_pegawai'))

@app.route('/master/ttd_spt')
@login_required
def master_ttd_spt():
    items = MasterTtdSpt.query.all()
    return render_template('master_index.html', title="Master Penandatangan SPT", items=items, 
                           add_url=url_for('master_ttdspt_form'), edit_url_base='/master/ttd_spt/form', delete_url_base='/master/ttd_spt/delete')

@app.route('/master/ttd_spt/form', defaults={'id': None}, methods=['GET', 'POST'])
@app.route('/master/ttd_spt/form/<int:id>', methods=['GET', 'POST'])
@login_required
def master_ttdspt_form(id):
    item = MasterTtdSpt.query.get(id) if id else None
    if request.method == 'POST':
        if not item:
            item = MasterTtdSpt()
            db.session.add(item)
        item.nama = request.form['nama']
        item.nip = request.form['nip']
        item.pangkat = request.form['pangkat']
        item.jabatan = request.form['jabatan']
        db.session.commit()
        flash('Data Penandatangan SPT berhasil disimpan!', 'success')
        return redirect(url_for('master_ttd_spt'))
    return render_template('master_form.html', title="Form Penandatangan SPT", item=item, back_url=url_for('master_ttd_spt'))

@app.route('/master/ttd_spt/delete/<int:id>')
@login_required
def master_ttdspt_delete(id):
    item = MasterTtdSpt.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Data dihapus!', 'success')
    return redirect(url_for('master_ttd_spt'))

@app.route('/master/ttd_spd')
@login_required
def master_ttd_spd():
    items = MasterTtdSpd.query.all()
    return render_template('master_index.html', title="Master Penandatangan SPD", items=items, 
                           add_url=url_for('master_ttdspd_form'), edit_url_base='/master/ttd_spd/form', delete_url_base='/master/ttd_spd/delete')

@app.route('/master/ttd_spd/form', defaults={'id': None}, methods=['GET', 'POST'])
@app.route('/master/ttd_spd/form/<int:id>', methods=['GET', 'POST'])
@login_required
def master_ttdspd_form(id):
    item = MasterTtdSpd.query.get(id) if id else None
    if request.method == 'POST':
        if not item:
            item = MasterTtdSpd()
            db.session.add(item)
        item.nama = request.form['nama']
        item.nip = request.form['nip']
        item.pangkat = request.form['pangkat']
        item.jabatan = request.form['jabatan']
        db.session.commit()
        flash('Data Penandatangan SPD berhasil disimpan!', 'success')
        return redirect(url_for('master_ttd_spd'))
    return render_template('master_form.html', title="Form Penandatangan SPD", item=item, back_url=url_for('master_ttd_spd'))

@app.route('/master/ttd_spd/delete/<int:id>')
@login_required
def master_ttdspd_delete(id):
    item = MasterTtdSpd.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Data dihapus!', 'success')
    return redirect(url_for('master_ttd_spd'))

@app.route('/master/ttd_kwitansi')
@login_required
def master_ttd_kwitansi():
    items = MasterTtdKwitansi.query.all()
    return render_template('master_index.html', title="Master Penandatangan Kwitansi", items=items, 
                           add_url=url_for('master_ttdkwitansi_form'), edit_url_base='/master/ttd_kwitansi/form', delete_url_base='/master/ttd_kwitansi/delete')

@app.route('/master/ttd_kwitansi/form', defaults={'id': None}, methods=['GET', 'POST'])
@app.route('/master/ttd_kwitansi/form/<int:id>', methods=['GET', 'POST'])
@login_required
def master_ttdkwitansi_form(id):
    item = MasterTtdKwitansi.query.get(id) if id else None
    if request.method == 'POST':
        if not item:
            item = MasterTtdKwitansi()
            db.session.add(item)
        item.nama = request.form['nama']
        item.nip = request.form['nip']
        item.jabatan = request.form['jabatan']
        item.pangkat = request.form.get('pangkat', '')
        db.session.commit()
        flash('Data Penandatangan Kwitansi berhasil disimpan!', 'success')
        return redirect(url_for('master_ttd_kwitansi'))
    return render_template('master_form.html', title="Form Penandatangan Kwitansi", item=item, back_url=url_for('master_ttd_kwitansi'))

@app.route('/master/ttd_kwitansi/delete/<int:id>')
@login_required
def master_ttdkwitansi_delete(id):
    item = MasterTtdKwitansi.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Data dihapus!', 'success')
    return redirect(url_for('master_ttd_kwitansi'))

# STREAMING_CHUNK:App Routes Part 2
@app.route('/')
@login_required
def index():
    search_query = request.args.get('q')
    if search_query:
        term = f"%{search_query}%"
        # Mencari berdasarkan tujuan, maksud tugas, no spt, atau nama pegawai yang ditugaskan
        query = SPT.query.outerjoin(PegawaiTugas).filter(
            db.or_(
                SPT.tempat_tujuan.ilike(term),
                SPT.maksud_tugas.ilike(term),
                SPT.no_spt.ilike(term),
                PegawaiTugas.nama.ilike(term)
            )
        )
        raw_spts = query.order_by(SPT.id.desc()).all()
        
        # Menghapus duplikat hasil query jika ada >1 pegawai yg cocok di 1 SPT yang sama
        spts = []
        seen = set()
        for s in raw_spts:
            if s.id not in seen:
                spts.append(s)
                seen.add(s.id)
    else:
        spts = SPT.query.order_by(SPT.id.desc()).all()
        
    return render_template('index.html', title="Dashboard", spts=spts)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    spt_type = request.args.get('type', 'biasa')
    
    if request.method == 'POST':
        try:
            dasar_surat_list = request.form.getlist('dasar_surat[]')
            maksud_tugas_list = request.form.getlist('maksud_tugas[]')
            
            # Format baru untuk tempat tujuan
            tujuan_kota = request.form.getlist('tujuan_kota[]')
            tujuan_tiba = request.form.getlist('tujuan_tiba[]')
            tujuan_berangkat = request.form.getlist('tujuan_berangkat[]')
            
            tempat_tujuan_list = []
            for i in range(len(tujuan_kota)):
                if tujuan_kota[i].strip() != '':
                    tempat_tujuan_list.append({
                        "kota": tujuan_kota[i],
                        "tgl_tiba": tujuan_tiba[i],
                        "tgl_berangkat": tujuan_berangkat[i]
                    })
            
            spt = SPT(
                no_spt=request.form['no_spt'],
                tanggal_spt=datetime.strptime(request.form['tanggal_spt'], '%Y-%m-%d').date() if request.form.get('tanggal_spt') else datetime.now().date(),
                jenis_spt=request.form.get('jenis_spt', 'biasa'),
                dasar_surat=json.dumps(dasar_surat_list) if dasar_surat_list else None,
                maksud_tugas=json.dumps(maksud_tugas_list),
                tempat_berangkat=request.form['tempat_berangkat'],
                tempat_tujuan=json.dumps(tempat_tujuan_list),
                tanggal_berangkat=datetime.strptime(request.form['tanggal_berangkat'], '%Y-%m-%d').date(),
                tanggal_kembali=datetime.strptime(request.form['tanggal_kembali'], '%Y-%m-%d').date(),
                kendaraan=request.form['kendaraan'],
                pejabat_pemberi_perintah=request.form['pejabat_pemberi_perintah'],
                tingkat_biaya=request.form['tingkat_biaya'],
                instansi_pembebanan=request.form['instansi_pembebanan'],
                akun_pembebanan=request.form['akun_pembebanan'],
                ttd_spt_nama=request.form['ttd_spt_nama'],
                ttd_spt_jabatan=request.form['ttd_spt_jabatan'],
                ttd_spt_pangkat=request.form.get('ttd_spt_pangkat', '-'),
                ttd_spt_nip=request.form.get('ttd_spt_nip', '-'),
                ttd_spd_nama=request.form['ttd_spd_nama'],
                ttd_spd_jabatan=request.form['ttd_spd_jabatan'],
                ttd_spd_pangkat=request.form['ttd_spd_pangkat'],
                ttd_spd_nip=request.form['ttd_spd_nip']
            )
            db.session.add(spt)
            db.session.commit()

            no_spds = request.form.getlist('no_spd[]')
            namas = request.form.getlist('nama[]')
            jenis_nips = request.form.getlist('jenis_nip[]')
            nips = request.form.getlist('nip[]')
            pangkats = request.form.getlist('pangkat[]')
            jabatans = request.form.getlist('jabatan[]')

            for i in range(len(namas)):
                if namas[i].strip() != '':
                    peg = PegawaiTugas(
                        spt_id=spt.id,
                        no_spd=no_spds[i] if i < len(no_spds) else '-',
                        nama=namas[i],
                        jenis_nip=jenis_nips[i] if i < len(jenis_nips) else 'NIP.',
                        nip=nips[i],
                        pangkat=pangkats[i],
                        jabatan=jabatans[i]
                    )
                    db.session.add(peg)
            
            db.session.commit()
            flash('Berhasil membuat SPT dan menugaskan pegawai!', 'success')
            return redirect(url_for('detail', id=spt.id))
        except Exception as e:
            flash(f'Terjadi kesalahan saat menyimpan: {str(e)}', 'error')
    
    pegawais = MasterPegawai.query.all()
    ttd_spts = MasterTtdSpt.query.all()
    ttd_spds = MasterTtdSpd.query.all()
    return render_template('form.html', title="Buat SPT", pegawais=pegawais, ttd_spts=ttd_spts, ttd_spds=ttd_spds)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    spt = SPT.query.get_or_404(id)
    if request.method == 'POST':
        try:
            dasar_surat_list = request.form.getlist('dasar_surat[]')
            maksud_tugas_list = request.form.getlist('maksud_tugas[]')
            
            tujuan_kota = request.form.getlist('tujuan_kota[]')
            tujuan_tiba = request.form.getlist('tujuan_tiba[]')
            tujuan_berangkat = request.form.getlist('tujuan_berangkat[]')
            
            tempat_tujuan_list = []
            for i in range(len(tujuan_kota)):
                if tujuan_kota[i].strip() != '':
                    tempat_tujuan_list.append({
                        "kota": tujuan_kota[i],
                        "tgl_tiba": tujuan_tiba[i],
                        "tgl_berangkat": tujuan_berangkat[i]
                    })
            
            spt.no_spt = request.form['no_spt']
            if request.form.get('tanggal_spt'):
                spt.tanggal_spt = datetime.strptime(request.form['tanggal_spt'], '%Y-%m-%d').date()
            spt.jenis_spt = request.form.get('jenis_spt', 'biasa')
            spt.dasar_surat = json.dumps(dasar_surat_list) if dasar_surat_list else None
            spt.maksud_tugas = json.dumps(maksud_tugas_list)
            spt.tempat_berangkat = request.form['tempat_berangkat']
            spt.tempat_tujuan = json.dumps(tempat_tujuan_list)
            spt.tanggal_berangkat = datetime.strptime(request.form['tanggal_berangkat'], '%Y-%m-%d').date()
            spt.tanggal_kembali = datetime.strptime(request.form['tanggal_kembali'], '%Y-%m-%d').date()
            spt.kendaraan = request.form['kendaraan']
            
            spt.pejabat_pemberi_perintah = request.form['pejabat_pemberi_perintah']
            spt.tingkat_biaya = request.form['tingkat_biaya']
            spt.instansi_pembebanan = request.form['instansi_pembebanan']
            spt.akun_pembebanan = request.form['akun_pembebanan']
            
            spt.ttd_spt_nama = request.form['ttd_spt_nama']
            spt.ttd_spt_jabatan = request.form['ttd_spt_jabatan']
            spt.ttd_spt_pangkat = request.form.get('ttd_spt_pangkat', '-')
            spt.ttd_spt_nip = request.form.get('ttd_spt_nip', '-')

            spt.ttd_spd_nama = request.form['ttd_spd_nama']
            spt.ttd_spd_jabatan = request.form['ttd_spd_jabatan']
            spt.ttd_spd_pangkat = request.form['ttd_spd_pangkat']
            spt.ttd_spd_nip = request.form['ttd_spd_nip']

            pegawai_ids_submitted = request.form.getlist('pegawai_id[]')
            no_spds = request.form.getlist('no_spd[]') # Fix naming
            if not no_spds: # fallback if empty
                no_spds = request.form.getlist('no_spd[]')

            namas = request.form.getlist('nama[]')
            jenis_nips = request.form.getlist('jenis_nip[]')
            nips = request.form.getlist('nip[]')
            pangkats = request.form.getlist('pangkat[]')
            jabatans = request.form.getlist('jabatan[]')

            submitted_ids_clean = []
            
            for i in range(len(namas)):
                if namas[i].strip() != '':
                    pid = pegawai_ids_submitted[i] if i < len(pegawai_ids_submitted) else ''
                    
                    if pid:
                        peg = PegawaiTugas.query.get(int(pid))
                        if peg and peg.spt_id == spt.id:
                            peg.no_spd = no_spds[i] if i < len(no_spds) else '-'
                            peg.nama = namas[i]
                            peg.jenis_nip = jenis_nips[i] if i < len(jenis_nips) else 'NIP.'
                            peg.nip = nips[i]
                            peg.pangkat = pangkats[i]
                            peg.jabatan = jabatans[i]
                            submitted_ids_clean.append(peg.id)
                    else:
                        peg = PegawaiTugas(
                            spt_id=spt.id,
                            no_spd=no_spds[i] if i < len(no_spds) else '-',
                            nama=namas[i],
                            jenis_nip=jenis_nips[i] if i < len(jenis_nips) else 'NIP.',
                            nip=nips[i],
                            pangkat=pangkats[i],
                            jabatan=jabatans[i]
                        )
                        db.session.add(peg)
                        db.session.flush() 
                        submitted_ids_clean.append(peg.id)

            for peg in spt.pegawais:
                if peg.id not in submitted_ids_clean:
                    db.session.delete(peg)

            db.session.commit()
            flash('Berhasil mengubah SPT dan daftar pegawai!', 'success')
            return redirect(url_for('detail', id=spt.id))
        except Exception as e:
            flash(f'Terjadi kesalahan saat mengupdate: {str(e)}', 'error')

    pegawais = MasterPegawai.query.all()
    ttd_spts = MasterTtdSpt.query.all()
    ttd_spds = MasterTtdSpd.query.all()
    return render_template('edit.html', title="Edit SPT", spt=spt, pegawais=pegawais, ttd_spts=ttd_spts, ttd_spds=ttd_spds)

@app.route('/delete/<int:id>')
@login_required
def delete_spt(id):
    spt = SPT.query.get_or_404(id)
    db.session.delete(spt)
    db.session.commit()
    flash('Data SPT berhasil dihapus secara permanen.', 'success')
    return redirect(url_for('index'))

@app.route('/detail/<int:id>')
@login_required
def detail(id):
    spt = SPT.query.get_or_404(id)
    return render_template('detail.html', title="Manajemen Detail", spt=spt)

@app.route('/print/spt/<int:id>')
@login_required
def print_spt(id):
    spt = SPT.query.get_or_404(id)
    hide_base_kop = spt.jenis_spt in ['kadis_bupati', 'kadis_sekda']
    return render_template('print_spt.html', title="Cetak SPT", spt=spt, hide_base_kop=hide_base_kop)

@app.route('/print/spd/<int:peg_id>')
@login_required
def print_spd(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    return render_template('print_spd.html', title=f"Cetak SPD - {peg.nama}", peg=peg, spt=peg.spt)

@app.route('/laporan/<int:id>', methods=['GET', 'POST'])
@login_required
def laporan(id):
    spt = SPT.query.get_or_404(id)
    if request.method == 'POST':
        try:
            spt.laporan_kepada = request.form.get('laporan_kepada')
            spt.laporan_dari = request.form.get('laporan_dari')
            spt.laporan_tanggal = datetime.strptime(request.form['laporan_tanggal'], '%Y-%m-%d').date()
            spt.laporan_hal = request.form.get('laporan_hal')
            spt.laporan_nama_kegiatan = request.form.get('laporan_nama_kegiatan')
            spt.laporan_waktu_tanggal = request.form.get('laporan_waktu_tanggal')
            spt.laporan_waktu_tujuan = request.form.get('laporan_waktu_tujuan')
            
            hasil_list = request.form.getlist('hasil_kegiatan[]')
            spt.hasil_laporan = json.dumps(hasil_list) if hasil_list else None
            spt.laporan_kesimpulan = request.form.get('laporan_kesimpulan')
            
            db.session.commit()
            flash('Laporan Hasil Perjalanan Dinas berhasil disimpan!', 'success')
            return redirect(url_for('detail', id=spt.id))
        except Exception as e:
            flash(f'Terjadi kesalahan saat menyimpan: {str(e)}', 'error')

    return render_template('form_laporan.html', title="Isi Laporan", spt=spt)

@app.route('/print/laporan/<int:peg_id>')
@login_required
def print_laporan(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    return render_template('print_laporan.html', title="Cetak Laporan", spt=peg.spt, peg=peg)

# STREAMING_CHUNK:Financial Endpoints
@app.route('/kwitansi/<int:peg_id>', methods=['GET', 'POST'])
@login_required
def kwitansi(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    if request.method == 'POST':
        try:
            RincianBiaya.query.filter_by(pegawai_id=peg.id).delete()
            
            perincians = request.form.getlist('perincian[]')
            jumlahs = request.form.getlist('jumlah[]')
            keterangans = request.form.getlist('keterangan[]')
            
            for i in range(len(perincians)):
                if perincians[i].strip() != '':
                    jml = int(jumlahs[i]) if jumlahs[i].strip() else 0
                    rb = RincianBiaya(
                        pegawai_id=peg.id,
                        perincian=perincians[i],
                        jumlah=jml,
                        keterangan=keterangans[i]
                    )
                    db.session.add(rb)
            
            peg.pa_nama = request.form.get('pa_nama')
            peg.pa_nip = request.form.get('pa_nip')
            peg.pa_jabatan = request.form.get('pa_jabatan')
            peg.pptk_nama = request.form.get('pptk_nama')
            peg.pptk_nip = request.form.get('pptk_nip')
            peg.pptk_jabatan = request.form.get('pptk_jabatan')
            peg.bendahara_nama = request.form.get('bendahara_nama')
            peg.bendahara_nip = request.form.get('bendahara_nip')
            peg.bendahara_jabatan = request.form.get('bendahara_jabatan')
            
            peg.kwitansi_jenis = request.form.get('kwitansi_jenis')
            peg.kwitansi_kode_sub = request.form.get('kwitansi_kode_sub')
            peg.kwitansi_kode_rek = request.form.get('kwitansi_kode_rek')
            peg.kwitansi_tahun = request.form.get('kwitansi_tahun')
            
            # Update Tanggal Kuitansi
            tanggal_str = request.form.get('kwitansi_tanggal')
            if tanggal_str:
                peg.kwitansi_tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
            else:
                peg.kwitansi_tanggal = None
                    
            db.session.commit()
            flash(f'Rincian Biaya dan Penandatangan untuk {peg.nama} berhasil disimpan!', 'success')
            return redirect(url_for('detail', id=peg.spt_id))
        except Exception as e:
            flash(f"Terjadi kesalahan: {str(e)}", 'error')
    
    ttd_kwitansis = MasterTtdKwitansi.query.all()
    return render_template('form_kwitansi.html', title="Keuangan", peg=peg, ttd_kwitansis=ttd_kwitansis)

@app.route('/print/kwitansi/<int:peg_id>')
@login_required
def print_kwitansi(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    return render_template('print_kwitansi.html', title=f"Kwitansi - {peg.nama}", peg=peg, spt=peg.spt)

@app.route('/pengeluaran_riil/<int:peg_id>', methods=['GET', 'POST'])
@login_required
def pengeluaran_riil(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    if request.method == 'POST':
        try:
            PengeluaranRiil.query.filter_by(pegawai_id=peg.id).delete()
            
            uraians = request.form.getlist('uraian[]')
            jumlahs = request.form.getlist('jumlah[]')
            
            for i in range(len(uraians)):
                if uraians[i].strip() != '':
                    jml = int(jumlahs[i]) if jumlahs[i].strip() else 0
                    pr = PengeluaranRiil(
                        pegawai_id=peg.id,
                        uraian=uraians[i],
                        jumlah=jml
                    )
                    db.session.add(pr)
            
            # Simpan Tanggal P. Riil
            tanggal_str = request.form.get('pengeluaran_riil_tanggal')
            if tanggal_str:
                peg.pengeluaran_riil_tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
            else:
                peg.pengeluaran_riil_tanggal = None
            
            db.session.commit()
            flash(f'Daftar Pengeluaran Riil untuk {peg.nama} berhasil disimpan!', 'success')
            return redirect(url_for('detail', id=peg.spt_id))
        except Exception as e:
            flash(f"Terjadi kesalahan: {str(e)}", 'error')
    
    return render_template('form_pengeluaran_riil.html', title="Pengeluaran Riil", peg=peg)

@app.route('/print/pengeluaran_riil/<int:peg_id>')
@login_required
def print_pengeluaran_riil(peg_id):
    peg = PegawaiTugas.query.get_or_404(peg_id)
    return render_template('print_pengeluaran_riil.html', title=f"Daftar Pengeluaran Riil - {peg.nama}", peg=peg, spt=peg.spt)

# STREAMING_CHUNK:Initialization and Seeder
def seed_manual_data():
    """Seed data Pegawai dari list manual agar tidak perlu file Excel"""
    if MasterPegawai.query.count() == 0:
        data = [
            ("H. Akhmad Rozain, S.Ag, M.M.", "197005272003121008", "Pembina Tingkat I (IV/b)", "Sekretaris"),
            ("H. Rakhmadi, SE, M.Ec.Dev", "196909122003121006", "Pembina (IV/a)", "Kepala Bidang Kawasan Permukiman"),
            ("M. Bahrudin Hamdani, SE", "197009181992031000", "Penata Tingkat I (II/d)", "Kepala Bidang Perumahan Rakyat"),
            ("Abdul Sani, S.ST", "197905211999031001", "Penata Tingkat I (II/d)", "Kepala Bidang Pertanahan"),
            ("Ryra Wardhani, S.E", "198106102008012037", "Penata Muda Tingkat I (III/b)", "Kepala Sub Bagian Umum dan Kepegawaian"),
            ("Lindebora Hutasoit, S.ST, MM", "197309181997032004", "Pembina (IV/a)", "Penata Kelola Perumahan Ahli Muda"),
            ("Rudi, S.ST", "196909181990021002", "Penata Tingkat I (II/d)", "Penata Kelola Bangunan Gedung dan Kawasan Permukiman Ahli Muda"),
            ("Imilda Eridanus, S.Pi, M.Pt", "197705112008012018", "Penata Tingkat I (II/d)", "Penata Kelola Perumahan Ahli Muda"),
            ("Ujang Fansyurnadi, ST", "198203232010011007", "Penata Tingkat I (II/d)", "Penata Kelola Perumahan Ahli Muda"),
            ("Siti Yayuk Zulaicha S.ST", "198201182006042017", "Penata (III/c)", "Penelaah Teknis Kebijakan"),
            ("Mulyadi, S.Sos", "197807302006041010", "Penata (III/c)", "Penelaah Teknis Kebijakan"),
            ("Mahfudzah, ST", "198201032015032001", "Penata Muda Tingkat I (III/b)", "Kepala Sub Bagian Perencanaan dan Keuangan"),
            ("Muhammad Aswin, SE", "199110112019031010", "Penata Muda Tingkat I (III/b)", "Penelaah Teknis Kebijakan"),
            ("Vicka Saraswati Anungkarisma, ST", "199009152019032015", "Penata Muda Tingkat I (III/b)", "Penelaah Teknis Kebijakan"),
            ("Syarkani, SE, MM", "197806132008011025", "Penata Muda Tingkat I (III/b)", "Penelaah Teknis Kebijakan"),
            ("Untung Surapati", "196909201994031009", "Penata Muda Tingkat I (III/b)", "Pengadministrasi Perkantoran"),
            ("Hendy Yoga Nugraha, ST", "199006302019031009", "Penata Muda Tingkat I (III/b)", "Penelaah Teknis Kebijakan"),
            ("Ariadi Pirdaus, SM", "198303252009011006", "Penata Muda (III/a)", "Penelaah Teknis Kebijakan"),
            ("Eka Dwi Noorhayati, SM", "197811222010012009", "Penata Muda (III/a)", "Penelaah Teknis Kebijakan"),
            ("Salamutus Sa'adah, S.E", "199904132025042003", "Penata Muda (III/a)", "Perencana Ahli Pertama"),
            ("Muhammad Khairi Ihsan, S.Kom", "199511182025041002", "Penata Muda (III/a)", "Pranata Komputer Ahli Pertama"),
            ("Al-Qadar, S.Tr.T", "199707162025041001", "Penata Muda (III/a)", "Penata Kelola Bangunan Gedung dan Kawasan Permukiman Ahli Pertama"),
            ("Hidayat Taufiq Rahman, S.T", "199302012025041001", "Penata Muda (III/a)", "Penata Kelola Perumahan Ahli Pertama"),
            ("Akhmad Syahid, S.T", "199711202025041006", "Penata Muda (III/a)", "Teknisi Sarana dan Prasarana"),
            ("Ria Angraini", "198505082010012020", "Pengatur Tingkat I (II/d)", "Pengadministrasi Perkantoran"),
            ("Bambang Mulyadi", "198107172008011020", "Pengatur Tingkat I (II/d)", "Pengadministrasi Perkantoran"),
            ("Taufiqurrahman", "197907272010011010", "Penata Muda (III/c)", "Pengadministrasi Perkantoran"),
            ("Masliani", "198010292010012011", "Pengatur (II/b)", "Pengadministrasi Perkantoran"),
            ("Teguh Pambudi, A.Md", "199212302025041001", "Pengatur (II/b)", "Penata Bangunan Gedung dan Permukiman"),
            ("Muhammad Ansori Hidayat, A.Md.T", "199906042025041003", "Pengatur (II/b)", "Penata Bangunan Gedung dan Permukiman"),
            ("Rudi Alfiani", "198206232009011007", "Pengatur Muda Tingkat I (II/a)", "Pengadministrasi Perkantoran"),
            ("Norhasanah, SE", "198710132023212035", "Penata Muda (III/a)", "Arsiparis Ahli Pertama"),
            ("Alfian Noor, S.Kom", "198905182024211007", "Penata Muda (III/a)", "Pranata Komputer Ahli Pertama"),
            ("Heri Kusnadi, S.E", "197908052025211019", "Penata Muda (III/a)", "Analis Kebijakan Ahli Pertama"),
            ("Siti Jamaliyah", "200004182025212041", "-", "Operator Layanan Operasional"),
            ("Wahyudi Candra, SE", "198301092025211069", "-", "Penata Layanan Operasional"),
            ("Muzakkir Kesuma", "198909162025211114", "-", "Operator Layanan Operasional"),
            ("Said Alfiansyah, SE", "197906272025211059", "-", "Penata Layanan Operasional"),
            ("Minarni", "197403102025212024", "-", "Operator Layanan Operasional"),
            ("Mahpujah, SE", "198505172025212078", "-", "Penata Layanan Operasional"),
            ("Rahma Linda", "198301242025212044", "-", "Operator Layanan Operasional"),
            ("Septiana Tiara Putri, S.Pd", "199409122025212094", "-", "Penata Layanan Operasional"),
            ("Fahriani, S.Pd", "198912272025212111", "-", "Penata Layanan Operasional"),
            ("Muhammad Alboes Sedam, S.AP", "199205272025211110", "-", "Penata Layanan Operasional"),
            ("M. Almas Said. S, S.Kom", "6302061509980002", "-", "Operator Layanan Operasional"),
            ("Mika Herlida Putri", "6302064702030008", "-", "Operator Layanan Operasional"),
            ("Mauliscia H.S", "6302065505030005", "-", "Operator Layanan Operasional"),
            ("Nurul Hikmah, SH", "6302066801000005", "-", "Operator Layanan Operasional"),
            ("Sandi Akhmad Rifani", "6302062902000004", "-", "Operator Layanan Operasional"),
            ("Lucky Ika Nur Efendi", "6302061905070005", "-", "Operator Layanan Operasional"),
            ("Eka Nurul Hudaya, S.Ars", "6302064705950003", "-", "Operator Layanan Operasional"),
            ("Fajar Eka Saputra", "6302062208000007", "-", "Operator Layanan Operasional"),
            ("Akhmad Ridani", "6302062104760005", "-", "Petugas Keamanan"),
            ("Muhammad Nor Hata", "6302060710930010", "-", "Petugas Keamanan")
        ]
        for nama, nip, pangkat, jabatan in data:
            jn = '-' if pangkat == '-' else 'NIP.'
            db.session.add(MasterPegawai(nama=nama, nip=nip, jenis_nip=jn, pangkat=pangkat, jabatan=jabatan))
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
# --- AUTO MIGRATE NEW COLUMNS ---
        from sqlalchemy import text
        for table, col, col_def in [
            ('pegawai_tugas', 'pa_nama', 'VARCHAR(100)'),
            ('pegawai_tugas', 'pa_nip', 'VARCHAR(50)'),
            ('pegawai_tugas', 'pa_jabatan', 'VARCHAR(100)'),
            ('pegawai_tugas', 'pptk_nama', 'VARCHAR(100)'),
            ('pegawai_tugas', 'pptk_nip', 'VARCHAR(50)'),
            ('pegawai_tugas', 'pptk_jabatan', 'VARCHAR(100)'),
            ('pegawai_tugas', 'bendahara_nama', 'VARCHAR(100)'),
            ('pegawai_tugas', 'bendahara_nip', 'VARCHAR(50)'),
            ('pegawai_tugas', 'bendahara_jabatan', 'VARCHAR(100)'),
            ('pegawai_tugas', 'kwitansi_jenis', "VARCHAR(20) DEFAULT 'GU'"),
            ('pegawai_tugas', 'kwitansi_kode_sub', "VARCHAR(100) DEFAULT '1.04.01.2.06.0009'"),
            ('pegawai_tugas', 'kwitansi_kode_rek', "VARCHAR(100) DEFAULT '5.1.02.04.001.0001'"),
            ('pegawai_tugas', 'kwitansi_tahun', "VARCHAR(10)"),
            ('pegawai_tugas', 'kwitansi_tanggal', 'DATE'), # TANGGAL KUITANSI
            ('pegawai_tugas', 'pengeluaran_riil_tanggal', 'DATE'), # TANGGAL PENGELUARAN RIIL
            ('spt', 'tanggal_spt', 'DATE'), # TANGGAL PEMBUATAN SPT
            ('master_pegawai', 'jenis_nip', "VARCHAR(20) DEFAULT 'NIP.'"),
            ('pegawai_tugas', 'jenis_nip', "VARCHAR(20) DEFAULT 'NIP.'"),
            ('spt', 'dasar_surat', 'TEXT'),
            ('spt', 'jenis_spt', "VARCHAR(20) DEFAULT 'biasa'"), # Tambahan untuk Multi KOP SPT
            ('spt', 'laporan_kepada', 'VARCHAR(100)'),
            ('spt', 'laporan_dari', 'VARCHAR(100)'),
            ('spt', 'laporan_tanggal', 'DATE'),
            ('spt', 'laporan_hal', 'VARCHAR(255)'),
            ('spt', 'laporan_nama_kegiatan', 'TEXT'),
            ('spt', 'laporan_waktu_tanggal', 'VARCHAR(100)'),
            ('spt', 'laporan_waktu_tujuan', 'VARCHAR(255)'),
            ('spt', 'laporan_kesimpulan', 'TEXT')
        ]:
            try:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                db.session.commit()
            except Exception:
                db.session.rollback() # Diabaikan jika kolom sudah ada
        # -----------------------------------------
            
        seed_manual_data()
        
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            default_admin = User(username='admin', password_hash=generate_password_hash('admin'))
            db.session.add(default_admin)
            db.session.commit()
            
    app.run(debug=True, port=5000)