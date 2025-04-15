#!/usr/bin/env python
import argparse
import logging
import os
import platform
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - DOCKER MANAGER - %(message)s",
)
log = logging.getLogger(__name__)

DEFAULT_DB_CONTAINER_PORT = "3306"
DEFAULT_DB_SERVICE_NAME = "db"
DEFAULT_API_SERVICE_NAME = "api"
DEFAULT_API_PORT = "9000"
DEFAULT_SANDBOX_SERVICE_NAME = "sandbox"
DEFAULT_SANDBOX_PORT = "8000"
DEFAULT_QDRANT_SERVICE_NAME = "qdrant"
DEFAULT_QDRANT_HTTP_PORT = "6333"
DEFAULT_SAMBA_SERVICE_NAME = "samba"
ADMIN_API_KEY_PREFIX = "ad_"


class DockerManager:
    _ENV_FILE = ".env"
    _DOCKER_COMPOSE_FILE = "docker-compose.yml"

    _GENERATED_SECRETS = [
        "SECRET_KEY",
        "MYSQL_ROOT_PASSWORD",
        "MYSQL_PASSWORD",
        "BOOTSTRAP_ADMIN_API_KEY",
        "ADMIN_API_KEY",
    ]

    _DEFAULT_VALUES = {
        "MYSQL_HOST": DEFAULT_DB_SERVICE_NAME,
        "MYSQL_PORT": DEFAULT_DB_CONTAINER_PORT,
        "MYSQL_DATABASE": "entities_db",
        "MYSQL_USER": "api_user",
        "ASSISTANTS_BASE_URL": f"http://{DEFAULT_API_SERVICE_NAME}:{DEFAULT_API_PORT}",
        "SANDBOX_SERVER_URL": f"http://{DEFAULT_SANDBOX_SERVICE_NAME}:{DEFAULT_SANDBOX_PORT}",
        "QDRANT_URL": f"http://{DEFAULT_QDRANT_SERVICE_NAME}:{DEFAULT_QDRANT_HTTP_PORT}",
        "LOG_LEVEL": "INFO",
        "PYTHONUNBUFFERED": "1",
        "DISABLE_FIREJAIL": "true",
        "SMBCLIENT_SERVER": DEFAULT_SAMBA_SERVICE_NAME,
        "SMBCLIENT_SHARE": "entities_share",
        "SMBCLIENT_USERNAME": "samba_user",
        "SMBCLIENT_PASSWORD": "default",
        "SMBCLIENT_PORT": "445",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
        "BOOTSTRAP_ADMIN_NAME": "Default Admin",
    }

    _ENV_STRUCTURE = {
        "Secrets": [
            "SECRET_KEY",
            "MYSQL_ROOT_PASSWORD",
            "MYSQL_PASSWORD",
            "BOOTSTRAP_ADMIN_API_KEY",
            "ADMIN_API_KEY",
        ],
        "Database": [
            "DATABASE_URL",
            "SPECIAL_DB_URL",
            "MYSQL_HOST",
            "MYSQL_PORT",
            "MYSQL_DATABASE",
            "MYSQL_USER",
        ],
        "Services": [
            "QDRANT_URL",
            "SANDBOX_SERVER_URL",
            "ASSISTANTS_BASE_URL",
        ],
        "Samba": [
            "SHARED_PATH",
            "SMBCLIENT_SERVER",
            "SMBCLIENT_SHARE",
            "SMBCLIENT_USERNAME",
            "SMBCLIENT_PASSWORD",
            "SMBCLIENT_PORT",
        ],
        "Application": [
            "LOG_LEVEL",
            "PYTHONUNBUFFERED",
            "DISABLE_FIREJAIL",
        ],
    }

    def __init__(self, args):
        self.args = args
        self.is_windows = platform.system() == "Windows"
        self.log = log
        if self.args.verbose:
            self.log.setLevel(logging.DEBUG)
        self.compose_config = self._load_compose_config()
        self._configure_shared_path()
        self._check_or_generate_env_file()

    def _run_command(self, cmd_list, **kwargs):
        self.log.info("Running: %s", " ".join(cmd_list))
        return subprocess.run(cmd_list, check=True, **kwargs)

    def _load_compose_config(self):
        try:
            with open(self._DOCKER_COMPOSE_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            self.log.warning("Failed to load compose config", exc_info=self.args.verbose)
            return None

    def _get_host_port_from_compose_service(self, service, container_port):
        if not self.compose_config:
            return None
        ports = self.compose_config.get("services", {}).get(service, {}).get("ports", [])
        for p in ports:
            parts = str(p).split(":")
            if len(parts) >= 2 and parts[-1] == str(container_port):
                return parts[-2]
        return None

    def _generate_dot_env_file(self):
        env = dict(self._DEFAULT_VALUES)

        shared_path = os.environ.get("SHARED_PATH")
        if shared_path:
            env["SHARED_PATH"] = shared_path

        admin_key = f"{ADMIN_API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        for key in self._GENERATED_SECRETS:
            if key in ["BOOTSTRAP_ADMIN_API_KEY", "ADMIN_API_KEY"]:
                env[key] = admin_key
            else:
                env[key] = secrets.token_urlsafe(32)

        escaped = quote_plus(env["MYSQL_PASSWORD"])
        db_url = (
            f"mysql+pymysql://{env['MYSQL_USER']}:{escaped}@"
            f"{env['MYSQL_HOST']}:{env['MYSQL_PORT']}/{env['MYSQL_DATABASE']}"
        )
        env["DATABASE_URL"] = db_url

        host_port = self._get_host_port_from_compose_service(
            DEFAULT_DB_SERVICE_NAME, DEFAULT_DB_CONTAINER_PORT
        )
        if host_port:
            env["SPECIAL_DB_URL"] = db_url.replace(env["MYSQL_HOST"], "localhost").replace(
                env["MYSQL_PORT"], host_port
            )

        lines = ["# Auto-generated .env"]
        for section, keys in self._ENV_STRUCTURE.items():
            lines.append(f"\n# {section}")
            for k in keys:
                if k in env:
                    v = env[k].replace('"', '\\"')
                    lines.append(f'{k}="{v}"')

        Path(self._ENV_FILE).write_text("\n".join(lines), encoding="utf-8")
        self.log.info(f"Generated {self._ENV_FILE}.")

    def _check_or_generate_env_file(self):
        if not Path(self._ENV_FILE).exists():
            self.log.warning(f"{self._ENV_FILE} missing. Generating...")
            self._generate_dot_env_file()

    def _configure_shared_path(self):
        system = platform.system().lower()
        base = Path.home()
        if system == "windows":
            shared = base / "Documents" / "entities_share"
        elif system == "linux":
            shared = base / ".local" / "share" / "entities_api_share"
        elif system == "darwin":
            shared = base / "Library" / "Application Support" / "entities_api_share"
        else:
            self.log.error("Unsupported OS")
            sys.exit(1)
        shared.mkdir(parents=True, exist_ok=True)
        os.environ["SHARED_PATH"] = str(shared)
        self.log.info(f"SHARED_PATH set to {shared}")

    def _handle_up(self):
        self._run_command(["docker", "compose", "up", "-d"])

    def _handle_down(self):
        self._run_command(["docker", "compose", "down", "--remove-orphans"])

    def run(self):
        if self.args.mode == "down_only":
            self._handle_down()
        elif self.args.mode == "up":
            self._handle_up()

    @staticmethod
    def parse_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["up", "down_only"], default="up")
        parser.add_argument("--verbose", action="store_true")
        return parser.parse_args()


if __name__ == "__main__":
    try:
        args = DockerManager.parse_args()
        if args.verbose:
            log.setLevel(logging.DEBUG)
        DockerManager(args).run()
    except Exception:
        log.critical("Fatal error occurred during orchestration startup", exc_info=True)
        sys.exit(1)
