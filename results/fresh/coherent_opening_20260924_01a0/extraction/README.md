# DSM opening extraction

`opening_jobs.json` records successful state-transition jobs through the end of day 8 (step 216) and daily end-of-day state for both seats. Job steps refer to the action applied between observations `steps[t]` and `steps[t+1]`. Purchase jobs are emitted from successful engine commit transactions; hires, land, planting, removal, and animal placement are emitted from observed state transitions. Daily inventory fields are private to each seat. `metadata.json` records source replay hashes and engine hash.

Limitations: this is a three-replay descriptive sample. Exact seed/product purchase line items follow the engine commit hook; hires expose only headcount delta because the engine action is atomic. Daily snapshots are end-of-day, after 24 hourly transitions.

```json
[
  {
    "episode_id": 112802103,
    "seat": 1,
    "jobs": 314,
    "milestones": [
      {
        "day": 3,
        "cash": 5.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 4,
          "WHEAT": 4,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "WHEAT:0": 3,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "WHEAT:1": 1,
          "SHEEP:0": 3
        }
      },
      {
        "day": 6,
        "cash": 845.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 10,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "SHEEP:0": 3
        }
      },
      {
        "day": 9,
        "cash": 924.0,
        "hands": 0,
        "quadrants": 2,
        "counts": {
          "STRAWBERRY": 16,
          "MELON": 10,
          "SHEEP": 10,
          "WHEAT": 7,
          "COW": 7
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "STRAWBERRY:6": 5,
          "STRAWBERRY:7": 1,
          "MELON:0": 6,
          "SHEEP:8": 3,
          "WHEAT:6": 1,
          "WHEAT:8": 4,
          "COW:0": 2,
          "COW:6": 4,
          "SHEEP:0": 3,
          "SHEEP:6": 4,
          "COW:7": 1,
          "WHEAT:7": 2
        }
      }
    ]
  },
  {
    "episode_id": 112794038,
    "seat": 1,
    "jobs": 345,
    "milestones": [
      {
        "day": 3,
        "cash": 9.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 4,
          "WHEAT": 4,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "WHEAT:0": 3,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "WHEAT:1": 1,
          "SHEEP:0": 3
        }
      },
      {
        "day": 6,
        "cash": 903.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 10,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "SHEEP:0": 3
        }
      },
      {
        "day": 9,
        "cash": 2440.0,
        "hands": 0,
        "quadrants": 2,
        "counts": {
          "STRAWBERRY": 16,
          "MELON": 10,
          "WHEAT": 9,
          "COW": 12,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "STRAWBERRY:6": 5,
          "STRAWBERRY:7": 1,
          "WHEAT:8": 7,
          "MELON:0": 6,
          "COW:0": 2,
          "COW:6": 8,
          "COW:7": 1,
          "COW:8": 1,
          "WHEAT:7": 2,
          "SHEEP:0": 3
        }
      }
    ]
  },
  {
    "episode_id": 112785833,
    "seat": 0,
    "jobs": 335,
    "milestones": [
      {
        "day": 3,
        "cash": 5.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 4,
          "WHEAT": 4,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "WHEAT:0": 3,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "WHEAT:1": 1,
          "SHEEP:0": 3
        }
      },
      {
        "day": 6,
        "cash": 904.0,
        "hands": 0,
        "quadrants": 1,
        "counts": {
          "STRAWBERRY": 10,
          "MELON": 10,
          "COW": 2,
          "SHEEP": 3
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "MELON:0": 6,
          "COW:0": 2,
          "SHEEP:0": 3
        }
      },
      {
        "day": 9,
        "cash": 2181.0,
        "hands": 0,
        "quadrants": 2,
        "counts": {
          "STRAWBERRY": 10,
          "MELON": 10,
          "WHEAT": 14,
          "COW": 10,
          "SHEEP": 3,
          "GOOSE": 2
        },
        "cohorts": {
          "STRAWBERRY:2": 4,
          "STRAWBERRY:3": 6,
          "MELON:1": 4,
          "WHEAT:7": 2,
          "WHEAT:6": 6,
          "WHEAT:8": 6,
          "MELON:0": 6,
          "COW:0": 2,
          "COW:6": 6,
          "COW:7": 2,
          "SHEEP:0": 3,
          "GOOSE:6": 2
        }
      }
    ]
  }
]
```
