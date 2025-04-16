#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime
from urllib.parse import quote_plus

from dotenv import find_dotenv, load_dotenv, set_key
from sqlalchemy import create_engine
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session, sessionmaker

try:
    # Assume the script is located in 'scripts/' (one level below the project root)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    from entities_api.models.models import ApiKey, User
    from projectdavid_common import UtilsInterface
    from projectdavid_common.utilities.logging_service import LoggingUtility
except ImportError as e:
    print("Error: Could not import project modules: " + str(e))
    print("Please ensure:")
    print("  1. The script is run from the '/app/scripts' directory inside the container.")
    print("  2. The project root ('" + project_root + "') is used to locate modules.")
    print(
        "  3. Required packages ('projectdavid_common', 'entities_api') are installed within the 'api' container image."
    )
    sys.exit(1)

# Constants
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_NAME = "Default Admin"
DEFAULT_ADMIN_KEY_NAME = "Admin Bootstrap Key"
DEFAULT_CREDENTIALS_FILENAME = "admin_credentials.txt"
DEFAULT_DOTENV_FILENAME = ".env"
ENV_VAR_API_KEY_ADMIN = "ADMIN_API_KEY"
ENV_VAR_API_KEY_ENTITIES = "ENTITIES_API_KEY"
ENV_VAR_DB_URL_INTERNAL = "DATABASE_URL"
ENV_VAR_DB_URL_EXTERNAL = "SPECIAL_DB_URL"

try:
    logging_utility = LoggingUtility()
    identifier_service = UtilsInterface.IdentifierService()
except NameError:
    print("Error: Failed to initialize utilities due to import errors.")
    sys.exit(1)


def setup_database(db_url: str) -> sessionmaker | None:
    """Connects to the database and returns a sessionmaker."""
    if not db_url:
        logging_utility.error(
            "Database URL is not configured. Checked --db-url, "
            + ENV_VAR_DB_URL_INTERNAL
            + ", and "
            + ENV_VAR_DB_URL_EXTERNAL
            + " environment variables."
        )
        print(
            "Error: Database URL not set via --db-url argument or environment variables ("
            + ENV_VAR_DB_URL_INTERNAL
            + ", "
            + ENV_VAR_DB_URL_EXTERNAL
            + ")."
        )
        return None

    try:
        engine = create_engine(db_url, echo=False, pool_pre_ping=True)
        with engine.connect() as connection:
            db_name = connection.engine.url.database
            logging_utility.info("Successfully connected to database: " + db_name)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logging_utility.info("Database session factory configured.")
        return SessionLocal
    except sqlalchemy_exc.OperationalError as e:
        logging_utility.error("Failed to connect to database: " + str(e), exc_info=False)
        print("\nError: Could not connect to the database.")
        print(
            "URL Used: "
            + (db_url[: db_url.find("@")] if "@" in db_url else db_url[:25])
            + "... (Check full URL and credentials)"
        )
        print("Details: " + str(e))
        print("Troubleshooting (inside container):")
        print("  - Is the database service ('db') running and healthy? (`docker compose ps`)")
        print("  - Are the credentials (user/password in URL) correct for the 'db' service?")
        print("  - Is the database name correct?")
        print("  - Is the hostname in the URL correct (should be 'db' inside the container)?")
        return None
    except Exception as e:
        logging_utility.error("Failed to initialize database engine: " + str(e), exc_info=True)
        print("\nError: An unexpected error occurred during database setup: " + str(e))
        return None


