#!/bin/bash
apt-get update -y && apt-get install -y python3-venv python3-pip
sudo -u ubuntu bash -c 'python3 -m venv /home/ubuntu/venv && /home/ubuntu/venv/bin/pip install -q kaggle-environments==1.32.7 psutil numpy && mkdir -p /home/ubuntu/repo /home/ubuntu/jobs'
cat > /usr/local/bin/kgr-guard.sh <<'EOF'
#!/bin/bash
now=$(date -u +%s)
[ "$now" -ge "$(date -u -d "2026-09-30 23:00 UTC" +%s)" ] && shutdown -h now
pgrep -f kgr-job >/dev/null && echo "$now" > /var/tmp/kgr-busy
last=$(cat /var/tmp/kgr-busy 2>/dev/null || echo "$now")
[ $((now - last)) -ge $((120 * 60)) ] && shutdown -h now
EOF
chmod +x /usr/local/bin/kgr-guard.sh
date -u +%s > /var/tmp/kgr-busy
echo "*/5 * * * * root /usr/local/bin/kgr-guard.sh" > /etc/cron.d/kgr-guard
touch /home/ubuntu/READY
