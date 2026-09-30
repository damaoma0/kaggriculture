# Diagnostic implementation failure

The first guarded trial counted every hire as failed because the engine's
`_do_hire` returns `None` for both success and failure. Therefore guarded results
in this directory are invalid for comparing feasibility selection. The static
contract arm is unaffected. Exact source copies are preserved under `sources/`.
The corrected implementation compares `hires_today` before and after the call;
its new experiment namespace is `v6r2`. No original trial result is overwritten.
