"""Fixed-world admission checks; no agents or simulated games."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import semantic_strategy_fixed_20260928 as F


class FixedWorldContracts(unittest.TestCase):
    def test_complete_daily_schedule(self):
        snapshots = [dict(day=d,current_observation={"town":{"unlocked_shops":[str(d)]}}) for d in range(30)]
        row = {"case":{"seat":1},"diagnostics":[[],snapshots],"shops":["final"]}
        self.assertEqual(F.schedules(row), [[str(d)] for d in range(30)]+[["final"]])
        snapshots.pop()
        with self.assertRaisesRegex(ValueError,"every day"):
            F.schedules(row)

    def test_timed_divergence_is_valid_but_cannot_reuse_natural_outcome(self):
        with tempfile.TemporaryDirectory() as temporary:
            study = Path(temporary)
            directory = study/"fixed_experiments/test"
            case = {"id":"live-00","seed":123,"seat":0}
            source = {"cash_by_seat":[100,200],"action_sha256":["a","b"]}
            F.G.write(study/"native.json",source)
            item = {"case":case,"source":"native.json","source_sha256":F.G.sha(study/"native.json"),"shops":[[]]*31}
            manifest = {"reference_candidate":"ref","cases":[item],"candidate_manifest_sha256":{"ref":"manifesthash"}}
            F.G.write(directory/"manifest.json",manifest)
            row = dict(source,completed=True,eligible=True,case=case,candidate_manifest_sha256="manifesthash",
                forced_shops_sha256=F.G.digest(item["shops"]),
                fixed_world={"experiment_manifest_sha256":F.G.sha(directory/"manifest.json")})
            row["action_sha256"] = ["changed","b"]
            output = directory/"runs/ref/live-00.json"
            F.G.write(output,row)
            self.assertFalse(F.certify_reference(study,directory,manifest)["live-00"]["reproduced"])
            self.assertTrue(F.certify_reference(study,directory,manifest)["live-00"]["reference_valid"])
            row["action_sha256"] = source["action_sha256"]
            F.G.write(output,row)
            self.assertTrue(F.certify_reference(study,directory,manifest)["live-00"]["reproduced"])
            row["forced_shops_sha256"] = "different"
            F.G.write(output,row)
            self.assertFalse(F.certify_reference(study,directory,manifest)["live-00"]["reproduced"])
            self.assertFalse(F.certify_reference(study,directory,manifest)["live-00"]["reference_valid"])

    def test_qualification_world_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as temporary:
            study = Path(temporary)
            F.G.write(study/"protocol.json",{"development":{"live":[{"id":"dev"}]}})
            F.G.write(study/"fixed_experiments/test/manifest.json",{
                "scope":"DEVELOPMENT_ONLY","protocol_sha256":F.G.sha(study/"protocol.json"),
                "harness_files":{},"cases":[{"case":{"id":"qualification"}}]})
            with self.assertRaisesRegex(ValueError,"exactly the eight development"):
                F.verify(study,"test")


if __name__ == "__main__":
    unittest.main()
