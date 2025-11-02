# PROJECT RULES v3.5

Tujuan: panduan kolaborasi AI–manusia agar hasil stabil, efisien, dan aman token.

## ⚠️ Warning!

Jangan pernah ubah isi file `project_rules.md` ini.
Jika terjadi konflik antar aturan, AI harus memprioritaskan **aturan yang lebih spesifik terhadap tugas aktif.**

---

## 🧩 Lingkungan

* Cantumkan bahasa & versi terbaru atau paling stabil.
* Semua dependency wajib dijelaskan (nama + versi). Sertakan file `requirements.txt`, `package.json`, atau lockfile bila relevan.
* Cara run harus jelas (contoh: `./run.sh` atau `python main.py`).
* **Untuk proyek Python, wajib menggunakan virtual environment** (`venv`, `poetry`, atau sejenisnya) agar dependency terisolasi.
* Semua error harus ditangani dengan log yang jelas — **tidak boleh** `pass` tanpa pesan.
* Dilarang menambahkan dependensi eksternal besar tanpa izin (framework/cloud berat).
* **Selalu sertakan `.gitignore`** berisi daftar file yang tidak relevan atau berisiko jika diunggah ke repositori publik, seperti:

  ```
  __pycache__/
  *.log
  .env
  /venv/
  /node_modules/
  /dist/
  /build/
  *.sqlite
  *.db
  *.pem
  .DS_Store
  ```

  AI wajib menyesuaikan isi `.gitignore` sesuai bahasa dan struktur proyek.

---

## 🪶 Observability (Lightweight)

* Setiap proyek wajib memiliki **observability dasar:** logging, runtime metrics ringan, dan monitoring sederhana tanpa beban eksternal berat.
* Logging wajib aktif di semua mode (dev, test, production).
* Gunakan sistem logging **lightweight**, tidak bergantung pada service eksternal.
* Semua log disimpan di folder `/logs/` dengan struktur:

  ```
  /logs/{service}/{date}.log
  ```
* Runtime dan background process **harus menulis log real-time** (streaming ke file).
* Gunakan format log konsisten: `[timestamp] [level] message`.
* Tambahkan snapshot runtime metrics ringan (CPU, RAM, uptime, loop status) bila memungkinkan.
* Error fatal → log, lalu exit dengan kode 1.
* Hindari loop tanpa delay — wajib ada `sleep()` atau mekanisme backoff.
* Prioritaskan logging daripada GUI untuk debugging dan audit.
* Audit proyek harus bisa dilakukan **hanya lewat isi folder `/logs/`** tanpa akses IDE.

---

## 🧱 Struktur Kode

* Terapkan sistem **modular & clean structure**: pisahkan fungsi ke modul/folder sesuai tanggung jawab (misal `core/`, `utils/`, `services/`, `api/`, dll).
* Tujuan penerapan sistem modular: agar proyek mudah dimaintain, dan fitur dapat ditambah atau dihapus **tanpa menimbulkan error atau konflik besar**.
* Bila modularisasi penuh tidak memungkinkan, gunakan **best practice terdekat** agar kode tetap mudah dibaca dan dirawat.
* File tidak lebih dari **300–400 baris** setelah fitur stabil.
* Setiap file/fungsi hanya punya satu tanggung jawab (single responsibility).
* Gunakan folder standar:

  ```
  src/    → kode utama
  logs/   → semua log
  tests/  → uji sederhana (opsional)
  ```
* Semua fungsi publik harus punya docstring singkat (tujuan, argumen, return).
* Hindari refactor besar tanpa permintaan eksplisit.

---

## 🧩 Gaya Perubahan

* **Perubahan minimal:** patch kecil, bukan rewrite massal.
* Sertakan langkah verifikasi (cara cek fix berhasil).
* Setelah patch diterapkan, jalankan minimal **1 contoh input/output** untuk bukti hasil.
* Sertakan rollback plan (cara balik ke versi sebelum patch).

---

## 🧰 Protokol Debug

1. Ulangi error dengan jelas.
2. Catat environment (`php -v`, `python --version`, dll).
3. Lampirkan log/error singkat (10–20 baris).
4. Ajukan 2–3 hipotesis penyebab.
5. Terapkan patch kecil, bukan rewrite besar.
6. Verifikasi hasil lalu dokumentasikan di log.

---

## 🤖 AI Interaction

* Jika tidak yakin, AI wajib jelaskan **2–3 hipotesis**.
* Fokus jelaskan **kenapa error terjadi** sebelum kasih solusi.
* Dilarang rename/pindah file kecuali diminta.
* Semua hasil eksekusi atau perubahan harus muncul di log (termasuk runtime/background).
* Jika **aturan dalam file ini tidak sepenuhnya bisa diterapkan**, AI wajib:

  1. Menerapkan **best practice terdekat yang tidak menimbulkan konflik atau masalah.**
  2. Menyampaikan hal tersebut secara eksplisit di **akhir jawaban.**
* AI juga wajib membuat file **README.md** yang jelas dan **beginner-friendly**, berisi:

  * Penjelasan struktur dan fungsi utama.
  * Panduan setup langkah demi langkah.
  * Petunjuk testing dan jalankan produksi.
  * Penanda mana yang **wajib**, **opsional**, dan **rekomendasi.**

---

## ✍️ Output Policy

* Jawaban harus padat, langsung ke eksekusi, dan tidak bertele-tele.
* Hindari penjelasan teori umum, narasi panjang, atau paragraf tidak relevan kecuali diminta eksplisit.
* Gunakan format langkah atau blok kode, bukan cerita deskriptif.

---

## ⏹️ Stop Signal

* Akhiri jawaban dengan `✅ Done` setelah semua langkah selesai.
* Jangan menambahkan penutup lain, komentar reflektif, atau saran tambahan di luar konteks tugas.
