#!/usr/bin/env python3
"""
Migration Runner Script
Safely executes database migrations with backup and validation.

Usage:
    python scripts/run_migration.py [migration_file]
    python scripts/run_migration.py scripts/migrations/001_fix_schema_constraints.sql
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
import asyncpg


async def get_db_connection():
    """Get database connection from environment variables."""
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))
    db_name = os.getenv("POSTGRES_DB", "bot_auto_order")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "")

    print(f"📡 Connecting to database: {db_user}@{db_host}:{db_port}/{db_name}")

    try:
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        )
        print("✅ Database connection established")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


async def create_migration_table(conn):
    """Create migrations tracking table if not exists."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_name TEXT NOT NULL UNIQUE,
            executed_at TIMESTAMPTZ DEFAULT NOW(),
            execution_time_ms INTEGER,
            status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'rollback')),
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    print("✅ Migration tracking table ready")


async def is_migration_applied(conn, migration_name: str) -> bool:
    """Check if migration has already been applied."""
    result = await conn.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM schema_migrations
            WHERE migration_name = $1 AND status = 'success'
        )
        """,
        migration_name,
    )
    return result


async def record_migration(
    conn,
    migration_name: str,
    execution_time_ms: int,
    status: str,
    error_message: str | None = None,
):
    """Record migration execution in tracking table."""
    await conn.execute(
        """
        INSERT INTO schema_migrations (migration_name, execution_time_ms, status, error_message)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (migration_name) DO UPDATE
        SET executed_at = NOW(),
            execution_time_ms = EXCLUDED.execution_time_ms,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message;
        """,
        migration_name,
        execution_time_ms,
        status,
        error_message,
    )


async def backup_critical_tables(conn):
    """Create backup of critical tables before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tables_to_backup = [
        "product_contents",
        "product_term_submissions",
        "coupons",
        "deposits",
        "orders",
        "payments",
    ]

    print("\n📦 Creating backup tables...")
    for table in tables_to_backup:
        backup_table = f"{table}_backup_{timestamp}"
        try:
            # Check if table exists
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = $1
                )
                """,
                table,
            )

            if table_exists:
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {backup_table} AS SELECT * FROM {table};"
                )
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {backup_table}")
                print(f"  ✅ Backed up {table} ({count} rows) -> {backup_table}")
            else:
                print(f"  ⚠️  Table {table} does not exist, skipping backup")
        except Exception as e:
            print(f"  ⚠️  Failed to backup {table}: {e}")

    return timestamp


async def validate_database_state(conn):
    """Validate database state before and after migration."""
    print("\n🔍 Validating database state...")

    # Check for basic table existence
    tables = [
        "users",
        "categories",
        "products",
        "orders",
        "order_items",
        "product_contents",
        "payments",
        "deposits",
        "coupons",
        "reply_templates",
    ]

    for table in tables:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = $1
            )
            """,
            table,
        )
        status = "✅" if exists else "❌"
        print(f"  {status} Table: {table}")

    # Get row counts
    print("\n📊 Database statistics:")
    for table in tables:
        try:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  - {table}: {count:,} rows")
        except Exception:
            print(f"  - {table}: N/A")


async def run_migration_file(conn, migration_file: Path):
    """Execute migration SQL file."""
    migration_name = migration_file.name

    print(f"\n🚀 Running migration: {migration_name}")
    print(f"   File: {migration_file}")

    # Check if already applied
    if await is_migration_applied(conn, migration_name):
        print(f"⚠️  Migration '{migration_name}' already applied, skipping...")
        return True

    # Read migration file
    try:
        with open(migration_file, "r", encoding="utf-8") as f:
            sql_content = f.read()
    except Exception as e:
        print(f"❌ Failed to read migration file: {e}")
        return False

    # Execute migration
    start_time = datetime.now()
    try:
        # Use a transaction for safety
        async with conn.transaction():
            # Execute SQL (split by semicolon for multiple statements)
            # Note: For complex migrations with DO blocks, we execute as single statement
            await conn.execute(sql_content)

        end_time = datetime.now()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Record success
        await record_migration(conn, migration_name, execution_time_ms, "success")

        print(f"✅ Migration completed successfully in {execution_time_ms}ms")
        return True

    except Exception as e:
        end_time = datetime.now()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        error_message = str(e)
        print(f"\n❌ Migration failed after {execution_time_ms}ms")
        print(f"   Error: {error_message}")

        # Record failure
        try:
            await record_migration(
                conn, migration_name, execution_time_ms, "failed", error_message
            )
        except Exception as record_error:
            print(f"⚠️  Failed to record migration failure: {record_error}")

        return False


async def list_applied_migrations(conn):
    """List all applied migrations."""
    print("\n📋 Applied migrations:")
    rows = await conn.fetch(
        """
        SELECT migration_name, executed_at, status, execution_time_ms
        FROM schema_migrations
        ORDER BY executed_at DESC
        LIMIT 10;
        """
    )

    if not rows:
        print("  No migrations applied yet")
    else:
        for row in rows:
            status_icon = "✅" if row["status"] == "success" else "❌"
            print(
                f"  {status_icon} {row['migration_name']} - "
                f"{row['executed_at'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"({row['execution_time_ms']}ms)"
            )


async def main():
    """Main migration runner."""
    print("=" * 80)
    print("🔧 Database Migration Runner")
    print("=" * 80)

    # Get migration file from args or use default
    if len(sys.argv) > 1:
        migration_file = Path(sys.argv[1])
    else:
        # Default to latest migration
        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            print("❌ No migration files found in migrations directory")
            sys.exit(1)
        migration_file = migration_files[-1]  # Use latest

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    # Connect to database
    conn = await get_db_connection()

    try:
        # Setup migration tracking
        await create_migration_table(conn)

        # Show applied migrations
        await list_applied_migrations(conn)

        # Validate database state before migration
        await validate_database_state(conn)

        # Ask for confirmation
        print("\n" + "=" * 80)
        response = input(
            f"⚠️  Ready to apply migration: {migration_file.name}\n"
            "   This will modify your database schema.\n"
            "   Continue? (yes/no): "
        )

        if response.lower() not in ("yes", "y"):
            print("❌ Migration cancelled by user")
            return

        # Create backups
        backup_timestamp = await backup_critical_tables(conn)
        print(f"\n💾 Backups created with timestamp: {backup_timestamp}")

        # Run migration
        success = await run_migration_file(conn, migration_file)

        # Validate database state after migration
        if success:
            print("\n" + "=" * 80)
            await validate_database_state(conn)
            print("\n" + "=" * 80)
            print("🎉 Migration completed successfully!")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("❌ Migration failed! Database may be in an inconsistent state.")
            print(f"   Backup tables are available with timestamp: {backup_timestamp}")
            print("   Review the error and consider manual rollback if needed.")
            print("=" * 80)
            sys.exit(1)

    finally:
        await conn.close()
        print("\n👋 Database connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
