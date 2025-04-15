#!/usr/bin/env python
import argparse
import json
import logging
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
from os.path import getsize, islink
from pathlib import Path
from urllib.parse import quote_plus  # Needed for password escaping in URL

# Third-party import
try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required. Please install it: pip install PyYAML",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


DEFAULT_DB_CONTAINER_PORT = "3306"
DEFAULT_DB_SERVICE_NAME = "db"


class DockerOrchestrationManager:
    """
    Manages Docker Compose stack operations (up/down) and .env file generation
    for running pre-built application images. Assumes API and Sandbox images
    are pulled, not built locally.
    """

    # --- Class Attributes ---
    _ENV_FILE = ".env"
    _DOCKER_COMPOSE_FILE = "docker-compose.yml" # Assumes the orchestration yml is named this

    _OLLAMA_IMAGE = "ollama/ollama"
    _OLLAMA_CONTAINER = "ollama"
    _OLLAMA_PORT = "11434"

    # Mapping: .env key -> (docker-compose service name, compose env var name)
    # ONLY include vars DEFINED in the orchestration compose file's environment section.
    # Primarily for DB credentials. Other vars come from defaults or generated secrets.
    _COMPOSE_ENV_MAPPING = {
        "MYSQL_ROOT_PASSWORD": (DEFAULT_DB_SERVICE_NAME, "MYSQL_ROOT_PASSWORD"),
        "MYSQL_DATABASE": (DEFAULT_DB_SERVICE_NAME, "MYSQL_DATABASE"),
        "MYSQL_USER": (DEFAULT_DB_SERVICE_NAME, "MYSQL_USER"),
        "MYSQL_PASSWORD": (DEFAULT_DB_SERVICE_NAME, "MYSQL_PASSWORD"),
        # Add QDRANT__LOG_LEVEL if it's consistently defined ONLY in compose env
        # 'QDRANT__LOG_LEVEL': ('qdrant', 'QDRANT__LOG_LEVEL'),
    }

    # Define keys that should always be generated using secrets module if not found elsewhere
    _GENERATED_SECRETS = [
        "SIGNED_URL_SECRET",
        "API_KEY", # Assuming the pre-built API image still needs this in .env
        "SECRET_KEY", # Application specific secret key (e.g., for FastAPI)
        # Add other secrets expected by the pre-built images here
    ]

    # Define Tool IDs to be generated (assuming pre-built images need these)
    _GENERATED_TOOL_IDS = [
        "TOOL_CODE_INTERPRETER",
        "TOOL_WEB_SEARCH",
        "TOOL_COMPUTER",
        "TOOL_VECTOR_STORE_SEARCH",
    ]

    # Define default values for keys if they aren't sourced from compose or generated
    # These MUST align with what the pre-built images expect.
    _DEFAULT_VALUES = {
        # --- Base URLs (Verify these are correct for container-to-container comms or host access) ---
        "ASSISTANTS_BASE_URL": "http://api:9000", # Internal URL for container comms
        "SANDBOX_SERVER_URL": "http://sandbox:8000", # Internal URL for container comms
        "DOWNLOAD_BASE_URL": "http://api:9000/v1/files/download", # Internal URL? Or localhost if accessed from host?
        "HYPERBOLIC_BASE_URL": "https://api.hyperbolic.xyz/v1", # External service
        "QDRANT_URL": "http://qdrant:6333", # Internal Qdrant URL
        # --- Database Components Fallbacks (if not in compose) ---
        "MYSQL_HOST": DEFAULT_DB_SERVICE_NAME, # Usually the service name for internal comms
        "MYSQL_PORT": DEFAULT_DB_CONTAINER_PORT,
        "MYSQL_DATABASE": "cosmic_catalyst", # Default DB name (should match compose)
        "MYSQL_USER": "ollama", # Default app user name (should match compose)
        # --- Platform Settings ---
        "BASE_URL_HEALTH": "http://api:9000/v1/health", # Internal health check URL
        "SHELL_SERVER_URL": "ws://sandbox:8000/ws/computer", # Internal WS URL
        "CODE_EXECUTION_URL": "ws://sandbox:8000/ws/execute", # Internal WS URL
        "DISABLE_FIREJAIL": "true", # Default value (Verify if pre-built sandbox needs this)
        # --- SMB Client Config (Using service names for internal access) ---
        "SMBCLIENT_SERVER": "samba_server",
        "SMBCLIENT_SHARE": "cosmic_share",
        "SMBCLIENT_USERNAME": "samba_user", # Default user (align with compose)
        "SMBCLIENT_PASSWORD": "default", # Default password (align with compose)
        "SMBCLIENT_PORT": "445",
        # --- Other Standard Vars ---
        "LOG_LEVEL": "INFO",
        "PYTHONUNBUFFERED": "1", # Often useful for container logs
    }

    # Define the structure and order of the final .env file
    # This structure should include ALL variables the pre-built images expect.
    _ENV_STRUCTURE = {
        "Base URLs": [
            "ASSISTANTS_BASE_URL",
            "SANDBOX_SERVER_URL",
            "DOWNLOAD_BASE_URL",
            "HYPERBOLIC_BASE_URL",
            "QDRANT_URL", # Added Qdrant URL
            # Add OLLAMA_URL if needed: 'OLLAMA_URL': 'http://ollama:11434',
            ],
        "Database Configuration": [
            "DATABASE_URL", # Internal connection string used by API/Sandbox
            "SPECIAL_DB_URL", # External connection string for host tools (e.g., bootstrap script)
            "MYSQL_ROOT_PASSWORD",
            "MYSQL_DATABASE",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_HOST", # Explicitly add if needed by some tool
            "MYSQL_PORT", # Explicitly add if needed by some tool
        ],
        "API Keys & Secrets": [
            "API_KEY",
            "SIGNED_URL_SECRET",
            "SECRET_KEY",
        ],
        "Platform Settings": [
            "BASE_URL_HEALTH",
            "SHELL_SERVER_URL",
            "CODE_EXECUTION_URL",
            "DISABLE_FIREJAIL",
        ],
        "SMB Client Configuration": [
            "SMBCLIENT_SERVER",
            "SMBCLIENT_SHARE",
            "SMBCLIENT_USERNAME",
            "SMBCLIENT_PASSWORD",
            "SMBCLIENT_PORT",
        ],
        "Tool Identifiers": [
            "TOOL_CODE_INTERPRETER",
            "TOOL_WEB_SEARCH",
            "TOOL_COMPUTER",
            "TOOL_VECTOR_STORE_SEARCH",
        ],
        "Other": [
            "LOG_LEVEL",
            "PYTHONUNBUFFERED",
        ],
    }

    # --- Initialization ---
    def __init__(self, args):
        """Initializes the DockerOrchestrationManager."""
        self.args = args
        self.is_windows = platform.system() == "Windows"
        self.log = log

        if self.args.verbose:
            self.log.setLevel(logging.DEBUG)
        self.log.debug("DockerOrchestrationManager initialized with args: %s", args)

        self.compose_config = self._load_compose_config() # Load config early

        # Initial setup steps
        self._check_for_required_env_file() # Check/generate the actual .env file
        self._configure_shared_path()
        # self._ensure_dockerignore() # Less critical if not building

    # --- Core Docker/System Command Execution ---
    def _run_command(
        self,
        cmd_list,
        check=True,
        capture_output=False,
        text=True,
        suppress_logs=False,
        **kwargs,
    ):
        """Helper method to run shell commands using subprocess."""
        if not suppress_logs:
            self.log.info("Running command: %s", " ".join(cmd_list))
        try:
            result = subprocess.run(
                cmd_list,
                check=check,
                capture_output=capture_output,
                text=text,
                shell=self.is_windows,
                **kwargs,
            )
            if not suppress_logs:
                self.log.debug("Command finished: %s", " ".join(cmd_list))
                if result.stdout:
                    self.log.debug("Command stdout:\n%s", result.stdout.strip())
                if result.stderr and result.stderr.strip():
                    self.log.debug("Command stderr:\n%s", result.stderr.strip())
            return result
        except subprocess.CalledProcessError as e:
            self.log.error(f"Command failed: {' '.join(cmd_list)}")
            self.log.error(f"Return Code: {e.returncode}")
            if e.stdout:
                self.log.error("STDOUT:\n%s", e.stdout.strip())
            if e.stderr:
                self.log.error("STDERR:\n%s", e.stderr.strip())
            if check:
                raise
            return e
        except Exception as e:
            self.log.error(
                f"Error running command {' '.join(cmd_list)}: {e}",
                exc_info=self.args.verbose,
            )
            raise

    # --- .dockerignore Generation (Optional but harmless) ---
    def _ensure_dockerignore(self):
        """Generates a default .dockerignore file if it doesn't exist."""
        dockerignore = Path(".dockerignore")
        if not dockerignore.exists():
            self.log.info(".dockerignore not found. Generating a minimal one.")
            # Minimal version, mostly for .env
            dockerignore.write_text("__pycache__/\n.venv/\n*.pyc\n.git/\n.env*\n.env\n")
            self.log.info("Generated minimal .dockerignore.")

    # --- Environment File Generation ---
    def _load_compose_config(self):
        """Loads and parses the docker-compose.yml file."""
        compose_path = Path(self._DOCKER_COMPOSE_FILE)
        if not compose_path.is_file():
            self.log.error(
                f"Docker compose file '{self._DOCKER_COMPOSE_FILE}' not found. Cannot generate .env correctly."
            )
            # Allow continuing but .env generation will be limited
            return None
        try:
            self.log.debug(f"Reading docker compose file: {compose_path}")
            compose_content = compose_path.read_text(encoding="utf-8")
            config = yaml.safe_load(compose_content)
            self.log.debug(f"Successfully parsed {self._DOCKER_COMPOSE_FILE}")
            return config
        except yaml.YAMLError as e:
            self.log.error(f"Error parsing {self._DOCKER_COMPOSE_FILE}: {e}")
            return None
        except Exception as e:
            self.log.error(f"Unexpected error reading {self._DOCKER_COMPOSE_FILE}: {e}")
            return None

    def _get_env_from_compose_service(self, service_name, env_var_name):
        """Safely extracts an environment variable value from a specific service in the loaded compose data."""
        if not self.compose_config:
            return None
        try:
            service_data = self.compose_config.get("services", {}).get(service_name)
            if not service_data:
                self.log.debug(f"Service '{service_name}' not found in compose config.")
                return None

            environment = service_data.get("environment")
            if not environment:
                # Check env_file as well? Less reliable as we don't parse the env_file itself here.
                # For this script, we rely on *explicit* 'environment' definitions in compose
                # for sourcing values directly.
                self.log.debug(
                    f"No explicit 'environment' section found for service '{service_name}' to source '{env_var_name}'."
                )
                return None

            if isinstance(environment, dict):
                return environment.get(env_var_name)
            elif isinstance(environment, list):
                pattern = re.compile(rf"^{re.escape(env_var_name)}(?:=(.*))?$")
                for item in environment:
                    match = pattern.match(item)
                    if match:
                        # Return value after '=', or empty string if just 'VARNAME' is present
                        return match.group(1) if match.group(1) is not None else ""
                return None # Not found in the list
            else:
                self.log.warning(
                    f"Unexpected format for 'environment' in service '{service_name}': {type(environment)}"
                )
                return None
        except Exception as e:
            self.log.error(
                f"Error accessing compose env for {service_name}/{env_var_name}: {e}"
            )
            return None

    def _get_host_port_from_compose_service(self, service_name, container_port):
        """Finds the host port mapped to a specific container port for a service."""
        if not self.compose_config:
            self.log.warning(f"Compose config not loaded, cannot determine host port for {service_name}:{container_port}")
            return None
        try:
            service_data = self.compose_config.get("services", {}).get(service_name)
            if not service_data: return None
            ports = service_data.get("ports", [])
            if not ports: return None

            container_port_str = str(container_port) # Ensure string comparison

            for port_mapping in ports:
                # Format examples: "host:container", "container", "ip:host:container"
                parts = str(port_mapping).split(":")
                host_port, cont_port = None, None
                if len(parts) == 1:
                    continue # Only container port specified
                elif len(parts) == 2:
                    host_port, cont_port = parts
                elif len(parts) >= 3: # Handles "ip:host:container" and potential future ipv6 formats
                     host_port, cont_port = parts[-2], parts[-1] # Take the last two parts

                if cont_port == container_port_str:
                    self.log.debug(f"Found host port mapping: {host_port}:{cont_port} for service {service_name}")
                    return host_port.strip()

            self.log.debug(f"No host port found mapped to container port {container_port_str} for service {service_name}")
            return None
        except Exception as e:
            self.log.error(f"Error parsing ports for service {service_name}: {e}")
            return None

    def _generate_dot_env_file(self):
        """
        Generates the .env file based on compose, defaults, and generated values,
        including constructing database URLs and formatting according to _ENV_STRUCTURE.
        """
        self.log.info(f"Generating '{self._ENV_FILE}'...")
        env_values = {}
        generation_log = {}  # Use dict for easier checking {key: comment}

        # 1. Populate from docker-compose environment sections (primarily DB)
        if self.compose_config:
             for env_key, (service_name, compose_key) in self._COMPOSE_ENV_MAPPING.items():
                value = self._get_env_from_compose_service(service_name, compose_key)
                if value is not None:
                    env_values[env_key] = str(value)
                    generation_log[env_key] = (
                        f"Value sourced from {self._DOCKER_COMPOSE_FILE} ({service_name}/{compose_key})"
                    )
                else:
                    generation_log[env_key] = (
                        f"NOT found in {self._DOCKER_COMPOSE_FILE} ({service_name}/{compose_key}), will use default/generate."
                    )
        else:
            self.log.warning(f"Cannot source values from {self._DOCKER_COMPOSE_FILE} as it wasn't loaded.")
            for env_key in self._COMPOSE_ENV_MAPPING.keys():
                 generation_log[env_key] = "Skipped compose sourcing: File not loaded"

        # 2. Fill in missing values with defaults
        for key, default_value in self._DEFAULT_VALUES.items():
            if key not in env_values:
                env_values[key] = default_value
                generation_log[key] = "Using default value"

        # 3. Generate required secrets if not already set
        for key in self._GENERATED_SECRETS:
            if key not in env_values:
                # Use appropriate lengths for known keys
                length = 16 if key == "API_KEY" else 32
                env_values[key] = secrets.token_hex(length)
                generation_log[key] = f"Generated new secret value ({length*2} hex chars)"

        # 4. Generate Tool IDs if not already set
        for key in self._GENERATED_TOOL_IDS:
            if key not in env_values:
                env_values[key] = f"tool_{secrets.token_hex(10)}"
                generation_log[key] = "Generated new tool ID"

        # --- 5. Construct Composite Database URLs ---
        # Use values potentially sourced from compose or defaults
        db_user = env_values.get("MYSQL_USER")
        db_pass = env_values.get("MYSQL_PASSWORD") # Password might be missing if not in compose/defaults
        db_host_internal = env_values.get("MYSQL_HOST", DEFAULT_DB_SERVICE_NAME) # Internal name default
        db_port_internal = env_values.get("MYSQL_PORT", DEFAULT_DB_CONTAINER_PORT)
        db_name = env_values.get("MYSQL_DATABASE")

        if all([db_user, db_pass is not None, db_host_internal, db_port_internal, db_name]):
            escaped_pass = quote_plus(str(db_pass))

            # Internal URL (for API/Sandbox containers)
            env_values["DATABASE_URL"] = (
                f"mysql+pymysql://{db_user}:{escaped_pass}@{db_host_internal}:{db_port_internal}/{db_name}"
            )
            generation_log["DATABASE_URL"] = "Constructed internal DB URL"

            # External URL (for host tools) - Requires host port mapping
            host_db_port = self._get_host_port_from_compose_service(
                DEFAULT_DB_SERVICE_NAME, DEFAULT_DB_CONTAINER_PORT
            )
            if host_db_port:
                env_values["SPECIAL_DB_URL"] = (
                    f"mysql+pymysql://{db_user}:{escaped_pass}@localhost:{host_db_port}/{db_name}"
                )
                generation_log["SPECIAL_DB_URL"] = (
                    f"Constructed external DB URL using host port ({host_db_port})"
                )
            else:
                log.warning(
                    f"Could not find host port mapped to {DEFAULT_DB_SERVICE_NAME}:{DEFAULT_DB_CONTAINER_PORT}. Cannot generate SPECIAL_DB_URL for host access."
                )
                generation_log["SPECIAL_DB_URL"] = (
                    "Skipped external DB URL: Could not find host port mapping"
                )
        else:
            missing_components = [
                k for k,v in {"User": db_user, "Password": db_pass, "Host": db_host_internal, "Port": db_port_internal, "Name": db_name}.items() if v is None
            ]
            log.warning(
                f"Missing one or more database components ({', '.join(missing_components)}). Cannot construct DATABASE_URL/SPECIAL_DB_URL."
            )
            generation_log["DATABASE_URL"] = f"Skipped: Missing DB components ({', '.join(missing_components)})"
            generation_log["SPECIAL_DB_URL"] = f"Skipped: Missing DB components ({', '.join(missing_components)})"


        # --- 6. Format the output .env file ---
        env_lines = [f"# Auto-generated .env file by {os.path.basename(__file__)}", ""]
        processed_keys = set()

        for section_name, keys_in_section in self._ENV_STRUCTURE.items():
            env_lines.append(f"#############################")
            env_lines.append(f"# {section_name}")
            env_lines.append(f"#############################")
            found_key_in_section = False
            for key in keys_in_section:
                if key in env_values:
                    value = str(env_values[key]) # Ensure string
                    # Simple quoting: quote if value contains space, #, =, ", or starts/ends with quotes
                    needs_quoting = any(c in value for c in [' ', '#', '=']) or \
                                    (value.startswith('"') and value.endswith('"')) or \
                                    (value.startswith("'") and value.endswith("'")) or \
                                    value == "" # Quote empty strings

                    if needs_quoting:
                        # Escape existing backslashes and double quotes
                        escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                        env_lines.append(f'{key}="{escaped_value}"')
                    else:
                        env_lines.append(f"{key}={value}")

                    processed_keys.add(key)
                    found_key_in_section = True
            if not found_key_in_section:
                env_lines.append(f"# (No variables configured for this section)")
            env_lines.append("")

        # Add any remaining keys (should be few if _ENV_STRUCTURE is comprehensive)
        remaining_keys = sorted(list(set(env_values.keys()) - processed_keys))
        if remaining_keys:
            env_lines.append(f"#############################")
            env_lines.append(f"# Other (Uncategorized)")
            env_lines.append(f"#############################")
            for key in remaining_keys:
                 value = str(env_values[key]) # Ensure string
                 needs_quoting = any(c in value for c in [' ', '#', '=']) or \
                                 (value.startswith('"') and value.endswith('"')) or \
                                 (value.startswith("'") and value.endswith("'")) or \
                                 value == ""
                 if needs_quoting:
                     escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                     env_lines.append(f'{key}="{escaped_value}"')
                 else:
                     env_lines.append(f"{key}={value}")
            env_lines.append("")

        content = "\n".join(env_lines)

        try:
            with open(self._ENV_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            self.log.info(f"Successfully generated '{self._ENV_FILE}'.")
            if self.args.verbose:
                self.log.debug("--- .env Generation Log ---")
                for key, comment in sorted(generation_log.items()):
                    if key in env_values: # Only log for keys actually written
                        self.log.debug(f"  - {key}: {comment}")
                self.log.debug(f"--- Generated {self._ENV_FILE} Content ---")
                self.log.debug(f"\n{content}\n")
                self.log.debug(f"--- End {self._ENV_FILE} Content ---")
        except IOError as e:
            self.log.error(f"Failed to write generated {self._ENV_FILE}: {e}")
            sys.exit(1)

    def _check_for_required_env_file(self):
        """Checks if the actual .env file exists; if not, generates it."""
        self.log.debug(f"Checking for required '{self._ENV_FILE}' file...")
        if not os.path.exists(self._ENV_FILE):
            self.log.warning(
                f"Required environment file '{self._ENV_FILE}' is missing."
            )
            self._generate_dot_env_file()
        else:
            self.log.info(
                f"Required environment file '{self._ENV_FILE}' exists. NOT overwriting."
            )
            # Optionally load it if needed by other parts of the script (e.g., SHARED_PATH default)
            # load_dotenv(dotenv_path=self._ENV_FILE)
            # self.log.debug(f"Loaded existing environment variables from '{self._ENV_FILE}'.")

    # --- Shared Path Configuration ---
    def _configure_shared_path(self):
        """Ensures SHARED_PATH is set and the directory exists."""
        system = platform.system().lower()
        shared_path_env = os.environ.get("SHARED_PATH")
        if shared_path_env:
            shared_path = shared_path_env
            self.log.info(
                "Using existing SHARED_PATH from environment: %s", shared_path
            )
        else:
            # Define platform-specific defaults
            default_base = os.path.expanduser("~")
            if system == "windows":
                shared_path = os.path.join(default_base, "entities_share")
            elif system == "linux":
                shared_path = os.path.join(
                    default_base, ".local", "share", "entities_share"
                )
            elif system == "darwin": # macOS
                shared_path = os.path.join(
                    default_base, "Library", "Application Support", "entities_share"
                )
            else:
                self.log.error(
                    "Unsupported OS: %s. Cannot set default SHARED_PATH.", system
                )
                # Fallback to a simple relative path? Or raise error?
                shared_path = "./entities_share"
                self.log.warning(f"Defaulting SHARED_PATH to relative path: {shared_path}")
                # raise RuntimeError("Unsupported OS for default SHARED_PATH")

            self.log.info("Defaulting SHARED_PATH to: %s", shared_path)
            # Set it in the current process environment so compose can use it if needed
            os.environ["SHARED_PATH"] = shared_path

        # Ensure the directory exists
        try:
            Path(shared_path).mkdir(parents=True, exist_ok=True)
            self.log.info("Ensured shared directory exists: %s", shared_path)
        except OSError as e:
            self.log.error(
                f"Failed to create shared directory {shared_path}: {e}. Check permissions."
            )
            # This might not be fatal if the user fixes permissions later

    # --- Ollama Integration (Keep as is) ---
    def _has_docker(self):
        return shutil.which("docker") is not None

    def _is_container_running(self, container_name):
        try:
            result = self._run_command(
                ["docker", "ps", "--filter", f"name=^{container_name}$", "--quiet"],
                capture_output=True, text=True, check=False, suppress_logs=True,
            )
            return bool(result.stdout.strip())
        except Exception: return False # Simplified error handling

    def _is_image_present(self, image_name):
        try:
            result = self._run_command(
                ["docker", "images", image_name, "--quiet"],
                capture_output=True, text=True, check=False, suppress_logs=True,
            )
            return bool(result.stdout.strip())
        except Exception: return False

    def _has_nvidia_support(self):
        has_smi = shutil.which("nvidia-smi") is not None
        if has_smi:
            try:
                self._run_command(["nvidia-smi"], check=True, capture_output=True, suppress_logs=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError): return False
        return False

    def _start_ollama(self, cpu_only=True):
        """Starts the external Ollama container."""
        if not self._has_docker():
            self.log.error("❌ Docker command not found. Cannot start external Ollama.")
            return False
        container_name = self._OLLAMA_CONTAINER
        if self._is_container_running(container_name):
            self.log.info(f"✅ External Ollama container '{container_name}' is already running.")
            return True
        image_name = self._OLLAMA_IMAGE
        if not self._is_image_present(image_name):
            self.log.info(f"📦 Pulling Ollama image '{image_name}'...")
            try: self._run_command(["docker", "pull", image_name], check=True)
            except Exception as e:
                self.log.error(f"❌ Failed to pull Ollama image '{image_name}': {e}")
                return False
        self.log.info(f"🚀 Starting external Ollama container '{container_name}'...")
        cmd = ["docker", "run", "-d", "--rm", "-v", "ollama:/root/.ollama",
               "-p", f"{self._OLLAMA_PORT}:{self._OLLAMA_PORT}", "--name", container_name]
        if not cpu_only and self._has_nvidia_support():
            self.log.info("   Attempting GPU support (--gpus=all).")
            cmd.insert(2, "--gpus=all")
        elif not cpu_only:
            self.log.warning("   GPU requested but unavailable/unsupported. Starting in CPU mode.")
        cmd.append(image_name) # Add image name at the end
        try:
            self._run_command(cmd, check=True)
            self.log.info(f"   Waiting briefly for '{container_name}' to initialize...")
            time.sleep(4) # Slightly longer wait
            if self._is_container_running(container_name):
                self.log.info(f"✅ External Ollama container '{container_name}' started successfully.")
                return True
            else:
                self.log.error(f"❌ External Ollama container '{container_name}' failed to start. Check logs: docker logs {container_name}")
                # Try showing logs directly
                try: self._run_command(["docker", "logs", container_name], check=False, suppress_logs=False)
                except Exception: pass # Ignore errors fetching logs here
                return False
        except Exception as e:
            self.log.error(f"❌ Failed to execute docker run command for Ollama: {e}")
            return False

    def _ensure_ollama(self, opt_in=False, use_gpu=False):
        """Manages the external Ollama container start if requested."""
        if not opt_in:
            self.log.info("ℹ️ External Ollama management not requested via --with-ollama. Skipping.")
            return True
        self.log.info("--- External Ollama Setup ---")
        # Basic checks
        if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_HOST"):
            self.log.warning("🛰 Running inside Docker or remote daemon. Skipping external Ollama management.")
            return True
        if not self._has_docker():
            self.log.error("❌ Docker command not found. Cannot manage external Ollama.")
            return False
        # GPU Handling
        if platform.system() == "Darwin":
            self.log.warning("⚠️ macOS detected. GPU passthrough may be limited. Native Ollama app recommended for GPU.")
        gpu_available = self._has_nvidia_support()
        attempt_gpu = use_gpu and gpu_available
        mode_str = "GPU" if attempt_gpu else "CPU"
        if use_gpu and not gpu_available and platform.system() != "Darwin":
            self.log.warning("⚠️ GPU requested (--ollama-gpu), but unavailable/unsupported. Proceeding in CPU mode.")
        # Start Ollama
        self.log.info(f"Attempting to start external Ollama container in {mode_str} mode...")
        success = self._start_ollama(cpu_only=not attempt_gpu)
        self.log.info("--- End External Ollama Setup ---")
        return success

    # --- Docker Compose Actions ---
    def _handle_nuke(self):
        """Stops stack, removes volumes, prunes ALL docker resources."""
        self.log.warning("!!! NUKE MODE ACTIVATED !!!")
        self.log.warning("This will: 1) Stop/remove this project's containers/volumes. 2) Prune ALL unused Docker data (containers, networks, images, build cache, VOLUMES).")
        try: confirm = input("Type 'confirm nuke' to proceed: ")
        except EOFError:
            self.log.error("Nuke requires interactive confirmation. Aborting."); sys.exit(1)
        if confirm != "confirm nuke":
            self.log.info("Nuke operation cancelled."); sys.exit(0)
        self.log.info("Proceeding with Docker nuke...")
        self.log.info("Step 1: Bringing down compose stack...")
        try: self._run_command(["docker", "compose", "down", "--volumes", "--remove-orphans"], check=False)
        except Exception as e: self.log.warning(f"Error during 'compose down': {e}. Continuing nuke.")
        self.log.warning("Step 2: Pruning ALL Docker system resources...")
        try: self._run_command(["docker", "system", "prune", "-a", "--volumes", "--force"], check=True)
        except Exception as e: self.log.critical(f"Critical error during 'system prune': {e}"); sys.exit(1)
        self.log.info("Docker environment nuke completed.")

    def _handle_down(self):
        """Stops containers, optionally removing volumes."""
        target_services = self.args.services or []
        target_desc = f" for services: {', '.join(target_services)}" if target_services else " for all services"
        action = "Stopping containers & removing associated volumes" if self.args.clear_volumes else "Stopping containers"
        self.log.info(f"{action}{target_desc}...")

        if self.args.clear_volumes:
            prompt_msg = f"Remove volumes associated with{' these services' if target_services else ' ALL services'}? (yes/no): "
            try: confirm = input(prompt_msg).lower().strip()
            except EOFError: self.log.error("Confirmation required. Aborting."); sys.exit(1)
            if confirm != "yes":
                self.log.info("Volume deletion cancelled. Stopping containers only.")
                self.args.clear_volumes = False # Update state
            elif target_services:
                self.log.warning("Note: --clear-volumes with specific services might not remove anonymously shared volumes.")

        down_cmd = ["docker", "compose", "down"]
        if self.args.clear_volumes: down_cmd.append("--volumes")
        down_cmd.append("--remove-orphans")
        if target_services: down_cmd.extend(target_services)
        try:
            self._run_command(down_cmd, check=False) # Don't fail script if down has minor issues
            final_action = "Stopping containers & removing volumes" if self.args.clear_volumes else "Stopping containers"
            self.log.info(f"{final_action} command completed.")
        except Exception as e: self.log.error(f"Error during 'docker compose down': {e}")

    def _handle_up(self):
        """Starts containers using docker compose up."""


        if not os.path.exists(self._ENV_FILE):
            self.log.error(f"Required environment file '{self._ENV_FILE}' is missing. Cannot start.")
            sys.exit(1)
        self.log.debug(f"Verified '{self._ENV_FILE}' exists.")

        mode = "attached" if self.args.attached else "detached (-d)"
        target_services = self.args.services or []
        target_desc = f" for services: {', '.join(target_services)}" if target_services else " all services"
        force_recreate_opt = " (with --force-recreate)" if self.args.force_recreate else ""
        self.log.info(f"Starting containers{target_desc} in {mode} mode{force_recreate_opt}...")

        up_cmd = ["docker", "compose", "up"]
        if not self.args.attached: up_cmd.append("-d")
        if self.args.force_recreate: up_cmd.append("--force-recreate")
        # Add --pull always or optionally? For orchestration, always pulling might be desired.
        up_cmd.append("--pull") # Add policy 'always' to ensure latest pre-built images are used
        up_cmd.append("always")
        # Or add a flag --pull-latest? For now, default to always pull.
        self.log.info("   (Will attempt to pull latest images for services)")

        if target_services: up_cmd.extend(target_services)

        try:
            self._run_command(up_cmd, check=True)
            self.log.info("Containers started successfully.")
            if not self.args.attached:
                logs_cmd_base = ["docker", "compose", "logs", "-f", "--tail=50"]
                if target_services: logs_cmd_base.extend(target_services)
                self.log.info(f"View logs: {' '.join(logs_cmd_base)}")
        except subprocess.CalledProcessError as e:
            self.log.critical(f"'docker compose up' failed (Code: {e.returncode}).")
            self.log.info("Attempting to show logs...")
            try:
                logs_cmd_fail = ["docker", "compose", "logs", "--tail=100"]
                if target_services: logs_cmd_fail.extend(target_services)
                self._run_command(logs_cmd_fail, check=False, suppress_logs=False)
            except Exception as log_e: self.log.error(f"Could not fetch logs: {log_e}")
            sys.exit(1)
        except Exception as e:
            self.log.critical(f"Unexpected error during 'up': {e}", exc_info=self.args.verbose)
            sys.exit(1)

    def run(self):
        """Main execution logic based on parsed arguments."""
        # Handle Ollama setup first if requested
        if self.args.with_ollama:
            ollama_ok = self._ensure_ollama(opt_in=True, use_gpu=self.args.ollama_gpu)
            if not ollama_ok:
                self.log.warning("External Ollama setup failed or skipped. Continuing...")

        # Nuke is exclusive
        if self.args.nuke:
            self._handle_nuke()
            sys.exit(0)

        mode = self.args.mode

        # Down action (if requested or implied)
        if self.args.down or self.args.clear_volumes or mode == "down_only":
            self._handle_down()
            if mode == "down_only":
                sys.exit(0)

        # Up action (default or explicit)
        if mode == "up":
            self._handle_up()

        self.log.info("Orchestration management script finished.")

    @staticmethod
    def parse_args():
        """Parses command-line arguments with validation for orchestration use."""
        parser = argparse.ArgumentParser(
            description="Manage Docker Compose stack for pre-built images: run 'up'/'down', setup .env, and optionally manage external Ollama.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        # Core Actions
        parser.add_argument(
            "--mode",
            choices=["up", "down_only"], # Simplified modes
            default="up",
            help="Primary action: 'up' starts the stack, 'down_only' stops it.",
        )
        parser.add_argument(
            "--services",
            nargs="+",
            metavar="SERVICE",
            help="Target specific service(s) for 'up' or 'down'.",
        )
        # Up Options
        parser.add_argument(
            "--attached",
            action="store_true",
            help="Run 'up' attached to the console (shows logs directly)."
        )
        parser.add_argument(
            "--force-recreate",
            action="store_true",
            help="Run 'up' with --force-recreate (useful after image updates)."
        )
        # Down/Cleanup Options
        parser.add_argument(
            "--down",
            action="store_true",
            help="Run 'down' before the 'up' action (if mode is 'up')."
        )
        parser.add_argument(
            "--clear-volumes",
            "-v",
            action="store_true",
            help="Implies --down. Removes volumes associated with services being stopped (prompts for confirmation).",
        )
        parser.add_argument(
            "--nuke",
            action="store_true",
            help="DANGER: Stops stack, removes its volumes, and prunes ALL unused Docker resources on your system!"
        )
        # Ollama Management
        parser.add_argument(
            "--with-ollama",
            action="store_true",
            help="Attempt to start/manage an external Ollama container.",
        )
        parser.add_argument(
            "--ollama-gpu",
            action="store_true",
            help="If using --with-ollama, attempt to enable GPU support for it."
        )
        # Utility/Debugging
        parser.add_argument(
            "--verbose",
            "--debug",
            dest="verbose",
            action="store_true",
            help="Enable detailed debug logging.",
        )

        args = parser.parse_args()

        # --- Argument Validation and Implied Actions ---
        if args.clear_volumes:
            args.down = True # --clear-volumes implies --down

        # If only down/clear flags are set with default mode 'up', switch mode to 'down_only'
        if args.down and args.mode == "up" and not (args.attached or args.force_recreate):
             args.mode = "down_only"
             log.debug("Implied mode 'down_only' from --down/--clear-volumes flags.")

        if args.nuke and (args.mode != "up" or args.down or args.clear_volumes or args.with_ollama):
            log.debug("--nuke is exclusive. Other mode/down/ollama flags ignored.")
            # Reset other flags if nuke is set? Or just let them be ignored.
            args.mode = "up" # Nuke implies a final state, doesn't need a mode. Resetting simplifies run logic.
            args.down = False
            args.clear_volumes = False
            args.with_ollama = False


        return args


# --- Main Execution ---
if __name__ == "__main__":
    # Set script name for logging clarity
    script_name = os.path.basename(__file__)
    log_formatter = logging.Formatter(f"%(asctime)s - {script_name} - %(levelname)s - %(message)s")
    # Get the root logger and handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(log_formatter)

    log.info(f"Starting {script_name}...")
    manager = None
    try:
        arguments = DockerOrchestrationManager.parse_args()
        if arguments.verbose:
            log.setLevel(logging.DEBUG) # Set level again in case parse_args reset it
            # Re-apply formatter if handlers were added before setting level
            for handler in root_logger.handlers: handler.setFormatter(log_formatter)
        log.debug("Parsed arguments: %s", arguments)

        manager = DockerOrchestrationManager(arguments)
        manager.run()

    except KeyboardInterrupt:
        log.info("\nOperation cancelled by user.")
        sys.exit(130)
    except subprocess.CalledProcessError as e:
        # Logged within _run_command, just exit
        sys.exit(e.returncode or 1)
    except FileNotFoundError as e:
        log.critical(f"Required command or file not found: {e}")
        sys.exit(1)
    except Exception as e:
        log.critical("An unexpected error occurred: %s", e, exc_info=log.level <= logging.DEBUG)
        sys.exit(1)
