# Dokumentasi Integrasi Pakasir

_Diperbarui: 16 Oktober 2025_

## 1. Persiapan

1. Daftar atau masuk ke akun Pakasir Anda.
2. Buat Proyek untuk setiap aplikasi atau situs yang ingin diintegrasikan.

### 1.1 Proyek

- Proyek bertindak sebagai identitas aplikasi atau website Anda.
- Setiap proyek memiliki `slug` dan `api_key` yang dibutuhkan untuk integrasi.
- Simpan kedua nilai tersebut dengan aman karena akan digunakan pada setiap permintaan.

## 2. Integrasi Lewat URL

Gunakan pola URL berikut untuk mengarahkan pelanggan ke halaman pembayaran:

```
https://app.pakasir.com/pay/{slug}/{amount}?order_id={order_id}
```

Parameter:
- `slug`: diambil dari proyek yang Anda miliki.
- `amount`: nominal transaksi tanpa titik dan spasi, mis. `100000`.
- `order_id`: ID transaksi atau invoice di sistem Anda, mis. `INV20250910-123456`.

Contoh:

```
https://app.pakasir.com/pay/depodomain/22000?order_id=240910HDE7C9
```

### 2.1 Opsi Tambahan

**Custom redirect**

Tambahkan parameter `redirect=https://websitekamu.com/tujuan` untuk mengarahkan pengguna ke halaman tertentu setelah pembayaran selesai.

```
https://app.pakasir.com/pay/depodomain/22000?order_id=240910HDE7C9&redirect=https://app.depodomain.com/invoices
```

**Hanya QRIS**

Tambahkan `qris_only=1` agar pengguna langsung melihat QR code dan tidak dapat memilih metode lain.

```
https://app.pakasir.com/pay/depodomain/22000?order_id=240910HDE7C9&qris_only=1
```

**PayPal**

Ganti segmen `/pay/` menjadi `/paypal/` untuk langsung membuka halaman pembayaran PayPal.

```
https://app.pakasir.com/paypal/depodomain/22000?order_id=240910HDE7C9
```

## 3. Integrasi Lewat API

### 3.1 Gambaran Umum

Endpoint API akan mengembalikan data berikut:

- QR string atau nomor virtual account.
- Nominal pembayaran.
- Waktu kedaluwarsa.

Penampilan QR code atau nomor virtual account kepada pengguna menjadi tanggung jawab Anda. Gunakan library pembentuk QR sesuai kebutuhan.

### 3.2 Endpoint `transactioncreate`

```
POST https://app.pakasir.com/api/transactioncreate/{method}
```

Body JSON:

```json
{
  "project": "depodomain",
  "order_id": "INV123123",
  "amount": 99000,
  "api_key": "xxx123"
}
```

Contoh `curl`:

```bash
curl -L 'https://app.pakasir.com/api/transactioncreate/qris' \
  -H 'Content-Type: application/json' \
  -d '{
        "project": "depodomain",
        "order_id": "INV123123",
        "amount": 99000,
        "api_key": "xxx123"
      }'
```

Contoh respons:

```json
{
  "payment": {
    "project": "depodomain",
    "order_id": "INV123123",
    "amount": 99000,
    "fee": 1003,
    "total_payment": 100003,
    "payment_method": "qris",
    "payment_number": "00020101021226610016ID.CO.SHOPEE.WWW01189360091800216005230208216005230303UME51440014ID.CO.QRIS.WWW0215ID10243228429300303UME5204792953033605409100003.005802ID5907Pakasir6012KAB. KEBUMEN61055439262230519SP25RZRATEQI2HQ65Q46304A079",
    "expired_at": "2025-09-19T01:18:49.678622564Z"
  }
}
```

### 3.3 Metode Pembayaran yang Didukung

- `cimb_niaga_va`
- `bni_va`
- `qris`
- `retail`
- `sampoerna_va`
- `bnc_va`
- `maybank_va`
- `permata_va`
- `atm_bersama_va`
- `artha_graha_va`
- `bri_va`

### 3.4 Endpoint `paymentsimulation`

