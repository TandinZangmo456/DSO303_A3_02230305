#!/usr/bin/env bash
# Deletes everything so the Learner Lab budget stops being used.
set -euo pipefail
source "$(dirname "$0")/_outputs.sh"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

empty_bucket() {   # versioned buckets need every version + delete marker removed
  local b=$1; [ -z "$b" ] || [ "$b" = "None" ] && return 0
  echo "Emptying $b"
  for q in Versions DeleteMarkers; do
    while true; do
      json=$(aws s3api list-object-versions --bucket "$b" --max-items 500 \
             --query "{Objects: $q[].{Key:Key,VersionId:VersionId}}" --output json 2>/dev/null || echo '{"Objects":null}')
      echo "$json" | grep -q '"Key"' || break
      aws s3api delete-objects --bucket "$b" --delete "$json" > /dev/null
    done
  done
  aws s3 rm "s3://$b" --recursive > /dev/null 2>&1 || true
}

empty_bucket "$(out UploadBucketName)"
empty_bucket "$(out FrontendBucketName)"
echo "Deleting stack $STACK (RDS + CloudFront take ~10-15 min)…"
aws cloudformation delete-stack --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --stack-name "$STACK"
empty_bucket "${STACK}-artifacts-${ACCOUNT}"
aws s3 rb "s3://${STACK}-artifacts-${ACCOUNT}" || true
echo "Done. Everything is deleted."
