"""
Eskiz SMS sender — reads credentials from .env, no command-line args.
Edit PHONE and MESSAGE below, then run:  python send_sms.py
"""

import os
import re
import sys
import io
import requests
from pathlib import Path

# Force UTF-8 output on Windows so Cyrillic API messages print correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ─────────────────────────────────────────────
#  EDIT THESE
# ─────────────────────────────────────────────
PHONE   = "998880378151"   # digits only, no + or spaces
CODE    = "1234"         # replace with the actual OTP code
MESSAGE = f"Siz iBron ilovasida ro'yxatdan o'tmoqdasiz. Kodni hech kimga bermang: {CODE}"
# ─────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"
BASE_URL  = "https://notify.eskiz.uz/api"


# ── .env reader ───────────────────────────────

def load_env() -> dict:
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def save_token(token: str):
    """Write updated ESKIZ_TOKEN back to .env."""
    text = ENV_PATH.read_text(encoding="utf-8")
    new  = f"ESKIZ_TOKEN={token}"
    if re.search(r"^ESKIZ_TOKEN=", text, re.MULTILINE):
        text = re.sub(r"^ESKIZ_TOKEN=.*$", new, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{new}\n"
    ENV_PATH.write_text(text, encoding="utf-8")


# ── Eskiz auth ────────────────────────────────

def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        data={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("data", {}).get("token") or r.json().get("token")
    if not token:
        raise RuntimeError(f"Login failed: {r.json()}")
    return token


def refresh(token: str) -> str:
    r = requests.patch(
        f"{BASE_URL}/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    new = r.json().get("data", {}).get("token") or r.json().get("token")
    if not new:
        raise RuntimeError(f"Refresh failed: {r.json()}")
    return new


# ── Send SMS ──────────────────────────────────

def send(token: str, phone: str, message: str, sender: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/message/sms/send",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mobile_phone": phone,
            "message":      message,
            "from":         sender,
        },
        timeout=10,
    )


# ── Main ──────────────────────────────────────

def main():
    env    = load_env()
    token  = env.get("ESKIZ_TOKEN", "").strip()
    sender = env.get("ESKIZ_SENDER", "4546").strip()
    email  = env.get("ESKIZ_EMAIL",  "").strip()
    password = env.get("ESKIZ_PASSWORD", "").strip()

    if not token:
        if not email or not password:
            print("[X]  No ESKIZ_TOKEN and no ESKIZ_EMAIL/ESKIZ_PASSWORD in .env")
            sys.exit(1)
        print("[..] No token found -- logging in ...")
        token = login(email, password)
        save_token(token)
        print("[OK] Token saved to .env")

    print(f"[>>] Sending to {PHONE} ...")
    resp = send(token, PHONE, MESSAGE, sender)

    # Token expired -> refresh automatically and retry once
    if resp.status_code == 401:
        print("[!]  Token expired -- refreshing ...")
        try:
            token = refresh(token)
        except Exception:
            if email and password:
                print("     Refresh failed -- logging in with credentials ...")
                token = login(email, password)
            else:
                print("[X]  Token expired. Add ESKIZ_EMAIL + ESKIZ_PASSWORD to .env and re-run.")
                sys.exit(1)
        save_token(token)
        print("[OK] New token saved -- retrying ...")
        resp = send(token, PHONE, MESSAGE, sender)

    body = resp.json()

    if resp.status_code == 200 and body.get("status") != "error":
        print(f"[OK] Sent!  id={body.get('id')}, status={body.get('status')}")
        return

    # -- Error handling with clear instructions --
    msg = body.get("message", "")
    print(f"\n[X]  Error {resp.status_code}: {msg}\n")

    if "модерацию" in msg or "moderation" in msg.lower():
        print("-" * 60)
        print("  The SMS text must be approved before sending.")
        print()
        print("  HOW TO FIX:")
        print("  1. Go to  https://my.eskiz.uz  → Login")
        print("  2. Open   SMS → Мои тексты  (My texts)")
        print(f'  3. Add this exact text:  "{MESSAGE}"')
        print("  4. Submit for moderation → wait for approval (usually fast)")
        print("  5. Re-run this script")
        print()
        print("  OR: register a custom sender name on Eskiz and set")
        print("      ESKIZ_SENDER=YourName  in .env (removes this restriction).")
        print("-" * 60)
    else:
        print(f"  Full response: {body}")

    sys.exit(1)


if __name__ == "__main__":
    main()
