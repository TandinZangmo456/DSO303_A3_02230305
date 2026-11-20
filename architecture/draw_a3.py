"""Hand-laid AWS architecture diagram -> SVG -> PNG (rsvg-convert)."""
import base64, os, subprocess

R = "/usr/local/lib/python3.13/dist-packages/resources"
ICON = {
    "users": "onprem/client/users.png", "route53": "aws/network/route-53.png",
    "cloudfront": "aws/network/cloudfront.png", "waf": "aws/security/waf.png",
    "acm": "aws/security/certificate-manager.png", "s3": "aws/storage/simple-storage-service-s3.png",
    "cognito": "aws/security/cognito.png", "igw": "aws/network/internet-gateway.png",
    "nat": "aws/network/nat-gateway.png", "alb": "aws/network/elastic-load-balancing.png",
    "ec2": "aws/compute/ec2.png", "rds": "aws/database/rds.png", "endpoint": "aws/network/endpoint.png",
    "dynamodb": "aws/database/dynamodb.png", "sqs": "aws/integration/simple-queue-service-sqs.png",
    "lambda": "aws/compute/lambda.png", "sns": "aws/integration/simple-notification-service-sns.png",
    "ses": "aws/engagement/simple-email-service-ses.png", "secrets": "aws/security/secrets-manager.png",
    "kms": "aws/security/key-management-service.png", "iam": "aws/security/identity-and-access-management-iam.png",
    "cloudwatch": "aws/management/cloudwatch.png", "cloudtrail": "aws/management/cloudtrail.png",
    "backup": "aws/storage/backup.png", "github": "onprem/vcs/github.png",
    "cfn": "aws/management/cloudformation.png", "cache": "aws/database/elasticache.png",
}
_cache = {}
def uri(k):
    if k not in _cache:
        _cache[k] = "data:image/png;base64," + base64.b64encode(open(os.path.join(R, ICON[k]), "rb").read()).decode()
    return _cache[k]

W, H = 2000, 1400
out = []
FONT = "font-family='Helvetica, Arial, sans-serif'"
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def box(x, y, w, h, label, stroke, fill="none", dash=None, lc=None, bold=True):
    d = f" stroke-dasharray='{dash}'" if dash else ""
    out.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='6' fill='{fill}' stroke='{stroke}' stroke-width='2'{d}/>")
    out.append(f"<text x='{x+10}' y='{y+20}' {FONT} font-size='15' font-weight='{'bold' if bold else 'normal'}' fill='{lc or stroke}'>{esc(label)}</text>")

def icon(k, cx, cy, label, size=60, sub=None):
    out.append(f"<image href='{uri(k)}' x='{cx-size/2}' y='{cy-size/2}' width='{size}' height='{size}'/>")
    lines = label.split("\n") + ([sub] if sub else [])
    for i, ln in enumerate(lines):
        col = "#555" if (sub and i == len(lines) - 1) else "#16191f"
        sz = 12 if (sub and i == len(lines) - 1) else 13
        out.append(f"<text x='{cx}' y='{cy+size/2+16+i*15}' text-anchor='middle' {FONT} font-size='{sz}' fill='{col}' stroke='white' stroke-width='3.5' paint-order='stroke'>{esc(ln)}</text>")

COL = {"k": "#3b4252", "b": "#1f6feb", "g": "#1a7f37", "o": "#b35900", "p": "#8250df"}
def arrow(pts, c="k", label=None, lpos=None, dash=False, width=2, both=False, anchor="middle"):
    col = COL[c]
    p = " ".join(f"{x},{y}" for x, y in pts)
    d = " stroke-dasharray='6,5'" if dash else ""
    ms = f" marker-start='url(#s{c})'" if both else ""
    out.append(f"<polyline points='{p}' fill='none' stroke='{col}' stroke-width='{width}'{d} marker-end='url(#a{c})'{ms}/>")
    if label:
        lx, ly = lpos
        out.append(f"<text x='{lx}' y='{ly}' text-anchor='{anchor}' {FONT} font-size='12.5' font-weight='bold' fill='{col}' "
                   f"stroke='white' stroke-width='4' paint-order='stroke'>{esc(label)}</text>")

def badge(cx, cy, n, c):
    out.append(f"<circle cx='{cx}' cy='{cy}' r='11' fill='{COL[c]}'/>")
    out.append(f"<text x='{cx}' y='{cy+4.5}' text-anchor='middle' {FONT} font-size='12.5' font-weight='bold' fill='white'>{n}</text>")

