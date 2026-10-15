#!/usr/bin/env bash
# Minimal firewall for the CROMO vLLM droplet (run once as root).
#   ./firewall.sh                      # SSH + vLLM ports open to the internet (API-key protected)
#   ALLOW_FROM=203.0.113.7 ./firewall.sh   # restrict vLLM ports to one IP (e.g. where CROMO runs)
#
# Evolus calls the reasoner (:8000) from its cloud, so :8000 must stay reachable for the Evolus agent.
# Vision (:8001) and embeddings (:8002) are only needed by the CROMO backend.
# Note: these servers use host networking, so ufw rules apply to them.
set -euo pipefail
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 8000/tcp
if [ -n "${ALLOW_FROM:-}" ]; then
  ufw allow from "$ALLOW_FROM" to any port 8001 proto tcp
  ufw allow from "$ALLOW_FROM" to any port 8002 proto tcp
else
  ufw allow 8001/tcp
  ufw allow 8002/tcp
fi
ufw --force enable
ufw status verbose
