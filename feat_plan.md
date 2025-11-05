# 🚨 Roadmap Pra-Produksi Bot Auto Order (Critical Only)

Dokumen ini hanya memuat fitur, mitigasi risiko, dan langkah yang benar-benar fatal/critical sebelum bot masuk produksi. Fokus pada pencegahan kegagalan besar, kehilangan data, downtime, dan compliance.

---

## 1. Ketahanan Infrastruktur & Failover

| Fokus | Rencana | Status | Risiko Fatal |
|-------|---------|--------|-------------|
| **Failover VPS / IP diblokir** | - Siapkan mode failover polling + webhook.<br>- Dokumentasi prosedur switch DNS/Reverse Proxy.<br>- Skrip health-check & alert downtime. | 🔴 | Bot tidak bisa diakses jika VPS/IP diblokir. |
| **Auto-recovery service** | - Supervisor/systemd unit dengan restart policy.<br>- Alert ke admin jika service mati. | 🟠 | Bot mati tanpa restart otomatis, downtime lama. |
| **Job Queue Integrity** | - Persistensi job queue (SNK pending) di storage terpisah (redis/tabel postgres).<br>- Distributed lock untuk multi-instance. | 🔴 | SNK/broadcast gagal diproses, duplikasi, atau hilang. |

---

## 2. Backup & Restore

| Fokus | Rencana | Status | Risiko Fatal |
|-------|---------|--------|-------------|
| **Backup otomatis & offsite** | - Backup terenkripsi database, .env, konfigurasi, dan log.<br>- Jadwal backup harian/mingguan.<br>- Backup offsite (cloud/remote server). | 🔴 | Kehilangan data total jika VPS rusak/hilang. |
| **Monitoring backup** | - Alert jika backup gagal/corrupt.<br>- Checksum & integritas backup. | 🔴 | Backup tidak valid, gagal restore saat dibutuhkan. |
| **SOP restore & uji berkala** | - Dokumentasi restore.<br>- Uji restore rutin, pastikan data konsisten. | 🔴 | Restore gagal saat insiden, downtime berkepanjangan. |

---

## 3. Keamanan & Compliance

| Fokus | Rencana | Status | Risiko Fatal |
|-------|---------|--------|-------------|
| **Rotasi kredensial** | - SOP rotasi API key/token.<br>- Reminder otomatis.<br>- Notifikasi ke owner saat rotasi. | 🔴 | Kredensial bocor, bot diambil alih pihak lain. |
| **Enkripsi data sensitif** | - Enkripsi data SNK, screenshot, dan data customer.<br>- Kebijakan retention & auto purge. | 🔴 | Data customer bocor, pelanggaran privasi. |
| **Audit & log rotasi** | - Log audit SNK/broadcast.<br>- Rotasi log otomatis.<br>- Monitoring disk usage. | 🔴 | Tidak ada jejak audit, disk penuh, bot crash. |

---

## 4. Monitoring & Alerting

| Fokus | Rencana | Status | Risiko Fatal |
|-------|---------|--------|-------------|
| **Health-check & alert downtime** | - Skrip health-check service.<br>- Alert ke admin jika bot down. | 🔴 | Bot mati tanpa diketahui, transaksi gagal. |
| **Early warning pembayaran** | - Alert ke owner jika pembayaran gagal beruntun (indikasi gateway down). | 🔴 | Transaksi gagal massal tanpa diketahui. |

---

## 5. Pencegahan Kegagalan Besar & Ambiguitas

- **Restore Parsial/Migrasi Data**  
  SOP restore harus terpadu, uji migrasi data agar tidak ada data menggantung.
- **Overlapping Admin Actions**  
  Audit notif ke owner jika ada edit bersamaan pada SNK/produk.
- **Resource Exhaustion**  
  Monitoring disk/memory, alert threshold, dan prosedur cleanup otomatis.
- **Dependency & API Change**  
  Pin versi dependency, monitor breaking change, dan siapkan fallback jika API eksternal berubah.

---

## 6. Uji Pra-Produksi (Wajib)

1. **Chaos Test VPS**  
   Matikan proses bot, verifikasi auto-restart & keutuhan job queue.
2. **Backup & Restore Drill**  
   Uji recovery penuh dari backup lokal & offsite, pastikan SOP restore jelas.
3. **Gateway Simulation**  
   Simulasi pembayaran gagal massal, cek alerting & recovery.
4. **Resource Exhaustion Test**  
   Simulasikan disk/memory penuh, pastikan bot fail gracefully & alert.
5. **Dependency/API Change Simulation**  
   Uji update dependency dan perubahan API eksternal di staging.

---

> Catatan: Hanya item di atas yang wajib sebelum produksi. Fitur opsional/tambahan dapat diprioritaskan setelah stabil dan aman.