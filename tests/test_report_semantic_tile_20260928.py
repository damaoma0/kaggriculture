"""Statistical direction and artifact-integrity regression checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_semantic_tile_20260928 import comparison, compare_provenance, load_world, summarize, wilson


class TileReportTests(unittest.TestCase):
    def test_regression_test_has_correct_tail(self):
        losses = summarize([-100, -80, -130, -105, -90, -95], draws=1000)
        gains = summarize([100, 80, 130, 105, 90, 95], draws=1000)
        self.assertTrue(losses["significantly_worse"])
        self.assertLess(losses["regression_p_one_sided"], .001)
        self.assertFalse(gains["significantly_worse"])
        self.assertGreater(gains["regression_p_one_sided"], .999)
        self.assertLess(losses["t95"][1], 0)
        self.assertEqual(losses, summarize([-100, -80, -130, -105, -90, -95], draws=1000))

    def test_identity_is_not_claimed_as_proven_noninferiority(self):
        summary = summarize([0] * 40, draws=100)
        self.assertEqual(summary["regression_p_one_sided"], 1.0)
        self.assertEqual(summary["t95"], [0.0, 0.0])
        self.assertEqual(summary["unchanged"], 40)
        low, high = wilson(20, 40)
        self.assertLess(low, .5)
        self.assertGreater(high, .5)

    def test_ledger_checks_final_cash_and_does_not_double_count_cumulative_leaks(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            result = root / "sector" / "multi" / "A" / "123.json"
            ledger = root / "ledgers" / "A" / "123.json"
            result.parent.mkdir(parents=True)
            ledger.parent.mkdir(parents=True)
            raw = dict(episode=123, arm="A", money={str(d): [100 + d - 11, 100] for d in range(11, 31)},
                       tier_err=dict(errors=0, bank_used=5, steps_over_1s=1),
                       tier_days={str(d): {"tp_leak": {"forbidden": 1}} for d in range(11, 30)})
            days = [dict(cash=100 + d - 11, rev={"WHEAT": 5}, spend={"BUY_SEED:WHEAT": 3}, wages=1,
                         land=0, failed={}, noeff={}, died={}) for d in range(30)]
            result.write_text(json.dumps(raw))
            ledger.write_text(json.dumps(dict(final=119, opp_final=100, days=days,
                                             engine_audit=dict(statuses=["DONE","DONE"],steps=720,act_timeout=1))))
            row = load_world(result)
            self.assertTrue(row["complete"])
            self.assertEqual(row["tp_leak"], {"forbidden": 1})
            self.assertTrue(row["own_cash_reconciled"])
            self.assertTrue(row["final_matches_ledger"])
            changed = json.loads(ledger.read_text())
            changed["final"] = 118
            ledger.write_text(json.dumps(changed))
            row = load_world(result)
            self.assertFalse(row["own_cash_reconciled"])
            self.assertFalse(row["final_matches_ledger"])

    def test_padded_cash_after_early_termination_is_never_a_completed_game(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            result=root/"sector"/"multi"/"A"/"123.json"
            ledger=root/"ledgers"/"A"/"123.json"
            result.parent.mkdir(parents=True);ledger.parent.mkdir(parents=True)
            raw=dict(episode=123,arm="A",money={str(d):[100,100] for d in range(11,31)},
                     tier_err=dict(errors=0,bank_used=64))
            days=[dict(cash=100 if d<25 else None,rev={},spend={},wages=0,land=0) for d in range(30)]
            result.write_text(json.dumps(raw));ledger.write_text(json.dumps(dict(final=100,opp_final=100,days=days)))
            row=load_world(result)
            self.assertTrue(row["reported_money_series_complete"])
            self.assertFalse(row["complete"])
            self.assertFalse(row["observed_daily_cash_complete"])
            self.assertIsNone(row["engine_verified_complete"])
            self.assertGreater(len(row["completion_issues"]),1)

    def test_source_policy_match_ignores_read_only_wrapper_changes(self):
        p=dict(executor_sha256="frozen",base="K5b",policy_cfg={"sd_clean":1},no_timeout=False,
               source_hashes={"scripts/semantic_tile_20260928_run.py":"old"})
        b=dict(provenance=p,engine_audit=dict(act_timeout=1))
        c=dict(provenance={**p,"source_hashes":{"scripts/semantic_tile_20260928_run.py":"new"}},engine_audit=dict(act_timeout=1))
        self.assertTrue(compare_provenance(b,c)["policy_match"])
        self.assertTrue(compare_provenance(b,c)["runtime_match"])
        c["provenance"]={**p,"policy_cfg":{"sd_clean":0}}
        self.assertFalse(compare_provenance(b,c)["policy_match"])
        c["provenance"]=p;c["engine_audit"]={"act_timeout":100000}
        self.assertFalse(compare_provenance(b,c)["runtime_match"])

    def test_missing_games_cannot_pass_requested_full40_gate(self):
        result = comparison({}, "baseline", "candidate", [str(i) for i in range(40)], "full40", 1, 100)
        self.assertEqual(result["paired_games"], 0)
        self.assertFalse(result["requested_competitive_gate"]["pass_"])
        self.assertFalse(result["evidence_supports_requested_gate"])
        self.assertFalse(result["noninferiority_proven"])

    def test_full40_gate_requires_twenty_wins_and_matched_frozen_policy(self):
        expected=[str(i) for i in range(40)]
        provenance=dict(executor_sha256="frozen",base="K5b",policy_cfg={"sd_clean":1},no_timeout=False)
        def row(ep,arm,margin):
            return dict(episode=ep,arm=arm,complete=True,ours=1000+margin,rival=1000,margin=margin,
                        ledger_path="fixture",executor_errors=0,tp_leak={},own_cash_reconciled=True,
                        final_matches_ledger=True,failed_market_requests={},no_effect_commands={},
                        crop_and_animal_deaths={},runtime_bank_used=5,steps_over_1s=2,
                        bank_exceeds_60s=False,ineffective_moves=0,
                        engine_audit=dict(statuses=["DONE","DONE"],steps=720,act_timeout=1),
                        engine_verified_complete=True,observed_daily_cash_complete=True,provenance=provenance)
        rows={}
        for i,ep in enumerate(expected):
            margin=100 if i<20 else -100
            rows[("baseline",ep)]=row(ep,"baseline",margin)
            rows[("candidate",ep)]=row(ep,"candidate",margin)
        passed=comparison(rows,"baseline","candidate",expected,"full40",1,100)
        self.assertTrue(passed["requested_competitive_gate"]["pass_"])
        self.assertTrue(passed["integrity_gate_pass"])
        self.assertFalse(passed["noninferiority_proven"])
        rows[("candidate","0")]=row("0","candidate",-100)
        nineteen=comparison(rows,"baseline","candidate",expected,"full40",1,100)
        self.assertFalse(nineteen["requested_competitive_gate"]["wins_at_least20"])
        rows[("candidate","0")]=row("0","candidate",100)
        rows[("candidate","0")]["provenance"]={**provenance,"executor_sha256":"other-policy"}
        mismatched=comparison(rows,"baseline","candidate",expected,"full40",1,100)
        self.assertFalse(mismatched["integrity_gate_pass"])
        self.assertFalse(mismatched["evidence_supports_requested_gate"])


if __name__ == "__main__":
    unittest.main()
