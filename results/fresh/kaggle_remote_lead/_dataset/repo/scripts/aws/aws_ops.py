"""One-VM AWS runner for game panels (2026-09-24). Uses ONLY the official AWS CLI (`aws`), which reads credentials
from its own store (`aws login` / `aws configure`); this script never reads, prints or stores key material.

  aws_ops.py whoami                      account + identity the CLI is using (no secrets)
  aws_ops.py quotas                      EC2 on-demand and spot vCPU quotas in the region
  aws_ops.py up [TYPE]                   launch ONE instance (default c7a.8xlarge), tagged Project=kaggriculture
  aws_ops.py status                      running instances, hours, cost so far; jobs on the VM
  aws_ops.py down                        TERMINATE every instance tagged Project=kaggriculture (the stop button)
  aws_ops.py push AGENT [AGENT ...]      copy scripts/, data/, the named agents and research libraries to the VM
  aws_ops.py run "CMD"                   run CMD in ~/repo with the VM's venv python, detached, logged to ~/jobs/
  aws_ops.py jobs                        running jobs and the tail of the latest logs
  aws_ops.py fetch REMOTE_PATH [LOCAL]   copy a file or folder (repo-relative) back into the local repo

Safety built into every instance: shutdown = TERMINATE (nothing left stopped-but-billing), a guard that shuts the
instance down after IDLE_MIN minutes without a job, and a hard stop at UNTIL (the competition deadline).
Region: KGR_AWS_REGION, else the CLI's configured region (eu-west-1 on this account).
"""
import calendar, io, json, os, subprocess, sys, tarfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'results/fresh/aws/state.json'
_AWS_DIR = r'C:\Program Files\Amazon\AWSCLIV2'
if os.name == 'nt' and os.path.isdir(_AWS_DIR) and _AWS_DIR not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _AWS_DIR + os.pathsep + os.environ.get('PATH', '')


