# MPE Course Analytics

An English-language course analytics dashboard for course managers and project researchers. It compares course offerings, Engagement, Assignments, academic results, Badge outcomes, Qualtrics feedback and Salesforce support cases. Student identifiers and row-level student records never leave the backend.

The project has two ways to view the same six pages:

- **Internal live application:** MySQL, FastAPI and the frontend. It supports data import, rule changes and model retraining.
- **Read-only static snapshot:** the current aggregate API results are stored with the frontend. It needs no database or backend and shows the saved model results.

## Quick view for course managers

Open `demo/index.html` in Chrome or Edge. It is a self-contained offline copy, so no command or installation is needed. The header shows the snapshot date. Model retraining is labelled as unavailable because it remains an internal operation.

`static_dashboard/` contains the same snapshot as ordinary website files. This directory is easier for a technical team to inspect or place on an internal web server. For a quick local check:

```powershell
Set-Location D:/path/to/MAST90107
python -m http.server 4173 --directory static_dashboard
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

The static snapshot supports course and offering selection, day/week/month timelines, all assignments, one selected assignment, AT1 or AT2 comparisons across offerings, all Insights targets and every page-level tab. Arbitrary assignment multi-selection and model retraining remain available in the live application.

## Project contents

| Path | Purpose |
| --- | --- |
| `backend/app/ingestion/` | Canvas Engagement, Assignment and Badge reading, normalization, identity-safe import and verification |
| `backend/app/supplemental/` | Offering calendar, Qualtrics and Salesforce import |
| `backend/app/dashboard/` | Aggregate page calculations and API routes |
| `backend/app/modeling/` | Cutoff-safe features, model training and saved artifacts |
| `backend/app/static_export.py` | Static API snapshot, release scan, website bundle and offline HTML generation |
| `frontend/` | Shared live/static frontend and local API-key proxy |
| `static_dashboard/` | Generated read-only website directory |
| `demo/index.html` | Generated self-contained offline dashboard |
| `backend/config/` | Reviewed source mappings and assessment rules |
| `backend/alembic/` | Versioned MySQL schema migrations |
| `docs/raw-data.sha256.json` | Source-file integrity baseline; contains hashes, not source rows |

## Requirements for a full local installation

- Windows PowerShell
- Python 3.11 or later
- MySQL 8.0.16 or later, running locally
- The nine source files listed below

The application uses MySQL directly. Docker is optional future packaging and is not required for setup or use.

## Required data files

Create `datasets/` at the project root and place these files inside it with the exact names shown:

| Source | Filename |
| --- | --- |
| Canvas Engagement | `Canvas Engagement_Final.xlsx` |
| Canvas Assignments | `canvas_assignment_activity_all_courses_anonymised.xlsx` |
| Badge awards | `Issuer Badge Awards - Annonymised 2.csv` |
| PBS offering calendar | `PBS - Autism Afferming Practice Salesforce Enrolments Extract.xls` |
| Treaty offering calendar | `Understanding Treaty Salesforce Enrolments Extract.xls` |
| PBS Qualtrics | `0AUTI0001_2025_MAR_PAR_1 _ PBS_ Autism Affirming Practice_August 26, 2026_00.20.csv` |
| Treaty Qualtrics | `Understanding Treaty _ 0UNDE0001_2026_FEB_PAR_2_August 26, 2026_00.21.csv` |
| PBS Salesforce cases | `PBS - Autism Afferming Practice Salesforce Extract.xls` |
| Treaty Salesforce cases | `Understanding Treaty Salesforce Extract.xls` |

The three primary filenames are declared in `backend/app/preflight.py`. Calendar, Survey and Salesforce mappings are declared in `backend/config/supplemental_sources.json`. When a later semester uses new filenames or offerings, update those reviewed mappings before import. Keep `datasets/` outside Git; it is already ignored.

## First-time setup and import

From the project root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt

Set-Location backend
../.venv/Scripts/python.exe -m app.setup_mysql
../.venv/Scripts/python.exe -m app.migrate upgrade
../.venv/Scripts/python.exe -m app.seed
../.venv/Scripts/python.exe -m app.ingestion init-key
../.venv/Scripts/python.exe -m app.preflight
../.venv/Scripts/python.exe -m app.ingestion import-all
../.venv/Scripts/python.exe -m app.supplemental
../.venv/Scripts/python.exe -m app.ingestion verify
../.venv/Scripts/python.exe -m app.ingestion report
```

`app.setup_mysql` asks for the MySQL administrator password without printing or saving it. It creates separate project and test databases, a project-scoped account and a private root `.env`. It refuses to overwrite an existing `.env`.

`app.ingestion import-all` imports Canvas Engagement, Assignment and Badge data. `app.supplemental` imports offering dates, Qualtrics and Salesforce. Each supplemental file or scope is transactional, so a failed import does not leave a partial scope.

Keep `.env` and `IDENTITY_HMAC_KEY` private and backed up. Changing the identity key prevents later files from matching existing students. Confirm `BADGE_DATA_AS_OF` in `.env` before Badge training; it is the actual cutoff date of the Badge export.

## Train the four targets

