# Work Log

## Current state — 2026-09-22

The project supports the complete local workflow from the nine reviewed source files through MySQL, aggregate APIs, local model training, the six-page English dashboard and a read-only offline snapshot. Course selection applies throughout. Operational pages can filter teaching periods; Insights pools compatible teaching periods within the selected course.

## Current product

- **Overview:** teaching periods, data availability, student coverage, dates, confirmed course pass, Survey feedback and verified course support demand.
- **Engagement:** Canvas resource mix, activity by first access date, teaching week and stage, expandable Other Canvas areas, and verified support operations.
- **Assignments:** submission status, attempts, time from course start to submission, per-assessment pass, overall course pass, self-assessment and AT1/AT2 completion.
- **Badge & Feedback:** active/revoked evidence, recorded Badge rate, course-pass reconciliation, award timing, Survey feedback and data checks.
- **Insights:** five business-question reports plus saved Logistic regression/Random forest results and internal retraining controls.
- **Data & Rules:** source quality and versioned assessment rules.

The frontend no longer displays assignment scores, late flags, deadline coverage or deadline-relative charts. Source values remain stored and available to compatible APIs. Unavailable values remain distinct from zero. Charts use direct values and legends; the Badge timeline draws points for isolated dates.

## Latest data and logic changes

- PBS Salesforce cases are retained internally but excluded from published support metrics because the file has no verifiable course field or enrolment link. Treaty support remains published because its course field verifies scope.
- Other Canvas areas can be expanded into normalized resource types.
- Assignment pass status uses Passed, Did not reach pass mark and Result unavailable. Submission timing uses valid submitted/graded timestamps and reports median and middle 50% from course start.
- Badge and course pass are compared on the same linked Canvas population without manually balancing the results. Differences are shown as review items.
- Insights now reports Canvas activity and passing, activity mix, start/submission timing, self-assessment and passing, and behaviours linked to recorded Badges. The main view uses plain-language findings; technical Spearman values remain in folded data.

## Static delivery

`backend/app/static_export.py` reads the authenticated API in-process, generates supported read-only filter combinations and scans the release before writing it. The scanner rejects student identity digests, forbidden identity fields, configured database/API/HMAC secrets and unredacted email addresses.

Output is stored in `static_dashboard/` for an internal web server and `demo/index.html` as one self-contained file for course managers. The snapshot includes cleaned anonymous Survey comments and only verified Salesforce issue summaries. Live and static views use the same frontend modules; model retraining remains internal.

## Modeling retained

- AT1, AT2 and weighted-final models use the fixed `<70`, `70–<80` and `>=80` classes required by the project.
- Badge training excludes assignment grades and weighted results and requires at least 60 days of observation.
- Logistic regression and random forest are compared with Macro F1 and Balanced Accuracy. Insufficient class support is reported rather than hidden.
- Existing successful artifacts remain available; new data can be imported and models retrained from the internal application or command line.

## Verification

- The automated suite contains 103 tests.
- The read-only API matrix, data preflight, ingestion verification, Python compilation and frontend JavaScript syntax checks pass.
- Static export and its identity/secret scan pass against the current MySQL data.
- The source and generated frontend contain no product or generator branding markers.

## Remaining work

- Add the assessment-weight editing window, optional upload flow and aggregate export.
- Decide whether future staff snapshots should use an authenticated internal host.
- Package Docker deployment when cross-computer deployment becomes a priority.
