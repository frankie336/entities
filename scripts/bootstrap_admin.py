# scripts/bootstrap_admin.py
import argparse
import os
import sys
from datetime import datetime
from urllib.parse import quote_plus # Import for potential URL construction

# Use find_dotenv to locate .env reliably, especially if script is run from different depths
from dotenv import find_dotenv, load_dotenv, set_key
from sqlalchemy import create_engine
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session, sessionmaker


try:
    # Assumes the script is in 'scripts/' directory, one level below project root
    # This path adjustment might need review depending on how dependencies are installed inside the container
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        # sys.path.insert(0, project_root) # Comment out or remove if causing issues inside container
        pass # Let Python find installed packages normally within the container

    # Now try importing project-specific modules (assuming they are installed in the container's Python env)
    from projectdavid_common import UtilsInterface
    from projectdavid_common.utilities.logging_service import LoggingUtility

    from entities_api.models.models import ApiKey, User

except ImportError as e:
    print(f"Error: Could not import project modules: {e}")
    print("Please ensure:")
    print(f"  1. The script is run from the '/app/scripts' directory inside the container.")
    print(f"  2. The project root ('{project_root}') is relevant for finding modules.")
    print(f"  3. Required packages ('projectdavid_common', 'entities_api') are installed within the 'api' container image.")
    sys.exit(1)
# --- End Path Adjustment & Imports ---


# --- Constants ---
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_NAME = "Default Admin"
DEFAULT_ADMIN_KEY_NAME = "Admin Bootstrap Key"
DEFAULT_CREDENTIALS_FILENAME = "admin_credentials.txt" # Output file location might change when run in container
DEFAULT_DOTENV_FILENAME = ".env" # Location of .env to *read* or *update* might change
ENV_VAR_API_KEY_ADMIN = "ADMIN_API_KEY"
ENV_VAR_API_KEY_ENTITIES = "ENTITIES_API_KEY"

# --- Define DB URL Environment Variables to Check ---
# Priority: 1. --db-url arg, 2. DATABASE_URL env, 3. SPECIAL_DB_URL env
ENV_VAR_DB_URL_INTERNAL = "DATABASE_URL" # Correct var for inside container
ENV_VAR_DB_URL_EXTERNAL = "SPECIAL_DB_URL" # Var for host access


# --- Setup ---
try:
    logging_utility = LoggingUtility()
    identifier_service = UtilsInterface.IdentifierService()
except NameError:
    print("Error: Failed to initialize utilities due to import errors.")
    sys.exit(1)


# --- Helper Functions ---

# (setup_database, find_or_create_admin_user, generate_and_save_key remain the same)
def setup_database(db_url: str) -> sessionmaker | None:
    """Connects to the database and returns a sessionmaker."""
    if not db_url:
        # Updated error message
        logging_utility.error(f"Database URL is not configured. Checked --db-url, {ENV_VAR_DB_URL_INTERNAL}, and {ENV_VAR_DB_URL_EXTERNAL} environment variables.")
        print(f"Error: Database URL not set via --db-url argument or environment variables ({ENV_VAR_DB_URL_INTERNAL}, {ENV_VAR_DB_URL_EXTERNAL}).")
        return None
    try:
        engine = create_engine(db_url, echo=False, pool_pre_ping=True)
        with engine.connect() as connection:
            db_name = connection.engine.url.database
            logging_utility.info(f"Successfully connected to database: {db_name}")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logging_utility.info("Database session factory configured.")
        return SessionLocal
    except sqlalchemy_exc.OperationalError as e:
        logging_utility.error(f"Failed to connect to database: {e}", exc_info=False)
        print(f"\nError: Could not connect to the database.")
        print(f"URL Used: {db_url[:db_url.find('@') if '@' in db_url else 25]}... (Check full URL and credentials)") # Hide password better
        print(f"Details: {e}")
        print(f"Troubleshooting (when running inside container):")
        print(f"  - Is the database service ('db') running and healthy? (`docker compose ps`)")
        print(f"  - Are the credentials (user/password in URL) correct for the 'db' service?")
        print(f"  - Is the database name ('{db_name if 'db_name' in locals() else 'N/A'}') correct?")
        print(f"  - Is the hostname in the URL correct (should be 'db' inside the container)?")
        return None
    except Exception as e:
        logging_utility.error(f"Failed to initialize database engine: {e}", exc_info=True)
        print(f"\nError: An unexpected error occurred during database setup: {e}")
        return None

