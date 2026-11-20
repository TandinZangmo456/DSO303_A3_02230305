# Failure and load tests

**Tool:** the Cloud Architecture Lab (the course simulator). I imported `architecture/lab-a3-*.json` and injected failures in **Failure Lab**. Then I sent the same request each time:

- **Request:** `PUT /api/attempts/demo/answers` (a student saving an answer)
- **Load:** 10 req/s
- **Screenshots:** in `evidence/lab/`

**Targets:** RPO ≤ 5 min, RTO ≤ 1 h.

## Summary

| # | Scenario | Expected impact | Measured (Lab) | RPO | RTO | Pass? |
|---|---|---|---|---|---|---|
| F1 | Whole AZ-A goes down | Lose the ALB node, API pair and RDS primary in AZ-A. Traffic moves to AZ-B | **HTTP 202, 147 ms.** 3 resources failed, 5 dependents survived | 0 | ~1–2 min | ✅ |
| F2 | RDS primary instance fails | Brief write errors while the standby is promoted | **HTTP 202.** Both API pairs and Backup "survived via redundancy" | 0 | ~1–2 min | ✅ |
| F3 | Marking Lambda unavailable | Auto-marking stops; students can still submit | **HTTP 202.** Lambda failed with no cascade to the user path | 0 | Minutes after the fix | ✅ (degraded) |
| F4 | Bad deployment on API instances in AZ-A | ALB health checks pull those targets | **HTTP 202.** ALB, ASG and Cognito survived | 0 | ~1 min (health check), or rollback | ✅ |
| F1b | AZ-A down with the cache in AZ-A only (intermediate version) | Should behave like F1 | **HTTP 503.** "ALL TARGETS failed" at the ALB health check | – | – | ❌ → fixed |

## Details

### F1: AZ-A outage (`az_failure` on AZ-A). Screenshot: `05-F1-az-a-outage-final.png`

- **Expected:** everything in AZ-A is lost: the ALB node, 2 API instances and the RDS primary. RDS fails over to the AZ-B standby. The ALB stops sending traffic to AZ-A. The ASG launches replacements in AZ-B.
- **Measured:** the Lab reported that the `az_failure` on AZ-A directly failed 3 resources and that 5 dependents fully survived. The request still returned **202**.
- **RPO 0:** the standby is synchronous and autosaves go to DynamoDB, which is regional.
- **RTO:** about 1–2 min for the RDS DNS flip and the health checks.
- **Likely solution / hardening:** this already passes. During an exam, keep the scheduled minimum at 4 so the surviving AZ starts with 2 warm instances instead of 1.

### F2: RDS primary down (`database_unavailable` on `node-rds-a`). Screenshot: `06-F2-rds-primary-failure.png`

- **Expected:** Multi-AZ automatic failover. Writes fail for about 60–120 s while DNS moves to the standby.
- **Measured:** **202.** The Lab said 1 resource failed directly and that both API pairs and AWS Backup fully survived through redundancy.
- **RPO 0, RTO about 2 min.**
- **Likely solution:** the API retries DB writes with exponential backoff, so the failover window isn't visible to students. A CloudWatch alarm on the `RDS-EVENT` failover notifies the admin.

### F3: Marking Lambda down (`service_unavailable` on `node-lambda-mark`). Screenshot: `07-F3-marking-lambda-failure.png`

- **Expected:** this is the accepted SPOF. Submissions still succeed because the API only puts a job on SQS. Jobs wait in the queue for up to 4 days and then go to the DLQ. Results are delayed, but nothing is lost.
- **Measured:** **202.** The failure stayed on the Lambda.
- **RPO 0:** jobs are durable in SQS and DLQ.
- **RTO:** until the function is fixed; the backlog then drains at 5 concurrent invocations.
- **Likely solution:** a DLQ-not-empty alarm (already there) plus a re-drive. A queue-age alarm should be added (`ApproximateAgeOfOldestMessage` > 10 min). If SQS itself fails, the API writes `pending_marking` to RDS and a sweeper re-queues the jobs later.

