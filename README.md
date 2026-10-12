# MPE Course Platform

An English-language course platform for course managers and project researchers. It compares teaching periods, Canvas engagement, assignment completion, confirmed course pass, Badge evidence, Qualtrics feedback and verified Salesforce support cases. Student identifiers and row-level student records never leave the backend.

The project has two ways to view the same six pages:

- **Internal live application:** MySQL, FastAPI and the frontend. It supports data import, rule changes and model retraining.
- **Static data snapshot:** the current aggregate API results are stored with the frontend. It needs no database or backend and shows the saved model results. Data is read-only; staff can edit chart insight notes.

## Quick view for course managers

Open `demo/index.html` in Chrome or Edge. It is a self-contained offline copy, so no command or installation is needed. The header shows the snapshot date. Model retraining is labelled as unavailable because it remains an internal operation.

`static_dashboard/` contains the same snapshot as ordinary website files. This directory is easier for a technical team to inspect or place on an internal web server. For a quick local check:

```powershell
Set-Location D:/path/to/MAST90107
python -m http.server 4173 --directory static_dashboard
```

Then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

The static snapshot supports course and teaching-period selection, day/week/month timelines, all assignments, one selected assignment, AT1 or AT2 comparisons across teaching periods, every Summary & Recommendations tab and the latest saved model results. Data & Rules is course-wide, so its Teaching period control is disabled. Arbitrary assignment multi-selection and model retraining remain available in the live application.

## Chart notes and comparisons

Charts and comparison panels include **Key insight → Edit insight → Save note**. Live notes are stored in MySQL and scoped by course, teaching period and chart. The Summary and Recommendations tabs are authored reports and do not add note editors; Predictive models has one course-wide Key insight. Assignment-selection and weekly-comparison notes are separated when the selected comparison changes. Notes are plain text, limited to 2,000 characters.

In the static version, Save note updates the open snapshot and also uses browser storage when available. Use the single **Download updated HTML** button at the top right to save a portable copy containing all saved notes across pages and courses. Browsers cannot silently overwrite the original HTML file. Share the downloaded file; browser storage alone is not portable. Save pending edits before downloading. Independently edited copies are not automatically merged.

Engagement **Page views by teaching week** starts with the selected teaching period. Click legend buttons to add or remove other periods; several can be shown together. **Page views by learning stage** always compares all periods in the course and outlines the selected one. Other Engagement panels retain their existing selection scope.

Each chart keeps its title, followed by a short subtitle describing the data and a smaller caption explaining the comparison.

### Assignment timing evidence and interpretation

The cumulative-submission chart shows student counts and aligns each assignment to its own deadline at Day 0. Negative days mean before the deadline; positive days mean after. AT1 uses blue circles and a solid curve; AT2 uses orange squares and a dashed curve. Smooth connections pass through observed counts without overshooting; they do not estimate working time. Coincident values remain coincident. The underlying API retains its original release-proxy fields.

In `datasets/canvas_assignment_activity_all_courses_anonymised.xlsx`, Sheet1 column D is `created_at`, G is `assignment_name`, H is `due_at` and I is `unlock_at`. The 956 AT1/AT2 rows represent 445 unique student/course pairs; every pair has exactly the same set of AT1 and AT2 creation timestamps. All `unlock_at` values are blank, and `published` is only a boolean. Thus the same start proxy is **not evidence of the actual publication date**. The following Excel row pairs show each assignment's earliest recorded creation timestamp (UTC):

| Course / teaching period | AT1 / AT2 Excel rows | Shared earliest `created_at` |
| --- | --- | --- |
| PBS 2025 MAR PAR 1 | 882 / 883 | 2025-02-11 05:06:25Z |
| PBS 2026 JUL PAR 1 | 84 / 85 | 2026-07-20 06:06:35Z |
| Treaty 2025 MAR PAR 1 | 552 / 553 | 2025-03-11 05:06:17Z |
| Treaty 2025 MAR PAR 2 | 120 / 121 | 2025-03-18 05:06:54Z |
| Treaty 2025 MAR PAR 4 | 776 / 777 | 2025-03-14 05:05:54Z |
| Treaty 2025 MAY PAR 2 | 248 / 249 | 2025-04-30 06:05:21Z |
| Treaty 2026 FEB PAR 1 | 872 / 873 | 2026-01-28 03:09:49Z |
| Treaty 2026 FEB PAR 2 | 152 / 153 | 2026-02-03 05:06:01Z |
| Treaty 2026 MAR PAR 1 | 734 / 735 | 2026-03-06 05:05:23Z |

## Project contents

