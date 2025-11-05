#!/usr/bin/env python3
"""Helper untuk membuat folder tenant baru berbasis template Compose."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from textwrap import dedent
import shutil


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_COMPOSE = REPO_ROOT / "docker-compose.template.yml"
TEMPLATE_ENV = REPO_ROOT / "bot.env.template"
DEFAULT_DEPLOY_DIR = REPO_ROOT / "deployments"


def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Template tidak ditemukan: {path}")
    return path.read_text()


def create_tenant(
    *,
    store_slug: str,
    gateway: str,
    image: str,
    webhook_port: int,
    pakasir_port: int,
    postgres_host: str | None,
    postgres_user: str | None,
    postgres_password: str | None,
    postgres_port: int,
    output_dir: Path,
) -> None:
    tenant_name = f"bot-{store_slug}-{gateway}"
    tenant_root = output_dir / tenant_name

    if tenant_root.exists():
        raise SystemExit(f"Folder {tenant_root} sudah ada. Gunakan --force (ubah manual) atau hapus dahulu.")

    tenant_root.mkdir(parents=True, exist_ok=False)
    for sub in ("logs", "backups/local", "backups/offsite", "logs/maintenance"):
        (tenant_root / sub).mkdir(parents=True, exist_ok=True)

    compose_body = _load_template(TEMPLATE_COMPOSE)
    compose_body = compose_body.replace("${IMAGE_NAME:-bot-auto-order:latest}", image)
    compose_body = compose_body.replace(
        "container_name: bot-${STORE_SLUG:?STORE_SLUG-not-set}",
        f"container_name: bot-{store_slug}-{gateway}",
    )
    compose_body = compose_body.replace("bot-${STORE_SLUG:?STORE_SLUG-not-set}", f"bot-{store_slug}-{gateway}")

    compose_path = tenant_root / "compose.yml"
    compose_path.write_text(compose_body)

    env_body = _load_template(TEMPLATE_ENV)
    db_name = f"db_{store_slug}"
    if postgres_host and postgres_user and postgres_password:
        env_body = env_body.replace(
            "postgresql://username:password@postgres-host:5432/db_store",
            f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{db_name}",
        )
    env_body = env_body.replace("BOT_STORE_NAME=Nama Toko Kamu", f"BOT_STORE_NAME={store_slug.title().replace('-', ' ')}")
    env_body = env_body.replace("STORE_SLUG=store-slug", f"STORE_SLUG={store_slug}")
    env_body = env_body.replace("IMAGE_NAME=yourdockerhub/bot-auto-order:latest", f"IMAGE_NAME={image}")
    env_body = env_body.replace("BOT_WEBHOOK_PORT=8080", f"BOT_WEBHOOK_PORT={webhook_port}")
    env_body = env_body.replace("PAKASIR_PORT=9000", f"PAKASIR_PORT={pakasir_port}")
    env_body = env_body.replace("BOT_STORE_NAME=Nama Toko Kamu", f"BOT_STORE_NAME={store_slug.title().replace('-', ' ')}")

    env_path = tenant_root / "bot.env"
    env_path.write_text(env_body)

    helper_path = tenant_root / "README_TENANT.md"
    helper_path.write_text(
        dedent(
            f"""
            # Tenant {tenant_name}

            - Store slug: {store_slug}
            - Gateway   : {gateway}
            - Compose   : compose.yml
            - Env file  : bot.env
            - Logs      : logs/
            - Backups   : backups/local, backups/offsite

            ## Langkah berikutnya
            1. Lengkapi kredensial di `bot.env` (token Telegram, API Pakasir, DATA_ENCRYPTION_KEY, dsb).
            2. Sesuaikan port bila perlu: `BOT_WEBHOOK_PORT`, `PAKASIR_PORT` (ekspor saat menjalankan docker compose).
            3. Jalankan service:

               ```bash
               cd {tenant_root.relative_to(REPO_ROOT)}
               IMAGE_NAME={image} BOT_WEBHOOK_PORT={webhook_port} PAKASIR_PORT={pakasir_port} \\
                 docker compose -f compose.yml up -d
               ```

            4. Tambahkan cron health-check dan backup sesuai README utama.
            """
        ).strip()
        + "\n"
    )

    run_script_src = REPO_ROOT / "scripts/run_tenant.sh"
    run_script_dest = tenant_root / "run.sh"
    shutil.copy2(run_script_src, run_script_dest)
    run_script_dest.chmod(0o755)

    print(f"Tenant berhasil dibuat di {tenant_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision tenant bot auto-order")
    parser.add_argument("store_slug", help="Slug unik toko, gunakan huruf kecil dan tanda hubung")
    parser.add_argument("gateway", nargs="?", default="qris", help="Nama gateway (default: qris)")
    parser.add_argument("--image", default="bot-auto-order:latest", help="Nama image Docker")
    parser.add_argument("--webhook-port", type=int, default=8080, help="Port lokal untuk webhook Telegram")
    parser.add_argument("--pakasir-port", type=int, default=9000, help="Port lokal untuk webhook Pakasir")
    parser.add_argument("--postgres-host", help="Hostname Postgres (opsional)")
    parser.add_argument("--postgres-user", help="User Postgres (opsional)")
    parser.add_argument("--postgres-password", help="Password Postgres (opsional)")
    parser.add_argument("--postgres-port", type=int, default=5432, help="Port Postgres")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DEPLOY_DIR,
        help="Folder utama deployments (default: ./deployments)",
    )

    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    create_tenant(
        store_slug=args.store_slug,
        gateway=args.gateway,
        image=args.image,
        webhook_port=args.webhook_port,
        pakasir_port=args.pakasir_port,
        postgres_host=args.postgres_host,
        postgres_user=args.postgres_user,
        postgres_password=args.postgres_password,
        postgres_port=args.postgres_port,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
