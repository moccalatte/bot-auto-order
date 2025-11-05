# Panduan Deploy Bot Auto Order (Mode Multi-Tenant)

Dokumen ini memandu owner (tanpa latar belakang teknis mendalam) men-deploy dan memelihara banyak bot auto order menggunakan Docker dan image yang tersedia di Docker Hub. Fokusnya adalah proses sederhana: buat folder tenant → jalankan bot → otomatis jalan sendiri (health-check & backup).

---

## 0. Persiapan Wajib

1. **Punya server/VPS** dengan Docker & Docker Compose terinstal.
2. **Punya domain/subdomain** yang diarahkan lewat Cloudflare (misal `myshop.pots.my.id`).
3. **Cloudflared** (Tunnel) dan **Caddy/Nginx** sudah berjalan via systemd (sesuai kebiasaan kamu). Tidak perlu memindahkan Cloudflared/Caddy ke Docker.
4. **PostgreSQL** (boleh di VPS berbeda) dengan pola database per tenant, contoh `db_myshop`, `db_bravo`, dst.
5. **Image Docker** sudah tersedia di Docker Hub, contoh nama: `yourdockerhub/bot-auto-order:0.2.1` (build & push sekali dari repo ini).
6. Simpan repo ini di satu tempat (boleh di laptop atau server). Repo berguna karena menyediakan skrip provisioning, template `bot.env`, dan update patch ke depan. *Anda tidak wajib meng-clone repo ini di semua server produksi*, cukup satu copy (bisa di laptop). Hasil provisioning bisa di-copy ke VPS target.

---

## 1. Workflow Singkat Tiap Tenant

1. Jalankan skrip provisioning (sekali per tenant) untuk membuat folder & file keperluan.
2. Edit `bot.env` di folder tenant (isi token/API/Database/port).
3. Jalankan `./run.sh` di folder tenant → container langsung berjalan.
4. Atur rute di Caddy (berdasarkan hostname + path) dan Cloudflared tetap diarahkan ke Caddy.
5. Backup & health-check otomatis jalan di dalam container; opsional: tambahkan cron host untuk sync offsite.

---

## 2. Detail Langkah

### 2.1 Provisioning Tenant

Di server atau laptop yang memiliki repositori ini, jalankan perintah berikut:

```bash
python scripts/provision_tenant.py <store_slug> <gateway>
```

Contoh pemakaian:

```bash
python scripts/provision_tenant.py alpha pakasir \
  --image yourdockerhub/bot-auto-order:0.2.1 \
  --postgres-host db.internal \
  --postgres-user bot_auto_order \
  --postgres-password supersecret
```

Keterangan:
- `<store_slug>`: nama pendek tenant, pakai huruf kecil & dash (mis. `alpha`, `bravo`, `bot-satu`).
- `<gateway>`: bawaan `pakasir`; di masa depan bisa diganti (`doku`, `midtrans`, dll.).
- `--image`: tag Docker Hub yang akan dipakai tenant.
- `--postgres-*`: optional; isi kalau mau auto-set `DATABASE_URL` di `bot.env`. Jika tidak diisi, nanti edit manual.

Output perintah di atas: folder `deployments/bot-<store_slug>-<gateway>/` berisi:
- `compose.yml`
- `bot.env`
- `run.sh`
- `logs/`, `backups/local/`, `backups/offsite/`, `logs/maintenance/`
- `README_TENANT.md` (ringkasan langkah lanjutan per tenant)

> **Catatan:** Bila repo ini tidak ada di server produksi, jalankan skrip di laptop lalu salin folder tenant yang dihasilkan ke server (menggunakan `scp`/`rsync`).

### 2.2 Mengisi `bot.env`

Edit file `bot.env` di folder tenant.
- `TELEGRAM_BOT_TOKEN`: token bot seller.
- `TELEGRAM_ADMIN_IDS`/`OWNER_IDS`: ID Telegram admin/owner.
- `DATABASE_URL`: contoh `postgresql://user:pass@host:5432/db_alpha`.
- `PAKASIR_PROJECT_SLUG`, `PAKASIR_API_KEY`, `PAKASIR_PUBLIC_DOMAIN` sesuai tenant.
- `BOT_WEBHOOK_PORT`, `PAKASIR_PORT`: port host (default 8080/9000). Ganti jika perlu unik (mis. `18080`, `19000`).
- `IMAGE_NAME`: default diisi oleh skrip; bisa diganti ke tag baru saat upgrade.
- `DATA_ENCRYPTION_KEY`: isi string base64 (gunakan `openssl rand -base64 32`).
- `BACKUP_ENCRYPTION_PASSWORD`: wajib diisi agar backup terenkripsi.
- Sisanya (`ENABLE_AUTO_HEALTHCHECK`, `ENABLE_AUTO_BACKUP`, `BACKUP_TIME`, dsb.) sudah default.

### 2.3 Menjalankan Tenant

Masuk ke folder tenant dan jalankan:

```bash
cd deployments/bot-alpha-pakasir
./run.sh
```

Skrip `run.sh` otomatis membaca `bot.env`, mengekspor variabel, lalu menjalankan `docker compose up -d`. Port host terbatas di `127.0.0.1`, jadi tidak mengganggu service lain.

### 2.4 Konfigurasi Caddy & Cloudflared

Tambahkan blok di `Caddyfile` (Caddy via systemd, bersama situs usaha lain):