# ---------------------------------------------------------------- groups
out.append(f"<text x='40' y='42' {FONT} font-size='26' font-weight='bold' fill='#16191f'>Online Exam &amp; Assignment Platform — A3 revised, cost-optimised architecture</text>")
out.append(f"<text x='40' y='66' {FONT} font-size='14' fill='#555'>Singapore (ap-southeast-1) · 8,000 students · ~$306/month average (normal $294 · exam $365) vs $1,000 budget · RPO ≤ 5 min · RTO ≤ 1 h · ✓ = SPOF removed · ! = SPOF accepted</text>")

box(200, 110, 270, 900, "Edge & identity (global)", "#5a6b86", fill="#f7f9fc")
box(500, 110, 1480, 940, "AWS Cloud — Region ap-southeast-1 (Singapore)  !  single region accepted (restore from backups)", "#147eba", dash="8,5")
box(525, 150, 830, 880, "VPC 10.0.0.0/16", "#8c4fff", fill="#fbf9ff")
# AZ columns
box(545, 185, 380, 830, "Availability Zone A", "#147eba", dash="5,4", bold=True)
box(955, 185, 380, 830, "Availability Zone B", "#147eba", dash="5,4", bold=True)
for x0, az in ((560, "a"), (970, "b")):
    pub = "10.0.1.0/24" if az == "a" else "10.0.2.0/24"
    app = "10.0.11.0/24" if az == "a" else "10.0.12.0/24"
    dat = "10.0.21.0/24" if az == "a" else "10.0.22.0/24"
    box(x0, 215, 350, 175, f"Public subnet {pub}", "#248814", fill="#eef7ec", bold=False)
    box(x0, 440, 350, 250, f"Private app subnet {app}", "#147eba", fill="#e9f3fa", bold=False)
    box(x0, 740, 350, 255, f"Private data subnet {dat}", "#147eba", fill="#e9f3fa", bold=False)
# Auto Scaling group spanning both AZs
out.append("<rect x='640' y='478' width='600' height='190' rx='8' fill='none' stroke='#d86613' stroke-width='2' stroke-dasharray='7,5'/>")
out.append(f"<text x='940' y='660' text-anchor='middle' {FONT} font-size='13' font-weight='bold' fill='#d86613'>Auto Scaling group · min 2 / max 6 · target CPU 50 % · scheduled scale-out to 4 for exams</text>")

box(1405, 150, 560, 290, "Data (regional, replicated across 3 AZs)", "#3b48cc", fill="#f5f6ff")
box(1405, 460, 560, 350, "Asynchronous processing", "#e7157b", fill="#fff5fa")
box(1405, 830, 560, 200, "Security", "#dd344c", fill="#fff6f7")
box(500, 1080, 820, 290, "Operations & resilience", "#e7157b", fill="#fff5fa")
box(1345, 1080, 615, 290, "CI/CD & infrastructure as code", "#5a6b86", fill="#f7f9fc")

# ---------------------------------------------------------------- icons
icon("users", 95, 470, "Students · Tutors\n· Admins", size=70, sub="browser")
icon("route53", 335, 190, "Route 53", sub="exams.<uni> alias")
icon("cloudfront", 335, 400, "CloudFront", sub="HTTPS · caches frontend")
icon("waf", 255, 560, "AWS WAF", size=52, sub="managed rules + rate")
icon("acm", 410, 560, "ACM", size=52, sub="TLS certificates")
icon("s3", 335, 730, "S3 — frontend", sub="private, OAC only")
icon("cognito", 335, 900, "Cognito", sub="students/tutors/admins")

icon("igw", 940, 150, "Internet gateway", size=48)
out.append(f"<text x='650' y='300' text-anchor='middle' {FONT} font-size='12.5' fill='#999'>NAT gateway removed</text>")
out.append(f"<text x='1245' y='300' text-anchor='middle' {FONT} font-size='12.5' fill='#999'>NAT gateway removed</text>")
icon("alb", 940, 300, "Application Load\nBalancer", size=62, sub="HTTPS :443 (ACM)")
icon("ec2", 740, 560, "API t4g.small ×2", sub="Graviton · Savings Plan")
icon("ec2", 1140, 560, "API t4g.small ×2", sub="Graviton · Savings Plan")
icon("rds", 650, 820, "RDS primary", sub="t4g.small · 1-yr RI")
icon("rds", 1250, 820, "RDS standby", sub="Multi-AZ, sync")
icon("cache", 840, 820, "ElastiCache", sub="Valkey primary")
icon("cache", 1060, 820, "ElastiCache", sub="replica (failover)")
icon("endpoint", 1355, 470, "Gateway\nendpoints", size=46, sub="S3 · DynamoDB")
icon("endpoint", 1355, 740, "Interface\nendpoints", size=46, sub="SQS · Secrets · Logs")

