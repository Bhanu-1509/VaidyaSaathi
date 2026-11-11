# VaidyaSaathi – run everything with Docker

Needs Docker Desktop (Windows/Mac) or Docker Engine + Compose (Linux).

## Services

| Service | Port | What it does |
|---|---|---|
| frontend | 5173 | The website. Open http://127.0.0.1:5173 |
| auth-service | 8000 | Logins, patient sign-up with email code, doctor accounts |
| doctor-service | 8001 | Doctors, specialities, weekly hours, leave |
| patient-service | 8002 | Patient profiles |
| appointment-service | 8003 | Doctor appointments |
| scheduling-service | 8004 | Free appointment slots |
| notification-service | 8005 | Emails (printed in its log when SMTP is not set) |
| lab-service | 8006 | Lab tests, health packages, lab centres, lab bookings |
| ai-service | 8007 | "Saathi" booking assistant (Google Gemini) |
| postgres | 5433 | Database (pgAdmin: host 127.0.0.1, port 5433, user postgres) |

## Setup (once)
1. Copy `.env.example` to `.env` and fill it in (commands to generate secrets are inside).
2. Optional: put a Gemini API key in `GEMINI_API_KEY` (free from https://aistudio.google.com/apikey).
   Without it the assistant still works in basic mode: it matches symptoms to specialists and tests.

## Sign-up codes by email
Until email is set up, the sign-up screen shows the 6-digit code itself (and it is also printed in
`docker compose logs notification-service`). To send real emails with Gmail:
1. Turn on 2-Step Verification for the Gmail account.
2. Create an App Password at https://myaccount.google.com/apppasswords (16 letters).
3. In `.env`: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=you@gmail.com`, `SMTP_PASSWORD=<app password>`.
4. `docker compose up -d`, then test: `docker compose exec notification-service python -m app.send_test you@gmail.com`

Once email works, codes are never shown on screen.

## Start and stop
```
docker compose up --build -d     # build and start in the background
docker compose ps                # everything should say "Up"
docker compose down              # stop (add -v only to delete all data)
```

## First-time data
```
docker compose exec auth-service python -m app.create_admin
Get-Content docker\seed-specialities.sql | docker compose exec -T postgres psql -U postgres -d doctor_db
```
(The second line is PowerShell. On Mac/Linux: `docker compose exec -T postgres psql -U postgres -d doctor_db < docker/seed-specialities.sql`.)

The lab test catalogue (45 tests, 9 packages) and 3 sample lab centres are added automatically the first
time lab-service starts. Change prices in `lab-service/app/seed.py` before the first start, and replace
the sample centres from **Admin → Lab centres**.

## Using it
- **Admin**: dashboard with today's numbers; add and edit doctors and specialities; see every
  appointment by date and doctor; block or unblock patients; add and edit lab tests and packages,
  hide tests; work through lab bookings (sample collected → processing → report link); add, edit,
  close lab centres.
- **Doctor**: *My appointments* shows patients for any date (week strip, arrows, or calendar) with age,
  gender, phone and reason; confirm, complete or cancel. *Hours and leave* sets weekly hours, checks
  free slots on any date, and takes a day off in one tap. No hours means no slots.
- **Patient**: sign up with email code, fill in the profile, book doctors, add lab tests to the cart and
  book home collection or a centre visit, see everything under *My bookings*, chat with Saathi.

## Rules you can change
- Lab slot times, capacity, home collection fee: `lab-service/app/config.py`
- Gemini model: `GEMINI_MODEL` in `.env` (default `gemini-3.5-flash-lite`; `gemini-3.8-flash` gives better answers)
- Assistant behaviour and safety rules: `system_prompt()` in `ai-service/app/tools.py`

## Useful
- `docker compose logs -f lab-service` – one service's log (OTP codes show in `notification-service`)
- API docs for each service: http://127.0.0.1:8000/docs, 8001/docs … 8007/docs
- After changing code in a service: `docker compose up --build -d <service>`
