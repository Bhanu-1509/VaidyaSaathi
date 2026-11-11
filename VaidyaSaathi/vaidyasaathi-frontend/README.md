# VaidyaSaathi frontend

Plain HTML, CSS and JavaScript. No npm or build step.

- `index.html` – page shell
- `style.css` – all styles (colours are at the top in `:root`)
- `app.js` – the whole app, in sections: helpers, API, cart, header and search, home, doctor page,
  slot picker, lab tests, lab booking, my bookings, sign in/up, profile, doctor portal, admin, Saathi assistant, router
- `server.py` – serves these files and forwards `/api/<service>/...` to the backend services (avoids CORS)

With Docker it runs automatically. Without Docker: start the services on ports 8000–8007, then run
`python server.py` here and open http://127.0.0.1:5173.
