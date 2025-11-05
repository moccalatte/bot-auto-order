# Fixing Plan: Daftar Error & Solusi Bot Auto Order

Dokumen ini mencatat error yang ditemukan selama proses debugging dan solusi yang sudah diterapkan atau perlu dilakukan.

---

## 1. ✅ TELEGRAM_ADMIN_IDS & TELEGRAM_OWNER_IDS Tidak Terdeteksi [FIXED]

**Gejala:**
- Bot tidak mendeteksi admin/owner walaupun sudah diisi di `.env`.
- Error Pydantic:  
  ```
  Value error, Invalid TELEGRAM_ADMIN_IDS value [type=value_error, input_value=5473468582, input_type=int]
  ```

**Penyebab:**
- Field di Settings didefinisikan sebagai `List[int]`, tapi value dari `.env` kadang diparse sebagai integer, bukan string.
- Validator belum handle tipe integer langsung.

**Solusi: ✅ SELESAI**
- Updated validator di `src/core/config.py` untuk handle value bertipe `int`:
  ```python
  if isinstance(value, int):
      return [value]
  ```
- Format `.env` yang benar:
  ```
  TELEGRAM_ADMIN_IDS=5473468582
  TELEGRAM_OWNER_IDS=341404536
  ```
  Untuk banyak ID:
  ```
  TELEGRAM_ADMIN_IDS=5473468582,123456789
  TELEGRAM_OWNER_IDS=341404536,987654321
  ```

---

## 2. Port 9000 Sudah Digunakan (OSError: [Errno 98])

**Gejala:**
- Error saat menjalankan server webhook:
  ```
  OSError: [Errno 98] error while attempting to bind on address ('0.0.0.0', 9000): address already in use
  ```

**Solusi:**
- Cari proses yang menggunakan port 9000:
  ```
  sudo lsof -i :9000
  ```
- Kill proses tersebut:
  ```
  kill <PID>
  ```
- Atau ganti port di konfigurasi jika perlu.

**Catatan:**
Ini adalah error environment, bukan bug code. Pastikan port tidak konflik sebelum menjalankan server.

---

## 3. ✅ AttributeError: 'TelemetrySnapshot' object has no attribute '__dict__' [ALREADY FIXED]

**Gejala:**
- Error saat logging telemetry:
  ```
  AttributeError: 'TelemetrySnapshot' object has no attribute '__dict__'
  ```

**Penyebab:**
- Class menggunakan `@dataclass(slots=True)` sehingga tidak punya atribut `__dict__`.

**Status: ✅ SUDAH DIPERBAIKI**
- Code di `src/core/telemetry.py` sudah menggunakan `vars(self.snapshot).copy()` yang benar.

---

## 4. ✅ PTBUserWarning: No `JobQueue` set up [FIXED]

**Gejala:**
- Warning saat menjalankan bot:
  ```
  PTBUserWarning: No `JobQueue` set up. To use `JobQueue`, you must install PTB via `pip install "python-telegram-bot[job-queue]"`
  ```

**Solusi: ✅ SELESAI**
- Updated `requirements.txt` dari:
  ```
  python-telegram-bot[webhooks]==21.3
  ```
  menjadi:
  ```
  python-telegram-bot[webhooks,job-queue]==21.3
  ```
- Install ulang dependency:
  ```
  pip install -r requirements.txt
  ```

---

## 5. ✅ NameError: name 'ConversationHandler' is not defined [ALREADY FIXED]

**Gejala:**
- Error saat menjalankan bot:
  ```
  NameError: name 'ConversationHandler' is not defined
  ```

**Status: ✅ SUDAH DIPERBAIKI**
- Import sudah ada di `src/bot/handlers.py`:
  ```python
  from telegram.ext import ConversationHandler
  ```

---

## 6. Proses Tidak Bisa Dihentikan dengan Ctrl+C (SSH)

**Gejala:**
- Proses bot/server tidak berhenti dengan Ctrl+C di terminal SSH.

**Solusi:**
- Cari dan kill proses secara manual:
  ```
  ps aux | grep python
  kill <PID>
  ```
- Untuk port tertentu:
  ```
  sudo fuser -k 9000/tcp
  ```

**Catatan:**
Signal handling untuk graceful shutdown sudah dihandle oleh `python-telegram-bot` library secara default. Jika masih ada masalah, gunakan cara manual di atas atau jalankan dalam Docker dengan proper signal handling.

---

## 7. ✅ UX/UI Improvements - Pesan Bot & Keyboard [FIXED]

**Gejala & Permasalahan:**
- InlineKeyboard "semua produk" muncul di pesan kedua, harusnya di pesan pertama.
- Pesan pertama bot kurang rapi, tidak ada penekanan (bold) pada bagian penting.
- Menu "🧮 Calculator" bisa diakses customer, padahal harusnya hanya di admin settings.
- Semua respon pesan bot perlu dirapikan, harus ada penekanan (bold) pada bagian penting dan penggunaan emoji yang konsisten.
- Desain emoji pada reply keyboard dan pesan masih seperti desain lawas, perlu diperbarui agar lebih modern dan konsisten.

**Solusi: ✅ SELESAI**

