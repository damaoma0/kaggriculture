# Independent release qualification audit

- Games: 384 / 384; records and ledgers valid: **True**.
- Cash reconciliations: 768 seats; spec cross-checks: 128.
- All-arm opening prefix equal: 128/128; Y3 and v9lite full action hashes equal: 103/128.

## Outcomes recomputed from raw records

| Arm | Mean own cash | Mean opponent cash | Mean margin | Wins / ties / losses | Max action s | Minimum bank s |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 105550.00 | 103713.84 | 1836.16 | 52 / 52 / 24 | 3.658987 | 56.737 |
| y3 | 105670.83 | 103525.33 | 2145.50 | 71 / 32 / 25 | 3.648388 | 56.741 |
| v9lite | 106088.43 | 103338.44 | 2749.99 | 80 / 28 / 20 | 13.791178 | 31.297 |

## Paired comparisons

| Comparison | Mean paired margin delta | Median | Positive pairs | Mean own-cash delta | Positive cash pairs |
|---|---:|---:|---:|---:|---:|
| y3 vs baseline | 309.34 | 0.00 | 36/128 | 120.83 | 29/128 |
| v9lite vs baseline | 913.83 | 0.00 | 46/128 | 538.43 | 38/128 |
| v9lite vs y3 | 604.49 | 0.00 | 19/128 | 417.60 | 16/128 |

## Audit errors

None.

No games were launched during this audit. See final_audit.json for per-spec hashes, values, and paired deltas.