### F4: Bad deployment on the AZ-A instances (`configuration_failure` on `node-api-a`). Screenshot: `08-F4-bad-deploy-api-a.png`

- **Expected:** a broken build fails `/health`. The ALB stops routing to those targets, AZ-B keeps serving, and the rolling update (`MinInstancesInService: 1`, batch 1) stops before it replaces everything.
- **Measured:** **202.** The ALB, ASG and Cognito survived.
- **RPO 0, RTO about 1 min** to drain the bad targets. A rollback redeploys the previous `AppVersion` (commit SHA) in about 10 min.
- **Likely solution:** add CloudFormation rollback triggers tied to the 5xx alarm, so a bad deploy rolls back by itself.

### F1b: the failure that changed the design. Screenshot: `09-cache-spof-az-a-503.png`

My first version of the cache fix put a single ElastiCache node in AZ-A, and the API instances depended on it. When I re-ran F1, the request returned **HTTP 503**. The Lab trace shows the ALB failing on "Target Health Check: ALL TARGETS failed". The AZ-B API pair was only "degraded", because its cache had gone down with AZ-A. So fixing the bottleneck had created a new single point of failure.

**Fix (C7 in the change log):**

- Add a replica in AZ-B with automatic failover.
- Make the cache **non-critical**: on a miss or connection error, the API reads from RDS.

After that change, F1 returns 202 again (screenshot 05).

## Load test

| Step | Design | Test | Result | Screenshot |
|---|---|---|---|---|
| 1 | A3 before fix: 2 API instances per AZ, all reading RDS directly | Analyze → Bottlenecks | **2 × HIGH "Database Connection & Throughput Contention"**: 6 compute nodes on one relational DB with no cache or proxy, so `max_connections` runs out at peak | `01-before-analyze-bottleneck.png` |
| 2 | Same | Simulate, 100× spike | 202 in 147 ms in the lab, but the analyzer still flags the contention, and lab cost jumps to about $2,677/mo (the lab extrapolates the 100× load across a whole month) | `02-before-simulate-100x.png` |
| 3 | **Fix:** ElastiCache cache-aside for exam papers and question banks (read-heavy, rarely changing) | – | – | – |
| 4 | Final design | Analyze → Bottlenecks | **"No bottlenecks detected."** | `03-final-analyze-no-bottleneck.png` |
| 5 | Final design | Simulate, 100× spike | **HTTP 202 in 147 ms**, all 12 steps OK | `04-final-simulate-100x.png` |

**In a real deployment** I would prove the bottleneck in CloudWatch with these RDS metrics:

- `DatabaseConnections` approaching `max_connections`: db.t4g.small has about 150. With 4 instances × 3 gunicorn workers × pool size, plus exam-start retries, the limit is reached quickly.
- `CPUUtilization` above 80% (the existing `rds-cpu` alarm).
- `ReadLatency` climbing.

After the fix, ElastiCache `CacheHitRate` and the drop in RDS `DatabaseConnections` show the fix working.

### Two more bottlenecks (reasoned, not simulated)

1. **Auto Scaling reacts too late for the exam-start burst.** Target tracking needs a few minutes of high CPU, and then a new instance needs 3–5 min to boot and pass health checks. The worst of the burst (8,000 logins and paper loads) happens in the first ~5 min, so the new capacity arrives after the peak.
   - **Fix:** scheduled scale-out to 4 instances 30 min before the first sitting (`ExamScaleOut`, `ExamPeriod=true`). It costs $10.21 per exam month.
2. **Marking backlog after submission.** At the end of an exam, about 8,000 submit jobs arrive within a few minutes. `MaximumConcurrency: 5` on the event-source mapping deliberately caps how fast the marker can hit DynamoDB and RDS, so a backlog forms. At about 1 s per job and 5 at a time, that's roughly 25–30 min to drain. This is fine because results are released later anyway.
   - **Fix:** monitor `ApproximateAgeOfOldestMessage`. If results ever need to be faster, raise the concurrency to 20, which the cache and DynamoDB can absorb.
   - DynamoDB on-demand itself isn't a bottleneck. It immediately serves up to double the previous peak, and the autosave peak is about 270 writes/s.