icon("dynamodb", 1545, 250, "DynamoDB", sub="autosaved answers · PITR")
icon("s3", 1825, 250, "S3 — assignment files", sub="SSE-KMS · versioned")
out.append(f"<text x='1825' y='330' text-anchor='middle' {FONT} font-size='12' fill='#555'>lifecycle: IA 30d → Deep Archive 180d → delete 5y</text>")
out.append(f"<text x='1545' y='330' text-anchor='middle' {FONT} font-size='12' fill='#555'>on-demand · ~100 writes/s at peak</text>")

icon("sqs", 1485, 545, "SQS marking", size=54, sub="+ DLQ")
icon("lambda", 1665, 545, "Lambda", size=54, sub="auto-mark MCQs")
icon("ses", 1865, 545, "SES", size=54, sub="results released")
icon("sqs", 1485, 715, "SQS upload events", size=54, sub="+ DLQ")
icon("lambda", 1665, 715, "Lambda", size=54, sub="notify tutor")
icon("sns", 1865, 715, "SNS", size=54, sub="email to tutor")

icon("secrets", 1505, 920, "Secrets Manager", size=54, sub="DB credentials")
icon("kms", 1685, 920, "KMS", size=54, sub="keys for RDS/S3/DDB")
icon("iam", 1865, 920, "IAM roles", size=54, sub="least privilege")

icon("cloudwatch", 620, 1180, "CloudWatch", sub="alarms · logs kept 30 days")
icon("cloudtrail", 840, 1180, "CloudTrail", sub="audit of every change")
icon("backup", 1060, 1180, "AWS Backup", sub="monthly, kept 5 years")
out.append(f"<text x='520' y='1290' {FONT} font-size='12.5' fill='#333'>Alarms: ALB 5xx · unhealthy targets · DLQ not empty · RDS CPU/connections · Lambda errors</text>")
out.append(f"<text x='520' y='1310' {FONT} font-size='12.5' fill='#333'>RPO ≤ 5 min: 30-s autosave, synchronous standby, RDS + DynamoDB point-in-time restore</text>")
out.append(f"<text x='520' y='1330' {FONT} font-size='12.5' fill='#333'>RTO ≤ 1 h: automatic AZ failover in minutes; worst case rebuild the stack from code + restore</text>")

icon("github", 1440, 1180, "GitHub repo", size=56, sub="push to main")
icon("github", 1640, 1180, "GitHub Actions", size=56, sub="lint · package · deploy")
icon("cfn", 1840, 1180, "CloudFormation", sub="whole stack as code")
out.append(f"<text x='1365' y='1300' {FONT} font-size='12.5' fill='#333'>New commit → new API package → CloudFormation rolling update of the Auto</text>")
out.append(f"<text x='1365' y='1320' {FONT} font-size='12.5' fill='#333'>Scaling group (one instance at a time, ≥1 always serving) → frontend synced</text>")
out.append(f"<text x='1365' y='1340' {FONT} font-size='12.5' fill='#333'>to S3 + CloudFront invalidation → smoke test.</text>")