### A. Welcome Message & Keyboard Structure
- ✅ Gabungkan inline keyboard kategori ke pesan pertama saat `/start`
- ✅ Format welcome message menggunakan HTML parse mode dengan bold pada bagian penting
- ✅ Statistik bot (total users, transaksi) sekarang menggunakan format `<b>bold</b>`
- ✅ Reply keyboard dikirim di pesan terpisah dengan instruksi yang jelas

**File yang diubah:** `src/bot/handlers.py` (fungsi `start`)

### B. Menu Calculator - Admin Only
- ✅ Hapus tombol "🧮 Calculator" dari main reply keyboard (customer view)
- Calculator tetap bisa diakses admin via command `/refund_calculator` dan `/set_calculator`

**File yang diubah:** `src/bot/keyboards.py` (fungsi `main_reply_keyboard`)

### C. Format Pesan dengan Bold & Emoji Konsisten
- ✅ `welcome_message`: Nama user dan store name di-bold, statistik di-bold
- ✅ `product_list_heading`: Judul daftar di-bold
- ✅ `product_list_line`: Nama produk, harga, stok, dan sold count di-bold
- ✅ `product_detail`: Label field penting di-bold (Harga, Stok, In Cart, Total)
- ✅ `cart_summary`: Judul dan total di-bold, disclaimer pakai italic
- ✅ `payment_prompt`: Section headers di-bold, nilai penting di-bold
- ✅ `payment_loading`: Text utama di-bold dengan emoji loading
- ✅ `payment_invoice_detail`: Headers di-bold, invoice ID pakai `<code>`, nilai penting di-bold
- ✅ `payment_expired`: Judul di-bold, invoice ID pakai `<code>`
- ✅ `payment_success`: Judul di-bold dengan checkmark, disclaimer pakai italic
- ✅ `generic_error`: Pesan utama di-bold

**File yang diubah:** `src/bot/messages.py` (semua fungsi template)

### D. Parse Mode HTML di Handlers
- ✅ Tambahkan `parse_mode=ParseMode.HTML` di semua fungsi yang mengirim pesan dengan template
- ✅ Locations: `handle_product_list`, `show_product_detail`, `text_router`, `callback_router`
- ✅ Total 10+ lokasi diperbaiki untuk konsistensi

**File yang diubah:** `src/bot/handlers.py` (berbagai fungsi)

---

## 8. ✅ Requirements.txt - Job Queue Support [FIXED]

**Status: ✅ SELESAI**
- Menambahkan `[job-queue]` ke dependency `python-telegram-bot`
- Ini menyelesaikan warning JobQueue dan memastikan scheduled tasks berjalan dengan baik

---

## Summary Status Perbaikan

| No | Issue | Status | File(s) Modified |
|----|-------|--------|------------------|
| 1 | TELEGRAM_ADMIN_IDS validator | ✅ Fixed | `src/core/config.py` |
| 2 | Port 9000 conflict | ⚠️ Manual | N/A (environment issue) |
| 3 | TelemetrySnapshot __dict__ | ✅ Already OK | `src/core/telemetry.py` |
| 4 | JobQueue warning | ✅ Fixed | `requirements.txt` |
| 5 | ConversationHandler import | ✅ Already OK | `src/bot/handlers.py` |
| 6 | Ctrl+C signal handling | ℹ️ Info | N/A (handled by PTB) |
| 7 | UX/UI improvements | ✅ Fixed | Multiple files |
| 8 | Requirements dependency | ✅ Fixed | `requirements.txt` |

---

## Checklist Testing Setelah Perbaikan

- [ ] Test `/start` command - pesan dan keyboard muncul dengan format benar
- [ ] Verify inline keyboard kategori ada di pesan pertama
- [ ] Test customer tidak bisa akses Calculator dari reply keyboard
- [ ] Test admin masih bisa akses `/refund_calculator` dan `/set_calculator`
- [ ] Test semua pesan menggunakan bold dengan benar (tidak ada error HTML parsing)
- [ ] Test payment flow - semua pesan terformat dengan baik
- [ ] Verify TELEGRAM_ADMIN_IDS bisa handle single ID dan multiple IDs
- [ ] Test JobQueue berjalan tanpa warning
- [ ] Test graceful shutdown dengan Ctrl+C

---

## Catatan Lanjutan

- ✅ Pastikan `.env` tidak ada karakter aneh, spasi, atau tanda kutip di value.
- ✅ Restart aplikasi setelah mengubah konfigurasi atau environment variable.
- ✅ Install ulang requirements: `pip install -r requirements.txt`
- ✅ Dokumentasikan error baru yang muncul di file ini untuk referensi tim.
- ✅ Semua perubahan UX/UI menggunakan HTML parse mode untuk konsistensi
- ✅ Bold digunakan untuk informasi penting, italic untuk disclaimer

---

## Next Steps (Opsional)

1. **Testing Menyeluruh**: Lakukan testing manual semua fitur untuk memastikan UX improvement tidak break existing functionality
2. **Admin Menu Review**: Review admin menu untuk memastikan semua pesan juga konsisten dengan format baru
3. **Documentation Update**: Update dokumentasi di `/docs` untuk mencerminkan perubahan UX
4. **Broadcast Messages**: Pastikan broadcast messages juga menggunakan parse mode yang benar
5. **Error Messages**: Review semua error messages untuk konsistensi format

---