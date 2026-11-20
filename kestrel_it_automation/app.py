import json, os, sqlite3, threading, time, uuid, secrets, string
from datetime import datetime
from pathlib import Path

import pika
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB = ROOT / "automation.db"
QUEUE = os.getenv("RABBITMQ_QUEUE", "kestrel_it_jobs")
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "guest")
RABBIT_PASS = os.getenv("RABBITMQ_PASSWORD", "guest")

app = FastAPI(title="Kestrel IT Operations Automation")
consumer_thread = None
consumer_stop = threading.Event()
rabbit_status = {"connected": False, "message": "Not connected yet"}

JOB_NAMES = {
    "login_id": "Employee Login ID Creation",
    "account": "Employee Account Creation",
    "access": "Access Request Management",
    "password": "Password Reset Automation",
    "ticket": "IT Helpdesk Ticket Management",
}

def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT, employee_code TEXT UNIQUE,
            first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT,
            department TEXT, designation TEXT, created_at TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, employee_id INTEGER, employee_name TEXT,
            employee_code TEXT, job_type TEXT, job_name TEXT, payload TEXT,
            status TEXT, result TEXT, error TEXT, created_at TEXT, updated_at TEXT)""")

class EmployeeIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=30)
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str = ""
    department: str = "IT"
    designation: str = "Employee"

class JobIn(BaseModel):
    employee_id: int
    job_type: str
    access_type: str = "Standard Application"
    ticket_category: str = "Software"
    issue: str = "General support request"

def rabbit_connection():
    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    params = pika.ConnectionParameters(host=RABBIT_HOST, credentials=credentials,
        heartbeat=30, blocked_connection_timeout=10,
        connection_attempts=2, retry_delay=2)
    return pika.BlockingConnection(params)

def publish_message(payload):
    conn = rabbit_connection()
    try:
        ch = conn.channel()
        ch.queue_declare(queue=QUEUE, durable=True)
        ch.basic_publish(exchange="", routing_key=QUEUE,
            body=json.dumps(payload).encode(),
            properties=pika.BasicProperties(delivery_mode=2,
                content_type="application/json"))
    finally:
        conn.close()

def make_login(first, last):
    first = ''.join(c for c in first.lower() if c.isalnum())
    last = ''.join(c for c in last.lower() if c.isalnum())
    return (last[:1] + first) if last else first

def process_job(ch, method, properties, body):
    try:
        data = json.loads(body.decode())
        job_id = data["job_id"]
        with db() as con:
            con.execute("UPDATE jobs SET status='Processing', updated_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"), job_id))
        emp = data["employee"]
        first, last = emp["first_name"], emp["last_name"]
        kind = data["job_type"]

        if kind == "login_id":
            result = {"login_id": make_login(first, last),
                      "message": "Login ID generated successfully"}
        elif kind == "account":
            # Demo-only account: never use this generated credential on a real system.
            temp = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#") for _ in range(12))
            result = {"account_id": "KLG-" + uuid.uuid4().hex[:8].upper(),
                      "temporary_password": temp,
                      "message": "Demo account created"}
        elif kind == "access":
            result = {"request_id": "ACC-" + uuid.uuid4().hex[:8].upper(),
                      "access_type": data.get("access_type", "Standard Application"),
                      "decision": "Pending Approval",
                      "message": "Access request recorded for administrator review"}
        elif kind == "password":
            temp = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
            result = {"reset_reference": "PWD-" + uuid.uuid4().hex[:8].upper(),
                      "temporary_password": temp,
                      "message": "Demo password reset completed"}
        elif kind == "ticket":
            result = {"ticket_id": "HD-" + uuid.uuid4().hex[:8].upper(),
                      "category": data.get("ticket_category", "Software"),
                      "issue": data.get("issue", "General support request"),
                      "ticket_status": "Open",
                      "message": "Helpdesk ticket created"}
        else:
            raise ValueError("Unknown job type")

        with db() as con:
            con.execute("""UPDATE jobs SET status='Completed', result=?, error=NULL, updated_at=?
                WHERE id=?""", (json.dumps(result), datetime.now().isoformat(timespec="seconds"), job_id))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        try:
            data = json.loads(body.decode())
            with db() as con:
                con.execute("UPDATE jobs SET status='Failed', error=?, updated_at=? WHERE id=?",
                    (str(exc), datetime.now().isoformat(timespec="seconds"), data.get("job_id", "")))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def consumer_loop():
    while not consumer_stop.is_set():
        conn = None
        try:
            conn = rabbit_connection()
            ch = conn.channel()
            ch.queue_declare(queue=QUEUE, durable=True)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=QUEUE, on_message_callback=process_job)
            rabbit_status.update(connected=True, message=f"Connected · queue: {QUEUE}")
            while conn.is_open and not consumer_stop.is_set():
                conn.process_data_events(time_limit=1)
        except Exception as exc:
            rabbit_status.update(connected=False, message=f"RabbitMQ unavailable: {exc}")
            time.sleep(4)
        finally:
            try:
                if conn and conn.is_open: conn.close()
            except Exception: pass
    rabbit_status.update(connected=False, message="Consumer stopped")

@app.on_event("startup")
def startup():
    global consumer_thread
    init_db()
    consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
    consumer_thread.start()

@app.on_event("shutdown")
def shutdown():
    consumer_stop.set()

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@app.get("/api/status")
def status():
    return {"rabbitmq": rabbit_status, "queue": QUEUE}

@app.get("/api/employees")
def employees():
    with db() as con:
        rows = con.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

@app.post("/api/employees")
def add_employee(emp: EmployeeIn):
    try:
        with db() as con:
            cur = con.execute("""INSERT INTO employees(employee_code,first_name,last_name,email,department,designation,created_at)
                VALUES(?,?,?,?,?,?,?)""", (emp.employee_code.strip(), emp.first_name.strip(),
                emp.last_name.strip(), emp.email.strip(), emp.department.strip(),
                emp.designation.strip(), datetime.now().isoformat(timespec="seconds")))
            new_id = cur.lastrowid
        return {"id": new_id, "message": "Employee added"}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Employee ID already exists")

@app.post("/api/submit")
def submit_job(job: JobIn):
    if job.job_type not in JOB_NAMES:
        raise HTTPException(400, "Invalid automation job")
    with db() as con:
        emp = con.execute("SELECT * FROM employees WHERE id=?", (job.employee_id,)).fetchone()
    if not emp:
        raise HTTPException(404, "Employee not found")
    emp = dict(emp)
    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")
    payload = {"job_id": job_id, "job_type": job.job_type, "employee": emp,
        "access_type": job.access_type, "ticket_category": job.ticket_category, "issue": job.issue}
    with db() as con:
        con.execute("""INSERT INTO jobs(id,employee_id,employee_name,employee_code,job_type,job_name,payload,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'Queued',?,?)""",
            (job_id, emp["id"], emp["first_name"]+" "+emp["last_name"], emp["employee_code"],
             job.job_type, JOB_NAMES[job.job_type], json.dumps(payload), now, now))
    try:
        publish_message(payload)
    except Exception as exc:
        with db() as con:
            con.execute("UPDATE jobs SET status='Broker Error',error=?,updated_at=? WHERE id=?",
                (str(exc), datetime.now().isoformat(timespec="seconds"), job_id))
        raise HTTPException(503, f"Could not publish to RabbitMQ: {exc}")
    return {"job_id": job_id, "message": "Message sent to RabbitMQ"}

@app.get("/api/jobs")
def jobs():
    with db() as con:
        rows = con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
    output = []
    for row in rows:
        d = dict(row)
        d["result"] = json.loads(d["result"]) if d["result"] else None
        output.append(d)
    return output

@app.get("/api/stats")
def stats():
    with db() as con:
        employees = con.execute("SELECT COUNT(*) n FROM employees").fetchone()["n"]
        total = con.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
        completed = con.execute("SELECT COUNT(*) n FROM jobs WHERE status='Completed'").fetchone()["n"]
        pending = con.execute("SELECT COUNT(*) n FROM jobs WHERE status IN ('Queued','Processing')").fetchone()["n"]
        failed = con.execute("SELECT COUNT(*) n FROM jobs WHERE status IN ('Failed','Broker Error')").fetchone()["n"]
    return {"employees": employees, "total": total, "completed": completed, "pending": pending, "failed": failed}
