"""Candidate route admission: protect live assets before changing a tape."""


def _mgt_switch_risk(farm, day, current, proposed, ignored=()):
    start, stop = day * 24, min(718, (day + 2) * 24 - 1)
    def visits(route):
        return _tc_visits(_tc_simulate(lambda t: _MGT_ROUTES[route][t],
                                       start, stop, [(4, 4)]))
    old, new = visits(current), visits(proposed)
    ignore = set(ignored or ())
    live = {}
    tiles = {}
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if y * len(row) + x in ignore:
                continue
            tiles[(x, y)] = tile
            if not isinstance(tile, dict):
                continue
            item = tile.get('animal') or tile.get('crop')
            if item:
                live[(x, y)] = item
    animals = ('COW', 'SHEEP', 'GOOSE')
    orphan = 0
    lost_crop_service = 0
    for pos, item in live.items():
        old_ops = [c[0] for _, _, c in old.get(pos, ()) if c]
        new_ops = [c[0] for _, _, c in new.get(pos, ()) if c]
        if item in animals:
            if 'FEED' in old_ops and 'FEED' not in new_ops:
                orphan += 1
        elif any(op in old_ops for op in ('WATER', 'FERTILIZE', 'HARVEST')) and not any(
                op in new_ops for op in ('WATER', 'FERTILIZE', 'HARVEST')):
            lost_crop_service += 1
    def wrong_targets(calendar):
        count = 0
        for pos, jobs in calendar.items():
            item = live.get(pos)
            tile = tiles.get(pos)
            for step, _, cmd in jobs:
                if step >= start + 24 or not cmd:
                    continue
                op = cmd[0]
                if op in ('FEED', 'CARE', 'COLLECT_FERTILIZER') and item not in animals:
                    count += 1
                elif op in ('WATER', 'FERTILIZE') and item not in live_crop_types:
                    count += 1
                elif op == 'PLACE' and not (isinstance(tile, dict) and
                        tile.get('kind') in ('PASTURE', 'COOP') and not tile.get('animal')):
                    count += 1
                elif op == 'HARVEST' and item is None:
                    count += 1
                elif op in ('BUILD_PASTURE', 'BUILD_COOP', 'PLANT') and tile is not None:
                    count += 1
        return count
    live_crop_types = set(live.values()) - set(animals)
    old_wrong, new_wrong = wrong_targets(old), wrong_targets(new)
    def long_asset_mismatch(route):
        labels = _MGT_TAPES[route]['lab'][day]
        return sum(1 for (x, y), item in live.items()
                   if item in animals or item in ('STRAWBERRY', 'TOMATO', 'MELON')
                   if labels[y * 10 + x] != (item[:2].lower() if item in animals else item[:2]))
    old_long, new_long = long_asset_mismatch(current), long_asset_mismatch(proposed)
    return {'orphan_animals': orphan, 'lost_crop_service': lost_crop_service,
            'incumbent_wrong': old_wrong, 'candidate_wrong': new_wrong,
            'incumbent_long_mismatch': old_long, 'candidate_long_mismatch': new_long,
            'safe': not orphan and not lost_crop_service and new_wrong <= old_wrong + 2
                    and new_long <= old_long and (day < 15 or new_long == 0)}
