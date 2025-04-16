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

### ▶️ 2. Launch the stack

```bash
python start_orchestration.py
```

This will:
- Generate `.env` if missing
- Pull required Docker images
- Start all containers in detached mode

---

## 🧑‍💻 Admin, User, and Assistant Setup

Once the stack is running, you'll want to:
1. Bootstrap the **default admin user**
2. Create one or more **regular users**
3. Provision the **default assistant**

📖 See the full step-by-step guide here:  
👉 [`docs/boot_strap.md`](docs/boot_strap.md)

---

## 🔁 Lifecycle Commands

| Action                     | Command |
|----------------------------|---------|
| **Start everything**           | See below |
```bash
python start_orchestration.py
```

| **Stop everything**            | |
```bash
python start_orchestration.py --mode down_only
```

| **Stop + remove volumes**      | |
```bash
python start_orchestration.py --clear-volumes
```

| **Fully restart (clean)**      | |
```bash
python start_orchestration.py --down --force-recreate
```

| **Use external Ollama**        | |
```bash
python start_orchestration.py --with-ollama
```

| **Ollama with GPU passthrough**| |
```bash
python start_orchestration.py --with-ollama --ollama-gpu
```

| **Start only selected services**        | |
```bash
python start_orchestration.py --services api db
```

| **Stop selected services**     | |
```bash
python start_orchestration.py --mode down_only --services api
```

| **View logs (attached)**       | |
```bash
python start_orchestration.py --attached
```

| **Enable verbose logs**        | |
```bash
python start_orchestration.py --verbose
```

| **💥 Nuke all Docker resources (requires confirmation)** | |
```bash
python start_orchestration.py --nuke
```
---

## 📦 Docker Images

Images are published to Docker Hub:

- [`thanosprime/entities-api-api`](https://hub.docker.com/r/thanosprime/entities-api-api)
- [`thanosprime/entities-api-sandbox`](https://hub.docker.com/r/thanosprime/entities-api-sandbox)

---

## 🧠 Related Repositories

| Name                                      | Purpose                                         |
|-------------------------------------------|-------------------------------------------------|
| [`entities_api`](https://github.com/frankie336/entities_api) | Main API source code (FastAPI backend)         |
| [`projectdavid`](https://github.com/frankie336/projectdavid) | SDK for interacting with the Entities API      |
| [`entities`](https://github.com/frankie336/entities)         | 🧱 **This repo** — orchestration and deployment |

---

## 📜 License

Distributed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).  
Commercial licensing available on request.
