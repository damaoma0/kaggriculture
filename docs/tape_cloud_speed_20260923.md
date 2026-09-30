# Tape search timing on Kaggle

## Run definition

Private notebook: [Tape Search V7 V8 CPU Benchmark 20260923](https://www.kaggle.com/code/yiyangxudmm/tape-search-v7-v8-cpu-benchmark-20260923).

The experiment uses the frozen sources from the previous V8 scout panel,
so concurrent development in this workspace cannot alter the cloud run.
The saved notebook loads the hash-checked bundle from a private Kaggle dataset.
The measured benchmark itself needs no API credentials, GPU, or network access.

Local experiment directory: `results/fresh/tape_speed_cloud_20260923_01a0/`.
The corrected bundle contains 149 files and has SHA256
`956039facf05de2ba10f36be6eb2f9b52f5c91890ce1c5bf334db2e722888961`.

## Timing protocol

- Six prespecified checkpoints, two each from D12, D15, and D18; four accepted
  commitments and two unchanged controls in the reference decisions.
- V7 and V8 run serially, in separate fresh processes for every checkpoint.
  Their order alternates between checkpoints.
- Each process performs one cold call and two warm calls. No forecast cache
  is shared between selectors. Pure tape and donor caches remain warm within
  a worker, as they do in a long-lived research agent.
- The timer surrounds the complete `choose` call, including preparation,
  retrieval, simulation, admission and the decision digest. First-use runtime
  construction is included in the cold call. Import time is recorded separately.
- The exact local 1.32.7 framework, schema, and Kaggriculture engine files are
  bundled. Unused environments and renderers are omitted, so import measurements
  are specific to this research harness, not a full Kaggle package startup.
- Each V8 worker subsequently probes a 0.8-second warm deadline. This is
  cooperative cancellation; the probe measures its actual elapsed time and
  whether any fully checked candidate was admitted.
- Hardware, Python, installed dependency versions, cgroup quotas, affinity,
  CPU time, wall time, and peak worker RSS are recorded. Notebook performance
  does not establish the hardware or timing of a competition submission.

Every input/source hash is verified before each worker. Forecast fingerprints,
selection equality, reference checkpoint equality, and input immutability are
checked. Raw failures and timing outliers remain in the results.

## Local packaging validation

All source/input hashes pass. All six public observations successfully construct
the simulator; the rival library has the expected 115 training examples.
The installed and checked-in engine bytes agree:
`bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

The production `agents/mgt_m1.py` hash remains
`1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.

## Remote execution

The first interactive worker startup returned a Kaggle infrastructure error;
refreshing recovered a running session. The first execution then exposed an
archive bug: nested rival-library manifests had been excluded along with the
root manifest. This failed before producing a timing sample. The corrected
builder includes both files and reopens the completed ZIP to hash-check every
archived member. The corrected notebook was uploaded and started.

All measurements completed and the notebook was saved privately as Version 1.
The original self-contained notebook exceeded Kaggle's 1MB saved-source limit;
the saved version instead loads private dataset Version 2's binary archive.
Its 149 input hashes were checked again. The notebook retains the measured
stdout; generated output files were not included in the quick save because
the account's batch CPU sessions were already occupied. The displayed quick-save
runtime is not the 421.86-second measured panel runtime.

All 42 displayed timing samples were exported locally to
`results/fresh/tape_speed_cloud_20260923_01a0/timing_samples_browser.json`.
`audit_export.py` verifies sample counts, uniqueness, selections and exact
agreement with the displayed aggregate timings. `validate_archive.py` also
checks a newly extracted copy of the completed archive, not just its staging
directory. Both checks passed. Subsequent optimization continues locally at
the user's request.

Observed hardware: Intel Xeon 2.20GHz, four CPUs, cgroup quota four CPU cores,
30GiB memory limit, Python 3.12.13. The notebook image's installed framework is
1.29.3; the benchmark explicitly loads its bundled, hash-checked 1.32.7 files.

## Time budget correction

The previous reports incorrectly said 12 seconds of total overage. The bundled
engine's specification overrides the generic framework default with **60 seconds**.
An actual `make('kaggriculture')` check gives `actTimeout=1`,
`remainingOverageTime=60`, and `runTimeout=1200`.
The [current official engine specification](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/kaggriculture.json)
also sets 1 second per action and 60 seconds of initial overage.

Consequently, exceeding one second on a small number of reveal turns does not
by itself establish a timeout. A full game must account for cumulative excess
time, cold initialization, native-agent calls, and the actual submission runner.

## Measured results

The serial panel completed in **421.86 seconds** on Kaggle: 36 full decisions
and six additional deadline probes. All 36 decisions selected the expected
route. All 124 common case/route/scenario forecasts agreed between V7 and V8,
all repeats were deterministic, and no compared historical forecast differed.

| Full `choose` time | V7 | V8 |
|---|---:|---:|
| Warm mean, 12 calls each | 9.275s | 6.832s |
| Warm median | 9.060s | 7.334s |
| Warm minimum–maximum | 2.587–16.372s | 2.599–10.301s |
| Cold mean, six calls each | 14.716s | 11.919s |
| Cold maximum | 19.692s | 14.577s |
| Warm mean process CPU time | 9.183s | 6.813s |

V8 reduces the mean warm wall time by **26.34%**, or **1.36× throughput**.
Mean cold wall time falls 19.01%. These are small, fixed diagnostic samples,
not a latency distribution across random games. Neither minimum nor average
runtime is a worst-case bound.

| Checkpoint | V7 warm median | V8 warm median | Wall time reduction |
|---|---:|---:|---:|
| Strawberry recovery, historical 111262874, D12 | 8.719s | 7.916s | 9.2% |
| Wool recovery, historical 111269605, D15 | 10.211s | 7.804s | 23.6% |
| Unchanged control, historical 111287532, D12 | 15.651s | 10.003s | 36.1% |
| Generalization 0 vs V56, D18 | 9.592s | 5.716s | 40.4% |
| Generalization 5 vs pasture, D15 | 8.867s | 6.906s | 22.1% |
| Unchanged generalization 4 vs sixday, D18 | 2.610s | 2.649s | -1.5% |

The last control has exactly the same simulated work under both policies.
Its approximately 39ms difference should not be sold as an improvement.
The container reports zero cgroup throttling throughout this run; wall and
process CPU time are close. This separates the measurement from local competing
agent workloads, but does not prove that every cloud worker has equal speed.

## Deadline probes

With a requested 0.8s deadline, the six warm V8 calls took
0.879, 0.894, 0.901, 0.804, 0.892 and 0.804 seconds. Every call returned native
routing. Five stopped before starting a rollout; the last started one but
completed none. A tight deadline currently removes the recovery gains.
Cancellation remains cooperative and overshot the requested instant by up to
101ms in these probes. The interrupted-rollout turn counter excludes partial
work, so a reported zero is not a claim that no CPU work occurred.

## Profiling and next implementation target

A separate profile ran after the latency panel, on the strawberry checkpoint:

- Runtime construction: 3.424s, paid once for that private runtime.
- Per-decision simulator preparation: 0.083s.
- Candidate retrieval: 0.023s.
- First scenario, including cold rival-library/profile setup: 1.916s.
- Eight scenarios with warm caches: 0.909s (preceding batch: 1.026s).
- One full-season native rollout, without profiling: 0.321s.

The profiled alternative rollout took 1.001s under profiler instrumentation,
with 1.55 million calls; this is **not** a normal latency sample. Native agent
execution accounts for about 64% cumulative time, engine interpretation 32%,
and board Hamming comparisons about 12%. Cumulative categories overlap and
must not be summed. The rollout's forecast still matches the saved reference.

The immediate exact optimization is to reuse work across the eight scenario
constructions: current rival-cohort output profiles and visible-board donor
distances repeat across worlds. Then investigate cached/packed board matching
inside rollouts. Preserve selection and full forecast equality while measuring
each change on this frozen cloud input. The 60-second bank also makes an
explicit reveal-time spending policy worth validating before replacing exact
rollouts with a learned continuation value.

Three representative V8 warm search calls would cost roughly 20.5s in total,
plus cold setup and normal agent execution. This arithmetic suggests that
three reveal-time searches might fit the 60s bank; it is not a full-game timing
result and is not grounds to submit or promote the research selector.
