# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Bolão** is a Brazilian World Cup betting pool (bolão) web application. Users authenticate via Google OAuth, create betting pools, place bets with score predictions, and earn points based on how accurate their predictions are. A background crawler fetches live match results from GloboEsporte to update scores automatically.

## Development Setup

### Local (Windows)

```bash
# Set up virtualenv and install dependencies
cd bolao
pip install virtualenv
virtualenv venv
venv\Scripts\activate
cd application
pip install -r requirements.txt

# Start MongoDB (must be installed and running as a Windows service)
net start MongoDB

# Run the app
python app.py

# Run the crawler (populates DB and calculates scores)
python GloboEsporteCrawler.py
```

### Docker (Production / EC2)

```bash
# From project root
docker-compose up --build
```

The `docker-compose.yml` spins up three services: `nginx` (ports 80/443), `app` (Gunicorn on port 8000), and `db` (MongoDB on port 27017, internal only).

## Architecture

### Stack
- **Backend:** Python 3.6, Flask 0.12, Gunicorn
- **Database:** MongoDB 3.6 via PyMongo (no ORM)
- **Auth:** Google OAuth 2.0 (rauth + Flask-Login)
- **Templates:** Jinja2 (server-rendered, no frontend framework)
- **Reverse proxy:** Nginx + Let's Encrypt (production)

### Key Files
- `application/app.py` — All Flask routes and business logic (~670 lines)
- `application/GloboEsporteCrawler.py` — Scrapes GloboEsporte for match results and calculates prediction scores
- `application/oauth.py` — Google OAuth setup
- `application/db_config.py` — MongoDB connection (tries `db` hostname first, falls back to `localhost`)
- `application/templates/` — Jinja2 templates, all extending `base.html`

### MongoDB Collections (`dev` database)
`jogo`, `selecao`, `usuario`, `bolao`, `aposta`, `palpite`, `pontuacao`, `historico`

Collections are accessed as module-level globals prefixed `tbl_` (e.g., `tbl_jogo = db.jogo`).

### Scoring System
- 3 pts: exact score match (`placar_exato`)
- 1 pt: correct winner/draw (`vencedor_ou_empate`)
- 1 pt: correct goals for one team (`gols_de_um_time`)

Rankings are recalculated by the crawler after each round with historical position tracking.

### Background Crawler
`loop.sh` runs `GloboEsporteCrawler.py` every 60 seconds in the background (started by `start.sh` alongside Gunicorn). It scrapes match results, updates the `jogo` collection, recalculates `pontuacao`, and updates `historico` for ranking evolution charts.

### Auth Flow
All authenticated routes use `@login_required` (Flask-Login). OAuth callback at `/callback/google` exchanges the code for a token, fetches the Google profile, and upserts the user in `tbl_usuario`. The `Usuario` class in `app.py` implements the Flask-Login interface.

### Adding New Dependencies
```bash
# After pip install:
pip freeze > requirements.txt
git add requirements.txt
```

## Development Process

### Test-Driven Development (TDD)
**Always follow the `tdd` skill for any production code change** — new features, bug fixes, and refactors alike.
The workflow is: write a failing test → confirm it fails for the right reason → write the minimum code to pass → confirm all tests pass.

```bash
# Run a single test file (fast feedback)
python -m pytest application/tests/test_foo.py -v

# Run full suite (regression check)
python -m pytest
```
