# 🛰️ Entities
[![Docker Pulls](https://img.shields.io/docker/pulls/thanosprime/entities-api-api?label=API%20Pulls&logo=docker&style=flat-square)](https://hub.docker.com/r/thanosprime/entities-api-api)

[![CI](https://github.com/frankie336/entities/actions/workflows/ci.yml/badge.svg)](https://github.com/frankie336/entities/actions/workflows/ci.yml)

[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0/)


> 🧠 **Orchestrated AI infrastructure** for the Entities V1 system.

This repository provides standalone orchestration for the full Entities stack, enabling you to spin up a complete environment with a single command. It includes Docker Compose configuration, optional Ollama GPU containers, volume management, and startup automation logic.

---

## 🧩 What's Inside

| Service    | Description                                        |
|------------|----------------------------------------------------|
| `api`      | Main FastAPI backend exposing assistant endpoints  |
| `sandbox`  | Secure code execution environment with Firejail    |
| `db`       | MySQL 8.0 database for all persistence needs       |
| `qdrant`   | Vector DB for embedding-based memory + RAG         |
| `samba`    | File sharing server for uploaded documents         |
| `ollama`   | Optional local LLMs (Mistral, Llama, etc)          |

---

### 🧠 Want to work directly with the Entities source code?

This repository is designed for orchestrating prebuilt Entities containers.  
If you're looking to **develop**, **extend**, or **contribute** to the Entities codebase itself, head over to:

👉 **[entities](https://github.com/frankie336/entities_api)** – The full source repository containing the FastAPI backend, AI inference logic, tooling framework, and SDK.

Perfect for advanced customization, assistant training, or building your own extensions.

```bash
git clone https://github.com/frankie336/entities_api.git
cd entities
python start_orchestration.py
```

---

## 🚀 Quick Start

> 🛠️ **Pre-requisites:**
> - Docker & Docker Compose
> - Python 3.11+ (`pip install -r requirements.txt` if using CLI tools)

### 🔧 1. Clone the repo

```bash
git clone https://github.com/frankie336/entities.git
cd entities
```

---

## 🔄 Lifecycle Commands

Run one of these commands. For first time starts, option 1 is a safe bet.

**1. First-time start (generates .env, pulls images, starts detached)**

``python start_orchestration.py``

**2. Stop all services**

```python start_orchestration.py --mode down_only```


Refer to [Extended commands](#extended-commands) for additional options.


---

👇

## Default Admin User 


 To enable executive functions, provision the default admin user by running:

```bash

docker compose exec api python /app/scripts/bootstrap_admin.py

```
Or

Override the default db URL with:

```bash

docker compose exec api python /app/scripts/bootstrap_admin.py --db-url "your_explicit_url_here"

```

---
👇

## 🛠️ Creating a Regular User via Admin Script

This script provisions a **new regular user** and generates their **initial API key** using an admin credential.

---

### 📦 Prerequisites

- Docker stack is running (`python start.py --mode up`)
- `.env` file contains a valid `ADMIN_API_KEY` (created via `bootstrap_admin.py`)
- Script path: `/app/scripts/create_user.py` (mounted from `./scripts`)

---

### 🚀 Basic Usage

#### 🔹 Create User with Auto-generated Name & Email

- Good for testing 

```bash
docker compose exec api python /app/scripts/create_user.py
```

- Name will be: `Regular User <timestamp>`
- Email will be: `test_user_<timestamp>@example.com`

---

#### 🔹 Create User with a Specific Name (auto-generates email)
```bash
docker compose exec api python /app/scripts/create_user.py --name "Bob Smith"
```

---

#### 🔹 Create User with Specific Name and Email
```bash
docker compose exec api python /app/scripts/create_user.py \
  --email bob.smith@company.com \
  --name "Bob Smith"
```

---

#### 🔹 Create User and Assign Custom Key Name
```bash
docker compose exec api python /app/scripts/create_user.py \
  --email carol@dev.co \
  --name "Carol Developer" \
  --key-name "Carol Dev Key"
```

---

### ⚙️ Command Breakdown

- `docker compose exec`: Run a command inside a running container
- `api`: Target service (FastAPI container)
- `python`: Interpreter inside container
- `/app/scripts/create_user.py`: The script inside the container
- `--email`, `--name`, `--key-name`: Optional flags passed to the script

---

### 🖨️ Example Output

```text
Using Admin API Key (loaded from environment variable 'ADMIN_API_KEY') starting with: ad_Y...YYYY
Initializing API client for base URL: http://api:9000
API client initialized.

Attempting to create user 'Regular User 1713200000' (test_user_1713200000@example.com)...

New REGULAR user created successfully:
  User ID:    usr_abc123def456ghi789jkl0
  User Email: test_user_1713200000@example.com
  Is Admin:   False

Attempting to generate initial API key ('Default Initial Key') for user usr_abc123def456ghi789jkl0 (test_user_1713200000@example.com)...
Calling SDK method 'create_key_for_user' on admin client for user ID usr_abc123def456ghi789jkl0

==================================================
  Initial API Key Generated for Regular User (by Admin)!
  User ID:    usr_abc123def456ghi789jkl0
  User Email: test_user_1713200000@example.com
  Key Prefix: ea_XyZ7a
  Key Name:   Default Initial Key
--------------------------------------------------
  PLAIN TEXT API KEY: ea_XyZ7aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLm
--------------------------------------------------
  >>> Provide this key to the regular user for their API access. <<<
==================================================

Script finished.
```

---

### ⚠️ Action Required

Copy the **plain text API key** from the output (e.g., `ea_XyZ7aBcDe...`) and deliver it securely to the user.  
They will need it to interact with the API. It does **not** need to be added to the system `.env`.

---
👇


---

## Extended commands

**1. First-time start (generates .env, pulls images, starts detached)**

``python start_orchestration.py``

**2. Stop all services**

```python start_orchestration.py --mode down_only```

**3. Stop services and remove associated volumes (will prompt!)**

```python start_orchestration.py --clear-volumes```

**4. Restart services, ensuring latest images are pulled and containers recreated**

```python start_orchestration.py --down --force-recreate```

**5. Start the stack and also manage an external Ollama container**

```python start_orchestration.py --with-ollama```

**6. Start with external Ollama, attempting GPU passthrough**

```python start_orchestration.py --with-ollama --ollama-gpu```

**7. Start only the 'api' and 'db' services**

```python start_orchestration.py --services api db```

**8. Stop only the 'api' service**

```python start_orchestration.py --mode down_only --services api```

**9. Start attached to view logs immediately**

```python start_orchestration.py --attached```

**10. Show verbose output during startup**

```python start_orchestration.py --verbose```


**11. <span style="color:red">DANGEROUS</span>: Nuke the project and prune all Docker resources (requires confirmation)**


```python start_orchestration.py --nuke```











## 📦 Docker Images

Images are published to Docker Hub:

- [`thanosprime/entities-api-api`](https://hub.docker.com/r/thanosprime/entities-api-api)
- [`thanosprime/entities-api-sandbox`](https://hub.docker.com/r/thanosprime/entities-api-sandbox)

---

## 🧠 Related Repositories

| Name         | Purpose                                |
|--------------|----------------------------------------|
| [`entities_api`](https://github.com/frankie336/entities_api)       | Main API source code (FastAPI backend)     |
| [`projectdavid`](https://github.com/frankie336/projectdavid)       | SDK for interacting with the Entities API  |
| [`entities`](https://github.com/frankie336/entities)               | 🧱 **This repo** — orchestration and deploy |

---










## 📜 License
Distributed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).  
Commercial licensing available on request.
