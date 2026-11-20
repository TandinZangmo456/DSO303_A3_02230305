"""Exam platform API (Flask). Runs on EC2 behind the ALB, in two AZs.

Stateless on purpose: every request can land on any instance in any AZ, because
all state lives in RDS (exams, attempts), DynamoDB (autosaved answers) or S3 (files).
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import boto3
import pymysql
import redis
from boto3.dynamodb.conditions import Key
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1")
MAX_UPLOAD = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXT = (".pdf", ".zip")
GRACE_SECONDS = 60             # network grace after the exam timer ends

dynamo = boto3.resource("dynamodb", region_name=REGION)
answers = dynamo.Table(os.environ.get("ANSWERS_TABLE", "exam-platform-answers"))
s3 = boto3.client("s3", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)
_db_creds = None

# A3: ElastiCache (Valkey) cache-aside for exam papers. Optional - if the cache is
# down or not configured, every call just falls through to RDS.
CACHE_HOST = os.environ.get("CACHE_HOST")
cache = (redis.Redis(host=CACHE_HOST, port=6379, ssl=True, socket_timeout=0.2,
                     socket_connect_timeout=0.2) if CACHE_HOST else None)
_schema_ready = False


# ---------------------------------------------------------------- helpers
def instance_info():
    """Which AZ / instance served this request (IMDSv2). Used to prove multi-AZ."""
    try:
        tok = requests.put("http://169.254.169.254/latest/api/token",
                           headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"}, timeout=1)
        tok.raise_for_status()
        tok = tok.text
        h = {"X-aws-ec2-metadata-token": tok}
        az = requests.get("http://169.254.169.254/latest/meta-data/placement/availability-zone", headers=h, timeout=1).text
        iid = requests.get("http://169.254.169.254/latest/meta-data/instance-id", headers=h, timeout=1).text
        return {"az": az, "instance": iid}
    except Exception:
        return {"az": "local", "instance": "local"}


INFO = None


def info():
    global INFO
    if INFO is None:
        INFO = instance_info()
    return INFO


def db():
    """New connection per request. Credentials come from Secrets Manager, never from code."""
    global _db_creds, _schema_ready
    if _db_creds is None:
        sm = boto3.client("secretsmanager", region_name=REGION)
        _db_creds = json.loads(sm.get_secret_value(SecretId=os.environ["DB_SECRET_ARN"])["SecretString"])
    conn = pymysql.connect(host=os.environ["DB_HOST"], user=_db_creds["username"],
                           password=_db_creds["password"], database="examdb",
                           connect_timeout=5, autocommit=True,
                           cursorclass=pymysql.cursors.DictCursor)
    if not _schema_ready:
        init_schema(conn)
        _schema_ready = True
    return conn


def init_schema(conn):
    with conn.cursor() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS exams (
            id VARCHAR(36) PRIMARY KEY, title VARCHAR(200), duration_minutes INT,
            questions JSON, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS attempts (
            id VARCHAR(36) PRIMARY KEY, exam_id VARCHAR(36), student_id VARCHAR(64),
            started_at DATETIME, deadline DATETIME, submitted_at DATETIME NULL,
            INDEX (exam_id), INDEX (student_id))""")
        c.execute("SELECT COUNT(*) AS n FROM exams")
        if c.fetchone()["n"] == 0:
            demo = [
                {"id": "q1", "type": "mcq", "text": "Which AWS service gives a synchronous standby database in a second AZ?",
                 "options": ["S3", "RDS Multi-AZ", "CloudFront", "SQS"], "answer": "RDS Multi-AZ"},
                {"id": "q2", "type": "mcq", "text": "What does an SQS dead-letter queue hold?",
                 "options": ["Messages that failed processing repeatedly", "Deleted S3 objects", "Old AMIs", "Expired passwords"],
                 "answer": "Messages that failed processing repeatedly"},
                {"id": "q3", "type": "short", "text": "In one sentence, why are presigned URLs used for uploads?"},
            ]
            c.execute("INSERT INTO exams (id, title, duration_minutes, questions) VALUES (%s,%s,%s,%s)",
                      (str(uuid.uuid4()), "DSO303 Demo Quiz", 20, json.dumps(demo)))


