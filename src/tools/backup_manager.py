"""Utility CLI untuk backup & restore terenkripsi."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import shutil
import subprocess
import tarfile
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, List, Tuple
from urllib.parse import urlparse

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.services.owner_alerts import notify_owners

LOGGER = logging.getLogger(__name__)

# Default lokasi backup lokal & offsite
LOCAL_BACKUP_DIR = Path(os.environ.get("BACKUP_LOCAL_DIR", "backups/local"))
OFFSITE_BACKUP_DIR = Path(os.environ.get("BACKUP_OFFSITE_DIR", "backups/offsite"))
METADATA_SUFFIX = ".meta.json"


@contextmanager
def temp_workdir(prefix: str) -> Iterator[Path]:
    """Buat direktori sementara."""

    with TemporaryDirectory(prefix=prefix) as tmp:
        yield Path(tmp)


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def _run(
    cmd: List[str], *, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    LOGGER.debug(
        "Menjalankan perintah: %s", " ".join(shlex.quote(part) for part in cmd)
    )
    result = subprocess.run(cmd, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        LOGGER.error(
            "Perintah gagal: %s\nstdout: %s\nstderr: %s",
            cmd,
            result.stdout,
            result.stderr,
        )
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with exit code {result.returncode}"
        )
    return result


def _parse_database_url(url: str) -> Tuple[str, dict[str, str]]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg", "postgres"}:
        raise ValueError("DATABASE_URL harus menggunakan skema PostgreSQL.")
    dbname = parsed.path.lstrip("/")
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or ""
    password = parsed.password or ""

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    dsn = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return dsn, env


def _create_tar(source_dir: Path, output_path: Path) -> None:
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=".")
    LOGGER.info("Arsip tar dibuat: %s", output_path)


def _encrypt_file(source: Path, dest: Path, password: str) -> None:
    env = os.environ.copy()
    env["BACKUP_ENCRYPTION_PASSWORD"] = password
    _run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-pass",
            "env:BACKUP_ENCRYPTION_PASSWORD",
            "-in",
            str(source),
            "-out",
            str(dest),
        ],
        env=env,
    )
    LOGGER.info("Arsip terenkripsi: %s", dest)


def _hash_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(args: argparse.Namespace) -> None:
    """Backup penuh database, konfigurasi, dan log."""

    settings = get_settings()
    password = os.environ.get("BACKUP_ENCRYPTION_PASSWORD")
    if not password:
        raise SystemExit("BACKUP_ENCRYPTION_PASSWORD belum di-set.")

    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if args.offsite:
        OFFSITE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = _timestamp()

    with temp_workdir("backup-") as tmpdir:
        LOGGER.info("Mulai backup ke direktori sementara %s", tmpdir)

        # Dump database
        dsn, env = _parse_database_url(settings.database_url)
        dump_path = tmpdir / "database.dump"
        _run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--file",
                str(dump_path),
                dsn,
            ],
            env=env,
        )
        LOGGER.info("Dump database selesai: %s", dump_path)

        # Salin file konfigurasi penting
        repo_root = Path(".").resolve()
        files_to_copy = [
            ".env",
            "refund_calculator_config.json",
            "refund_calculator_history.json",
        ]
        config_dir = tmpdir / "config"
        config_dir.mkdir(exist_ok=True)
        for file_name in files_to_copy:
            src = repo_root / file_name
            if src.exists():
                shutil.copy2(src, config_dir / src.name)

        # Salin log terbaru
        logs_dir = repo_root / "logs"
        if logs_dir.exists():
            target_logs = tmpdir / "logs"
            shutil.copytree(logs_dir, target_logs)

        # Buat tarball
        tar_path = tmpdir / f"backup-{timestamp}.tar.gz"
        _create_tar(tmpdir, tar_path)

        # Enkripsi
        encrypted_local = LOCAL_BACKUP_DIR / f"backup-{timestamp}.tar.gz.enc"
        _encrypt_file(tar_path, encrypted_local, password)

        # Metadata
        metadata = {
            "created_at": timestamp,
            "store_name": settings.store_name,
            "hash_sha256": _hash_file(encrypted_local),
            "size_bytes": encrypted_local.stat().st_size,
            "files": sorted(f.name for f in files_to_copy if (Path(".") / f).exists()),
        }
        metadata_path = encrypted_local.with_suffix(
            encrypted_local.suffix + METADATA_SUFFIX
        )
        metadata_path.write_text(json.dumps(metadata, indent=2))
        LOGGER.info("Metadata tersimpan: %s", metadata_path)

        # Salin ke offsite
        if args.offsite:
            destination = OFFSITE_BACKUP_DIR / encrypted_local.name
            shutil.copy2(encrypted_local, destination)
            shutil.copy2(
                metadata_path,
                destination.with_suffix(destination.suffix + METADATA_SUFFIX),
            )
            LOGGER.info("Backup disalin ke offsite: %s", destination)

        LOGGER.info("Backup selesai dan terenkripsi: %s", encrypted_local)

        # Notifikasi owner (opsional, hanya saat create)
        asyncio.run(
            notify_owners(
                (
                    f"🗄️ Backup selesai untuk {settings.store_name}\n"
                    f"📦 File: {encrypted_local.name}\n"
                    f"📁 Lokasi: {encrypted_local.parent}"
                ),
                disable_notification=True,
            )
        )


def list_backups() -> None:
    backups = sorted(LOCAL_BACKUP_DIR.glob("backup-*.tar.gz.enc"), reverse=True)
    for file in backups:
        meta_path = file.with_suffix(file.suffix + METADATA_SUFFIX)
        info = {}
        if meta_path.exists():
            info = json.loads(meta_path.read_text())
        LOGGER.info(
            "%s | size=%s | hash=%s",
            file.name,
            info.get("size_bytes"),
            info.get("hash_sha256"),
        )


def verify_backup(args: argparse.Namespace) -> None:
    target = Path(args.path)
    meta = target.with_suffix(target.suffix + METADATA_SUFFIX)
    if not target.exists() or not meta.exists():
        raise SystemExit("Berkas backup atau metadata tidak ditemukan.")
    metadata = json.loads(meta.read_text())
    current_hash = _hash_file(target)
    if current_hash != metadata.get("hash_sha256"):
        LOGGER.error(
            "Hash mismatch! metadata=%s current=%s",
            metadata.get("hash_sha256"),
            current_hash,
        )
        raise SystemExit("Backup korup.")
    LOGGER.info("Backup valid: %s", target)


def prune_backups(args: argparse.Namespace) -> None:
    keep = args.keep
    backups = sorted(LOCAL_BACKUP_DIR.glob("backup-*.tar.gz.enc"), reverse=True)
    to_delete = backups[keep:]
    for file in to_delete:
        LOGGER.info("Menghapus backup lama: %s", file)
        file.unlink(missing_ok=True)
        meta = file.with_suffix(file.suffix + METADATA_SUFFIX)
        meta.unlink(missing_ok=True)


def restore_backup(args: argparse.Namespace) -> None:
    password = os.environ.get("BACKUP_ENCRYPTION_PASSWORD")
    if not password:
        raise SystemExit("BACKUP_ENCRYPTION_PASSWORD belum di-set.")
    settings = get_settings()
    target = Path(args.path)
    if not target.exists():
        raise SystemExit("File backup tidak ditemukan.")

    with temp_workdir("restore-") as tmpdir:
        decrypted = tmpdir / "backup.tar.gz"
        env = os.environ.copy()
        env["BACKUP_ENCRYPTION_PASSWORD"] = password
        _run(
            [
                "openssl",
                "enc",
                "-d",
                "-aes-256-cbc",
                "-pbkdf2",
                "-pass",
                "env:BACKUP_ENCRYPTION_PASSWORD",
                "-in",
                str(target),
                "-out",
                str(decrypted),
            ],
            env=env,
        )
        LOGGER.info("Backup didekripsi, mulai ekstraksi.")
        with tarfile.open(decrypted, "r:gz") as tar:
            tar.extractall(tmpdir)

        # Restore database
        dump_file = next(tmpdir.glob("database.dump"), None)
        if not dump_file:
            raise SystemExit("Dump database tidak ditemukan di arsip.")

        dsn, env = _parse_database_url(settings.database_url)
        _run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--dbname",
                dsn,
                str(dump_file),
            ],
            env=env,
        )

        # Restore file konfigurasi
        config_dir = tmpdir / "config"
        if config_dir.exists():
            for item in config_dir.iterdir():
                dest = Path(".") / item.name
                shutil.copy2(item, dest)
                LOGGER.info("File konfigurasi dipulihkan: %s", dest)

        LOGGER.info("Restore selesai.")


def generate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup Manager Bot Auto Order")
    parser.add_argument(
        "--offsite", action="store_true", help="Salin ke direktori offsite juga"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub_create = sub.add_parser("create", help="Buat backup baru")
    sub_create.set_defaults(func=create_backup)

    sub_list = sub.add_parser("list", help="Daftar backup yang tersedia")
    sub_list.set_defaults(func=lambda args: list_backups())

    sub_verify = sub.add_parser("verify", help="Verifikasi hash backup")
    sub_verify.add_argument("path", help="Path backup terenkripsi")
    sub_verify.set_defaults(func=verify_backup)

    sub_restore = sub.add_parser("restore", help="Restore backup")
    sub_restore.add_argument("path", help="Path backup terenkripsi")
    sub_restore.set_defaults(func=restore_backup)

    sub_prune = sub.add_parser("prune", help="Hapus backup lama, sisakan N terakhir")
    sub_prune.add_argument("--keep", type=int, default=7)
    sub_prune.set_defaults(func=prune_backups)

    return parser


def main() -> None:
    setup_logging(service_name="maintenance")
    parser = generate_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        LOGGER.exception("Operasi backup gagal: %s", exc)
        settings = get_settings()
        try:
            asyncio.run(
                notify_owners(
                    f"🚨 Backup gagal untuk {settings.store_name}: {exc}",
                )
            )
        except Exception:
            LOGGER.error("Gagal mengirim notifikasi owner.")
        raise


if __name__ == "__main__":
    main()
