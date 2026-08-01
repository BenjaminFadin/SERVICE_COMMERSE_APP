"""
Eskiz SMS connection tester.
- Verifies your token
- Shows your account info and SMS balance
- Detects your registered sender nick
- Sends a real test SMS using your nick (no moderation required)

Run:  python test_sms.py
"""

import io
import re
import sys
import requests
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ─────────────────────────────────────────────
#  EDIT: phone number to receive the test SMS
# ─────────────────────────────────────────────
TEST_PHONE = "998880378151"
# ─────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"
BASE_URL  = "https://notify.eskiz.uz/api"


# ── helpers ───────────────────────────────────

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
    text = ENV_PATH.read_text(encoding="utf-8")
    new  = f"ESKIZ_TOKEN={token}"
    if re.search(r"^ESKIZ_TOKEN=", text, re.MULTILINE):
        text = re.sub(r"^ESKIZ_TOKEN=.*$", new, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{new}\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/auth/login",
                      data={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    token = r.json().get("data", {}).get("token") or r.json().get("token")
    if not token:
        raise RuntimeError(f"Login failed: {r.json()}")
    return token


def refresh(token: str) -> str:
    r = requests.patch(f"{BASE_URL}/auth/refresh",
                       headers=headers(token), timeout=10)
    r.raise_for_status()
    new = r.json().get("data", {}).get("token") or r.json().get("token")
    if not new:
        raise RuntimeError(f"Refresh failed: {r.json()}")
    return new


def divider(char="-", n=55):
    print(char * n)


# ── main ──────────────────────────────────────

def main():
    env      = load_env()
    token    = env.get("ESKIZ_TOKEN", "").strip()
    email    = env.get("ESKIZ_EMAIL", "").strip()
    password = env.get("ESKIZ_PASSWORD", "").strip()

    divider("=")
    print("  Eskiz SMS — Connection Test")
    divider("=")

    # ── Step 1: get/refresh token ──────────────
    if not token:
        if not email or not password:
            print("[X] No token and no ESKIZ_EMAIL/ESKIZ_PASSWORD in .env")
            sys.exit(1)
        print("[..] Logging in ...")
        token = login(email, password)
        save_token(token)
        print("[OK] Token obtained and saved.\n")

    # ── Step 2: verify token → get user info ──
    print("[1] Checking token and account info ...")
    r = requests.get(f"{BASE_URL}/auth/user", headers=headers(token), timeout=10)

    if r.status_code == 401:
        print("    Token expired — refreshing ...")
        try:
            token = refresh(token)
        except Exception:
            if email and password:
                print("    Refresh failed — re-logging in ...")
                token = login(email, password)
            else:
                print("[X] Token expired. Add ESKIZ_EMAIL + ESKIZ_PASSWORD to .env")
                sys.exit(1)
        save_token(token)
        print("    New token saved.")
        r = requests.get(f"{BASE_URL}/auth/user", headers=headers(token), timeout=10)

    if r.status_code != 200:
        print(f"[X] Could not fetch user info: {r.status_code} {r.text}")
        sys.exit(1)

    user_data = r.json().get("data", r.json())
    print()
    print(f"    Email   : {user_data.get('email', 'N/A')}")
    print(f"    Name    : {user_data.get('name', 'N/A')}")
    nick = user_data.get("nick") or user_data.get("name_sender") or ""
    print(f"    Nick    : {nick or '(none registered)'}")
    print(f"    Status  : {user_data.get('status', 'N/A')}")

    # ── Step 3: check SMS balance ──────────────
    print()
    print("[2] Checking SMS balance ...")
    r2 = requests.get(f"{BASE_URL}/user/get-limit", headers=headers(token), timeout=10)
    if r2.status_code == 200:
        limit_data = r2.json().get("data", r2.json())
        balance = (
            limit_data.get("balance")
            or limit_data.get("smses_count")
            or limit_data.get("limit")
            or limit_data
        )
        print(f"    Balance : {balance}")
    else:
        print(f"    Could not fetch balance: {r2.status_code}")

    # ── Step 4: send test SMS ──────────────────
    print()
    print("[3] Sending test SMS ...")

    # Use registered nick if available — no moderation needed
    # Fall back to 4546 if no nick (requires approved text)
    if nick and nick != "4546":
        sender      = nick
        test_message = f"ibron: test SMS from {nick}. Connection OK."
        print(f"    Sender  : {nick}  (registered nick — no moderation needed)")
    else:
        sender      = "4546"
        test_message = "test"   # add "test" to my.eskiz.uz -> SMS -> Mои тексты
        print(f"    Sender  : 4546  (shared sender — text needs moderation)")

    print(f"    To      : +{TEST_PHONE}")
    print(f"    Message : {test_message}")
    print()

    r3 = requests.post(
        f"{BASE_URL}/message/sms/send",
        headers=headers(token),
        json={
            "mobile_phone": TEST_PHONE,
            "message":      test_message,
            "from":         sender,
        },
        timeout=10,
    )

    body   = r3.json()
    status = r3.status_code

    divider()

    if status == 200 and body.get("status") != "error":
        print()
        print("[OK] TEST SMS SENT SUCCESSFULLY!")
        print(f"     id     : {body.get('id')}")
        print(f"     status : {body.get('status')}")
        print()
        print("     Your Eskiz setup is working correctly.")

    else:
        err_msg = body.get("message", str(body))
        print(f"[X] Send failed ({status}): {err_msg}")
        print()

        if "модерацию" in err_msg or "moderation" in err_msg.lower():
            print("  The message text needs approval first.")
            print()
            if not nick or nick == "4546":
                print("  OPTION 1 — Quick fix (approve text):")
                print('    1. Go to https://my.eskiz.uz -> SMS -> Мои тексты')
                print(f'    2. Add exactly:  "{test_message}"')
                print("    3. Wait for approval, then re-run this script.")
                print()
                print("  OPTION 2 — Permanent fix (register sender name):")
                print("    1. Go to https://my.eskiz.uz -> SMS -> Мои отправители")
                print("    2. Register a sender name (e.g. IBRON)")
                print("    3. Set  ESKIZ_SENDER=IBRON  in .env")
                print("       (registered senders skip moderation entirely)")
            else:
                print(f"  Even with nick '{nick}', this text needs approval.")
                print(f'  Go to my.eskiz.uz -> Мои тексты -> add: "{test_message}"')
        else:
            print(f"  Full response: {body}")

    divider("=")


if __name__ == "__main__":
    main()
