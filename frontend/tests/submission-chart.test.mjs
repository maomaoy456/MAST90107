import test from 'node:test';
import assert from 'node:assert/strict';
import { submissionChart } from '../submission-chart.js';

const schedule = (key, status='source_date_available') => ({dimensions:{assessment_key:key,assignment_ref:key,
  assignment_name:key,deadline_date:'2025-05-11',deadline_status:status,deadline_days_after_course_end:status==='source_date_after_course_end'?'152':'0'}});
const row = (key, day, count) => ({dimensions:{assignment_ref:key,days_from_deadline:day},metrics:{submitted_students:{value:count}}});

test('each assignment uses Day 0 and starts with an observed submission', () => {
  const html=submissionChart([row('AT1',-8,1),row('AT1',0,29),row('AT2',-3,2),row('AT2',0,33)],
    [schedule('AT1'),schedule('AT2')]);
  assert.match(html,/AT1 · Day 0: 29 submissions/);
  assert.match(html,/AT2 · Day 0: 33 submissions/);
  assert.match(html,/AT1 · Day -8: 1 submissions/);
  assert.match(html,/AT2 · Day -3: 2 submissions/);
  assert.match(html,/data-series-key="AT1" aria-pressed="true"/);
  assert.match(html,/data-series-key="AT2" aria-pressed="true"/);
  assert.match(html,/Cumulative submissions \(count\)/);
  assert.doesNotMatch(html,/start proxy|Students submitted \(%\)|NaN/);
});

test('AT2 keeps its colour and square markers even when shown alone', () => {
  const html=submissionChart([row('AT2',2,1),row('AT2',4,5)],[schedule('AT2')]);
  assert.match(html,/stroke="#d9792b"/);
  assert.match(html,/stroke-dasharray="7 4"/);
  assert.match(html,/<rect /);
  assert.match(html,/AT2 5/);
});

test('withheld counts do not produce a fabricated curve', () => {
  assert.match(submissionChart([row('AT1',4,null)],[schedule('AT1')]),/source deadline/);
});

test('a deadline after the teaching period is labelled and hidden by default', () => {
  const html=submissionChart([row('AT1',-2,4),row('AT2',-150,3)],
    [schedule('AT1'),schedule('AT2','source_date_after_course_end')]);
  assert.match(html,/data-series-key="AT2" aria-pressed="false"/);
  assert.match(html,/AT2 deadline requires review/);
  assert.match(html,/152 days after the teaching period ended/);
});