def find_or_create_admin_user(db: Session, admin_email: str, admin_name: str) -> User | None:
    """Finds the admin user by email or creates a new one."""
    try:
        logging_utility.info("Checking for existing admin user: " + admin_email)
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if admin_user:
            logging_utility.warning(
                "Admin user '" + admin_email + "' already exists (ID: " + str(admin_user.id) + ")."
            )
            if not admin_user.is_admin:
                logging_utility.warning(
                    "Existing user "
                    + admin_email
                    + " found but IS NOT admin. Setting is_admin=True."
                )
                admin_user.is_admin = True
                admin_user.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(admin_user)
                logging_utility.info("User " + str(admin_user.id) + " updated to be an admin.")
            return admin_user
        else:
            logging_utility.info(
                "Creating new admin user: " + admin_email + ", Name: " + admin_name
            )
            admin_user_id = identifier_service.generate_user_id()
            admin_user = User(
                id=admin_user_id,
                email=admin_email,
                full_name=admin_name,
                email_verified=True,
                oauth_provider="local",
                is_admin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(admin_user)
            logging_utility.info("Admin user object created with ID: " + str(admin_user.id))
            db.commit()
            db.refresh(admin_user)
            logging_utility.info("Admin user committed to database.")
            return admin_user
    except Exception as e:
        logging_utility.error(
            "Error finding or creating admin user '" + admin_email + "': " + str(e), exc_info=True
        )
        print("\nError: Failed during admin user lookup/creation: " + str(e))
        db.rollback()
        return None


def generate_and_save_key(
    db: Session, admin_user: User, key_name: str
) -> tuple[str | None, str | None]:
    """Generates, hashes, and saves an API key for the admin user. Returns (plain_key, prefix) or (None, existing_prefix)."""
    plain_text_api_key = None
    key_prefix = None
    try:
        logging_utility.info("Checking for existing API key for admin user: " + str(admin_user.id))
        existing_key = db.query(ApiKey).filter(ApiKey.user_id == admin_user.id).first()
        if existing_key:
            logging_utility.warning(
                "Admin user "
                + str(admin_user.id)
                + " already has an API key (Prefix: "
                + str(existing_key.prefix)
                + "). Skipping key generation."
            )
            print(
                "\nInfo: Admin user '"
                + admin_user.email
                + "' already has an API key. No new key generated."
            )
            return None, existing_key.prefix
        logging_utility.info(
            "Generating new API key '" + key_name + "' for admin user: " + str(admin_user.id)
        )
        plain_text_api_key = ApiKey.generate_key(prefix="ad_")
        key_prefix = plain_text_api_key[:8]
        hashed_key = ApiKey.hash_key(plain_text_api_key)
        api_key_record = ApiKey(
            user_id=admin_user.id,
            key_name=key_name,
            hashed_key=hashed_key,
            prefix=key_prefix,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(api_key_record)
        logging_utility.info("API Key record created (Prefix: " + key_prefix + ")")
        db.commit()
        logging_utility.info("API Key record committed to database.")
        return plain_text_api_key, key_prefix
    except Exception as e:
        logging_utility.error(
            "Error generating or saving API key for user " + str(admin_user.id) + ": " + str(e),
            exc_info=True,
        )
        print("\nError: Failed during API key generation/saving: " + str(e))
        db.rollback()
        return None, None


def save_credentials(
    plain_text_key: str, key_prefix: str, admin_user: User, creds_file_path: str, dotenv_path: str
):
    """Saves the generated credentials to a text file and updates the .env file."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    logging_utility.info(
        "Attempting to write credentials to: " + creds_file_path + " (inside container)"
    )
    try:
        os.makedirs(os.path.dirname(creds_file_path), exist_ok=True)
        file_content = (
            "# Admin Credentials Generated: "
            + timestamp
            + "\n"
            + "# WARNING: Contains sensitive information.\n"
            + "ADMIN_USER_EMAIL="
            + admin_user.email
            + "\n"
            + "ADMIN_USER_ID="
            + str(admin_user.id)
            + "\n"
            + "ADMIN_KEY_PREFIX="
            + key_prefix
            + "\n"
            + ENV_VAR_API_KEY_ADMIN
            + "="
            + plain_text_key
            + "\n"
            + ENV_VAR_API_KEY_ENTITIES
            + "="
            + plain_text_key
            + "\n"
        )
        with open(creds_file_path, "w") as f:
            f.write(file_content)
        logging_utility.info("Successfully wrote credentials to: " + creds_file_path)
        print(
            "\nInfo: Admin credentials written to: "
            + creds_file_path
            + " (within the 'api' container)"
        )
        print("      You may need to copy the key from console output to your host's .env file.")
    except Exception as file_err:
        logging_utility.error(
            "Failed to write credentials file '"
            + creds_file_path
            + "' inside container: "
            + str(file_err),
            exc_info=True,
        )
        print(
            "\nWarning: Failed to write credentials file at "
            + creds_file_path
            + " inside container: "
            + str(file_err)
        )

    logging_utility.info(
        "Attempting to update .env file at: " + dotenv_path + " (inside container)"
    )
    try:
        os.makedirs(os.path.dirname(dotenv_path), exist_ok=True)
        set_key(dotenv_path, "ADMIN_USER_EMAIL", admin_user.email, quote_mode="always")
        set_key(dotenv_path, "ADMIN_USER_ID", str(admin_user.id), quote_mode="always")
        set_key(dotenv_path, "ADMIN_KEY_PREFIX", key_prefix, quote_mode="always")
        set_key(dotenv_path, ENV_VAR_API_KEY_ADMIN, plain_text_key, quote_mode="always")
        set_key(dotenv_path, ENV_VAR_API_KEY_ENTITIES, plain_text_key, quote_mode="always")
        logging_utility.info(
            "Successfully updated .env file: " + dotenv_path + " (inside container)"
        )
        print("Info: Admin credentials also updated in: " + dotenv_path + " (inside container)")
        print(
            "      >>> IMPORTANT: Remember to copy the PLAIN TEXT API KEY from the console output <<<"
        )
        print("      >>> and add/update it in the main .env file on your HOST machine. <<<")
        print("      >>> Then restart the API service: docker compose restart api <<<")
    except Exception as dotenv_err:
        logging_utility.error(
            "Failed to update .env file '" + dotenv_path + "' inside container: " + str(dotenv_err),
            exc_info=True,
        )
        print(
            "\nWarning: Failed to update .env file at "
            + dotenv_path
            + " inside container: "
            + str(dotenv_err)
        )


def print_key_to_console(
    user: User, key_prefix: str, plain_key: str, creds_filepath: str, dotenv_filepath: str
):
    """Prints the generated key and confirmation details to the console."""
    print("\n" + "=" * 60)
    print("  IMPORTANT: Admin API Key Generated!")
    print("  User Email: " + user.email)
    print("  User ID:    " + str(user.id))
    print("  Key Prefix: " + key_prefix)
    print("-" * 60)
    print("  PLAIN TEXT API KEY: " + plain_key)
    print("-" * 60)
    print(
        "  >>> Action Required: Copy this key and add/update ADMIN_API_KEY / ENTITIES_API_KEY <<<"
    )
    print("  >>> in the main .env file on your HOST system, then restart the API service:      <<<")
    print("  >>> docker compose restart api                                                    <<<")
    print("-" * 60)
    print("  Details also saved/updated inside the container at:")
    print("    1. Credentials File: " + creds_filepath)
    print("    2. DotEnv File:      " + dotenv_filepath)
    print(
        "       (Key saved as both "
        + ENV_VAR_API_KEY_ADMIN
        + " and "
        + ENV_VAR_API_KEY_ENTITIES
        + ")"
    )
    print("=" * 60 + "\n")


def parse_arguments():
    container_dotenv_path = find_dotenv(
        filename=DEFAULT_DOTENV_FILENAME, raise_error_if_not_found=False
    )
    if container_dotenv_path:
        logging_utility.info("Found .env file inside container at: " + container_dotenv_path)
        load_dotenv(dotenv_path=container_dotenv_path, override=False)
    else:
        logging_utility.warning(
            "Could not find "
            + DEFAULT_DOTENV_FILENAME
            + " inside container search path. Relying solely on inherited environment variables."
        )

    parser = argparse.ArgumentParser(
        description="Bootstrap the initial admin user and API key for the Entities API (intended for use inside API container).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    db_url_env_internal = os.getenv(ENV_VAR_DB_URL_INTERNAL)
    db_url_env_external = os.getenv(ENV_VAR_DB_URL_EXTERNAL)
    default_db_url = db_url_env_internal or db_url_env_external
    is_required = default_db_url is None

    parser.add_argument(
        "--db-url",
        type=str,
        default=default_db_url,
        help="Database connection string (SQLAlchemy format). Overrides env vars "
        + ENV_VAR_DB_URL_INTERNAL
        + " (preferred) or "
        + ENV_VAR_DB_URL_EXTERNAL
        + ".",
        required=is_required,
    )

    parser.add_argument(
        "--email",
        type=str,
        default=os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL),
        help="Email address for the admin user. Overrides ADMIN_EMAIL env var.",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=DEFAULT_ADMIN_NAME,
        help="Full name for the admin user.",
    )
    parser.add_argument(
        "--key-name",
        type=str,
        default=DEFAULT_ADMIN_KEY_NAME,
        help="Name for the initial admin API key.",
    )

    default_creds_path = os.path.join(".", DEFAULT_CREDENTIALS_FILENAME)
    default_dotenv_update_path = os.path.join(".", DEFAULT_DOTENV_FILENAME)

    parser.add_argument(
        "--creds-file",
        type=str,
        default=default_creds_path,
        help="Output file path inside the container for admin credentials (plain text).",
    )
    parser.add_argument(
        "--dotenv-path",
        type=str,
        default=default_dotenv_update_path,
        help="Path inside the container to the .env file to attempt updating.",
    )

    args = parser.parse_args()

    if not args.db_url:
        parser.error(
            "Database URL is required. Please set the "
            + ENV_VAR_DB_URL_INTERNAL
            + " (preferred) or "
            + ENV_VAR_DB_URL_EXTERNAL
            + " environment variable inside the container, or use the --db-url argument."
        )
    elif args.db_url == db_url_env_external and db_url_env_internal:
        logging_utility.warning(
            "Using DB URL from "
            + ENV_VAR_DB_URL_EXTERNAL
            + " ('"
            + db_url_env_external[:15]
            + "...') even though "
            + ENV_VAR_DB_URL_INTERNAL
            + " ('"
            + db_url_env_internal[:15]
            + "...') is also set. Prefer using "
            + ENV_VAR_DB_URL_INTERNAL
            + " inside the container."
        )
    elif args.db_url == db_url_env_external:
        logging_utility.warning(
            "Using DB URL from "
            + ENV_VAR_DB_URL_EXTERNAL
            + " ('"
            + db_url_env_external[:15]
            + "...'). This URL is typically for host access and might not work correctly inside the container. Ensure "
            + ENV_VAR_DB_URL_INTERNAL
            + " is set correctly in the container's environment for optimal use."
        )

    return args


def run_bootstrap(args):
    SessionLocal = setup_database(args.db_url)
    if not SessionLocal:
        sys.exit(1)

    db: Session | None = None
    try:
        db = SessionLocal()
        admin_user = find_or_create_admin_user(db, args.email, args.name)
        if not admin_user:
            raise Exception("Failed to find or create admin user.")
        plain_text_key, key_prefix = generate_and_save_key(db, admin_user, args.key_name)
        if plain_text_key and key_prefix:
            save_credentials(
                plain_text_key, key_prefix, admin_user, args.creds_file, args.dotenv_path
            )
            print_key_to_console(
                admin_user, key_prefix, plain_text_key, args.creds_file, args.dotenv_path
            )
        elif key_prefix:
            print(
                "Admin user '"
                + admin_user.email
                + "' already exists with key prefix '"
                + key_prefix
                + "'."
            )
            print("No new credentials generated or saved.")
        else:
            logging_utility.warning("Key generation did not return a plain key or prefix.")
    except Exception as e:
        logging_utility.error(
            "An critical error occurred during bootstrap: " + str(e), exc_info=True
        )
        print("\nCritical Error: Bootstrap process failed. Check logs. Error: " + str(e) + "\n")
    finally:
        if db and db.is_active:
            db.close()
            logging_utility.info("Database session closed.")


if __name__ == "__main__":
    print("Starting admin user bootstrap process (running inside container)...")
    logging_utility.info("Admin bootstrap script started.")
    args = parse_arguments()
    logging_utility.info(
        "Running with arguments: Email='"
        + args.email
        + "', DB URL Used='"
        + (args.db_url[: args.db_url.find("@")] if "@" in args.db_url else args.db_url[:25])
        + "...', Output Files='"
        + args.creds_file
        + "', '"
        + args.dotenv_path
        + "'"
    )
    for path in [args.creds_file, args.dotenv_path]:
        target_dir = os.path.dirname(path)
        if os.path.isabs(path) and not os.path.exists(target_dir):
            print(
                "Info: Directory '"
                + target_dir
                + "' for output file '"
                + os.path.basename(path)
                + "' inside container does not exist. Will attempt to create."
            )
    run_bootstrap(args)
    print("Bootstrap process finished.")
    logging_utility.info("Admin bootstrap script finished.")
