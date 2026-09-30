"""Small contract checks; no full-game simulations or qualification reads."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/semantic_strategy_gate_20260928.py"
spec = importlib.util.spec_from_file_location("semantic_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def case(episode):
    return {"id": "recorded-" + episode, "episode": episode, "seed": int(episode), "seat": 0}


def protocol(tmp_path):
    value = {"development": {"live": [], "recorded": [case("1")]},
             "qualification": {"live": [], "recorded": [case("2")]},
             "recorded_reserve": [case("3"), case("4"), case("5")]}
    gate.write(tmp_path / "protocol.json", value)
    return value


def test_replaces_only_failed_source_control_in_reserve_order(tmp_path):
    value = protocol(tmp_path)
    called = []

    def fake_run(jobs, workers):
        for job in jobs:
            episode = job["case"]["episode"]
            called.append(episode)
            gate.write(job["output"], {"eligible": episode == "4", "case": job["case"],
                "protocol_sha256": gate.sha(tmp_path / "protocol.json")})

    with patch.object(gate, "pool_run", fake_run):
        chosen = gate.controls_and_selection(tmp_path, value, "qualification", 2, ["3"])
    assert [x["episode"] for x in chosen] == ["4"]
    assert called == ["2", "4"]
    saved = gate.read(tmp_path / "selections/qualification.json")
    assert [x["accepted"] for x in saved["attempts"]] == [False, True]
    assert saved["selection_blind_to_candidate"] is True


def test_selected_panel_cannot_gain_training_overlap_on_resume(tmp_path):
    value = protocol(tmp_path)
    gate.write(tmp_path / "selections/qualification.json", {
        "protocol_sha256": gate.sha(tmp_path / "protocol.json"), "cases": [case("4")]})
    with unittest.TestCase().assertRaisesRegex(ValueError, "overlaps candidate training"):
        gate.controls_and_selection(tmp_path, value, "qualification", 1, ["4"])


def test_candidate_failure_retains_full_denominator(tmp_path):
    value = protocol(tmp_path)
    value["qualification"]["recorded"].append(case("3"))
    gate.write(tmp_path / "protocol.json", value)
    folder = tmp_path / "runs/version/qualification/recorded"
    gate.write(folder / "recorded-2.json", {"case": case("2"), "completed": True,
        "eligible": True, "margin": 100})
    gate.write(folder / "recorded-3.json", {"case": case("3"), "completed": True,
        "eligible": False, "margin": 500})
    gate.write(folder / "recorded-2.actions.json", [[], []])
    result = gate.report(tmp_path, "version", "qualification", "recorded")
    assert result["expected"] == 2 and result["valid"] == 1
    assert result["eligible_wins"] == 1 and not result["gate_complete"]
    assert result["invalid_cases"] == ["recorded-3"]


def test_source_snapshot_hash_rejects_edits(tmp_path):
    source = tmp_path / "agent.py"
    source.write_text("original", encoding="utf-8")
    hashes = {"agent.py": gate.sha(source)}
    gate.verify_files(tmp_path, hashes)
    source.write_text("changed", encoding="utf-8")
    with unittest.TestCase().assertRaisesRegex(ValueError, "Frozen source/input changed"):
        gate.verify_files(tmp_path, hashes)


def test_release_locks_one_candidate_and_protocol(tmp_path):
    protocol(tmp_path)
    for candidate in ("first", "second"):
        gate.write(tmp_path / "candidates" / candidate / "manifest.json", {
            "candidate_id": candidate, "protocol_sha256": gate.sha(tmp_path / "protocol.json")})
    first = gate.release(tmp_path, "first")
    assert gate.release(tmp_path, "first") == first
    with unittest.TestCase().assertRaisesRegex(ValueError, "different frozen candidate"):
        gate.release(tmp_path, "second")
    gate.write(tmp_path / "protocol.json", {"changed": True})
    with unittest.TestCase().assertRaisesRegex(ValueError, "Protocol changed"):
        gate.release(tmp_path, "first")


def test_release_binds_prospective_scoring_addendum(tmp_path):
    protocol(tmp_path)
    gate.write(tmp_path / "candidates/first/manifest.json", {
        "candidate_id": "first", "protocol_sha256": gate.sha(tmp_path / "protocol.json")})
    addendum=tmp_path / "shipping_score_addendum.json"
    gate.write(addendum,{"original_protocol_sha256":gate.sha(tmp_path / "protocol.json")})
    first=gate.release(tmp_path,"first")
    assert first['shipping_score_addendum_sha256']==gate.sha(addendum)
    assert gate.release(tmp_path,"first")==first
    gate.write(addendum,{"original_protocol_sha256":gate.sha(tmp_path / "protocol.json"),"changed":True})
    with unittest.TestCase().assertRaisesRegex(ValueError,"addendum changed"):
        gate.release(tmp_path,"first")


class GateContracts(unittest.TestCase):
    def test_contracts(self):
        for name, check in list(globals().items()):
            if name.startswith("test_") and callable(check):
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    check(Path(directory))


if __name__ == "__main__":
    unittest.main()