# (find_or_create_admin_user remains the same)
def find_or_create_admin_user(db: Session, admin_email: str, admin_name: str) -> User | None:
    """Finds the admin user by email or creates a new one."""
    try:
        logging_utility.info(f"Checking for existing admin user: {admin_email}")
        admin_user = db.query(User).filter(User.email == admin_email).first()

        if admin_user:
            logging_utility.warning(
                f"Admin user '{admin_email}' already exists (ID: {admin_user.id})."
            )
            # Ensure the existing user has admin privileges if found by email
            if not admin_user.is_admin:
                logging_utility.warning(
                    f"Existing user {admin_email} found but IS NOT admin. Setting is_admin=True."
                )
                admin_user.is_admin = True
                admin_user.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(admin_user)
                logging_utility.info(f"User {admin_user.id} updated to be an admin.")
            return admin_user
        else:
            # --- Create New Admin User ---
            logging_utility.info(f"Creating new admin user: {admin_email}, Name: {admin_name}")
            admin_user_id = identifier_service.generate_user_id()
            admin_user = User(
                id=admin_user_id,
                email=admin_email,
                full_name=admin_name,
                email_verified=True,  # Assume verified for bootstrap
                oauth_provider="local",  # Indicates created locally
                is_admin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(admin_user)
            logging_utility.info(f"Admin user object created with ID: {admin_user.id}")
            db.commit()  # Commit user creation separately
            db.refresh(admin_user)
            logging_utility.info("Admin user committed to database.")
            return admin_user
    except Exception as e:
        logging_utility.error(
            f"Error finding or creating admin user '{admin_email}': {e}", exc_info=True
        )
        print(f"\nError: Failed during admin user lookup/creation: {e}")
        db.rollback()  # Rollback any partial changes
        return None

# (generate_and_save_key remains the same)
def generate_and_save_key(
    db: Session, admin_user: User, key_name: str
) -> tuple[str | None, str | None]:
    """Generates, hashes, and saves an API key for the admin user. Returns (plain_key, prefix) or (None, existing_prefix)."""
    plain_text_api_key = None
    key_prefix = None
    try:
        logging_utility.info(f"Checking for existing API key for admin user: {admin_user.id}")
        existing_key = db.query(ApiKey).filter(ApiKey.user_id == admin_user.id).first()
        if existing_key:
            logging_utility.warning(
                f"Admin user {admin_user.id} already has an API key (Prefix: {existing_key.prefix}). Skipping key generation."
            )
            print(
                f"\nInfo: Admin user '{admin_user.email}' already has an API key. No new key generated."
            )
            # We don't have the plain text key here, so we can't save it again.
            # Return None to indicate no *new* key was generated.
            return None, existing_key.prefix  # Return None for key, but existing prefix

        logging_utility.info(f"Generating new API key '{key_name}' for admin user: {admin_user.id}")

        # 1. Generate the plain text key (assuming 'ad_' prefix for admin)
        plain_text_api_key = ApiKey.generate_key(prefix="ad_")
        key_prefix = plain_text_api_key[:8]  # Standard prefix length

        # 2. Hash the key
        hashed_key = ApiKey.hash_key(plain_text_api_key)

        # 3. Create the ApiKey DB record
        api_key_record = ApiKey(
            user_id=admin_user.id,
            key_name=key_name,
            hashed_key=hashed_key,
            prefix=key_prefix,
            is_active=True,
            created_at=datetime.utcnow(),
            # expires_at=datetime.utcnow() + timedelta(days=365) # Optional expiration
        )
        db.add(api_key_record)
        logging_utility.info(f"API Key record created (Prefix: {key_prefix})")

        # 4. Commit the API Key
        db.commit()
        logging_utility.info("API Key record committed to database.")
        return plain_text_api_key, key_prefix

    except Exception as e:
        logging_utility.error(
            f"Error generating or saving API key for user {admin_user.id}: {e}",
            exc_info=True,
        )
        print(f"\nError: Failed during API key generation/saving: {e}")
        db.rollback()
        return None, None


# (save_credentials adjusted slightly for container context)
def save_credentials(
    plain_text_key: str,
    key_prefix: str,
    admin_user: User,
    creds_file_path: str,
    dotenv_path: str,
):
    """Saves the generated credentials to the text file and .env file."""
    timestamp = datetime.utcnow().isoformat() + "Z"

    # --- Write details to text file (inside the container) ---
    # Note: Path will be relative to the container's execution context (e.g., /app/scripts/)
    logging_utility.info(f"Attempting to write credentials to: {creds_file_path} (inside container)")
    try:
        # Ensure directory exists *inside the container* if path is nested
        os.makedirs(os.path.dirname(creds_file_path), exist_ok=True)
        file_content = (
            f"# Admin Credentials Generated: {timestamp}\n"
            f"# WARNING: Contains sensitive information.\n"
            f"ADMIN_USER_EMAIL={admin_user.email}\n"
            f"ADMIN_USER_ID={admin_user.id}\n"
            f"ADMIN_KEY_PREFIX={key_prefix}\n"
            f"{ENV_VAR_API_KEY_ADMIN}={plain_text_key}\n"
            f"{ENV_VAR_API_KEY_ENTITIES}={plain_text_key}\n"
        )
        with open(creds_file_path, "w") as f:
            f.write(file_content)
        logging_utility.info(f"Successfully wrote credentials to: {creds_file_path}")
        # Adjust print message for clarity
        print(f"\nInfo: Admin credentials written to: {creds_file_path} (within the 'api' container)")
        print(f"      You may need to copy the key from console output to your host's .env file.")
    except Exception as file_err:
        logging_utility.error(
            f"Failed to write credentials file '{creds_file_path}' inside container: {file_err}",
            exc_info=True,
        )
        print(f"\nWarning: Failed to write credentials file at {creds_file_path} inside container: {file_err}")

    # --- Append/Update details in .env file (inside the container) ---
    # IMPORTANT: Updating the .env file inside the container via `docker exec`
    # WILL NOT affect the already running API process. A container restart (`docker compose restart api`)
    # is required for the main process to pick up changes made to the .env file after it started.
    # Emphasize copying the key from console output to the HOST .env file.
    logging_utility.info(f"Attempting to update .env file at: {dotenv_path} (inside container)")
    try:
        os.makedirs(os.path.dirname(dotenv_path), exist_ok=True)
        # Note: dotenv_path needs to point to the correct .env location inside the container (e.g., /app/.env)
        set_key(dotenv_path, "ADMIN_USER_EMAIL", admin_user.email, quote_mode="always")
        set_key(dotenv_path, "ADMIN_USER_ID", str(admin_user.id), quote_mode="always")
        set_key(dotenv_path, "ADMIN_KEY_PREFIX", key_prefix, quote_mode="always")
        set_key(dotenv_path, ENV_VAR_API_KEY_ADMIN, plain_text_key, quote_mode="always")
        set_key(dotenv_path, ENV_VAR_API_KEY_ENTITIES, plain_text_key, quote_mode="always")

        logging_utility.info(f"Successfully updated .env file: {dotenv_path} (inside container)")
        print(f"Info: Admin credentials also updated in: {dotenv_path} (inside container)")
        print(f"      >>> IMPORTANT: Remember to copy the PLAIN TEXT API KEY from the console output <<<")
        print(f"      >>> and add/update it in the main .env file on your HOST machine. <<<")
        print(f"      >>> Then restart the API service: docker compose restart api <<<")

    except Exception as dotenv_err:
        logging_utility.error(
            f"Failed to update .env file '{dotenv_path}' inside container: {dotenv_err}", exc_info=True
        )
        print(f"\nWarning: Failed to update .env file at {dotenv_path} inside container: {dotenv_err}")


# (print_key_to_console remains the same)
def print_key_to_console(
    user: User,
    key_prefix: str,
    plain_key: str,
    creds_filepath: str,
    dotenv_filepath: str,
):
    """Prints the generated key and confirmation details to the console."""
    print("\n" + "=" * 60)
    print("  IMPORTANT: Admin API Key Generated!")
    print(f"  User Email: {user.email}")
    print(f"  User ID:    {user.id}")
    print(f"  Key Prefix: {key_prefix}")
    print("-" * 60)
    print(f"  PLAIN TEXT API KEY: {plain_key}")
    print("-" * 60)
    print(f"  >>> Action Required: Copy this key and add/update ADMIN_API_KEY / ENTITIES_API_KEY <<<")
    print(f"  >>> in the main .env file on your HOST system, then restart the API service:      <<<")
    print(f"  >>> docker compose restart api                                                    <<<")
    print("-" * 60)
    print(f"  Details also saved/updated inside the container at:")
    print(f"    1. Credentials File: {creds_filepath}")
    print(f"    2. DotEnv File:      {dotenv_filepath}")
    print(f"       (Key saved as both {ENV_VAR_API_KEY_ADMIN} and {ENV_VAR_API_KEY_ENTITIES})")
    print("=" * 60 + "\n")


def parse_arguments():
    """Parses command-line arguments, prioritizing environment variables for DB URL."""
    # Find .env potentially mounted inside container (e.g., /app/.env if WORKDIR is /app)
    # Adjust find_dotenv path if needed, or rely on load_dotenv(verbose=True) to show search paths
    # This loading might not be strictly necessary if docker compose exec passes env vars correctly, but good practice.
    container_dotenv_path = find_dotenv(filename=DEFAULT_DOTENV_FILENAME, raise_error_if_not_found=False)
    if container_dotenv_path:
        logging_utility.info(f"Found .env file inside container at: {container_dotenv_path}")
        load_dotenv(dotenv_path=container_dotenv_path, override=False) # Load existing, don't override existing env vars
    else:
        logging_utility.warning(f"Could not find {DEFAULT_DOTENV_FILENAME} inside container search path. Relying solely on inherited environment variables.")

    parser = argparse.ArgumentParser(
        description="Bootstrap the initial admin user and API key for the Entities API (intended for use inside API container).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # --- Determine DB URL ---
    # Priority: --db-url > DATABASE_URL env > SPECIAL_DB_URL env > Error
    db_url_env_internal = os.getenv(ENV_VAR_DB_URL_INTERNAL)
    db_url_env_external = os.getenv(ENV_VAR_DB_URL_EXTERNAL)

    # Choose the default based on environment variable priority
    default_db_url = db_url_env_internal or db_url_env_external
    is_required = default_db_url is None # Only required if no suitable env var is found

    parser.add_argument(
        "--db-url",
        type=str,
        default=default_db_url,
        help=f"Database connection string (SQLAlchemy format). "
             f"Overrides env vars {ENV_VAR_DB_URL_INTERNAL} (preferred) or {ENV_VAR_DB_URL_EXTERNAL}.",
        required=is_required,
    )

    # --- Other Arguments ---
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

    # --- Output File Paths (relative to container execution path) ---
    # Default to current directory inside container if not specified
    default_creds_path = os.path.join(".", DEFAULT_CREDENTIALS_FILENAME) # e.g., /app/scripts/admin_credentials.txt
    default_dotenv_update_path = os.path.join(".", DEFAULT_DOTENV_FILENAME) # e.g., /app/scripts/.env - might not be the main one!

    parser.add_argument(
        "--creds-file",
        type=str,
        default=default_creds_path,
        help="Output file path inside the container for admin credentials (plain text).",
    )
    parser.add_argument(
        "--dotenv-path",
        type=str,
        default=default_dotenv_update_path, # Carefully consider if this should default to /app/.env or similar
        help="Path inside the container to the .env file to attempt updating.",
    )

    args = parser.parse_args()

    # --- Final Check ---
    if not args.db_url:
        # This error should only trigger if required=True was set, meaning no default was found
        parser.error(
             f"Database URL is required. Please set the {ENV_VAR_DB_URL_INTERNAL} (preferred) or "
             f"{ENV_VAR_DB_URL_EXTERNAL} environment variable inside the container, or use the --db-url argument."
        )
    elif args.db_url == db_url_env_external and db_url_env_internal:
         logging_utility.warning(
             f"Using DB URL from {ENV_VAR_DB_URL_EXTERNAL} ('{db_url_env_external[:15]}...') "
             f"even though {ENV_VAR_DB_URL_INTERNAL} ('{db_url_env_internal[:15]}...') is also set. "
             f"Prefer using {ENV_VAR_DB_URL_INTERNAL} inside the container."
         )
    elif args.db_url == db_url_env_external:
        logging_utility.warning(
             f"Using DB URL from {ENV_VAR_DB_URL_EXTERNAL} ('{db_url_env_external[:15]}...'). "
             f"This URL is typically for host access and might not work correctly inside the container. "
             f"Ensure {ENV_VAR_DB_URL_INTERNAL} is set correctly in the container's environment for optimal use."
         )


    # --- Adjust output paths based on script location if needed ---
    # If the script runs from /app/scripts, make output paths relative to /app maybe?
    # For simplicity, let's assume the defaults relative to the script execution dir are okay for now.
    # User can override with --creds-file /app/admin_credentials.txt --dotenv-path /app/.env if needed

    return args


# --- Main Bootstrap Logic ---
# (run_bootstrap remains the same)
def run_bootstrap(args):
    """Main function to coordinate the bootstrap process."""
    SessionLocal = setup_database(args.db_url)
    if not SessionLocal:
        sys.exit(1)  # Exit if DB setup failed

    db: Session | None = None  # Initialize db to None
    try:
        db = SessionLocal()
        # 1. Find or Create Admin User
        admin_user = find_or_create_admin_user(db, args.email, args.name)
        if not admin_user:
            raise Exception("Failed to find or create admin user.")  # Propagate error

        # 2. Generate and Save Key
        plain_text_key, key_prefix = generate_and_save_key(db, admin_user, args.key_name)

        # 3. Save Credentials and Print Output (only if a *new* key was generated)
        if plain_text_key and key_prefix:
            # Use the potentially adjusted paths
            save_credentials(
                plain_text_key,
                key_prefix,
                admin_user,
                args.creds_file,
                args.dotenv_path,
            )
            print_key_to_console(
                admin_user,
                key_prefix,
                plain_key,
                args.creds_file,
                args.dotenv_path,
            )
        elif key_prefix:  # Existing key found, prefix was returned
            print(f"Admin user '{admin_user.email}' already exists with key prefix '{key_prefix}'.")
            print("No new credentials generated or saved.")
        else:
            # This case shouldn't happen if user exists but key gen failed, error handled in generate_and_save_key
            logging_utility.warning("Key generation did not return a plain key or prefix.")

    except Exception as e:
        logging_utility.error(f"An critical error occurred during bootstrap: {e}", exc_info=True)
        print(f"\nCritical Error: Bootstrap process failed. Check logs. Error: {e}\n")
        # Rollback is handled within helper functions or commit only happens on success
        # db.rollback() might be redundant or cause issues if session already closed
    finally:
        if db and db.is_active:
            db.close()
            logging_utility.info("Database session closed.")


# --- Script Entry Point ---
if __name__ == "__main__":
    print("Starting admin user bootstrap process (running inside container)...")
    logging_utility.info("Admin bootstrap script started.")

    args = parse_arguments()
    # Log the *resolved* DB URL being used
    logging_utility.info(
        f"Running with arguments: Email='{args.email}', DB URL Used='{args.db_url[:args.db_url.find('@') if '@' in args.db_url else 25]}...', Output Files='{args.creds_file}', '{args.dotenv_path}'"
    )

    # --- Pre-run Checks (inside container) ---
    # Permissions are less likely to be an issue inside the container unless volumes are mounted read-only
    for path in [args.creds_file, args.dotenv_path]:
        target_dir = os.path.dirname(path)
        # Basic check if path is absolute and dir doesn't exist
        if os.path.isabs(path) and not os.path.exists(target_dir):
            print(f"Info: Directory '{target_dir}' for output file '{os.path.basename(path)}' inside container does not exist. Will attempt to create.")
        # Write access check is less reliable/meaningful across OS/container contexts here

    # --- Execute Main Logic ---
    run_bootstrap(args)

    print("Bootstrap process finished.")
    logging_utility.info("Admin bootstrap script finished.")
