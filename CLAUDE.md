# iBron — Service Commerce App

Django 4.2 marketplace for booking beauty salons, PC clubs, and other services in Uzbekistan.
Language: Python 3.8 · DB: PostgreSQL · Auth: django-allauth + custom email/username backend.

---

## Project Structure

```
SERVICE_COMMERSE_APP/
├── config/          # Django settings, root URLs, wsgi/asgi
├── accounts/        # Custom User, Profile, PasswordResetCode, auth views
├── marketplace/     # Salons, Services, Masters, Appointments, Categories
├── pc_clubs/        # PCClub, PCPlan, PCBooking, PCWorkingHours
├── bot/             # Telegram bot (aiogram 3)
├── templates/       # Global HTML templates
├── static/          # CSS/JS/images
├── locale/          # i18n translations (ru, en, uz)
├── send_sms.py      # Manual SMS test script (Eskiz)
├── test_sms.py      # Eskiz SMS diagnostic tool
└── .env             # Secrets (never commit)
```

---

## Apps Overview

### accounts
- `User` — extends `AbstractUser`; email optional, username required
- `Profile` — OneToOne with User; stores `phone`, `full_name`, `avatar`, `role` (customer/provider), `language` (ru/en/uz), `telegram_id`
- `PasswordResetCode` — 6-digit OTP, expires in 15 min, single-use
- Auth backends: `ModelBackend`, `allauth`, `EmailOrUsernameModelBackend`
- Password reset flow: email → 6-digit code → verify → new password
- Registration: currently email+password only (SMS OTP for registration is **planned**)

### marketplace
- `Category` (MPTT tree) — multilingual (ru/en/uz), `is_pc_club` flag
- `Salon` — owned by User, has logo/cover (auto-converted to WebP), QR token
- `Address` — lat/lng/map link for each Salon
- `SalonPhoto`, `Service`, `Master`, `SalonWorkingHours` (per-weekday schedule)
- `Appointment` — client books master+service at a salon; overlap validation built-in
- `BusinessLead` — contact form for businesses wanting to join

### pc_clubs
- `PCClub` — similar to Salon but with `total_pcs` count
- `PCPlan` — pricing tiers per club (price per hour)
- `PCBooking` — client books N PCs for N hours; availability checked against `total_pcs`
- `PCWorkingHours`, `PCAddress`, `PCPhoto`
- Notifications on booking: Telegram + SMS to client and club owner

### bot
- Telegram bot built with **aiogram 3**
- Handles user registration via Telegram, links `telegram_id` to Profile

---

## Key Settings (.env variables)

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=
DB_NAME=, DB_USER=, DB_PASSWORD=, DB_HOST=, DB_PORT=
DOMAIN_NAME=
EMAIL_HOST_USER=, EMAIL_HOST_PASSWORD=, DEFAULT_FROM_EMAIL=
GOOGLE_CLIENT_ID=, GOOGLE_SECRET=
TELEGRAM_BOT_TOKEN=
BUSINESS_LEADS_TELEGRAM_ID=
ESKIZ_EMAIL=, ESKIZ_PASSWORD=, ESKIZ_TOKEN=
ESKIZ_SENDER=4546        # or custom registered sender name
SMS_BACKEND=eskiz        # set this to enable real SMS sending
```

---

## SMS Integration (Eskiz)

Provider: **Eskiz** (notify.eskiz.uz) — Uzbekistan SMS gateway.

### Approved SMS template (registered on my.eskiz.uz → SMS → Мои тексты):
```
Siz iBron ilovasida ro'yxatdan o'tmoqdasiz. Kodni hech kimga bermang: #CODE
```
Replace `#CODE` with the actual numeric OTP before sending.

### send_sms.py — manual test script
Edit `PHONE` and `CODE` at the top, then run:
```bash
python send_sms.py
```
Current message format:
```python
CODE    = "123456"
MESSAGE = f"Siz iBron ilovasida ro'yxatdan o'tmoqdasiz. Kodni hech kimga bermang: {CODE}"
```

### App SMS utility — `marketplace/utils.py:send_sms(phone, text)`
- Reads `SMS_BACKEND` from settings; if `"eskiz"` → posts to Eskiz API
- Uses `ESKIZ_TOKEN` from settings and sender `"4546"` (shared sender)
- Callers must format the message text before calling `send_sms()`
- Currently used in: `pc_clubs/signals.py` (booking notifications), `pc_clubs/views.py` (status change)

### Eskiz moderation note
When using shared sender `4546`, every unique message text must be pre-approved on
`my.eskiz.uz → SMS → Мои тексты`. Registering a custom sender name removes this restriction.
Contract signed for 300,000 UZS.

---

## URL Routes

| Prefix         | App                        |
|----------------|----------------------------|
| `/`            | marketplace (home, salons) |
| `/pc-clubs/`   | pc_clubs                   |
| `/accounts/`   | accounts + allauth         |
| `/admin/`      | Django admin               |

---

## i18n / Multilingual

- Languages: **ru** (default), **en**, **uz**
- `LocaleMiddleware` + `UserLanguageMiddleware` (reads `profile.language`)
- Language switcher POSTs to `accounts:set_language`
- Models with multilingual fields use `_ru`/`_en`/`_uz` suffix pattern + `MultilingualMixin.get_i18n()`
- Translation files in `locale/`

---

## Image Handling

All uploaded images (salon logo, cover, gallery, master photo, PC club images) are automatically resized and converted to **WebP** format on save via `_process_image_to_webp()`.

---

## Notifications

| Event                  | Telegram | SMS |
|------------------------|----------|-----|
| New PC booking         | ✓        | ✓   |
| PC booking status change | ✓      | ✓   |
| Appointment (salon)    | -        | -   |
| Password reset         | -        | planned |
| Registration OTP       | -        | planned |

---

## Dependencies (requirements.txt)

```
Django==4.2.26
aiogram==3.13.1
django-allauth==65.13.1
django-mptt==0.14.0
psycopg / psycopg-binary==3.2.13
pillow==10.4.0
python-dotenv==1.0.1
requests==2.32.4
gunicorn==23.0.0
whitenoise==6.7.0
qrcode[pil]>=7.4.2
xlsxwriter==3.2.9
pandas==2.0.3
```

---

## Priority TODO (from todo.md)

1. **Deploy to server** — put site live on domain `ibron.uz`
2. **SMS OTP registration** — user registers via phone number + Eskiz OTP code
   - Approved template: `"Siz iBron ilovasida ro'yxatdan o'tmoqdasiz. Kodni hech kimga bermang: #CODE"`
   - Eskiz contract done (300,000 UZS)
3. **Add Privacy Policy page**
4. **Fix sort button position** — move sort button slightly lower on list pages
5. **Complete i18n translations** — fill in RU, UZ, EN dictionary entries for all strings

---

## Dev Commands

```bash
# Run dev server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Collect static
python manage.py collectstatic

# Test SMS (manual)
python send_sms.py

# Run Telegram bot
python bot/main.py
```

---

## Recent Git History

- `a239b11` sorting added to list pages
- `65a39a7` pc list page fixed
- `5629daa` pc clubs added
- `498014f` pc club starting with new logic
- `76f93fd` nearby locs added
