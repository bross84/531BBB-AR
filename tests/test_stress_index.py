"""Stress is a separate, descriptive metric. No calls to the real Hevy account."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

import stress_index as stress

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def S(w=220, reps=5, rpe=6, **extra):
    return {"weight_kg":w, "reps":reps, "rpe":rpe, "type":"normal", **extra}


def history(days=1, id="one", **set_args):
    return {**S(**set_args), "workout_id":id, "workout_start_time":(NOW-timedelta(days=days)).isoformat()}


class TestSessionStress(unittest.TestCase):
    def test_reproduces_controlled_examples_without_using_loading_chart(self):
        cases = [([S()], (.48,.59,.37)),
                 ([S(231,3,7),S()], (1.25,1.20,1.30)),
                 ([S(231,1,10),S(198,5,6)], (2.59,1.20,3.98)),
                 ([S(231,1,9.5),S(209,3,8)], (2.20,1.23,3.18))]
        for sets, expected in cases:
            with self.subTest(sets=sets):
                result = stress.session_score(sets)
                for key, value in zip(("total","peripheral","central"),expected):
                    self.assertAlmostEqual(value,result[key],delta=.03)
                self.assertEqual(result['total'],(result['peripheral']+result['central'])/2)

    def test_uniform_weight_scaling_and_order_do_not_change_score(self):
        sets=[S(231,3,7),S()]
        expected=stress.session_score(sets)
        self.assertEqual(expected,stress.session_score(list(reversed(sets))))
        scaled=[dict(s,weight_kg=s['weight_kg']/2.20462) for s in sets]
        for key in ('total','central','peripheral'):
            self.assertAlmostEqual(expected[key],stress.session_score(scaled)[key])

    def test_missing_rpe_is_flagged_and_does_not_mutate_source(self):
        sets=[S(231,3,7),S(rpe=None)]
        original=deepcopy(sets)
        result=stress.session_score(sets)
        self.assertEqual(1,result['estimated_sets'])
        self.assertEqual(stress.session_score([sets[0],S(rpe=5)])['total'],result['total'])
        self.assertEqual(original,sets)
        self.assertNotEqual(stress.session_score([S(rpe=0)])['total'],stress.session_score([S(rpe=None)])['total'])

    def test_warmups_excluded_and_invalid_or_uncovered_sets_reported(self):
        sets=[S(type='warmup'),S(w=0),S(reps=0),S(reps=100),S(w=float('nan'))]
        result=stress.session_score(sets)
        self.assertEqual((0,4,0),(result['sets'],result['skipped_sets'],result['total']))

    def test_tied_heaviest_sets_have_an_order_independent_reference(self):
        sets=[S(100,3,7),S(100,3,9)]
        self.assertEqual(stress.session_score(sets),stress.session_score(list(reversed(sets))))


class TestHistoryAndWindows(unittest.TestCase):
    def test_local_snapshot_replaces_hevy_and_preserves_low_rpe(self):
        remote=[history(),history(id='other')]
        local=[dict(S(rpe=4.5),hevy_workout_id='one',workout_start=remote[0]['workout_start_time'])]
        merged=stress.merge_history(remote,local)
        self.assertEqual(2,len(merged))
        self.assertEqual(4.5,next(s['rpe'] for s in merged if s['workout_id']=='one'))
        self.assertEqual('other',merged[0]['workout_id'])

    def test_local_only_workout_is_included_once(self):
        local=[dict(S(),hevy_workout_id='local',workout_start=NOW.isoformat())]
        self.assertEqual(1,len(stress.merge_history([],local)))

    def test_cutoffs_future_timezone_and_draft_counted_once(self):
        entries=[history(1,'a'),history(7,'b'),history(8,'c'),history(28,'d'),history(-1,'future')]
        offset=history(2,'offset')
        offset['workout_start_time']=(NOW-timedelta(days=2)).astimezone(timezone(timedelta(hours=-4))).isoformat()
        entries.append(offset)
        result=stress.build_summary(entries,[S()],now=NOW)
        one=stress.session_score([S()])['total']
        self.assertAlmostEqual(3*one,result['rolling_7']['total']) # 1d, 2d, draft
        self.assertAlmostEqual(5*one,result['rolling_28']['total']) # adds 7d and 8d
        self.assertEqual(5,result['window']['sessions']) # includes 28d, not future/draft

    def test_baseline_uses_sessions_not_empty_weeks_and_excludes_draft(self):
        entries=[history(2,'a'),history(20,'b'),history(40,'c'),history(57,'old')]
        result=stress.build_summary(entries,[S(reps=10,rpe=10)],now=NOW)
        self.assertEqual(3,result['window']['sessions'])
        typical=stress.session_score([S()])['total']
        self.assertAlmostEqual(typical,result['window']['median'])
        self.assertAlmostEqual(.8*typical,result['window']['lower'])
        self.assertTrue(result['window']['provisional'])
        self.assertEqual('much_higher',result['status'])

    def test_empty_history_has_no_invented_window(self):
        result=stress.build_summary([],[],now=NOW)
        self.assertIsNone(result['window']['median'])
        self.assertEqual('no_sets',result['status'])
        self.assertEqual('no_baseline',stress.build_summary([],[S()],now=NOW)['status'])

    def test_old_draft_not_added_to_recent_totals(self):
        result=stress.build_summary([], [S()],now=NOW,session_start=NOW-timedelta(days=8))
        self.assertEqual(0,result['rolling_7']['total'])
        self.assertGreater(result['rolling_28']['total'],0)