def _cli_region():
    try:
        return subprocess.run(['aws', 'configure', 'get', 'region'], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ''


REGION = os.environ.get('KGR_AWS_REGION') or _cli_region() or 'eu-west-1'
TAG = 'kaggriculture'
KEY_NAME = 'kgr-aws'
KEY_PATH = Path.home() / '.ssh' / 'kgr-aws.pem'
SG_NAME = 'kgr-ssh'
IDLE_MIN = 120
UNTIL = '2026-09-30 23:00 UTC'
PRICE = {'c7a.xlarge': 0.2202, 'c7a.8xlarge': 1.7619}  # eu-west-1 Linux on-demand $/h (AWS pricing API, 2026-09-24)
AMI_PARAM = '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'


def aws(*args, check=True):
    p = subprocess.run(['aws', '--region', REGION, '--output', 'json', *args], capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f'aws {" ".join(args[:3])} failed:\n{p.stderr.strip()}')
    return json.loads(p.stdout) if p.stdout.strip() else {}


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def ssh_base(s):
    return ['ssh', '-i', str(KEY_PATH), '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ServerAliveInterval=30',
            f'ubuntu@{s["ip"]}']


def ssh(s, cmd, stdin=None):
    return subprocess.run(ssh_base(s) + [cmd], input=stdin, capture_output=True)


USER_DATA = r'''#!/bin/bash
apt-get update -y && apt-get install -y python3-venv python3-pip
sudo -u ubuntu bash -c 'python3 -m venv /home/ubuntu/venv && /home/ubuntu/venv/bin/pip install -q kaggle-environments==1.32.7 psutil numpy && mkdir -p /home/ubuntu/repo /home/ubuntu/jobs'
cat > /usr/local/bin/kgr-guard.sh <<'EOF'
#!/bin/bash
now=$(date -u +%s)
[ "$now" -ge "$(date -u -d "__UNTIL__" +%s)" ] && shutdown -h now
pgrep -f kgr-job >/dev/null && echo "$now" > /var/tmp/kgr-busy
last=$(cat /var/tmp/kgr-busy 2>/dev/null || echo "$now")
[ $((now - last)) -ge $((__IDLE__ * 60)) ] && shutdown -h now
EOF
chmod +x /usr/local/bin/kgr-guard.sh
date -u +%s > /var/tmp/kgr-busy
echo "*/5 * * * * root /usr/local/bin/kgr-guard.sh" > /etc/cron.d/kgr-guard
touch /home/ubuntu/READY
'''.replace('__UNTIL__', UNTIL).replace('__IDLE__', str(IDLE_MIN))


def cmd_whoami():
    ident = aws('sts', 'get-caller-identity')
    print('account', ident.get('Account'), 'as', ident.get('Arn'), 'region', REGION)


def cmd_quotas():
    for code, name in (('L-1216C47A', 'on-demand standard vCPUs'), ('L-34B43A08', 'spot standard vCPUs')):
        q = aws('service-quotas', 'get-service-quota', '--service-code', 'ec2', '--quota-code', code, check=False)
        print(f'{name:26s} {q.get("Quota", {}).get("Value", "unknown (not readable)")}  [{code}, {REGION}]')


def cmd_up(itype='c7a.xlarge'):     # the account's quota is 5 vCPUs in eu-west-1 (2026-09-24)
    if state().get('instance'):
        raise SystemExit(f'already running {state()["instance"]}; use status / down')
    ami = aws('ssm', 'get-parameter', '--name', AMI_PARAM)['Parameter']['Value']
    if not KEY_PATH.exists():
        KEY_PATH.parent.mkdir(exist_ok=True)
        km = aws('ec2', 'create-key-pair', '--key-name', KEY_NAME, '--key-type', 'ed25519')['KeyMaterial']
        KEY_PATH.write_text(km)
        os.chmod(KEY_PATH, 0o600)
        if os.name == 'nt':                    # Windows OpenSSH refuses keys readable by other accounts
            subprocess.run(['icacls', str(KEY_PATH), '/inheritance:r', '/grant:r', f'{os.environ["USERNAME"]}:R'],
                           capture_output=True)
    my_ip = subprocess.run(['curl', '-s', 'https://checkip.amazonaws.com'], capture_output=True, text=True).stdout.strip()
    sgs = aws('ec2', 'describe-security-groups', '--filters', f'Name=group-name,Values={SG_NAME}')['SecurityGroups']
    sg = sgs[0]['GroupId'] if sgs else aws('ec2', 'create-security-group', '--group-name', SG_NAME,
                                             '--description', 'kaggriculture ssh')['GroupId']
    aws('ec2', 'authorize-security-group-ingress', '--group-id', sg, '--protocol', 'tcp', '--port', '22',
        '--cidr', f'{my_ip}/32', check=False)
    ud = ROOT / 'results/fresh/aws/user_data.sh'
    ud.parent.mkdir(parents=True, exist_ok=True)
    ud.write_text(USER_DATA, newline='\n')
    r = aws('ec2', 'run-instances', '--image-id', ami, '--instance-type', itype, '--key-name', KEY_NAME,
            '--security-group-ids', sg, '--count', '1', '--user-data', f'file://{ud}',
            '--instance-initiated-shutdown-behavior', 'terminate',
            '--block-device-mappings', '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true}}]',
            '--tag-specifications', f'ResourceType=instance,Tags=[{{Key=Project,Value={TAG}}},{{Key=Name,Value=kgr-runner}}]')
    iid = r['Instances'][0]['InstanceId']
    subprocess.run(['aws', '--region', REGION, 'ec2', 'wait', 'instance-running', '--instance-ids', iid])
    ip = aws('ec2', 'describe-instances', '--instance-ids', iid)['Reservations'][0]['Instances'][0].get('PublicIpAddress')
    save(dict(instance=iid, ip=ip, type=itype, region=REGION, launched=time.time(), price=PRICE.get(itype)))
    print(f'launched {iid} {itype} at {ip} (${PRICE.get(itype)}/h); setup takes ~3-5 min (check: status)')


def cmd_status():
    res = aws('ec2', 'describe-instances', '--filters', f'Name=tag:Project,Values={TAG}',
              'Name=instance-state-name,Values=pending,running,stopping,stopped')['Reservations']
    insts = [i for r in res for i in r['Instances']]
    if not insts:
        print('NOTHING RUNNING (no instance tagged Project=kaggriculture). Cost now: $0/h.')
    for i in insts:
        launched = calendar.timegm(time.strptime(i['LaunchTime'][:19], '%Y-%m-%dT%H:%M:%S'))   # AWS gives UTC
        hours = (time.time() - launched) / 3600
        price = PRICE.get(i['InstanceType'], 0)
        print(f'{i["InstanceId"]} {i["InstanceType"]} {i["State"]["Name"]} ip {i.get("PublicIpAddress")} '
              f'up {hours:.1f} h, ~${hours * price:.2f} so far at ${price}/h (+ disk ~$0.003/h)')
    s = state()
    if insts and s.get('ip'):
        out = ssh(s, 'test -f READY && echo setup-done || echo setting-up; pgrep -fa kgr-job | grep -v pgrep | wc -l; ls -t jobs | head -3')
        print('VM:', out.stdout.decode(errors='replace').replace(chr(10), ' | '))


def cmd_down():
    res = aws('ec2', 'describe-instances', '--filters', f'Name=tag:Project,Values={TAG}',
              'Name=instance-state-name,Values=pending,running,stopping,stopped')['Reservations']
    ids = [i['InstanceId'] for r in res for i in r['Instances']]
    if ids:
        aws('ec2', 'terminate-instances', '--instance-ids', *ids)
        print('terminating', ids)
    else:
        print('nothing to terminate')
    save({})


PUSH_PATHS = ['scripts', 'data/ladder_panel', 'data/mg_tapes', 'data/leader_tapes', 'data/leader_semantics',
              'data/dsm_tapes', 'data/router_refresh_20260916', 'data/router_refresh_20260922', 'data/kaggriculture.py',
              'results/fresh/value_tape_followup_20260923/rival_library',
              'results/fresh/value_tape_followup_20260923/modern_rival_library',
              'results/fresh/v56_random_20260922/manifest.json',
              'results/fresh/newphase_20260923/y3/v56_paired/manifest.json',
              'results/fresh/newphase_20260923/y3/v56_paired_b/manifest.json',
              'submissions/2026-09-24-mgt_v9lite/pkg']


def cmd_push(*agents):
    buf = io.BytesIO()
    skip = ('__pycache__', '_raw', '.log')
    with tarfile.open(fileobj=buf, mode='w:gz') as t:
        for p in PUSH_PATHS + [f'agents/{a}.py' for a in agents]:
            src = ROOT / p
            if src.exists():
                t.add(src, arcname=p, filter=lambda ti: None if any(x in ti.name for x in skip) else ti)
    r = ssh(state(), 'mkdir -p repo && tar xzf - -C repo && echo ok', stdin=buf.getvalue())
    print(f'pushed {len(buf.getvalue()) / 1e6:.1f} MB:', r.stdout.decode().strip(), r.stderr.decode()[-300:])


def cmd_run(command):
    tag = time.strftime('%m%d-%H%M%S')
    remote = (f"nohup bash -c ': kgr-job; cd ~/repo && PATH=~/venv/bin:$PATH LP_MAX=64 {command}' "
              f"> ~/jobs/{tag}.log 2>&1 &")
    ssh(state(), remote)
    print('started job', tag, '->', f'~/jobs/{tag}.log')


def cmd_jobs():
    out = ssh(state(), "pgrep -fa kgr-job | grep -v pgrep; for f in $(ls -t jobs/*.log | head -3); do echo == $f; tail -3 $f; done")
    print(out.stdout.decode(errors='replace'))


def cmd_fetch(remote, local=None):
    out = ssh(state(), f'cd ~/repo && tar czf - {remote}')
    if out.returncode:
        raise SystemExit(out.stderr.decode()[-500:])
    dest = ROOT if local is None else Path(local)
    with tarfile.open(fileobj=io.BytesIO(out.stdout), mode='r:gz') as t:
        t.extractall(dest)
    print(f'fetched {remote} ({len(out.stdout) / 1e6:.1f} MB) into {dest}')


if __name__ == '__main__':
    c, a = sys.argv[1], sys.argv[2:]
    {'whoami': cmd_whoami, 'quotas': cmd_quotas, 'up': cmd_up, 'status': cmd_status, 'down': cmd_down,
     'push': cmd_push, 'run': cmd_run, 'jobs': cmd_jobs, 'fetch': cmd_fetch}[c](*a)
