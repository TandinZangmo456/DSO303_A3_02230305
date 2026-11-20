#!/usr/bin/env bash
# Simulates losing Availability Zone A:
#   1. API tier: remove AZ-a from the Auto Scaling group -> its instances are terminated
#      and replaced in AZ-b. The ALB stops sending traffic to AZ-a.
#   2. Data tier: force an RDS Multi-AZ failover -> the standby in the other AZ is promoted.
# DynamoDB and S3 are regional (3 AZs) so they need nothing.
set -euo pipefail
source "$(dirname "$0")/_outputs.sh"
ASG=$(out AsgName); SUBNET_B=$(out AppSubnetB); AZ_A=$(out AzA); DB=$(out DbInstanceId)

echo "== Before =="
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG" \
  --query "AutoScalingGroups[0].Instances[].[InstanceId,AvailabilityZone,HealthStatus]" --output table
aws rds describe-db-instances --db-instance-identifier "$DB" \
  --query "DBInstances[0].{Primary:AvailabilityZone,Standby:SecondaryAvailabilityZone}" --output table

echo "== Failing $AZ_A: ASG now only allowed to use AZ-b =="
aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$ASG" --vpc-zone-identifier "$SUBNET_B"

echo "== Forcing RDS failover to the standby =="
aws rds reboot-db-instance --db-instance-identifier "$DB" --force-failover > /dev/null
date +"failover started at %H:%M:%S"
aws rds wait db-instance-available --db-instance-identifier "$DB"
date +"database available again at %H:%M:%S"

echo "== After (give the ASG ~3-5 min to finish replacing instances) =="
aws rds describe-db-instances --db-instance-identifier "$DB" \
  --query "DBInstances[0].{Primary:AvailabilityZone,Standby:SecondaryAvailabilityZone}" --output table
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG" \
  --query "AutoScalingGroups[0].Instances[].[InstanceId,AvailabilityZone,LifecycleState,HealthStatus]" --output table
echo "Run ./scripts/restore-az.sh afterwards to give AZ-a back to the ASG."
