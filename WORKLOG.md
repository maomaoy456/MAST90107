# Work Log

## Current state — 2026-09-30

The project supports the complete local workflow from the nine reviewed source files through MySQL, aggregate APIs, local model training, the six-page English dashboard and an offline data snapshot with editable chart notes. Course selection applies throughout. Assignments opens on the latest teaching period and scored work; Summary & Recommendations combines a project-wide report with course-level models. Data & Rules is course-wide and does not use a teaching-period filter.

## Current product

- **Overview:** teaching periods, data availability, Canvas Assignment student totals, teaching dates, confirmed course pass, Qualtrics feedback and verified Salesforce support demand.
- **Engagement:** Canvas resource mix, students and views by first access date, AT1/AT2 deadline markers, teaching week/stage views, expandable Other Canvas areas and verified Salesforce support operations. Interactive-action counts remain internal for modeling.
- **Assignments:** submitted/total counts, attempts, cumulative submissions aligned to each assignment deadline, confirmed course pass, self-assessment completion and Badge reconciliation.
- **Feedback:** Qualtrics NPS with coloured percentage shares, four expandable source-question groups with local legends, open-question response volume, the leading classified type in each feedback area and folded cleaned comments.
- **Summary & Recommendations:** project-wide evidence summary, eight evidence-linked recommendations, and saved Course pass/Active Badge model results with internal retraining controls.
- **Data & Rules:** course-specific source availability, a shared cross-page glossary, calculation definitions, versioned assessment rules and interpretation limitations.

The product title is **MPE Course Platform**. Counts and rates display their units. Result labels are Passed, Fail and Result unavailable.

## Latest data and logic changes

- Overview uses the consistent **Assignment cohort**, **Engagement cohort** and **Survey response cohort** terms. Qualtrics and Salesforce are named explicitly.
- Badge records are resolved through student identity to exactly one Assignment teaching period in the same course. Course pass and Badge comparison now share the Assignment cohort. Badge rates, award timelines, award delay charts and public matching diagnostics were removed.
- The Badge section follows course pass on Assignments. The previous Badge & Feedback page is now Feedback only.
- Source review confirmed identical AT1/AT2 `created_at` values for all 445 student/course pairs across nine teaching periods. `unlock_at` is blank, so these are record-creation proxies rather than verified publication times. The submission chart now aligns both assignments to their own deadline at Day 0, with cumulative counts, shape-preserving smooth connections, blue circles/solid AT1 and orange squares/dashed AT2. Original API calculations remain unchanged.
- Shared chart notes now cover graph and comparison panels on all six pages. Migration `0008_chart_notes` adds course-wide and chart-specific scopes. Live notes persist in MySQL; static notes persist in the downloaded HTML, with browser storage as a local convenience. There is one HTML-download button in the page header.
- Weekly Engagement views support multi-period legend selection, defaulting to the current period. Learning-stage views compare all periods and outline the selected one.
- Chart titles are retained, with separate concise data subtitles and smaller purpose captions. Shared note, caption and assignment-chart modules replace the former single-chart editor and unused timeline rendering options.
- Engagement page APIs and charts expose students and views, while interactive-action counts remain available only to modeling.
- Qualtrics NPS is labelled on its −100 to +100 scale; Detractor, Passive and Promoter shares display explicit coloured percentages in both Overview and Feedback. Folded data tables also retain the percent symbol.
- Q1, Q3, Q4 and Q5 are the only four response-distribution foldouts. Each uses the original question stem, shows every full statement and includes its own five-level colour legend.
- Feedback now separates two questions: response volume compares how often students answered the four open-feedback prompts, while the second chart shows the leading classified type within each area. Topic output excludes `other_unclassified` and `no_text` and retains at most five classified types per area for audit.
- PBS Salesforce cases remain excluded because the supplied file has no verified course field or enrolment link. Treaty support remains published.

## Static delivery

`backend/app/static_export.py` reads the authenticated API in-process, generates supported read-only filters and scans the release for student identifiers, forbidden fields, configured secrets and unredacted email addresses.

Output is stored in `static_dashboard/` for an internal web server and `demo/index.html` as one self-contained file for course managers. The current export contains 243 aggregate responses. Data & Rules is exported once per course rather than once per teaching period. Live and static views use the same frontend modules; model retraining remains internal.

## Summary and modeling update

- The former five-question Insights exploration was removed because its findings now sit beside the relevant source charts. The page is named Summary & Recommendations and has Summary, Recommendations and Predictive models tabs.
- Recommendations are returned by the backend and reproduce the reviewed four-stage learner-journey layout. Each action includes its evidence, source page and either Supported by current data or Data groundwork status.
- Models now target only confirmed course pass and active Badge. Both use Canvas behaviour and non-scored self-assessment completion; AT1/AT2 submission indicators and every grade field are excluded.
- Pass is binary under the confirmed AT1 40% + AT2 60%, 70% rule. Current Pass runs are insufficient because PBS has no failing class and Treaty has only one linked result below 70.
- PBS Badge selected Logistic regression (Macro F1 0.935); Treaty Badge selected Random forest (Macro F1 0.756). Badge retains the 60-day observation rule.
- Migration `0009_model_targets` retires version-1 runs; model version 2 and the offline snapshot now contain only Pass and Badge targets.
- Summary and Recommendations do not display editable insight notes. Predictive models has one course-wide Key insight editor.

## Reference guide and terminology update

- Data & Rules now acts as the dashboard manual: Data sources, Glossary, Calculation rules, Assessment rules and Data limitations.
- The Teaching period selector is disabled on Data & Rules. Changing Course updates source status, including the verified Treaty Salesforce support export and the excluded PBS export.
- The shared glossary defines Assignment cohort, Engagement cohort, Survey response cohort, Model cohort, support case records, Canvas view terms, assignment proxies, course pass, Active Badge, response time, NPS, Key insight and Not available.
- Frontend labels, chart subtitles, population descriptions and Badge reconciliation wording use the same cohort terms.

## Verification

- 104 automated backend tests pass.
- API matrix checks, Python compilation and frontend JavaScript syntax checks pass.
- Static export and identity/secret scan pass against the current MySQL data.
- Browser checks covered all eight Recommendations plus Data & Rules for PBS and Treaty. Course switching updates source availability, the teaching-period control stays disabled, and no browser errors were recorded.

## Remaining work

- Add the assessment-weight editing window, optional upload flow and aggregate export.
- Decide whether future staff snapshots should use an authenticated internal host.
- Package Docker deployment when cross-computer deployment becomes a priority.
