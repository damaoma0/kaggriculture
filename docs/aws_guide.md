# AWS for Kaggriculture panels: operating guide (2026-09-24)

## ▶ The one thing to do first (5-10 min, only you can)
Give the AWS CLI on this laptop your sign-in. Keys never go into chat or a file I touch.

1. Install the AWS CLI (PowerShell, your own terminal):
   `winget install -e --id Amazon.AWSCLI`
   (or run the installer https://awscli.amazonaws.com/AWSCLIV2.msi), then open a NEW terminal.
2. Sign in, one of:
   - `aws login` — signs the CLI in with your console account through the browser (recent CLI versions).
   - If that command does not exist: Console → IAM → Users → Create user `kgr-runner` → attach
     `AmazonEC2FullAccess`, `AmazonSSMReadOnlyAccess`, `ServiceQuotasReadOnlyAccess` → user → Security credentials →
     Create access key (CLI) → run `aws configure` and type the two keys INTO THAT PROMPT.
3. `aws configure set region us-east-1`
4. Check: `aws sts get-caller-identity` shows your account id and user name (no secrets). Tell me "AWS ready".
5. Recommended safety net (2 min): Console → Billing and Cost Management → Budgets → Create budget → template
   "Monthly cost budget" → $50 → your email. AWS emails you if spend passes it.

After that I run everything with `scripts/aws/aws_ops.py`, which only calls the official CLI.
If the vCPU quota is too low I will tell you the one click: Service Quotas → Amazon EC2 → "Running On-Demand
Standard (A, C, D, H, I, M, R, T, Z) instances" → Request increase → 64.

## What runs and what it costs
- Nothing is running yet.
- Plan: ONE instance `kgr-runner`, c7a.8xlarge (32 cores, 64 GB), on-demand $1.64/h, us-east-1.
  Only while jobs run. 30 GB disk, deleted with the instance.
- Expected use: 10-20 hours until 30 Sep = **~$15-35 of the $200 credit**.
- See it: `.venv/Scripts/python.exe scripts/aws/aws_ops.py status` prints each instance, hours up and $ so far.
  Console: Billing → Bills (credits appear as a negative line).

## ■ How to stop everything
- One command: `.venv/Scripts/python.exe scripts/aws/aws_ops.py down`
  (terminates every instance tagged Project=kaggriculture; nothing is left billing).
- Console / phone app: EC2 → Instances → tick `kgr-runner` → Instance state → **Terminate instance**.
- It also stops ITSELF: after 2 hours without a job, and at 30 Sep 23:00 UTC at the latest. Its shutdown is set to
  TERMINATE, so a stopped-but-billing instance cannot happen.

## How to check it is healthy
- `aws_ops.py status` → instance up? setup done? how many jobs running? latest job logs.
- `aws_ops.py jobs` → the running jobs and the last lines of their logs.
- Results come back into this repo (`results/fresh/...`) and are committed; commit messages say "AWS".
- Nothing from AWS is trusted until a control set reproduces local results to the dollar (reported separately).

## What changes for you
- Your laptop is free again for your other agent system: game batches move to the VM.
- Panels: 185 games take minutes instead of 20-40 min on Kaggle; a 5-cell x 60-game ablation run goes from ~2.5 h
  locally to minutes. (Exact games/hour will be MEASURED on the VM and reported; these are estimates.)
