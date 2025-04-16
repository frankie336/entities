# scripts/create_user.py
import argparse
import os
import sys
import time

try:

    from projectdavid import Entity
except ImportError:

    try:
        from projectdavid import Entity
    except ImportError as e:
        print(f"Error: Could not import 'projectdavid': {e}")
        print("Please ensure:")
        print(
            "  1. The 'projectdavid' package is correctly installed within the 'api' container image."
        )
        print(
            "  2. The script is run from a location where Python can find the installed packages (e.g., /app/scripts if WORKDIR=/app)."
        )
        sys.exit(1)


# --- Constants ---
# MODIFIED: Default base URL for internal container communication
DEFAULT_BASE_URL = "http://api:9000"
# Default path for reading creds file *if* env var fails (relative to script location inside container)
DEFAULT_CREDS_FILE = "admin_credentials.txt"
DEFAULT_KEY_NAME = "Default Initial Key"
ENV_VAR_ADMIN_KEY = "ADMIN_API_KEY"  # Environment variable to check


# --- Helper Functions ---
def load_admin_key(env_var=ENV_VAR_ADMIN_KEY, creds_file=DEFAULT_CREDS_FILE):
    """
    Loads the Admin API key primarily from environment variable.
    Falls back to credentials file as a secondary option.
    """
    admin_api_key = os.getenv(env_var)
    source = f"environment variable '{env_var}'"

    if not admin_api_key:
        creds_file_path = os.path.join(
            os.path.dirname(__file__), creds_file
        )  # Assume creds file is sibling to script
        if os.path.exists(creds_file_path):
            source = f"credentials file '{creds_file_path}' (inside container)"
            print(f"{env_var} not found in env, attempting to read from {source}")
            try:
                with open(creds_file_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        # Allow for ADMIN_API_KEY or ENTITIES_API_KEY in creds file
                        if line.startswith(f"{ENV_VAR_ADMIN_KEY}=") or line.startswith(
                            "ENTITIES_API_KEY="
                        ):
                            admin_api_key = line.split("=", 1)[1]
                            break
            except Exception as e:
                print(f"Error reading {creds_file_path}: {e}")
                admin_api_key = None
        else:
            print(
                f"{env_var} not found in env, and fallback credentials file '{creds_file_path}' not found."
            )

    if not admin_api_key:
        # Clearer error when running via exec
        raise ValueError(
            f"Admin API key ({env_var}) could not be loaded from environment or fallback file. "
            f"Ensure '{env_var}' is set in the host's .env file before running 'docker compose exec'. "
            f"The host .env file should have been updated after running 'bootstrap_admin.py'."
        )

    print(
        f"Using Admin API Key (loaded from {source}) starting with: {admin_api_key[:4]}...{admin_api_key[-4:]}"
    )
    return admin_api_key


def create_api_client(base_url, api_key):
    """Initializes the API client."""
    print(f"Initializing API client for base URL: {base_url}")
    try:
        client = Entity(base_url=base_url, api_key=api_key)
        if not hasattr(client, "users") or not hasattr(client, "keys"):
            print(
                "Warning: API client might not be fully initialized. Missing 'users' or 'keys' attribute."
            )
        print("API client initialized.")
        return client
    except Exception as e:
        print(f"Error initializing API client: {e}")
        sys.exit(1)


def create_user(client, full_name, email):
    """Creates a new regular user using the admin client."""
    print(f"\nAttempting to create user '{full_name}' ({email})...")
    try:
        new_user = client.users.create_user(
            full_name=full_name,
            email=email,
            is_admin=False,  # Explicitly creating a regular user
        )
        print("\nNew REGULAR user created successfully:")
        print(f"  User ID:    {getattr(new_user, 'id', 'N/A')}")
        print(f"  User Email: {getattr(new_user, 'email', 'N/A')}")
        print(f"  Is Admin:   {getattr(new_user, 'is_admin', 'N/A')}")  # Should be False
        return new_user
    except Exception as e:
        print(f"\nError creating regular user: {e}")
        error_response = getattr(e, "response", None)
        if error_response is not None:
            print(f"Status Code: {error_response.status_code}")
            try:
                error_detail = error_response.json()
            except Exception:
                error_detail = error_response.text
            print(f"Response Body: {error_detail}")
        return None


def generate_user_key(admin_client, user, key_name=DEFAULT_KEY_NAME):
    """Generates an initial API key for the specified user using admin credentials."""
    if not user or not hasattr(user, "id"):
        print("\nSkipped API key generation: User object is invalid or missing ID.")
        return None

    target_user_id = user.id
    user_email = getattr(user, "email", "N/A")

    print(
        f"\nAttempting to generate initial API key ('{key_name}') for user {target_user_id} ({user_email})..."
    )
    try:
        key_payload = {"key_name": key_name}
        print(
            f"Calling SDK method 'create_key_for_user' on admin client for user ID {target_user_id}"
        )
        key_creation_response = admin_client.keys.create_key_for_user(
            target_user_id=target_user_id, **key_payload
        )

        plain_text_key = getattr(key_creation_response, "plain_key", None)
        if plain_text_key:
            print("\n" + "=" * 50)
            print("  Initial API Key Generated for Regular User (by Admin)!")
            print(f"  User ID:    {target_user_id}")
            print(f"  User Email: {user_email}")
            key_details = getattr(key_creation_response, "details", None)
            key_prefix = getattr(key_details, "prefix", "N/A") if key_details else "N/A"
            actual_key_name = getattr(key_details, "name", "N/A") if key_details else "N/A"
            print(f"  Key Prefix: {key_prefix}")
            print(f"  Key Name:   {actual_key_name}")
            print("-" * 50)
            print(f"  PLAIN TEXT API KEY: {plain_text_key}")
            print("-" * 50)
            print("  >>> Provide this key to the regular user for their API access. <<<")
            print("=" * 50 + "\n")
            return plain_text_key
        else:
            print("\nAPI call successful, but plain text key not found in the response.")
            print(f"Response details received: {key_creation_response}")
            return None

    except AttributeError as ae:
        print("\n--- SDK ERROR ---")
        print(f"AttributeError: {ae}")
        print("Could not find the required method (e.g., `create_key_for_user`) on the SDK client.")
        print("Verify SDK version and initialization.")
        print("--- END SDK ERROR ---")
        return None
    except Exception as key_gen_e:
        print(f"\nError generating key for user {target_user_id}: {key_gen_e}")
        error_response = getattr(key_gen_e, "response", None)
        if error_response is not None:
            print(f"Status Code: {error_response.status_code}")
            try:
                error_detail = error_response.json()
            except Exception:
                error_detail = error_response.text
            print(f"Response Body: {error_detail}")
            if error_response.status_code == 404:
                print(f"Hint: Check API endpoint POST /v1/admin/users/{target_user_id}/keys")
            elif error_response.status_code == 403:
                print("Hint: Ensure the ADMIN_API_KEY has permission.")
            elif error_response.status_code == 422:
                print("Hint: Check the key_payload.")
        else:
            print(f"An unexpected error occurred: {key_gen_e}")
        return None


def main():
    """Main script execution function."""
    parser = argparse.ArgumentParser(
        description="Create a new regular user and generate an initial API key using admin credentials (run inside API container).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--email",
        type=str,
        help="Email address for the new user. If omitted, a unique default is generated.",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Full name for the new user. If omitted, a default name is used.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=os.getenv("ASSISTANTS_BASE_URL", DEFAULT_BASE_URL),  # Prefer env var if set
        help=f"Base URL for the API. Defaults to ASSISTANTS_BASE_URL env var or {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--creds-file",
        type=str,
        default=DEFAULT_CREDS_FILE,
        help=f"Fallback path (relative to script) inside container for admin credentials file. Default: {DEFAULT_CREDS_FILE}",
    )
    parser.add_argument(
        "--key-name",
        type=str,
        default=DEFAULT_KEY_NAME,
        help=f"Name for the initial API key generated for the user. Default: '{DEFAULT_KEY_NAME}'",
    )

    args = parser.parse_args()

    # --- Load Environment Variables from .env if present (less critical now) ---
    # load_dotenv() # Can be useful for local testing, but rely on inherited env for exec

    # --- Get Admin API Key ---
    try:
        # Pass the specific path from args if the user overrode the default
        admin_api_key = load_admin_key(creds_file=args.creds_file)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # --- Initialize Admin Client ---
    # Use the potentially overridden base_url from args
    admin_client = create_api_client(args.base_url, admin_api_key)

    # --- Determine User Details ---
    timestamp = int(time.time())
    user_email = args.email or f"test_user_{timestamp}@example.com"
    user_full_name = args.name or f"Regular User {timestamp}"

    # --- Create User ---
    new_user = create_user(admin_client, user_full_name, user_email)

    # --- Generate Key (if user created) ---
    if new_user:
        # Use the potentially overridden key_name from args
        generate_user_key(admin_client, new_user, key_name=args.key_name)
    else:
        print("\nSkipping API key generation due to user creation failure.")

    print("\nScript finished.")


if __name__ == "__main__":
    main()
