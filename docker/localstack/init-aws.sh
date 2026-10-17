#!/bin/bash
set -euo pipefail

awslocal s3 mb s3://eip-raw-payloads
awslocal s3 mb s3://eip-audit-archive

DLQ_URL=$(awslocal sqs create-queue --queue-name eip-ingest-dlq --query QueueUrl --output text)
DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url "$DLQ_URL" \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

cat > /tmp/ingest-queue.json <<EOF
{
  "VisibilityTimeout": "60",
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"5\"}"
}
EOF

awslocal sqs create-queue --queue-name eip-ingest --attributes file:///tmp/ingest-queue.json

echo "EIP local AWS resources ready"
