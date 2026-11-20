# Cost and service report (Assignment 3)

All prices are **AWS Pricing Calculator, ap-southeast-1 (Singapore), estimate date 20 Nov 2026**, USD.
Calculator links are in the main README and `evidence/calculator/links.txt`. The screenshots are in `evidence/calculator/`.

**Assumptions:** 8,000 students and 400 staff. A year has 10 normal months and 2 exam months. Exam days run about 10 hours, 12 days a month. Answers autosave every 30 s. Uploads are up to 40 MB each.

## 1. Monthly cost per service

| Service | Normal month | Exam month | What drives it |
|---|---:|---:|---|
| CloudFront | 71.03 | 94.84 | 565 → 675 GB out to users, 22.3M → 36.3M HTTPS requests |
| VPC (interface endpoints + public IPv4) | 64.34 | 64.54 | 3 endpoints × 2 AZ × 730 h, 2 public IPv4 on the ALB |
| RDS MySQL db.t4g.small Multi-AZ (1-yr RI) | 64.14 | 64.14 | flat, reserved |
| ElastiCache Valkey 2 × cache.t4g.micro | 28.03 | 28.03 | flat, 24/7 |
| EC2 2 × t4g.small (Savings Plan) + EBS | 26.18 | 26.18 | base fleet |
| EC2 +2 × t4g.small On-Demand (scheduled) | – | 10.21 | 12 days × 10 h |
| CloudWatch | 11.03 | 13.84 | 6 → 10 GB logs, 20 metrics, 8 alarms, 1 dashboard |
| WAF | 20.38 | 28.78 | per-request charge |
| ALB | 19.57 | 20.74 | LCUs: 0.15 → 0.3 GB/h |
| DynamoDB on-demand (answers) | 4.00 | 23.09 | 0.96M → 12.5M writes (autosave) |
| S3 assignment files (Std 70 GB / IA 330 GB / Deep Archive 400 GB) | 7.68 | 7.68 | year-1 steady state |
| AWS Backup (RDS + DynamoDB) | 5.42 | 5.42 | monthly snapshots, RDS 20 GB at 1%/day change + DynamoDB 5 GB |
| KMS | 2.90 | 3.50 | 2 keys + requests |
| SES | 1.60 | 6.40 | 16k → 64k result emails |
| Route 53 | 1.90 | 1.90 | 1 zone, health check |
| SQS | 0.60 | 0.64 | |
| Secrets Manager | 0.43 | 0.43 | |
| SNS | 0.30 | 0.30 | |
| Cognito (Lite, 8,400 MAU) | 0.01 | 0.01 | under the free 10k MAU |
| Lambda | 0.00 | 0.00 | inside the free tier (~$0.05 without it) |
| **Total / month** | **329.54** | **400.68** | |

Both calculator estimates contain all 19 services above. ElastiCache was added after the load test.

**Annual total:** 10 × 329.54 + 2 × 400.68 = **$4,096.76**. That is an average of **$341.40/month**.

**Cost per student:** $4,096.76 / 8,000 = **$0.51 per student per year**, or about 4 cents a month.

## 2. Hidden costs

These don't appear as a server line on the diagram but still show up on the bill:

| Hidden cost | Where it sits | Amount | What I did |
|---|---|---:|---|
| Data transfer out | Inside CloudFront | most of $71–95 | Biggest bill driver. All traffic goes through CloudFront, because origin → CloudFront transfer is free, and the frontend is cached |
| NAT data processing + hourly | A2 VPC line | $102.51 → 0 | Removed NAT entirely (C2) |
| Interface endpoint hours | VPC line | 6 ENIs × 730 h ≈ $56.94 | This is the price of removing NAT. It's still $38/month cheaper |
| Public IPv4 addresses | VPC line | 2 × $3.65 = $7.30 | Only the ALB has public IPs. Instances have none |
| CloudWatch Logs ingest + storage | CloudWatch line | part of $11–14, and growing | 30-day retention so storage doesn't pile up (C9) |
| KMS requests | KMS line | $2.90–3.50 | S3 Bucket Keys cut the KMS calls per object |
| Backups | AWS Backup line | $5.42 now, grows each year | The calculator caps retention at 12 months. With 5-year retention the snapshot storage will grow to roughly 5× this by year 5 (~$25–30) |
| DynamoDB PITR | DynamoDB line | included | Needed for RPO, so kept |

## 3. Three most expensive components

| Rank | Normal month | Exam month | Share (normal) |
|---|---|---|---|
| 1 | CloudFront $71.03 | CloudFront $94.84 | 22% |
| 2 | VPC endpoints $64.34 | VPC endpoints $64.54 | 20% |
| 3 | RDS $64.14 | RDS $64.14 | 19% |

Together they make up about 60% of the bill. RDS is already reserved. The endpoints replaced something more expensive (the NAT gateways). CloudFront is mostly data transfer, which you pay one way or another. The next cut would be the CloudFront Security Savings Bundle, or caching more of the API responses.

## 4. Service comparisons

### 4.1 Compute: EC2 ASG vs Fargate vs Lambda (API tier, normal month)

