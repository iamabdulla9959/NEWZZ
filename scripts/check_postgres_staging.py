import os
import sys
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

def redact_url(url: str) -> str:
    """Redacts the password from a URL."""
    try:
        u = make_url(url)
        return u.render_as_string(hide_password=True)
    except Exception:
        return "<redacted_url>"

def main():
    parser = argparse.ArgumentParser(description="Preflight check for PostgreSQL Staging connection.")
    parser.parse_args()

    db_url = os.environ.get("NEWZZ_TEST_DATABASE_URL")
    confirmation = os.environ.get("NEWZZ_STAGING_DB_CONFIRMATION")

    print("=== PostgreSQL Staging Preflight Check ===")

    if not db_url:
        print("ERROR: NEWZZ_TEST_DATABASE_URL environment variable is missing.")
        sys.exit(1)

    if not confirmation or confirmation.strip() != "I_CONFIRM_THIS_IS_DISPOSABLE_STAGING":
        print("ERROR: Explicit confirmation missing. Please set NEWZZ_STAGING_DB_CONFIRMATION=I_CONFIRM_THIS_IS_DISPOSABLE_STAGING")
        sys.exit(1)

    print(f"Connection URL (redacted): {redact_url(db_url)}")

    if db_url.startswith("sqlite"):
        print("ERROR: SQLite URL rejected for PostgreSQL staging test.")
        sys.exit(1)

    if not (db_url.startswith("postgres://") or db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg://")):
        print("ERROR: Invalid PostgreSQL URL scheme.")
        sys.exit(1)

    # Normalize url to use psycopg
    if db_url.startswith("postgres://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgres://"):]
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

    print("Attempting to connect...")
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            # Check version
            version_row = conn.execute(text("SELECT version();")).fetchone()
            print(f"PostgreSQL Version: {version_row[0] if version_row else 'Unknown'}")

            # Check current database and user
            current_db = conn.execute(text("SELECT current_database();")).fetchone()
            current_user = conn.execute(text("SELECT current_user;")).fetchone()
            print(f"Connected Database: {current_db[0] if current_db else 'Unknown'}")
            print(f"Connected User: {current_user[0] if current_user else 'Unknown'}")

            # Check SSL status (might be None if not using pg_stat_ssl or lack perms, but we can try)
            try:
                ssl_row = conn.execute(text("SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();")).fetchone()
                if ssl_row and ssl_row[0]:
                    print(f"SSL: Enabled (Version: {ssl_row[1]}, Cipher: {ssl_row[2]})")
                else:
                    print("SSL: Not enabled on current connection.")
            except Exception as e:
                print("SSL: Unable to query pg_stat_ssl (check permissions or extension).")

            # Check pgvector
            extensions = conn.execute(text("SELECT extname FROM pg_extension;")).fetchall()
            ext_names = [e[0] for e in extensions]
            print(f"Installed Extensions: {', '.join(ext_names)}")

            if 'vector' not in ext_names:
                print("WARNING/INFO: 'vector' extension is not installed. If pgvector is required, please enable it.")

    except Exception as e:
        print(f"ERROR: Failed to connect or execute preflight checks. Exception: {e}")
        sys.exit(1)

    print("\nPreflight Check PASSED.")
    sys.exit(0)

if __name__ == "__main__":
    main()