Gunakan saat proyek masih dalam mode Sandbox untuk melakukan simulasi pembayaran dan menguji webhook.

```
POST https://app.pakasir.com/api/paymentsimulation
```

Body JSON:

```json
{
  "project": "depodomain",
  "order_id": "INV123123",
  "amount": 99000,
  "api_key": "xxx123"
}
```

Contoh `curl`:

```bash
curl -L 'https://app.pakasir.com/api/paymentsimulation' \
  -H 'Content-Type: application/json' \
  -d '{
        "project": "depodomain",
        "order_id": "INV123123",
        "amount": 99000,
        "api_key": "xxx123"
      }'
```

## 4. Webhook

Ketika pembayaran sukses, sistem Pakasir akan mengirim permintaan HTTP `POST` ke Webhook URL yang Anda daftarkan.

Contoh payload:

```json
{
  "amount": 22000,
  "order_id": "250910HDE7C9",
  "project": "depodomain",
  "status": "completed",
  "payment_method": "qris",
  "completed_at": "2025-09-10T08:07:02.819+07:00"
}
```

Catatan:
- Pastikan nilai `amount` dan `order_id` sesuai dengan data transaksi di sistem Anda.
- Disarankan memanggil API pengecekan status untuk validasi tambahan.

## 5. Transaction Detail API

Gunakan endpoint ini untuk mengambil status transaksi terbaru.

```
GET https://app.pakasir.com/api/transactiondetail?project={slug}&amount={amount}&order_id={order_id}&api_key={api_key}
```

Contoh `curl`:

```bash
curl 'https://app.pakasir.com/api/transactiondetail?project=depodomain&amount=22000&order_id=240910HDE7C9&api_key=JHGejwhe237dkhjeukyw8e33'
```

Respons contoh:

```json
{
  "transaction": {
    "amount": 22000,
    "order_id": "250910HDE7C9",
    "project": "depodomain",
    "status": "completed",
    "payment_method": "qris",
    "completed_at": "2025-09-10T08:07:02.819+07:00"
  }
}
```

## 6. Webhook Callback ke Wizard

Setelah pembayaran sukses, Pakasir akan memanggil webhook `POST /webhooks/pakasir` pada service Wizard (default port 8080). Payload akan diproses untuk:

- Memvalidasi signature (`X-Pakasir-Signature`) menggunakan `PAKASIR_WEBHOOK_SECRET` (opsional, aktif jika diset).
- Mencatat user (berdasarkan `metadata.telegram_id` atau pola `order_id` seperti `tg12345-abcdef`).
- Menyimpan payment dengan idempotency (`gateway_id == order_id`).
- Membuat `deployment_orders` status `pending` dan menandai `queued` agar auto deploy bisa berjalan.

### Contoh Payload

```json
{
  "amount": 22000,
  "order_id": "tg12345-250910HDE7C9",
  "project": "depodomain",
  "status": "completed",
  "payment_method": "qris",
  "completed_at": "2025-09-10T08:07:02.819+07:00",
  "metadata": {
    "telegram_id": 12345,
    "telegram_username": "ghost_user"
  }
}
```

> **Catatan:** Pastikan `order_id` atau `metadata` menyertakan `telegram_id` agar wizard dapat mengaitkan pembayaran dengan user yang benar.

## 7. Custom Domain `pots.my.id`

Untuk pengalaman pelanggan, Little Ghost menggunakan domain kustom `https://pots.my.id` yang diarahkan ke Pakasir. Seluruh link pembayaran, termasuk tombol “Bayar via Browser” di wizard, memakai format:

```
https://pots.my.id/pay/{slug}/{amount}?order_id={order_id}&qris_only=1
```

- `qris_only=1` memastikan hanya metode QRIS yang tampil.
- Domain dapat diganti melalui environment variable `PAKASIR_PUBLIC_DOMAIN` jika dibutuhkan (default `https://pots.my.id`).

Pelanggan akan menerima gambar QR (hasil konversi `payment_number`) dan tautan di atas ketika memilih menu 💳 Beli Userbot pada Wizard.
