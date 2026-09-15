# Work Log

## Current state — 2026-09-16

The project now supports a complete local workflow from the nine reviewed source files through MySQL, aggregate APIs, model training, the six-page live dashboard and a read-only static snapshot. The interface is English-only. Course selection applies throughout; operational pages support offering selection, while Insights pools offerings within the selected course.

## Completed application

- **Overview:** cohort/source coverage, offering comparison, academic and weighted-grade results, Qualtrics themes/NPS and Salesforce summaries.
- **Engagement:** resource categories, first-view and midpoint timelines, course weeks/phases, support volume, response time, channels, topics and cleaned representative issue summaries.
- **Assignments:** scored/self-assessment modes, assignment selection, submission/missing/late status, attempts, timing, grades, feedback and AT1 40% + AT2 60% weighted results.
- **Badge & Outcomes:** valid/revoked evidence, completion rate, award timeline, course-end delay, independent academic outcomes, Survey results, cleaned anonymous comments and matching diagnostics.
- **Insights:** AT1, AT2, weighted-final and Badge targets; five exploration areas; coverage funnels; Spearman plots with uncertainty; group comparisons; class distributions; logistic-regression/random-forest results; internal retraining.
- **Data & Rules:** source quality, calendar information and versioned assessment rules.

All multicolour charts have legends or direct labels. The Badge award timeline draws markers for isolated observations. Fast page switching discards stale responses. Unavailable values remain distinct from zero.

## Static delivery completed

`backend/app/static_export.py` runs the real authenticated API without requiring the web servers, generates the supported read-only filter combinations and performs a release scan before writing files. The scanner rejects student identity digests, forbidden identity fields, configured database/API/HMAC secrets and unredacted email addresses.

The current snapshot contains 267 aggregate responses for both courses. It includes cleaned Survey comments and Salesforce issue summaries. Output is stored in:

- `static_dashboard/` for an internal static web server;
- `demo/index.html` as a self-contained file that a course manager can open directly.

The live and static views use the same frontend modules. Static mode replaces API calls with snapshot lookups and labels model results as saved. It supports all assignments, a single assignment, and AT1/AT2 cross-offering groups; arbitrary multi-selection and model retraining stay in the internal live application.

## Data and modeling rules retained

- The source import pipeline preserves unknown attempts, independent submission flags, zero-point self-assessments, timezone meaning and the maximum available source columns.
- Badge and academic pass remain independent. Badge training excludes assignment grades and requires a 60-day observation window.
- Grade targets use `<70`, `70–<80` and `>=80`; insufficient class support is reported rather than hidden.
- Existing successful artifacts remain for Treaty AT1, Treaty AT2, Treaty Badge and PBS Badge. Other grade targets remain insufficient under the fixed class rules.

## Verification

- Static export completed against the current MySQL data and passed its release scan.
- The snapshot includes both cleaned text tables: Survey feedback comments and Salesforce issue summaries.
- The static bundle contains no configured credentials or student identity digests.
- The source frontend contains no product or generator branding markers.
- 101 automated tests pass. The read-only API matrix passes 180 requests across six pages and nine offerings without changing assessment rules.
- Python compilation, frontend JavaScript syntax and generated-artifact checks pass.

## Remaining work

- Design a future aggregate prediction-output experience.
- Add the assessment-weight editing window, optional upload flow and aggregate export.
- Decide whether the staff static snapshot should later use an authenticated internal host.
- Package Docker deployment when cross-computer deployment becomes a priority.
