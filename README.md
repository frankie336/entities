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
