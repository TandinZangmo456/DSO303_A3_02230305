#!/usr/bin/env bash
# Hit the API once a second and print which AZ answered. Keep this running in a
# second terminal during the AZ-failure demo and screenshot it.
source "$(dirname "$0")/_outputs.sh"
URL=$(out AppUrl)
echo "Watching $URL/api/health  (Ctrl+C to stop)"
while true; do
  printf '%s  ' "$(date +%H:%M:%S)"
  curl -s -o /tmp/h.json -w '%{http_code}  ' --max-time 3 "$URL/api/health"
  cat /tmp/h.json 2>/dev/null | tr -d '\n'; echo
  sleep 1
done
