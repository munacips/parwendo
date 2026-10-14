# Parwendo

> A Django REST + WebSocket backend for a trip-sharing platform: drivers publish trips, passengers book seats, chat, pay and share live location, and staff verify drivers and vehicles from a customised Django admin.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture & Patterns](#architecture--patterns)
- [Data Models](#data-models)
- [Services / API Layer](#services--api-layer)
- [Navigation & Routing](#navigation--routing)
- [Admin Panel](#admin-panel)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Further Reading](#further-reading)

---

## Features

### Passengers

- **Registration & verification** – create an account (username, password, email, phone); a 6-digit OTP valid for 5 minutes is emailed on sign-up and can be re-sent.
- **OAuth2 login** – exchange username/password for a bearer token (access token lifetime 1 hour, refresh token 7 days).
- **Trip search** – filter trips by destination, start location, date and driver; `available=true` returns only upcoming, paid-for trips that still have free seats.
- **Seat booking** – book one or more seats on a trip (one booking per passenger per trip). The total price is calculated from `price_per_seat × number_of_seats`.
- **Booking confirmation code** – when a driver confirms a booking, a 6-digit code is generated and sent to both parties.
- **In-app chat** – one chat thread per trip/passenger/driver, with an `is_location` flag for location messages.
- **Reviews** – rate and comment on a trip (one review per reviewer per trip).
- **SOS alerts** – raise an alert with a location; the alert is auto-populated with the caller's active trip, driver, vehicle, source and destination.
- **User reports** – report another user, optionally linked to a chat thread.
- **Personal statistics** – booking counts by status, trips driven, total amount spent and earned.

### Drivers & Fleet Owners

- **Driver onboarding (KYC)** – submit licence number, national ID number, licence (front and back) and ID uploads; profile starts as `pending` until staff verify it.
- **Companies** – create a company and attach drivers and vehicles to it.
- **Vehicle registry** – register cars, bikes or trucks with make, model, colour, year, capacity, picture, registration and insurance documents; staff verify each vehicle.
- **Trip publishing** – create trips with start/destination names and coordinates, start and estimated end time, seat count and price per seat. Trips move through `scheduled → ongoing → completed / cancelled`.
- **Booking management** – confirm or reject incoming bookings; passengers are notified automatically.

### Payments

- **Paynow** – mobile-money express checkout (EcoCash, OneMoney) or web checkout for other methods, with status polling and a server-to-server result webhook. A successful payment marks the trip `paid_for`.
- **OPPWA ("ZipIT") card checkout** – create a checkout, render the hosted payment widget (`payment.html`), and read the result; the user receives a push + WhatsApp confirmation.

### Notifications

- **Push** – Firebase Cloud Messaging to every registered device token of the target user; invalid tokens are deleted automatically. Payloads carry a `screen` hint (e.g. `booking`, `chat`, `payments`, `vehicle-details`, `my-account`) so the client can deep-link.
- **WhatsApp** – text messages through the WhatsApp Cloud API (local numbers are normalised to `+263…`).
- **Email** – OTP delivery (SMTP in development, SendGrid in production).

### Real-time Location

- **WebSocket location feed** – clients stream `latitude`/`longitude` to `/ws/location/`; the latest position per user is persisted in `UserLocation`.
- **REST fallback** – `GET /api/v1/trips/<id>/live-location/` returns the latest position for an ongoing trip (driver first, otherwise a confirmed passenger).

### Operations (Django Admin)

- Review and verify/reject driver KYC documents with inline previews, and step through the pending queue.
- Verify vehicles with registration/insurance previews.
- Block/unblock reported users and step through unresolved reports.
- Watch a trip live on a Google Map from the trip page.
- Read-only audit log of admin actions.

---

## Tech Stack

Versions are the pins in `requirements.txt`.

| Concern | Package / Tool | Version |
| --- | --- | --- |
| Language | Python (code uses `match`; Django 5.2 requires 3.10+) | 3.10+ |
| Web framework | Django | 5.2.1 |
| REST API | Django REST Framework | 3.16.0 |
| Filtering | django-filter | 25.1 |
| Authentication | django-oauth-toolkit (OAuth2, password grant) | 3.0.1 |
| CORS | django-cors-headers | 4.7.0 |
| WebSockets | Channels | 4.3.2 |
| Channel layer | channels_redis | 4.3.0 |
| ASGI server | Daphne | 4.2.1 |
| WSGI server | Gunicorn | 23.0.0 |
| Cache / sessions (prod) | django-redis, redis | 6.0.0, 6.2.0 |
| Database (dev) | SQLite | bundled |
| Database (prod) | PostgreSQL via psycopg2-binary, dj-database-url | 2.9.10, 3.0.1 |
| Static files (prod) | WhiteNoise | 6.9.0 |
| Push notifications | firebase-admin | 6.9.0 |
| Payments | paynow (Paynow Zimbabwe SDK) | 1.0.8 |
| Email (prod) | django-sendgrid-v5, sendgrid | 1.3.0, 6.12.5 |
| HTTP client | requests | 2.32.3 |
| Env loading | python-dotenv | 1.1.0 |
| Image handling | Pillow | 11.2.1 |

`requirements.txt` also pins other packages (e.g. `google-cloud-firestore`, `google-cloud-storage`, `sentry-sdk`, `httpx`) that are not imported anywhere in the application code at present.

---

## Project Structure

```text
parwendo/                              # repository root
├── manage.py                          # Django CLI; defaults to parwendo.settings.dev
├── requirements.txt                   # Pinned Python dependencies
├── Procfile                           # `web: gunicorn parwendo.wsgi:application --bind 0.0.0.0:$PORT`
├── activate.bat                       # Windows helper: activates a venv in parwendo\scripts
├── deploy.bat                         # Windows helper: git add + commit "<msg>" + push origin main
├── verify_sos.py                      # Manual script exercising SOS auto-population (not part of the test runner)
├── LIVE_TRACKING_FEATURE.md           # Design notes for admin live tracking
├── SETUP_GUIDE.md                     # Setup/testing guide for admin live tracking
├── WEBSOCKET_IMPLEMENTATION.md        # Notes on the WebSocket + polling implementation
│
├── parwendo/                          # Django project package
│   ├── urls.py                        # Root URLs: admin, oauth2, api/v1, pdf-viewer, media/static in DEBUG
│   ├── asgi.py                        # ProtocolTypeRouter: HTTP + WebSocket (session auth)
│   ├── wsgi.py                        # WSGI entry point
│   ├── settings.py                    # Standalone single-file settings (superseded by the settings/ package)
│   └── settings/
│       ├── __init__.py                # Package marker
│       ├── dev.py                     # Development settings (SQLite, DEBUG on, Gmail SMTP) – default module
│       └── settings.py                # Production settings (Postgres, Redis cache, HTTPS hardening, SendGrid)
│
├── main/                              # The single Django app containing all domain logic
│   ├── models.py                      # 17 models (users, drivers, trips, bookings, chat, payments, SOS, …)
│   ├── serializers.py                 # Read serializers (nested) and Create serializers (inject request.user)
│   ├── views.py                       # Function-based DRF views, filters, helpers, payment + notification code
│   ├── urls.py                        # /api/v1/ route table
│   ├── consumer.py                    # LocationConsumer – WebSocket location ingest
│   ├── routing.py                     # WebSocket route: ws/location/
│   ├── admin.py                       # Admin customisations (KYC review, vehicle verify, report moderation, live tracking)
│   ├── apps.py                        # App config
│   ├── tests.py                       # Empty placeholder
│   ├── migrations/                    # 0001_initial … 0012_trip_paid_for_trip_payment_transaction
│   ├── management/commands/
│   │   └── create_superuser.py        # Creates a superuser from DJANGO_SUPERUSER_* env vars
│   └── templates/
│       ├── main/payment.html          # OPPWA hosted payment widget page
│       └── admin/main/
│           ├── driverprofile/change_form.html   # Verify / Reject / Go to next pending buttons
│           ├── vehicle/change_form.html         # Mark as Verified button
│           ├── userreport/change_form.html      # Block / Unblock / Go to next pending report buttons
│           └── trip/
│               ├── change_form.html             # Live-tracking map container + Google Maps script
│               └── live_tracking.js             # Template-side copy of the tracking script
│
└── static/
    ├── static_files/                  # STATICFILES_DIRS source
    │   └── admin/main/trip/live_tracking.js     # Live tracking logic (WebSocket + 5 s polling fallback)
    ├── static_root/                   # collectstatic output (dev)
    └── media/                         # Dev MEDIA_ROOT for uploads
        ├── kyc/{profile_pictures,licenses,national_ids}/
        └── vehicles/{pictures,registration,insurance}/
```

---

## Architecture & Patterns

**Single-app, function-based API.** All HTTP endpoints live in `main/views.py` as DRF `@api_view` functions. Repetitive CRUD is delegated to small helpers: `apply_filter_and_respond` (django-filter + optional pagination), `get_and_respond`, `create_object`, `update_object` and `delete_object`. Every resource follows the same shape: a collection route (`GET`, `POST`) and a detail route (`GET`, `PATCH`, `DELETE`).

**Paired serializers.** Each resource has a *read* serializer that nests related objects (e.g. `TripSerializer` embeds `DriverProfileSerializer`, `VehicleSerializer`, `PaymentTransactionSerializer`) and a *create* serializer with a minimal field set. Create serializers (and some views) inject the current user — `driver`, `passenger`, `sender`, `reviewer`, `user` — so clients never send identity fields.

**Filter classes.** One `FilterSet` per resource in `views.py` defines the supported query parameters (see [API Reference](#api-reference)). Only trips (and reviews) are paginated through the helper; other list endpoints return plain arrays.

**Authentication flow.**

1. `POST /api/v1/users/` registers a user and emails an OTP.
2. `POST /api/v1/get_token_from_oauth/` wraps django-oauth-toolkit's token view, performing a `password` grant with `CLIENT_ID`/`CLIENT_SECRET` from the environment, and returns the token payload plus `user_id`, `username` and `email`.
3. Clients send `Authorization: Bearer <access_token>`. DRF is configured with `OAuth2Authentication` and `SessionAuthentication`; the default permission is `IsAuthenticated`.

**Lifecycles.**

| Entity | States |
| --- | --- |
| Trip | `scheduled → ongoing → completed` or `cancelled` |
| Booking | `pending → confirmed` / `rejected` / `cancelled` |
| Driver profile | `pending → verified` / `rejected` |
| Vehicle | `verified` flag set by staff |
| Payment transaction | `initiated → sent / paid / …` (status text from Paynow) |

**Notification fan-out.** Booking creation, booking confirmation/rejection, new chat messages, payment results and admin verification actions all use the same pair of helpers — `send_push_notification` (FCM, to every `FCMDevice` token of the user) and `send_whatsapp_message` (WhatsApp Cloud API). Chat itself is plain REST; the WebSocket channel is used only for location.

**Payment flow (Paynow).**

1. Client calls `POST /paynow_initiate/` with `trip_id`, `amount`, `method`, `email`, `reference` (and `phone` for mobile money).
2. The server creates the Paynow payment (`send_mobile` for `ecocash`/`onemoney`, `send` otherwise), stores a `PaymentTransaction`, links it to the trip, and returns `success`, `redirect_url`, `poll_url` and `instructions`.
3. The client polls `POST /paynow_payment_status/` with `poll_url` + `reference`; when Paynow reports `paid` (or `sent`) the trip's `paid_for` flag is set.
4. Paynow may also call `POST /paynow_result/` server-to-server to update the transaction status.

**Real-time location.**

- `asgi.py` routes HTTP to Django and WebSockets through `AuthMiddlewareStack` (Django session cookies) to `LocationConsumer` at `ws/location/`.
- On connect the consumer joins the `tracking` channel-layer group (Redis). Each JSON message `{"latitude": …, "longitude": …}` is upserted into `UserLocation` (one row per user) and published to the group; invalid payloads get an `{"error": …}` reply.
- The admin trip page (`live_tracking.js`) first fetches the REST endpoint, then tries `ws(s)://<host>/ws/location/`; if the socket isn't connected it polls the REST endpoint every 5 seconds. A status badge shows *Connected* (WebSocket) or *Polling*.

**Admin workflow pattern.** Review queues are implemented by overriding `change_form.html` to add submit buttons (`_mark_verified`, `_mark_rejected`, `_block_user`, `_go_to_next`, …) and handling them in `ModelAdmin.response_change`, which updates the record, notifies the user, and optionally jumps to the next pending item.

**Settings split.** `parwendo.settings.dev` (default) is permissive and SQLite-backed. `parwendo.settings.settings` is the production module: it refuses to start without `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, uses PostgreSQL with `sslmode=require`, Redis-backed cache/sessions, WhiteNoise, HSTS/SSL redirect/secure cookies, DRF throttling (`100/hour` anonymous, `1000/hour` per user) and JSON-only rendering.

---

## Data Models

All models are defined in `main/models.py`.

| Model | File | Key Fields |
| --- | --- | --- |
| `User` (extends `AbstractUser`) | `main/models.py` | `phone` (unique), `profile_picture`, `is_driver`, `verified`, `is_private` |
| `DriverProfile` | `main/models.py` | `user` (1:1), `company`, `license_number`, `national_id_number`, `license_upload`, `license_upload_backside`, `national_id_upload`, `verification_status` (`pending`/`verified`/`rejected`) |
| `Company` | `main/models.py` | `name`, `owner`, `created`, `updated` |
| `Vehicle` | `main/models.py` | `driver`, `owner` (company), `vehicle_number` (unique), `vehicle_type` (`car`/`bike`/`truck`), `vehicle_make`, `vehicle_model`, `vehicle_color`, `vehicle_year`, `vehicle_capacity`, `vehicle_registration_upload`, `insurance_upload`, `vehicle_picture`, `verified` |
| `Trip` | `main/models.py` | `driver`, `vehicle`, `start_location`, `destination`, start/destination `x`/`y` coordinates, `start_time`, `estimated_end_time`, `available_seats`, `price_per_seat`, `status`, `paid_for`, `payment_transaction` |
| `Booking` | `main/models.py` | `trip`, `passenger`, `number_of_seats`, `total_price` (auto-calculated if unset), `status`, `code`; unique on (`trip`, `passenger`) |
| `ChatThread` | `main/models.py` | `trip`, `passenger`, `driver`, `is_active`; unique on (`trip`, `passenger`, `driver`) |
| `ChatMessage` | `main/models.py` | `thread`, `sender`, `message`, `timestamp`, `is_read`, `is_location` |
| `FavouriteDriver` | `main/models.py` | `user`, `driver`; unique pair |
| `FavouriteDestination` | `main/models.py` | `user`, `destination`, `save_as`; unique on (`user`, `destination`) |
| `UserReport` | `main/models.py` | `user`, `reported_user`, `reason`, `is_resolved`, `chat_thread` |
| `OTP` | `main/models.py` | `user`, `code` (6 chars), `expires_at`, `is_expired()` |
| `FCMDevice` | `main/models.py` | `user`, `token` (unique) |
| `Review` | `main/models.py` | `trip`, `reviewer`, `rating`, `comment`; unique on (`trip`, `reviewer`) |
| `PaymentTransaction` | `main/models.py` | `user`, `reference` (unique), `email`, `method`, `phone`, `amount`, `poll_url`, `redirect_url`, `status` |
| `SOSAlert` | `main/models.py` | `user`, `trip`, `driver`, `vehicle`, `location`, `source`, `destination`, `attended_to` |
| `UserLocation` | `main/models.py` | `user` (1:1), `latitude`, `longitude`, `updated_at` |

---

## Services / API Layer

| Service | Transport | Purpose |
| --- | --- | --- |
| django-oauth-toolkit | HTTPS REST (OAuth2 password grant) | Issues and refreshes bearer tokens; wrapped by `get_token_from_oauth` |
| Firebase Cloud Messaging (`firebase_admin.messaging`) | Firebase Admin SDK over HTTPS | Push notifications to `FCMDevice` tokens; stale tokens are removed |
| WhatsApp Cloud API | REST `POST https://graph.facebook.com/v24.0/<phone_number_id>/messages` | Text notifications for bookings, chat, payments and verification |
| Paynow | REST via the `paynow` SDK | Mobile-money express checkout and web checkout; poll URL + result webhook |
| OPPWA (ZipIT) | REST (`eu-test.oppwa.com`) + hosted JS widget | Card checkout creation, payment page, result lookup |
| Email | SMTP (dev, Gmail) / SendGrid API (prod) | OTP delivery |
| Redis | Channel layer (`127.0.0.1:6379`); cache + sessions in prod | WebSocket group messaging; production cache |
| `LocationConsumer` | WebSocket `/ws/location/` | Location ingest and group publish |
| Google Maps JavaScript API | Browser | Live-tracking map in the admin trip page |

---

## Navigation & Routing

```text
/
├── admin/                                   Django admin (customised – see Admin Panel)
├── oauth2/                                  django-oauth-toolkit endpoints (e.g. token/, revoke_token/)
├── pdf-viewer/<path:file_path>              Serves a PDF from MEDIA_ROOT (used by admin previews)
├── ws/location/                             WebSocket – location ingest (LocationConsumer)
└── api/v1/
    ├── Accounts & auth
    │   ├── users/                           GET list · POST register
    │   ├── users/<id>/                      GET · PATCH · DELETE
    │   ├── users/<id>/statistics/           GET
    │   ├── get_token_from_oauth/            POST login
    │   ├── verify_otp/                      POST
    │   ├── resend_otp/                      POST
    │   └── register_fcm_token/              POST
    ├── Drivers, fleet & trips
    │   ├── drivers/ · drivers/<id>/
    │   ├── companies/ · companies/<id>/
    │   ├── vehicles/ · vehicles/<id>/
    │   ├── trips/ · trips/<id>/
    │   └── trips/<trip_id>/live-location/   GET
    ├── Bookings & chat
    │   ├── bookings/ · bookings/<id>/
    │   ├── chat/threads/ · chat/threads/<id>/
    │   └── chat/messages/ · chat/messages/<id>/
    ├── Trust & safety
    │   ├── reviews/ · reviews/<id>/
    │   ├── user_reports/ · user_reports/<id>/
    │   └── sos_alerts/ · sos_alerts/<id>/
    ├── Payments
    │   ├── paynow_initiate/                 POST
    │   ├── paynow_payment_status/           POST
    │   ├── paynow_result/                   POST (Paynow webhook)
    │   ├── paynow_return/                   GET  (browser return URL)
    │   ├── zipit_create_checkout/           POST
    │   ├── zipit_payment/<checkout_id>/     GET  (hosted payment page)
    │   └── zipit_payment/result/            GET  (shopper result URL)
    └── debug_time/                          GET server time + current user
```

Typical flow:

```text
register ─► verify_otp ─► get_token_from_oauth ─► register_fcm_token
   │
   ├─ passenger: trips?available=true ─► bookings (POST) ─► [driver PATCH status=confirmed → code]
   │                                      └─► chat/threads ─► chat/messages ─► reviews
   └─ driver:    drivers (POST, KYC) ─► [staff verify] ─► vehicles (POST) ─► trips (POST)
                                                         └─► paynow_initiate ─► paynow_payment_status
```

---

## Admin Panel

Available at `/admin/`.

| Admin page | Scope |
| --- | --- |
| **Users** | Staff can view and edit users; the permissions, groups and superuser fields are hidden/read-only for non-superusers. |
| **Driver profiles** | Inline previews of licence and national ID uploads (images, PDFs via `pdf-viewer`, other files as links). Buttons: *Mark as Verified*, *Mark as Rejected*, *Go to next pending*. Verify/reject sends push + WhatsApp to the driver. |
| **Vehicles** | Registration and insurance previews. *Mark as Verified* sets `verified` and notifies the driver. |
| **User reports** | *Block Reported User* / *Unblock User* toggle the reported user's `is_active` and send a push notification; *Go to next pending report* walks unresolved reports. |
| **Trips** | List shows ID, driver, destination, status. The change form has a *Start Live Tracking* button that opens a Google Map, tracks via WebSocket with 5 s REST polling fallback, and a *Stop Tracking* button. |
| **Bookings, Chat threads, Chat messages, FCM devices, Reviews, Payment transactions, SOS alerts** | Registered with default `ModelAdmin`. |
| **Log entries** | Read-only audit trail (add/change/delete disabled). |

`Company`, `FavouriteDriver`, `FavouriteDestination`, `OTP` and `UserLocation` are not registered in the admin.

---

## Configuration

### Settings modules

| Module | When | Notes |
| --- | --- | --- |
| `parwendo.settings.dev` | Default (`manage.py`, `wsgi.py`, `asgi.py`) | `DEBUG=True`, SQLite (`db.sqlite3`), Gmail SMTP, media in `static/media/` |
| `parwendo.settings.settings` | Production | Select with `DJANGO_SETTINGS_MODULE=parwendo.settings.settings` |

### How environment variables are loaded

`main/views.py` calls `load_dotenv()` on a `.env` file in the repository root, but this happens **after** the settings module has been imported. Therefore:

- Variables read **inside settings modules** (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and every production variable below) must be exported in the real process environment.
- Variables read **inside views/admin** (`CLIENT_ID`, `PAYNOW_*`, `WHATSAPP_*`) can live in `.env`.

### Environment variables

| Variable | Read by | Required | Purpose |
| --- | --- | --- | --- |
| `CLIENT_ID` | `get_token_from_oauth` (and production `OAUTH2_PROVIDER`) | Yes | Client ID of the OAuth2 application used for the password grant |
| `CLIENT_SECRET` | same | Yes | Client secret of that application |
| `PAYNOW_INTEGRATION_ID` | `views.py` | For Paynow | Paynow integration ID |
| `PAYNOW_INTEGRATION_KEY` | `views.py` | For Paynow | Paynow integration key |
| `WHATSAPP_TOKEN` | `views.py`, `admin.py` | For WhatsApp | WhatsApp Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | `views.py`, `admin.py` | For WhatsApp | WhatsApp Cloud API phone number ID |
| `EMAIL_HOST_USER` | dev settings | For OTP email (dev) | Gmail SMTP username (also the default sender) |
| `EMAIL_HOST_PASSWORD` | dev settings | For OTP email (dev) | Gmail SMTP password |
| `DJANGO_SETTINGS_MODULE` | Django | No | Defaults to `parwendo.settings.dev` |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | `create_superuser` command | For that command | Credentials of the superuser to create |
| `DJANGO_SECRET_KEY` | prod settings | Yes (prod) | Django secret key; startup fails without it |
| `DJANGO_ALLOWED_HOSTS` | prod settings | Yes (prod) | Comma-separated host list; startup fails without it |
| `DATABASE_URL` | prod settings | Yes, unless `DB_*` set | Database URL parsed by `dj-database-url` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` (default `localhost`), `DB_PORT` (default `5432`) | prod settings | Alternative to `DATABASE_URL` | PostgreSQL connection with `sslmode=require` |
| `REDIS_URL` | prod settings | Yes (prod) | Redis cache/session backend |
| `SENDGRID_API_KEY` | prod settings | For email (prod) | SendGrid API key |
| `CSRF_TRUSTED_ORIGINS` | prod settings | Recommended | Comma-separated trusted origins |
| `TIME_ZONE` | prod settings | No | Defaults to `UTC` |
| `ADMIN_URL` | prod settings | No | Defined in the settings module (default `admin/`); `parwendo/urls.py` currently mounts the admin at `admin/` |

Example `.env` (repository root):

```dotenv
# OAuth2 application credentials (create the application in /admin/ first)
CLIENT_ID=your-oauth-client-id
CLIENT_SECRET=your-oauth-client-secret

# Paynow
PAYNOW_INTEGRATION_ID=your-integration-id
PAYNOW_INTEGRATION_KEY=your-integration-key

# WhatsApp Cloud API
WHATSAPP_TOKEN=your-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
```

Dev email variables must be exported in the shell:

```bash
export EMAIL_HOST_USER="you@example.com"        # Windows (cmd): set EMAIL_HOST_USER=you@example.com
export EMAIL_HOST_PASSWORD="app-password"
```

### Required local files and services

| Item | Details |
| --- | --- |
| Firebase service-account JSON | `main/views.py` initialises `firebase_admin` at import time from `parwendo-c278c-firebase-adminsdk-fbsvc-46354a366f.json` in the repository root. The file is git-ignored; the server will not start without it. |
| Redis | The channel layer connects to `127.0.0.1:6379` in both settings modules. |
| OAuth2 application | Create one in the admin (**Django OAuth Toolkit → Applications**): *Confidential*, grant type *Resource owner password-based*. Put its client ID/secret in `CLIENT_ID`/`CLIENT_SECRET`. |

### Values currently set in source code

| Value | Location |
| --- | --- |
| Paynow `result_url` / `return_url` (`https://parwendo-eqps.onrender.com/api/v1/paynow_result` / `…/paynow_return`) and `PAYNOW.sandbox = True` | `main/views.py` |
| OPPWA test endpoint (`eu-test.oppwa.com`), entity ID and authorization header | `zipit_create_checkout`, `zipit_payment_result` in `main/views.py`; widget script in `main/templates/main/payment.html` |
| Google Maps API key | `<script>` tag in `main/templates/admin/main/trip/change_form.html` |
| Redis host/port | `CHANNEL_LAYERS` in both settings modules |
| Sender address for production email | `DEFAULT_FROM_EMAIL` in `parwendo/settings/settings.py` |

---

## Getting Started

**Prerequisites:** Python 3.10+, Redis running on `127.0.0.1:6379`, and a Firebase service-account JSON file.

1. **Clone and create a virtual environment**

   ```bash
   git clone https://github.com/munacips/parwendo.git
   cd parwendo
   python -m venv venv
   source venv/bin/activate          # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Add the Firebase credentials** – place `parwendo-c278c-firebase-adminsdk-fbsvc-46354a366f.json` in the repository root (next to `manage.py`).

4. **Configure the environment** – create `.env` and export the dev email variables as shown in [Configuration](#configuration).

5. **Start Redis**

   ```bash
   redis-server
   ```

6. **Apply migrations**

   ```bash
   python manage.py migrate
   ```

7. **Create an admin user**

   ```bash
   python manage.py createsuperuser
   # or, using DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD:
   python manage.py create_superuser
   ```

8. **Register the OAuth2 application** – sign in at `http://localhost:8000/admin/`, add an application under *Django OAuth Toolkit → Applications* (Confidential, Resource owner password-based), and copy its client ID/secret into `.env`.

9. **Collect static files**

   ```bash
   python manage.py collectstatic --noinput
   ```

10. **Run the server** – Daphne is first in `INSTALLED_APPS`, so `runserver` serves both HTTP and WebSockets:

    ```bash
    python manage.py runserver
    ```

11. **Smoke-test**

    ```bash
    curl http://localhost:8000/api/v1/debug_time/
    ```

    Log in:

    ```bash
    curl -X POST http://localhost:8000/api/v1/get_token_from_oauth/ \
      -H "Content-Type: application/json" \
      -d '{"username": "jane", "password": "secret"}'
    ```

    Use the returned `access_token`:

    ```bash
    curl http://localhost:8000/api/v1/trips/ -H "Authorization: Bearer <access_token>"
    ```

**Tests.** `main/tests.py` is empty, so `python manage.py test` runs no tests. `verify_sos.py` is a manual script that creates `test_*` users, a trip and a booking, posts an SOS alert through the `sos_alerts` view and checks that trip, driver and destination are auto-populated; it is not wired into the test runner.

---

## API Reference

Base path: `/api/v1/`. Unless noted, endpoints require `Authorization: Bearer <access_token>` (or a Django session). Paginated responses use DRF's `PageNumberPagination` (`?page=`, 20 per page) and return `count`, `next`, `previous`, `results`.

### Accounts & authentication

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET, POST | `/users/` | None | List users (filters: `id`, `username`, `is_driver`) / register (a 6-digit OTP is emailed) |
| GET, PATCH, DELETE | `/users/<id>/` | Bearer | User detail |
| GET | `/users/<id>/statistics/` | Bearer | Booking counts, trips, amount spent/earned |
| POST | `/get_token_from_oauth/` | None | Body `{username, password}` → OAuth2 token payload + `user_id`, `username`, `email` |
| POST | `/verify_otp/` | None | Body `{username, otp}` |
| POST | `/resend_otp/` | None | Body `{username}` |
| POST | `/register_fcm_token/` | Bearer | Body `{token}` – register/reassign an FCM device token |

### Drivers, companies, vehicles, trips

| Method | Path | Filters / notes |
| --- | --- | --- |
| GET, POST | `/drivers/` | Filters: `user`, `license_number`, `national_id_number`, `verification_status`, `company`. POST creates the caller's profile and sets `is_driver` (multipart for uploads) |
| GET, PATCH, DELETE | `/drivers/<id>/` | Driver profile detail |
| GET, POST | `/companies/` | Filters: `name`, `owner` |
| GET, PATCH, DELETE | `/companies/<id>/` | Company detail |
| GET, POST | `/vehicles/` | Filters: `driver`, `vehicle_type`, `vehicle_make`, `vehicle_model`, `owner`. POST requires a driver profile |
| GET, PATCH, DELETE | `/vehicles/<id>/` | Vehicle detail |
| GET, POST | `/trips/` | Paginated. Filters: `driver`, `destination` (contains), `start_location` (contains), `start_time` (date), `available` (`true`: upcoming + paid + free seats; `false`: fully booked). POST requires a driver profile |
| GET, PATCH, DELETE | `/trips/<id>/` | Trip detail |
| GET | `/trips/<trip_id>/live-location/` | Latest location for an ongoing trip → `{status, username, lat, lng, updated_at}` |

### Bookings & chat

| Method | Path | Filters / notes |
| --- | --- | --- |
| GET, POST | `/bookings/` | Filters: `trip`, `passenger`, `status`, `user`. POST body `{trip, number_of_seats}`; notifies the driver |
| GET, PATCH, DELETE | `/bookings/<id>/` | PATCH `status` to `confirmed` (generates a 6-digit `code`, notifies both parties) or `rejected` (notifies the passenger) |
| GET, POST | `/chat/threads/` | Filters: `trip`, `passenger`, `driver`, `booking` |
| GET, PATCH, DELETE | `/chat/threads/<id>/` | Thread detail |
| GET, POST | `/chat/messages/` | Filters: `thread`, `sender`. POST body `{thread, message, is_location}`; notifies the other participant |
| GET, PATCH, DELETE | `/chat/messages/<id>/` | Message detail |

### Trust & safety

| Method | Path | Filters / notes |
| --- | --- | --- |
| GET, POST | `/reviews/` | Filters declared: `trip`, `reviewer`. POST body `{trip, rating, comment}` |
| GET, PATCH, DELETE | `/reviews/<id>/` | Review detail |
| GET, POST | `/user_reports/` | Filters: `user`, `reported_user`, `chat_thread`. POST body `{reported_user, reason, chat_thread}` |
| GET, PATCH, DELETE | `/user_reports/<id>/` | Report detail |
| GET, POST | `/sos_alerts/` | Filters: `user`, `driver`, `trip`. POST body `{location}`; trip, driver, vehicle, source and destination are filled from the caller's active trip |
| GET, PATCH, DELETE | `/sos_alerts/<id>/` | Alert detail (`attended_to`) |

### Payments

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/paynow_initiate/` | Bearer | Body `{trip_id, amount, method, email, reference, phone?, description?}`; `method` of `ecocash`/`onemoney` uses mobile express checkout |
| POST | `/paynow_payment_status/` | None (plain view) | Body `{poll_url, reference}` – checks Paynow and updates the transaction/trip |
| POST | `/paynow_result/` | None | Paynow server-to-server result webhook (form data: `reference`, `status`) |
| GET | `/paynow_return/` | None | Browser return URL |
| POST | `/zipit_create_checkout/` | None | Body `{amount, currency, entityId?, paymentType?, integrity?}` → OPPWA checkout response |
| GET | `/zipit_payment/<checkout_id>/` | None | Renders the hosted payment widget page |
| GET | `/zipit_payment/result/?resourcePath=…` | None | Fetches the payment result and notifies the user |

Example `paynow_initiate` body:

```json
{
  "trip_id": 1,
  "amount": 10.50,
  "method": "ecocash",
  "phone": "0777000000",
  "email": "user@example.com",
  "reference": "ORDER123",
  "description": "Payment for trip 1"
}
```

### Utility

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/debug_time/` | None | Returns `server_time` and the current user |
| GET | `/pdf-viewer/<path>` (root URL, not under `/api/v1/`) | None | Serves a PDF from `MEDIA_ROOT` |

### WebSocket

| Path | Auth | Messages |
| --- | --- | --- |
| `/ws/location/` | Django session (`AuthMiddlewareStack`) | Client → server: `{"latitude": -17.8252, "longitude": 31.0335}`. Server → client on bad input: `{"error": "Missing required fields: latitude and longitude"}` or `{"error": "Invalid JSON format"}` |

---

## Deployment

The repository ships with a `Procfile` for platforms that read one (Heroku-style, Render):

```text
web: gunicorn parwendo.wsgi:application --bind 0.0.0.0:$PORT
```

Production checklist:

1. **Settings** – set `DJANGO_SETTINGS_MODULE=parwendo.settings.settings` and provide the production variables listed in [Configuration](#configuration) (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL` or `DB_*`, `REDIS_URL`, `SENDGRID_API_KEY`, `CSRF_TRUSTED_ORIGINS`, plus the OAuth, Paynow and WhatsApp variables).
2. **Services** – PostgreSQL (connections use `sslmode=require`) and Redis.
3. **Build/release steps**

   ```bash
   pip install -r requirements.txt
   python manage.py collectstatic --noinput   # WhiteNoise serves from staticfiles/
   python manage.py migrate
   python manage.py create_superuser          # optional, needs DJANGO_SUPERUSER_* vars
   ```

4. **Firebase credentials** – the service-account JSON must exist in the repository root on the server because `views.py` loads it at import time.
5. **WebSockets** – Gunicorn with the WSGI app (as in the `Procfile`) does not serve `/ws/location/`. Run an ASGI server for the WebSocket route, for example:

   ```bash
   daphne -b 0.0.0.0 -p $PORT parwendo.asgi:application
   ```

   Note that `asgi.py` and `wsgi.py` default to `parwendo.settings.dev` unless `DJANGO_SETTINGS_MODULE` is set.
6. **Payments** – update the Paynow `result_url`/`return_url` and the `PAYNOW.sandbox` flag in `main/views.py` for your environment, and replace the OPPWA test endpoint/credentials before going live.
7. **HTTPS** – the production settings enable `SECURE_SSL_REDIRECT`, HSTS and secure cookies and trust the `X-Forwarded-Proto` header, so deploy behind a TLS-terminating proxy.
8. **Media** – uploads (KYC documents, vehicle pictures) are written to `MEDIA_ROOT` (`media/` in production) on the local filesystem; the application does not configure remote storage.

`deploy.bat "<commit message>"` is a Windows convenience script that stages everything, commits, and pushes to `origin main`. No Dockerfile or CI configuration is included in this repository.

---

## Further Reading

- [`LIVE_TRACKING_FEATURE.md`](LIVE_TRACKING_FEATURE.md) – how admin live tracking works
- [`SETUP_GUIDE.md`](SETUP_GUIDE.md) – setup, testing and troubleshooting for live tracking
- [`WEBSOCKET_IMPLEMENTATION.md`](WEBSOCKET_IMPLEMENTATION.md) – WebSocket and polling fallback details
