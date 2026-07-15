#!/usr/bin/env bash
# Run ON the fresh Oracle A1.Flex VM (Ubuntu 24.04 aarch64) as the ubuntu
# user. Installs Docker + DataHub quickstart and opens the on-instance
# firewall. VCN Security List rules (ports 9002/8080) must be added in the
# Oracle console separately — see docs/ORACLE_BRINGUP.md step 3.
set -euo pipefail

echo "==> On-instance firewall (Oracle images ship a REJECT-all rule)"
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 9002 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo apt-get install -y iptables-persistent >/dev/null 2>&1 || true
sudo netfilter-persistent save || true

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> DataHub CLI + quickstart (arm64 images)"
sudo apt-get update -q && sudo apt-get install -y python3-pip python3-venv
python3 -m venv "$HOME/dh"
"$HOME/dh/bin/pip" install -q acryl-datahub
# newgrp so the docker group applies without re-login
sg docker -c "$HOME/dh/bin/datahub docker quickstart"

echo
echo "DataHub up: http://\$(curl -s ifconfig.me):9002 (datahub/datahub)"
echo "NEXT (manual, before judges): change the default password, enable"
echo "METADATA_SERVICE_AUTH_ENABLED=true, mint a token — runbook step 5."
