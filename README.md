# DSO303 Assignment 3: cost-optimised exam platform (Singapore)

This is a revised version of my A2 architecture for the online exam and assignment platform (8,000 students). A3 changes it in two ways:

- **Costed:** I priced it in the AWS Pricing Calculator for a normal month and an exam month.
- **Tested:** I ran the load and failure tests in the Cloud Architecture Lab and changed the design based on what they showed.

## Summary

| | |
|---|---|
| Region | ap-southeast-1 (Singapore) |
| Normal month | **$329.54** |
| Exam month | **$400.68** |
| Average / annual | **$341.40 / month**, **$4,096.76 / year** |
| Per student | **$0.51 / year** |
| Savings from optimisations | **$70.21 / month (~$842 / year)**: NAT → VPC endpoints, Graviton + Savings Plan, RDS Reserved Instance |

**Main design changes vs A2:**

- No NAT gateways
- Graviton instances
- Reserved and committed pricing
- Scheduled scale-out on exam days
- ElastiCache to fix the RDS bottleneck the load test found
- Deep Archive for the 5-year retention
- 30-day log retention

The full change log is in `architecture/README.md`.

## Feasibility verdict

**Feasible.**

- **Budget:** about 34% of the $1,000/month budget is used on average, and the worst month is $400.68.
- **Peak load:** the 100× spike returns 202 in 147 ms with no bottlenecks.
- **RPO:** 0 for an AZ loss, and ≤ 5 min for corruption via point-in-time restore.
- **RTO:** about 2 min for an AZ loss and under 1 h for a full rebuild.
- **Accepted risks:** a full regional outage (single region), and the SQS/Lambda marking path (results are delayed, but no data is lost).

The numbers behind this are in `docs/cost-report.md`, section 6.

## AWS Pricing Calculator (20 Nov 2026)

| Estimate | Link |
|---|---|
| Normal month ($329.54) | https://calculator.aws/#/estimate?id=0e5d0b19169add1da7f5e97aa9c832abd8cacac6 |
| Exam month ($400.68) | https://calculator.aws/#/estimate?id=f09315d41728e33373dc5162336f3b3267d24835 |
| Optimisations before/after ($221.03 → $150.82) | https://calculator.aws/#/estimate?id=09198a2ce3d53ad6fb518815bb1050eae6e44783 |

Screenshots and the exports are in `evidence/calculator/`.

## Repo layout

```
architecture/   revised diagram (png/svg + draw_a3.py), change log, SPOF list, Lab JSON files
docs/           cost-report.md: costs, hidden costs, top 3, 5 comparisons, region, verdict
infra/          template.yaml (updated CloudFormation, cfn-lint clean), failure-tests.md
evidence/       calculator/ screenshots + links, lab/ load & failure test screenshots
app/ frontend/ scripts/ .github/   carried over from A2 (CI now vendors arm64 wheels, region ap-southeast-1)
```