| Path | Purpose |
| --- | --- |
| `backend/app/ingestion/` | Canvas Engagement, Assignment and Badge reading, normalization, identity-safe import and verification |
| `backend/app/supplemental/` | Offering calendar, Qualtrics and Salesforce import |
| `backend/app/dashboard/` | Aggregate page calculations and API routes |
| `backend/app/modeling/` | Cutoff-safe features, model training and saved artifacts |
| `backend/app/static_export.py` | Static API snapshot, release scan, website bundle and offline HTML generation |
| `frontend/` | Shared live/static frontend and local API-key proxy |
| `static_dashboard/` | Generated static website directory |
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


Salesforce cases are published only when the file contains a course field that verifies attribution to the selected course. The current Treaty file meets this condition. The current PBS file has no course field or enrolment link, so its rows are retained internally with an unverified-scope status and are excluded from dashboard totals and issue summaries. A matching date range alone is not treated as proof of course membership.

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

## Train the two targets

Training is local and separate for each course and target: confirmed course pass and active Badge.

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m app.modeling --course 0AUTI0001 --target all
../.venv/Scripts/python.exe -m app.modeling --course 0UNDE0001 --target all
```

Logistic regression and random forest are compared with three-fold student-grouped validation using Macro F1 and Balanced Accuracy. Course pass is binary: both valid component results are required, AT1 contributes 40%, AT2 contributes 60%, and the weighted result must reach 70%. Badge is binary. A target is intentionally marked insufficient when a required class is missing, a class has fewer than three students, the total has fewer than twenty students, or grouped validation cannot be formed. An insufficient run never replaces a valid saved model.

Both targets use only Canvas behaviour and non-scored self-assessment completion. AT1/AT2 submission indicators, AT1/AT2 scores and the weighted grade are excluded from every predictor set. Pass features stop at the latest confirmed assessment deadline. Badge features stop at course end and require a 60-day observation window.

With the current snapshot, both Pass targets are correctly marked insufficient: PBS has 29 passes and no failing result, while Treaty has 251 passes and one result below 70 among the records linked to Canvas activity. PBS Badge selected Logistic regression with Macro F1 0.935; Treaty Badge selected Random forest with Macro F1 0.756. These are exploratory course-level results, not individual decisions.

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
| Overview | Teaching periods, source availability, Canvas Assignment student totals, confirmed course pass, Qualtrics feedback and verified Salesforce support demand |
| Engagement | Canvas resource mix, students and views by first access date, AT1/AT2 deadline markers, teaching-week/stage views, expandable Other Canvas areas and verified Salesforce support operations |
| Assignments | AT1/AT2 submitted counts, attempts, cumulative submissions aligned to each assignment deadline, confirmed course pass, self-assessment completion and Badge reconciliation |
| Feedback | Qualtrics NPS with coloured percentage shares, Q1/Q3/Q4/Q5 response distributions with a legend in each group, open-question response volume, the leading classified feedback type in each area and folded cleaned anonymous comments |
| Summary & Recommendations | Project-wide summary, eight evidence-linked recommendations and two course-level model targets with saved evaluation and internal retraining controls |
| Data & Rules | Course-level source guide, shared glossary, calculation definitions, versioned assessment rules and data limitations |

Data availability and teaching-period dates appear only on Overview. Qualtrics feedback has its own page. Badge evidence follows confirmed course pass at the end of Assignments. Visible counts identify their unit, and source-specific technical fields remain in folded data where needed.

Assignment charts answer four operational questions: who submitted, how many attempts were recorded, how submissions accumulated before and after each deadline, and whether the confirmed pass mark was reached. The frontend does not display raw scores or late flags. These source fields remain in MySQL for audit and future analysis.

The Canvas export has no reliable assignment publication timestamp. The API retains the earliest recorded `created_at` per assignment as a release proxy; the frontend shifts each curve to its own deadline at Day 0. See the source evidence above. This chart does not measure active working time.

Pass summaries show **Passed**, **Fail** and **Result unavailable**. Overall course pass requires valid AT1 and AT2 results and uses the effective versioned rule returned by the API. The confirmed current rule is AT1 40%, AT2 60% and a 70% pass mark. Result unavailable is never counted as a failure.

Badge evidence is matched by student identity to exactly one Assignment teaching period within the course. The Assignment cohort is the shared denominator for the reconciliation panel. Passed students without an active Badge record and Badge records without a confirmed pass remain visible; the values are not manually balanced. Revoked-only evidence is separate from academic failure.

Visible cohort names are consistent across pages: **Assignment cohort** means distinct students with Canvas Assignment records, **Engagement cohort** means distinct students with Canvas Engagement records, **Survey response cohort** means completed anonymous Qualtrics responses, and **Model cohort** means records that contain the outcome and predictors required by a model. Data & Rules defines these terms and the remaining chart terminology in one course-wide glossary.

Survey valid-response counts are not interchangeable: a theme requires at least half its items answered in a completed questionnaire; each individual question counts its own valid answers. This is why a theme can have 10 valid responses while its item counts range from 9 to 11. Open-question response volume counts completed questionnaires containing text for that prompt area. Classified topic counts may overlap when one comment matches more than one auditable keyword rule. No anonymous Survey-to-student or Survey-to-assignment-score join is implied.

## API summary

Protected routes use `/api/v1` and require `X-API-Key`.

| Route | Purpose |
| --- | --- |
| `GET /catalog` | Courses, offerings, dates and source coverage |
| `GET /overview` | Overview page |
| `GET /engagement` | Engagement and support page |
| `GET /assignment-options` | Valid assignment references for the selected scope |
| `GET /assignments` | Assignment page |
| `GET /outcomes` | Qualtrics Feedback page |
| `GET /insights` | Recommendations plus Summary-page model targets, status and interpretation notes |
| `GET /models` | Saved model runs and metrics |
| `POST /models/train` | Internal model retraining |
| `GET /data-rules` | Course-level data source guide, glossary, calculations, assessment rules and limitations |
| `GET /rules` | Rule history |
| `PUT /rules/{offering_code}` | Internal offering-rule update |
| `GET /insight-notes` | Saved notes for a course and optional offering; optional `chart_key` returns one note |
| `PUT /insight-notes` | Save plain-text `note` with `course`, optional `offering`, and `chart_key` |
| `GET /health` | Application and database status |

Common filters are `course`, `offering`, or comma-separated `offerings`. Data & Rules accepts `course` only because its definitions do not vary by teaching period. Engagement accepts `interval=day|week|month`. Assignments accepts `mode=combined|scored|self_assessment` and references returned by `/assignment-options`. Summary model metadata accepts `target=all|pass|badge`; the model view pools compatible teaching periods within the selected course.

The Assignment API returns `assessment_pass_status`, `assignment_schedule`, `assignment_cumulative_submission`, `academic_results`, `badge_status`, `badge_course_reconciliation` and `badge_offering_comparison`. Rows include readable `assignment_name` and confirmed `assessment_key` alongside the stable `assignment_ref`. Academic results expose the effective `calculation_rule` and `pass_threshold_pct`; frontends should use these rather than hard-code offering overrides.

Engagement includes `other_resource_types`, which expands the combined Other Canvas areas category, plus `assignment_deadlines` for timeline markers. Interactive-action counts are excluded from the Engagement page contract but remain available internally for modeling. Outcomes groups the original Qualtrics items under Q1, Q3, Q4 and Q5. It returns `survey_feedback_response_counts` for the number of completed responses containing text in each open-question area, `survey_feedback_topic_highlights` for each area's leading classified type, the top five classified topics per area and cleaned comments. Unverified support exports return `support_data_status` instead of publishing case totals or text summaries.

## Core interpretation rules

- Explicit `Z` or offset timestamps are stored as UTC instants. Naive timestamps use `Australia/Melbourne`; calendar views use Melbourne dates.
- Engagement `start_date` means the first view of a resource, not course commencement. Only first-view attribution is used: the full resource-summary count is placed on that date. It is not a daily click log; the midpoint output has been removed.
- Both courses have AT1 at 40% and AT2 at 60%, no final exam and a pass threshold of 70. Both valid component grades are required; missing work stays unknown.
- Missing attempts stay null. Submission status, `missing`, `late` and `excused` remain independent. Zero-point self-assessments remain non-scored activities.
- Badge and academic pass are independent. Revoked-only evidence is unsuccessful; a separate valid award remains valid.
- Badge offering membership comes from unique student-to-Assignment matching within the course, rather than award dates.
- Survey responses and Salesforce cases are not joined to students. `Age (Hours)` is Salesforce response time.
- Summary and Recommendations cover both reviewed courses and all nine teaching periods. Predictive models remain course-specific and pool compatible teaching periods to preserve the available sample.
- The Pass and Badge models exclude assignment submission indicators and every grade field. Saved metrics describe grouped validation performance; they do not support individual learner decisions.

## Verification

```powershell
Set-Location D:/path/to/MAST90107/backend
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m app.dashboard.check
../.venv/Scripts/python.exe -m app.preflight
../.venv/Scripts/python.exe -m app.ingestion verify
```

The test database must be empty, configured through `TEST_DATABASE_URL`, start with `mpe_` and end in `_test`. Tests never clean or mutate the project database. Raw files must not be edited or committed. Current schema head: `0009_model_targets`. The current backend automated suite contains 104 tests.

For the isolated assignment-chart checks (requires Node.js), run from the project root:

```powershell
node frontend/tests/submission-chart.test.mjs
```

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