| Option | $/month | Notes |
|---|---:|---|
| **EC2 2 × t4g.small, Savings Plan** ✅ | **22.34** | Cheapest for a 24/7 base load; scheduled scale-out handles exams |
| EC2 2 × t4g.small, On-Demand | 30.95 | |
| Fargate 2 tasks (1 vCPU, 2 GB, ARM) | ≈ 72 | No servers to patch, but about 3× the price for the same always-on capacity |
| Lambda + API Gateway (exam-month load) | ≈ 66 | Scales to zero and is great for spiky load. But the API Gateway per-request charge at 36M requests plus cold starts during the exam-start burst make it worse here |

**Pick:** EC2. The load is predictable (always-on plus known exam windows), which is exactly where committed EC2 wins.

### 4.2 Database for answers: RDS Multi-AZ vs Aurora Serverless v2 vs DynamoDB

| Option | $/month | Notes |
|---|---:|---|
| **RDS MySQL db.t4g.small Multi-AZ, RI** ✅ (exams, users, results) | **64.14** | Relational data with joins (exams ↔ attempts ↔ results) |
| Aurora Serverless v2 (min 0.5 ACU × 2 for HA) | ≈ 73 | 2 × 0.5 × 730 × $0.10. It never goes below the minimum, so it costs more than the RI at our steady load |
| **DynamoDB on-demand** ✅ (autosaved answers only) | **4.00 – 23.09** | 270 writes/s at exam start needs no capacity planning, and you pay per write |

**Pick:** both, split by access pattern. Autosave is high-volume key-value writes, so it goes to DynamoDB. Everything relational stays on the reserved RDS.

### 4.3 Private subnet egress: NAT gateways vs VPC endpoints

| Option | $/month |
|---|---:|
| 2 NAT gateways (A2) + IPv4 | 102.51 |
| **3 interface endpoints × 2 AZ + free S3/DynamoDB gateway endpoints** ✅ | **64.34** |

The saving is **$38.17/month (37%)**. Traffic also stays on the AWS network. The trade-off is that instances can't reach the internet at all, so Python wheels have to be bundled at build time in CI.

### 4.4 Pricing model: On-Demand vs Savings Plans / Reserved Instances

| Item | On-Demand | Committed (1 yr, no upfront) | Saving |
|---|---:|---:|---:|
| EC2 base fleet | 38.54 (t3.small) / 30.95 (t4g.small) | 22.34 (Compute SP) | 16.20 vs A2 |
| RDS Multi-AZ | 79.98 | 64.14 (RI) | 15.84 |

I only committed the 24/7 baseline. The two exam-time instances stay On-Demand, because committing to them would mean paying for 730 hours to use 120.

### 4.5 S3 for 5-year retention (≈ 4 TB of old submissions by year 5)

| Storage class | $/GB-month (SG) | 4 TB/month |
|---|---:|---:|
| S3 Standard | 0.025 | ≈ $100 |
| Intelligent-Tiering (ends up in Archive Instant) | ≈ 0.005 + monitoring | ≈ $21 |
| Glacier Flexible Retrieval (A2) | 0.0045 | ≈ $18 |
| **Glacier Deep Archive** ✅ | ≈ 0.002 | **≈ $8** |

**Pick:** a lifecycle of Standard, then IA at 30 days, then Deep Archive at 180 days, then delete at 5 years. Access to old work is rare and predictable (appeals), and Deep Archive's 12-hour restore is acceptable for that. Intelligent-Tiering would only make sense if the access pattern were unknown.

## 5. Region: Singapore vs Mumbai (ap-south-1)

| | Singapore | Mumbai |
|---|---|---|
| Whole estimate | baseline | ≈ 8% cheaper |
| Compute (EC2) | baseline | ≈ 47% cheaper |
| RDS | baseline | ≈ 18% cheaper |
| Latency from Bhutan, measured 20 Nov 2026 (median of repeated pings to the regional DynamoDB endpoints) | **89 ms** | **68 ms** |

Mumbai is both cheaper and about 21 ms faster from Bhutan. I kept **Singapore** because:

- the brief fixes the region;
- 89 ms is fine for an exam app, since autosave is asynchronous and pages come from CloudFront edges anyway;
- the saving is only about $26/month.

If the region were free to choose, Mumbai would be the better pick.

## 6. Feasibility verdict

| Requirement | Target | Result | Verdict |
|---|---|---|---|
| Budget | ≤ $1,000/month average | $341.40 average, $400.68 in the worst (exam) month | ✅ **Feasible.** 66% headroom |
| Peak load | 8,000 students starting together | 4 API instances pre-scaled; DynamoDB on-demand takes ~270 writes/s; cache removes the RDS read bottleneck. Lab at 100× spike: HTTP 202 in 147 ms, no bottlenecks | ✅ |
| RPO | ≤ 5 min | AZ loss: 0 (synchronous standby, 30-s autosave). Corruption: RDS and DynamoDB point-in-time restore to about the last 5 min | ✅ |
| RTO | ≤ 1 h | AZ loss: ~1–2 min (Multi-AZ failover plus ALB health checks). Total rebuild: CloudFormation stack plus restore ≈ 40–50 min | ✅ (regional rebuild is the tight case) |

**Overall:** the design is feasible on all four. It meets them with a lot of budget to spare. The one risk I accept is a regional outage, which would use most of the 1-hour RTO.
