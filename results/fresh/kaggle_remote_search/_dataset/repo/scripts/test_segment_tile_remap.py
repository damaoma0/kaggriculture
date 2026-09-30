from fragments.segment_tile_remap import _ss_remap


def _farm(tiles):
    return {"tiles": tiles}


def test_remaps_same_assets_once_and_clears_signature():
    none = None
    donor = _farm([[none, {"kind": "PLANT", "crop": "WHEAT", "planted_day": 8},
                    {"kind": "COOP", "animal": None}],
                   [none, {"kind": "PLANT", "crop": "WHEAT", "planted_day": 8}, none]])
    live = _farm([[none, none, {"kind": "COOP", "animal": None}],
                  [{"kind": "PLANT", "crop": "WHEAT", "planted_day": 8}, none,
                   {"kind": "PLANT", "crop": "WHEAT", "planted_day": 8}]])
    node = {"start_farm": donor, "start": {"tiles": {"1,0": {"bad": True}}},
            "jobs": [{"tile": [1, 0], "cmd": ["HARVEST"]},
                     {"tile": [1, 1], "cmd": ["WATER"]},
                     {"tile": [2, 0], "cmd": ["BUILD_COOP"]}]}
    got = _ss_remap({"player": 0, "farms": [live]}, node)
    assert got is not None
    assert "start" not in got
    assert got["jobs"][0]["tile"] != got["jobs"][1]["tile"]
    assert got["start_farm"] == live


def test_identity_mismatch_rejects():
    node = {"start_farm": _farm([[{"kind": "PLANT", "crop": "TOMATO", "planted_day": 2}]]),
            "jobs": [{"tile": [0, 0], "cmd": ["HARVEST"]}]}
    live = _farm([[{"kind": "PLANT", "crop": "WHEAT", "planted_day": 2}]])
    assert _ss_remap({"player": 0, "farms": [live]}, node) is None


if __name__ == "__main__":
    test_remaps_same_assets_once_and_clears_signature()
    test_identity_mismatch_rejects()
    print("segment tile remap tests passed")