# ---------------------------------------------------------------- arrows
# shared entry path (black)
arrow([(95, 425), (95, 190), (300, 190)], "k", "DNS", (180, 180))
arrow([(335, 225), (335, 365)])
arrow([(130, 462), (300, 418)], "k", "HTTPS", (215, 462))
arrow([(255, 532), (303, 412)], dash=True)
arrow([(410, 532), (367, 412)], dash=True)
arrow([(335, 438), (335, 695)], "k", "static files", (345, 680), anchor="start")
arrow([(95, 562), (95, 900), (300, 900)], "k", "sign-in (JWT)", (180, 890))
arrow([(372, 400), (480, 400), (480, 410), (940, 410), (940, 340)], "k", "/api/* (HTTPS)", (700, 403))
arrow([(940, 175), (940, 262)])
arrow([(920, 345), (770, 525)])
arrow([(960, 345), (1110, 525)])
# app -> database
arrow([(730, 600), (660, 780)], "b", "SQL", (640, 700), anchor="end")
arrow([(1110, 600), (690, 795)], "b")
arrow([(760, 600), (830, 780)], "o", "cache-aside", (815, 740), anchor="start")
arrow([(1140, 600), (1065, 780)], "o")
arrow([(870, 820), (1030, 820)], "p", dash=True)
arrow([(650, 905), (650, 965), (1250, 965), (1250, 905)], "p", "sync replication · auto failover", (950, 958), width=3, both=True)
# walkthrough 1 (blue): autosave + async marking
arrow([(1240, 515), (1328, 480)], "b")
arrow([(1378, 455), (1508, 262)], "b", "autosave every 30 s", (1420, 400), anchor="start")
arrow([(1240, 600), (1455, 560)], "b", "submit → job", (1300, 625))
arrow([(1515, 545), (1635, 545)], "b")
arrow([(1660, 515), (1578, 262)], "b", "write score", (1635, 420), anchor="start")
arrow([(1695, 545), (1835, 545)], "o", "on release", (1765, 535))
# walkthrough 2 (green): direct upload + notify
arrow([(60, 435), (60, 92), (1825, 92), (1825, 215)], "g", "presigned POST — 40 MB file goes straight to S3 (S3 enforces ≤ 50 MB)", (1000, 86))
arrow([(1378, 488), (1792, 262)], "g")
arrow([(1855, 235), (1958, 235), (1958, 632), (1485, 632), (1485, 685)], "g", "ObjectCreated", (1720, 625))
arrow([(1515, 715), (1635, 715)], "g")
arrow([(1695, 715), (1835, 715)], "g")
# security links
arrow([(1240, 668), (1475, 893)], "k", "read DB secret", (1300, 718), dash=True, anchor="end")
# CI/CD
arrow([(1470, 1180), (1608, 1180)])
arrow([(1670, 1180), (1805, 1180)])
arrow([(1840, 1145), (1840, 1062)], "k", "creates / updates everything above", (1835, 1075), anchor="end")

# walkthrough badges
for (x, y, n, c) in [(118, 200, "1", "k"), (230, 405, "2", "k"), (1000, 410, "3", "k"), (870, 440, "4", "k"),
                     (1400, 440, "5", "b"), (1270, 560, "6", "b"), (1575, 545, "7", "b"), (1615, 380, "8", "b")]:
    badge(x, y, n, c)

def mark(cx, cy, ok):
    c = '#1a7f37' if ok else '#cf222e'
    out.append(f"<circle cx='{cx}' cy='{cy}' r='12' fill='{c}' stroke='white' stroke-width='2'/>")
    out.append(f"<text x='{cx}' y='{cy+5}' text-anchor='middle' {FONT} font-size='15' font-weight='bold' fill='white'>{'✓' if ok else '!'}</text>")
for (x, y) in [(975, 270), (775, 530), (1175, 530), (685, 790), (875, 790), (365, 370), (365, 160)]: mark(x, y, True)
for (x, y) in [(1515, 515), (1695, 515)]: mark(x, y, False)
# legend
lx, ly = 40, 1080
out.append(f"<rect x='{lx}' y='{ly}' width='440' height='310' rx='6' fill='white' stroke='#999'/>")
out.append(f"<text x='{lx+12}' y='{ly+24}' {FONT} font-size='15' font-weight='bold'>Legend</text>")
rows = [("k", "Request path shared by both walkthroughs", False),
        ("b", "Walkthrough 1 — open exam, autosave, auto-mark", False),
        ("g", "Walkthrough 2 — 40 MB upload, tutor notified", False),
        ("p", "Database replication between AZs", False),
        ("o", "Results email when tutor releases", False),
        ("k", "Config / security dependency", True),
        ("o", "Cache-aside reads (non-critical, falls back to RDS)", False)]
for i, (c, t, dsh) in enumerate(rows):
    y = ly + 52 + i * 30
    arrow([(lx + 14, y), (lx + 64, y)], c, dash=dsh)
    out.append(f"<text x='{lx+76}' y='{y+4}' {FONT} font-size='13'>{esc(t)}</text>")
out.append(f"<text x='{lx+12}' y='{ly+265}' {FONT} font-size='12.5' fill='#333'>Security groups: ALB ← internet :443 · API ← ALB only · RDS ← API only.</text>")
out.append(f"<text x='{lx+12}' y='{ly+285}' {FONT} font-size='12.5' fill='#333'>No NAT: instances reach AWS APIs only via VPC endpoints.</text>")

defs = "".join(
    f"<marker id='a{k}' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{v}'/></marker>"
    f"<marker id='s{k}' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{v}'/></marker>"
    for k, v in COL.items())
svg = (f"<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>"
       f"<defs>{defs}</defs><rect width='100%' height='100%' fill='white'/>" + "".join(out) + "</svg>")
dst = os.path.dirname(os.path.abspath(__file__))
open(f"{dst}/architecture.svg", "w").write(svg)
subprocess.run(["rsvg-convert", "-z", "1.25", "-o", f"{dst}/architecture.png", f"{dst}/architecture.svg"], check=True)
print("ok")