Training is local and separate for each course and target: AT1, AT2, weighted final and Badge.

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m app.modeling --course 0AUTI0001 --target all
../.venv/Scripts/python.exe -m app.modeling --course 0UNDE0001 --target all
```

Logistic regression and random forest are compared with three-fold student-grouped validation using Macro F1 and Balanced Accuracy. Grade classes are `<70`, `70–<80` and `>=80`; Badge is binary. A target is intentionally marked insufficient when a required class is missing, a class has fewer than three students, the total has fewer than twenty students, or grouped validation cannot be formed. An insufficient run never replaces a valid saved model.

AT1 features stop at the AT1 deadline. AT2 and weighted-final features stop at the AT2 deadline and may use AT1 information available by then. Badge features stop at course end, exclude assignment scores and weighted grades, and require a 60-day observation window.

## Run the internal live application

Open PowerShell window 1:

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

Open PowerShell window 2:

```powershell
Set-Location D:/path/to/MAST90107
.venv/Scripts/python.exe frontend/server.py
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Port 8000 is deliberately unused. The frontend proxy reads the API key from `.env` and attaches it server-side; the browser never receives the key. API documentation is available at [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

## Refresh the static dashboard

Import any new semester data and retrain the desired targets first. The backend and frontend servers do not need to be running. MySQL must be available.

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m app.static_export
```

The exporter reads the real protected API in-process and writes every supported aggregate/filter response. The count changes when offerings or assignments are added. It blocks the release if it finds a student identity digest, forbidden identity field, configured database/API/HMAC secret or unredacted email address.

Successful output replaces:

- `static_dashboard/`: normal static website files plus `snapshot-manifest.json`;
- `demo/index.html`: one self-contained file for nontechnical viewers.

The export is read-only: it does not modify the database or train models. Survey comments and Salesforce issue summaries shown in the live API are included after the same direct-identifier cleaning. Anyone who receives the static files can read their embedded aggregate and text data, so distribute them only to the intended staff group.

## Pages

| Page | Main content |
| --- | --- |
| Overview | Cohort and source coverage, offering comparison, academic results, weighted grade bands, Survey themes/NPS and Salesforce summaries |
| Engagement | Resource categories; activity timelines and course phases; support activity, response time, channels, topics and representative cleaned issue summaries |
| Assignments | Scored/self-assessment modes, submission and missing status, lateness, attempts, timing, scores, feedback and AT1 40% + AT2 60% weighted results |
| Badge & Outcomes | Valid/revoked Badge evidence, completion, award timing, delay, independent academic outcomes, Survey summaries and cleaned anonymous comments |
| Insights | Five question-led exploratory views with one relationship chart and one group comparison each; a separate Models tab shows saved model evaluation and internal retraining controls |
| Data & Rules | Source quality, calendar information and versioned assessment rules |

## API summary

Protected routes use `/api/v1` and require `X-API-Key`.

| Route | Purpose |
| --- | --- |
| `GET /catalog` | Courses, offerings, dates and source coverage |
| `GET /overview` | Overview page |
| `GET /engagement` | Engagement and support page |
| `GET /assignment-options` | Valid assignment references for the selected scope |
| `GET /assignments` | Assignment page |
| `GET /outcomes` | Badge, academic and Survey outcomes |
| `GET /insights` | Exploratory analysis |
| `GET /models` | Saved model runs and metrics |
| `POST /models/train` | Internal model retraining |
| `GET /data-rules` | Source quality and rules page |
| `GET /rules` | Rule history |
| `PUT /rules/{offering_code}` | Internal offering-rule update |
| `GET /health` | Application and database status |

Common filters are `course`, `offering`, or comma-separated `offerings`. Engagement and Outcomes accept `interval=day|week|month`. Assignments accepts `mode=combined|scored|self_assessment` and references returned by `/assignment-options`. Insights accepts `target=all|AT1|AT2|weighted_final|badge` and always pools compatible offerings within the selected course.

## Core interpretation rules

- Explicit `Z` or offset timestamps are stored as UTC instants. Naive timestamps use `Australia/Melbourne`; calendar views use Melbourne dates.
- Engagement `start_date` means the first view of a resource, not course commencement. First-view and midpoint timelines are alternate estimates and must not be added.
- Both courses have AT1 at 40% and AT2 at 60%, no final exam and a pass threshold of 70. Both valid component grades are required; missing work stays unknown.
- Missing attempts stay null. Submission status, `missing`, `late` and `excused` remain independent. Zero-point self-assessments remain non-scored activities.
- Badge and academic pass are independent. Revoked-only evidence is unsuccessful; a separate valid award remains valid.
- Badge offering membership comes from unique student-to-Engagement matching within the course, rather than award dates.
- Survey responses and Salesforce cases are not joined to students. `Age (Hours)` is Salesforce response time.
- Insights pools compatible offerings within each course because the student sample is small. Its Exploration tab opens one of five questions at a time: engagement and grades, page categories, contact timing, self-assessment, or Badge relationships. Each view contains one necessary assessment selector, a short finding, a Spearman relationship chart, a group comparison, a compact coverage note and one folded supporting table.
- Spearman correlation describes a ranked association, not causation. Intervals crossing zero are shown as directionally uncertain. The within-offering rank value remains available in the folded table as a secondary reference and is not mixed with the raw estimate in the chart.

## Verification

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m app.dashboard.check
../.venv/Scripts/python.exe -m app.preflight
../.venv/Scripts/python.exe -m app.ingestion verify
```

The test database must be empty, configured through `TEST_DATABASE_URL`, start with `mpe_` and end in `_test`. Tests never clean or mutate the project database. Raw files must not be edited or committed. Current schema head: `0006_model_artifacts`.

## Prepare a private GitHub repository

The current folder is not yet a Git repository. After reviewing the generated static content for the intended staff audience:

```powershell
Set-Location D:/path/to/MAST90107
git init
git add .
git status
git commit -m "Initial course analytics dashboard"
git branch -M main
git remote add origin <private-repository-url>
git push -u origin main
```

Before committing, confirm that `datasets/`, `.env`, `.venv/`, `model_artifacts/` and `.idea/` do not appear in `git status`. The generated `static_dashboard/` and `demo/` contain the approved aggregate/text snapshot and should only be committed to a repository whose readers may view that snapshot.

Current implementation status and remaining work are recorded in `WORKLOG.md`.