```caddyfile
# Tenant Alpha
alpha.pots.my.id {
    encode gzip zstd
    route /telegram* {
        reverse_proxy 127.0.0.1:18080
    }
    route /webhooks/pakasir* {
        reverse_proxy 127.0.0.1:19000
    }
}

# Tenant Bravo (contoh tenant kedua)
bravo.pots.my.id {
    encode gzip zstd
    route /telegram* {
        reverse_proxy 127.0.0.1:28080
    }
    route /webhooks/pakasir* {
        reverse_proxy 127.0.0.1:29000
    }
}
```

Pastikan `BOT_WEBHOOK_PORT` & `PAKASIR_PORT` di `bot.env` sesuai dengan rute Caddy di atas.

Kemudian, di `cloudflared/config.yml` cukup arahkan host ke Caddy (tidak perlu join network Docker):

```yaml
ingress:
  - hostname: alpha.pots.my.id
    service: https://127.0.0.1:443
  - hostname: bravo.pots.my.id
    service: https://127.0.0.1:443
  - service: http_status:404
```

Dari sisi Pakasir/Telegram:
- Telegram Webhook URL → `https://alpha.pots.my.id/telegram`
- Pakasir Webhook URL → `https://alpha.pots.my.id/webhooks/pakasir`

Tidak ada port publik selain 80/443 yang dibuka ke Internet; Caddy & Cloudflared tetap via systemd seperti biasa.

### 2.5 Backup & Health-Check Otomatis

- Di `bot.env`, aktifkan:
  ```env
  ENABLE_AUTO_HEALTHCHECK=true
  HEALTHCHECK_INTERVAL_MINUTES=5
  ENABLE_AUTO_BACKUP=true
  BACKUP_TIME=00:00
  BACKUP_AUTOMATIC_OFFSITE=true
  ```
- Container akan menjalankan health-check sendiri (log di `logs/health-check/...`).
- Backup terenkripsi dibuat otomatis setiap jam 00:00 (lokasi `backups/local`). Jika `BACKUP_AUTOMATIC_OFFSITE=true`, kopian juga dibuat di `backups/offsite` (tinggal sinkronkan ke storage eksternal dengan `rclone` setelahnya).
- Notifikasi berhasil/gagal akan dikirim ke owner (prefix `[BOT_STORE_NAME]`).
- Jika tetap ingin cadangan melalui host, gunakan `scripts/cron_backup.sh` & `scripts/cron_healthcheck.sh` (contoh ada di README). Tapi ini opsional karena container sudah otomatis.

### 2.6 Monitoring

- Cek status container: `docker compose -f compose.yml ps`.
- Log runtime: `logs/telegram-bot/YYYY-MM-DD.log`.
- Log maintenance (backup/health-check) ada di `logs/maintenance/`.
- Jika ada alert kegagalan beruntun (mis. API Pakasir error), owner akan menerima pesan dari bot owner (pastikan `OWNER_BOT_TOKEN` atau `TELEGRAM_OWNER_IDS` sudah diisi).

---

## 3. FAQ

### Q: Harus clone repo ini di server produksi?
- **Tidak wajib.** Kamu bisa menyimpan repo di laptop, jalankan `provision_tenant.py` di sana, kemudian kopi folder tenant ke server via `scp`. Kalau merasa gampang, kamu boleh clone juga di server; skrip tidak mengganggu service lain.

### Q: Apakah semua tenant pakai port internal sama (8080/9000)?
- Ya. Port internal di dalam container sama, tapi port host berbeda. Contoh Tenant Alpha pakai `18080/19000`, Tenant Bravo pakai `28080/29000`. Ini supaya memudahkan Caddy mengarahkan ke container yang benar.

### Q: “Aku takut banyak port kebuka di VPS.”
- Semua port host di-bind ke `127.0.0.1`, jadi tidak bisa diakses dari luar. Publik hanya lewat Cloudflared/Caddy pada 80/443.

### Q: Kalau VPS kena suspend/banned?
- Backup otomatis tersimpan terenkripsi di `deployments/.../backups/local`. Rekomen sinkronkan `backups/offsite` ke storage eksternal (S3/Backblaze/GDrive via rclone). Di server baru tinggal restore backup (`python -m src.tools.backup_manager restore <file>`) lalu jalankan `./run.sh`.

### Q: Bagaimana upgrade versi bot?
- Build image baru → push ke Docker Hub → edit `bot.env` (ubah `IMAGE_NAME`) → rerun `./run.sh` (atau `docker compose pull && docker compose up -d`).

### Q: Bagaimana menambah gateway baru (selain Pakasir)?
- Strukturnya sudah dirancang modular. Satu tenant bisa pakai gateway lain cukup buat image baru atau ganti setting di `bot.env`. Untuk provisioning, cukup set `--gateway midtrans` agar nama folder jelas.

---

## 4. Ringkasan

1. **Provision**: `python scripts/provision_tenant.py <slug> <gateway>`.
2. **Edit `bot.env`**: isi token, DB, port host, kunci enkripsi.
3. **Jalankan**: `cd deployments/bot-<slug>-<gateway> && ./run.sh`.
4. **Arahkan domain**: update Caddy (hostname/path → port host tenant), Cloudflared tetap ke Caddy.
5. **Nikmati otomatisasi**: health-check & backup jalan sendiri; log di folder tenant.

Dengan alur ini kamu hanya perlu mengisi file `bot.env`, menambahkan rule di Caddy satu kali, dan tenant langsung siap pakai. Project lain (web lain, servis lain) tetap aman karena port host kontainer hanya di 127.0.0.1 dan semua domain dikelola Caddy seperti biasa.
