# 🛰️ Entities
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
python start.py
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

### ⚙️ 2. Bootstrap environment files

```bash
python start.py --generate-env
```

This will scaffold `.env.dev` and `.env.docker` with secure keys, MySQL credentials, and tool IDs.

### 🧱 3. Build and launch containers

```bash
python start.py --mode both
```

Or skip building and run pre-published images from Docker Hub:

```bash
python start.py --mode up --no-build
```

---

## 🔄 Supported Lifecycle Commands

| Command                             | Purpose                                      |
|-------------------------------------|----------------------------------------------|
| `--mode build`                      | Build containers                             |
| `--mode up`                         | Start containers                             |
| `--mode both`                       | Build & start all containers                 |
| `--mode up --with-ollama`           | Include Ollama container with CPU support    |
| `--mode up --with-ollama --ollama-gpu` | Enable GPU acceleration for Ollama         |
| `--down`                            | Stop containers                              |
| `--down --clear-volumes`           | Stop and wipe all data volumes               |
| `--mode up --clear-volumes`        | Full redeploy with fresh volumes             |

---

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

## 🛡️ Philosophy

> **Entities** is designed for serious developers building intelligent assistants.
> This repo gives you command-line control, version-aware builds, secure sandboxing, and seamless orchestration—all without relying on cloud lock-in.

---

## 🧠 Pro Tips

- Use `--debug-cache` if Docker layer caching seems broken.
- Set `DEFAULT_SECRET_KEY` and `SIGNED_URL_SECRET` in `.env.dev` for secure API key generation.
- Ollama not required—but it's slick if you want local inferencing.

---

## 📜 License

Distributed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).  
Commercial licensing available on request.