def role_required(*roles):
    """Demo role check. Production: verify the Cognito JWT and read the cognito:groups claim."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if request.headers.get("X-Demo-Role", "student") not in roles:
                return jsonify(error="forbidden for this role"), 403
            return fn(*a, **kw)
        return wrapper
    return deco


def public_questions(qs):
    return [{k: v for k, v in q.items() if k != "answer"} for q in qs]


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health():
    # Shallow on purpose: if this checked the DB, an RDS failover would mark EVERY
    # instance unhealthy and the ASG would kill a healthy fleet.
    return jsonify(status="ok", version=os.environ.get("APP_VERSION", "dev"), **info())


@app.get("/api/status")
def status():
    t = time.time()
    try:
        with db().cursor() as c:
            c.execute("SELECT 1")
        db_ok = True
    except Exception as e:  # noqa: BLE001
        db_ok = str(e)
    return jsonify(db=db_ok, db_ms=int((time.time() - t) * 1000), **info())


# ---------------------------------------------------------------- exams
@app.get("/api/exams")
def list_exams():
    with db().cursor() as c:
        c.execute("SELECT id, title, duration_minutes FROM exams ORDER BY created_at DESC")
        return jsonify(c.fetchall())


@app.post("/api/exams")
@role_required("tutor", "admin")
def create_exam():
    body = request.get_json(force=True)
    qs = body.get("questions", [])
    if not body.get("title") or not qs:
        return jsonify(error="title and questions required"), 400
    eid = str(uuid.uuid4())
    with db().cursor() as c:
        c.execute("INSERT INTO exams (id, title, duration_minutes, questions) VALUES (%s,%s,%s,%s)",
                  (eid, body["title"], int(body.get("durationMinutes", 30)), json.dumps(qs)))
    return jsonify(id=eid), 201


@app.get("/api/exams/<eid>")
def get_exam(eid):
    key = f"exam:{eid}"
    if cache:
        try:
            hit = cache.get(key)
            if hit:
                return jsonify(json.loads(hit))
        except redis.RedisError:
            pass                                   # cache trouble never breaks the exam
    with db().cursor() as c:
        c.execute("SELECT id, title, duration_minutes, questions FROM exams WHERE id=%s", (eid,))
        row = c.fetchone()
    if not row:
        return jsonify(error="not found"), 404
    row["questions"] = public_questions(json.loads(row["questions"]))  # never send the answer key
    if cache:
        try:
            cache.setex(key, 300, json.dumps(row, default=str))
        except redis.RedisError:
            pass
    return jsonify(row)


@app.post("/api/exams/<eid>/attempts")
@role_required("student")
def start_attempt(eid):
    student = (request.get_json(silent=True) or {}).get("studentId", "demo-student")
    with db().cursor() as c:
        c.execute("SELECT duration_minutes FROM exams WHERE id=%s", (eid,))
        exam = c.fetchone()
        if not exam:
            return jsonify(error="exam not found"), 404
        # Resume an open attempt instead of starting a new one (refresh / AZ failover safe)
        c.execute("""SELECT id, deadline FROM attempts WHERE exam_id=%s AND student_id=%s
                     AND submitted_at IS NULL ORDER BY started_at DESC LIMIT 1""", (eid, student))
        open_attempt = c.fetchone()
        if open_attempt:
            return jsonify(attemptId=open_attempt["id"], deadline=open_attempt["deadline"].isoformat() + "Z", resumed=True)
        aid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        deadline = now + timedelta(minutes=exam["duration_minutes"])  # server owns the timer
        c.execute("INSERT INTO attempts (id, exam_id, student_id, started_at, deadline) VALUES (%s,%s,%s,%s,%s)",
                  (aid, eid, student, now, deadline))
    return jsonify(attemptId=aid, deadline=deadline.isoformat() + "Z", resumed=False), 201


def load_attempt(aid):
    with db().cursor() as c:
        c.execute("SELECT * FROM attempts WHERE id=%s", (aid,))
        return c.fetchone()


@app.put("/api/attempts/<aid>/answers")
@role_required("student")
def autosave(aid):
    """Called every 30 s by the browser. DynamoDB absorbs the exam-peak write burst."""
    att = load_attempt(aid)
    if not att:
        return jsonify(error="attempt not found"), 404
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if att["submitted_at"] or now > att["deadline"] + timedelta(seconds=GRACE_SECONDS):
        return jsonify(error="exam closed"), 409
    saved_at = int(time.time())
    with answers.batch_writer() as bw:
        for qid, ans in (request.get_json(force=True).get("answers") or {}).items():
            bw.put_item(Item={"attemptId": aid, "questionId": qid, "answer": str(ans)[:5000],
                              "savedAt": saved_at})
    return jsonify(savedAt=saved_at, **info())


@app.get("/api/attempts/<aid>/answers")
def get_answers(aid):
    items = answers.query(KeyConditionExpression=Key("attemptId").eq(aid))["Items"]
    return jsonify({i["questionId"]: i.get("answer") for i in items if not i["questionId"].startswith("#")})


@app.post("/api/attempts/<aid>/submit")
@role_required("student")
def submit(aid):
    att = load_attempt(aid)
    if not att:
        return jsonify(error="attempt not found"), 404
    with db().cursor() as c:
        c.execute("UPDATE attempts SET submitted_at=UTC_TIMESTAMP() WHERE id=%s AND submitted_at IS NULL", (aid,))
        c.execute("SELECT questions FROM exams WHERE id=%s", (att["exam_id"],))
        qs = json.loads(c.fetchone()["questions"])
    key = {q["id"]: q["answer"] for q in qs if q.get("type") == "mcq"}
    shorts = sum(1 for q in qs if q.get("type") == "short")
    # Hand marking off to the queue: the student gets an instant response even at peak
    sqs.send_message(QueueUrl=os.environ["MARKING_QUEUE_URL"],
                     MessageBody=json.dumps({"attemptId": aid, "answerKey": key, "shortCount": shorts}))
    return jsonify(status="submitted, marking queued")


@app.get("/api/attempts/<aid>/result")
def result(aid):
    item = answers.get_item(Key={"attemptId": aid, "questionId": "#RESULT"}).get("Item")
    if not item:
        return jsonify(status="marking"), 202
    return jsonify(status="marked", mcqScore=int(item["mcqScore"]), mcqTotal=int(item["mcqTotal"]),
                   shortAnswersPending=int(item["shortAnswersPending"]))


# ---------------------------------------------------------------- uploads
@app.post("/api/uploads/presign")
@role_required("student")
def presign():
    """Browser uploads straight to S3; the 40-50 MB file never passes through the API."""
    b = request.get_json(force=True)
    fname = os.path.basename(b.get("filename", ""))
    if not fname.lower().endswith(ALLOWED_EXT):
        return jsonify(error="only PDF or ZIP"), 400
    if int(b.get("size", 0)) > MAX_UPLOAD:
        return jsonify(error="max 50 MB"), 400
    key = f"assignments/{b.get('assignmentId', 'A1')}/{b.get('studentId', 'demo-student')}/{int(time.time())}-{fname}"
    post = s3.generate_presigned_post(
        os.environ["UPLOAD_BUCKET"], key,
        Conditions=[["content-length-range", 1, MAX_UPLOAD]],  # S3 itself rejects >50 MB
        ExpiresIn=300)
    return jsonify(key=key, **post)


@app.get("/api/submissions")
@role_required("tutor", "admin")
def submissions():
    prefix = f"assignments/{request.args.get('assignmentId', 'A1')}/"
    resp = s3.list_objects_v2(Bucket=os.environ["UPLOAD_BUCKET"], Prefix=prefix)
    return jsonify([{"key": o["Key"], "sizeMB": round(o["Size"] / 1048576, 2),
                     "uploaded": o["LastModified"].isoformat()} for o in resp.get("Contents", [])])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
