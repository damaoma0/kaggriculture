# DSM tape explorer

Open `viz/dsm-tapes.html` in a current Edge, Chrome, or Firefox browser. The file
works offline and decompresses one selected replay at a time. The game selector,
result filter, playback controls, tile inspection, opponent view, and day navigator
all use recorded state. Requested actions are displayed separately from outcomes.

The expanded library contains the 108 completed episodes for DSM submission
56444344 in the saved September 22, 2026 inventory. This is a complete copy of
that API response window, not a claim to cover all historical or newer DSM games.
Original replays are cached in `data/dsm_replays/`.

Rebuild from the saved inventory (existing downloads are reused):

```powershell
.venv/Scripts/python.exe scripts/build_dsm_visualizer.py --limit 108
node scripts/check_dsm_visualizer.cjs 108
```

To regenerate the inline tile-change heatmap, pass an absolute destination:

```powershell
node scripts/build_dsm_change_map.cjs C:/path/to/dsm-tile-changes.html
```

The map counts changes between consecutive nonempty crop/animal types, ignoring
empty, locked, weed, and empty-building intervals. Initial placement and replanting
the same type are not changes. Each coordinate's count is averaged over all loaded
games; coordinates never productive in any game are marked missing. The underlying
counts, episode IDs, and transition frequencies are saved to
`results/fresh/dsm_visualizer/tile_change_map.json`.
