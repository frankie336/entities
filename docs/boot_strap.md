# 🧠 Entities Orchestration: Admin → User → Assistant

A complete, automated lifecycle for standing up **Entities** using the CLI.

---

## ✅ 1. Bootstrap Admin User (First-Time Only)

This creates the initial **admin user** and outputs a secure `ADMIN_API_KEY`.

```bash
python start_orchestration.py --bootstrap-admin --bootstrap-db-url "mysql+pymysql://api_user:YOUR_PASSWORD@db:3306/cosmic_catalyst"
```

🧾 The script will:
- Bootstrap the database
- Generate and output a secure `ADMIN_API_KEY`
- Save it to:
  - `./.env`
  - `admin_credentials.txt` (inside container)

---

## ✏️ 2. Update `.env` (if needed)

Ensure your local `.env` has the generated `ADMIN_API_KEY`.

```env
ADMIN_API_KEY=ad_<your_admin_key_here>
```

---

## 🔄 3. Reload the API Service

To load the new environment variable:

```bash
docker compose down && docker compose up -d
```

✅ Confirm it's loaded:

```bash
docker compose exec api printenv | grep ADMIN_API_KEY
```

---

## 👤 4. Create a Regular User

Use the admin key to create a new user and generate their API key.

```bash
python start_orchestration.py \
  --create-user \
  --user-name "Alice Tester" \
  --user-email "alice@example.com"
```

📦 Output includes:

```
PLAIN TEXT API KEY: ea_...
>>> Provide this key to the regular user for their API access. <<<
```

No need to add the user's API key to `.env` — it's for the user.

---

## 🤖 5. (Optional) Setup Default Assistant

Provision the intelligent default assistant for the regular user.

```bash
python start_orchestration.py \
  --setup-assistant \
  --exec-api-key "ad_<your_admin_key>" \
  --exec-user-id "user_<admin_user_id>"
```

🧠 The assistant:
- Is named `"Q"`
- Uses the default `BASE_TOOLS` (function-calling capable)
- Becomes available for conversations and tool use

---

## 🧩 Final Summary

| Step                     | Command Example                                                                 |
|--------------------------|----------------------------------------------------------------------------------|
| 🧬 Bootstrap Admin        | `--bootstrap-admin --bootstrap-db-url "<url>"`                                  |
| ✏️ Update `.env`          | Add `ADMIN_API_KEY=ad_...` if missing                                           |
| 🔄 Reload API             | `docker compose down && docker compose up -d`                                  |
| 👤 Create Regular User    | `--create-user --user-name "..." --user-email "..."`                           |
| 🤖 Setup Assistant        | `--setup-assistant --exec-api-key "..." --exec-user-id "..."`                   |

---

Once complete, your **Entities** environment is ready for production-grade AI assistant usage.

> 🧠 *“You didn't just launch a stack. You gave cognition a home.”*

```bash
python start_orchestration.py
```
