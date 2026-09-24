# Work Log

## Current state — 2026-09-24

The project supports the complete local workflow from the nine reviewed source files through MySQL, aggregate APIs, local model training, the six-page English dashboard and a read-only offline snapshot. Course selection applies throughout. Assignments opens on the latest teaching period and scored work; Insights pools compatible teaching periods within each course.

## Current product

- **Overview:** teaching periods, data availability, Canvas Assignment student totals, teaching dates, confirmed course pass, Qualtrics feedback and verified Salesforce support demand.
- **Engagement:** Canvas resource mix, students and views by first access date, AT1/AT2 deadline markers, teaching week/stage views, expandable Other Canvas areas and verified Salesforce support operations. Interactive-action counts remain internal for Insights/modeling.
- **Assignments:** submitted/total counts, attempts, cumulative submissions from a labelled release proxy, per-assignment Pass/Fail status, confirmed course pass, self-assessment completion and Badge reconciliation.
- **Feedback:** Qualtrics NPS with coloured percentage shares, four expandable source-question groups with local legends, open-question response volume, the leading classified type in each feedback area and folded cleaned comments.
- **Insights:** five question-led business reports plus saved Logistic regression/Random forest results and internal retraining controls.
- **Data & Rules:** source quality and versioned assessment rules.

The product title is **MPE Course Platform**. Counts and rates display their units. Result labels are Passed, Fail and Result unavailable.

## Latest data and logic changes

- Overview uses Canvas Assignment records for Total number of students and no longer displays the cross-source intersection card. Qualtrics and Salesforce are named explicitly.
- Badge records are resolved through student identity to exactly one Assignment teaching period in the same course. Course pass and Badge comparison now share the Assignment population. Badge rates, award timelines, award delay charts and public matching diagnostics were removed.
- The Badge section follows course pass on Assignments. The previous Badge & Feedback page is now Feedback only.
- The Canvas export has no reliable assignment publication timestamp. Row-level `created_at` varies by student, so the cumulative submission curve uses the earliest recorded value per assignment as a release proxy and states that limitation. Source deadlines remain visible as reference markers.
- Engagement page APIs and charts expose students and views, while participations remain available only to Insights/modeling.
- Qualtrics NPS is labelled on its −100 to +100 scale; Detractor, Passive and Promoter shares display explicit coloured percentages in both Overview and Feedback. Folded data tables also retain the percent symbol.
- Q1, Q3, Q4 and Q5 are the only four response-distribution foldouts. Each uses the original question stem, shows every full statement and includes its own five-level colour legend.
- Feedback now separates two questions: response volume compares how often students answered the four open-feedback prompts, while the second chart shows the leading classified type within each area. Topic output excludes `other_unclassified` and `no_text` and retains at most five classified types per area for audit.
- PBS Salesforce cases remain excluded because the supplied file has no verified course field or enrolment link. Treaty support remains published.

## Static delivery

`backend/app/static_export.py` reads the authenticated API in-process, generates supported read-only filters and scans the release for student identifiers, forbidden fields, configured secrets and unredacted email addresses.

Output is stored in `static_dashboard/` for an internal web server and `demo/index.html` as one self-contained file for course managers. The current export contains 245 aggregate responses. Live and static views use the same frontend modules; model retraining remains internal.

## Modeling retained

- AT1, AT2 and weighted-final models use the required `<70`, `70–<80` and `>=80` classes.
- Badge training excludes assignment grades and weighted results and requires at least 60 days of observation.
- Logistic regression and random forest are compared with Macro F1 and Balanced Accuracy. Insufficient class support is reported rather than hidden.

## Verification

- 103 automated tests pass.
- API matrix checks, Python compilation and frontend JavaScript syntax checks pass.
- Static export and identity/secret scan pass against the current MySQL data.
- Browser checks confirmed Overview, Engagement, Assignments and Feedback structure, labels, default filters and visual data availability.

## Remaining work

- Add the assessment-weight editing window, optional upload flow and aggregate export.
- Decide whether future staff snapshots should use an authenticated internal host.
- Package Docker deployment when cross-computer deployment becomes a priority.
