#!/usr/bin/env bash
# "AZ-a is back": let the Auto Scaling group use both AZs again.
set -euo pipefail
source "$(dirname "$0")/_outputs.sh"
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$(out AsgName)" \
  --vpc-zone-identifier "$(out AppSubnetA),$(out AppSubnetB)"
echo "ASG uses both AZs again. AZ rebalancing will move one instance back to AZ-a."
