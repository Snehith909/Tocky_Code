"""
VulnShop - INTENTIONALLY VULNERABLE demo app for testing security tools/plugins.
DO NOT deploy this on a public server. Run locally only.
Every "VULN #n" comment marks a deliberate security flaw.
"""
import os
import sqlite3
from flask import (Flask, request, redirect, render_template_string,
                   session, send_file, make_response, g)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
DB = "vulnshop.db"
os.makedirs("uploads", exist_ok=True)
os.makedirs("files", exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS comments;
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT,
                        email TEXT, role TEXT, secret_note TEXT);
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL);
    CREATE TABLE comments (id INTEGER PRIMARY KEY, author TEXT, body TEXT);
    -- VULN #2: passwords stored in plaintext
    INSERT INTO users VALUES (1,'admin','admin123','admin@vulnshop.local','admin','Admin API key: ADMIN-KEY-9999');
    INSERT INTO users VALUES (2,'alice','alice123','alice@vulnshop.local','user','Alice private note');
    INSERT INTO users VALUES (3,'bob','bob123','bob@vulnshop.local','user','Bob private note');
    INSERT INTO products VALUES (1,'Laptop',799.99),(2,'Phone',499.50),(3,'Headphones',59.00);
    """)
    db.commit()
    db.close()
    with open("files/readme.txt", "w") as f:
        f.write("Public file.\n")


BASE = """
<!doctype html><title>VulnShop</title>
<body style="font-family:sans-serif;max-width:800px;margin:2rem auto">
<h1>VulnShop <small style="color:red">(intentionally vulnerable)</small></h1>
<nav>
 <a href="/">Home</a> | <a href="/search">Search</a> | <a href="/comments">Comments</a> |
 <a href="/ping">Ping</a> | <a href="/download?file=readme.txt">Download</a> |
 <a href="/upload">Upload</a> | <a href="/login">Login</a>
</nav><hr>
{{ body|safe }}
</body>
"""


def page(body):
    return render_template_string(BASE, body=body)


@app.route("/")
def home():
    user = session.get("user")
    return page(f"<p>Welcome {user or 'guest'}!</p>")  # VULN #3: unescaped username (XSS)


# VULN #4: SQL injection in login (string concatenation)
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        u_clean = u.replace("'", "''")
        p_clean = p.replace("'", "''")
        q = f"SELECT * FROM users WHERE username='{u_clean}' AND password='{p_clean}'"
        try:
            row = get_db().execute(q).fetchone()
        except Exception as e:
            return page(f"<pre>SQL error: {e}\nQuery: {q}</pre>")  # VULN #5: verbose errors
        if row:
            session["user"] = row["username"]
            session["uid"] = row["id"]
            session["role"] = row["role"]
            return redirect("/")
        msg = "<p style='color:red'>Invalid login</p>"   # VULN #6: no rate limiting / lockout
    return page(msg + """
    <form method=post>
      <input name=username placeholder=username><br>
      <input name=password type=password placeholder=password><br>
      <button>Login</button>
    </form>""")


# VULN #7: SQL injection (UNION-able) + VULN #8: reflected XSS
@app.route("/search")
def search():
    q = request.args.get("q", "")
    out = ""
    if q:
        try:
            rows = get_db().execute(
                "SELECT name, price FROM products WHERE name LIKE ?", (f"%{q}%",)).fetchall()
        except Exception as e:
            return page(f"<pre>{e}</pre>")
        out = f"<h3>Results for: {q}</h3><ul>" + \
              "".join(f"<li>{r['name']} - ${r['price']}</li>" for r in rows) + "</ul>"
    return page(f"<form><input name=q value=''><button>Search</button></form>{out}")


# VULN #9: stored XSS, VULN #10: no CSRF token
@app.route("/comments", methods=["GET", "POST"])
def comments():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO comments (author, body) VALUES (?, ?)",
                   (session.get("user", "anon"), request.form.get("body", "")))
        db.commit()
        return redirect("/comments")
    rows = db.execute("SELECT * FROM comments").fetchall()
    items = "".join(f"<p><b>{r['author']}</b>: {r['body']}</p>" for r in rows)
    return page(f"<form method=post><input name=body><button>Post</button></form>{items}")


# VULN #11: IDOR - no check that the logged-in user owns this profile
@app.route("/profile/<int:uid>")
def profile(uid):
    if session.get("uid") != uid and session.get("role") != "admin":
        return page("Access denied"), 403
def profile(uid):
    r = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not r:
        return page("Not found"), 404
    return page(f"<h3>{r['username']}</h3><p>{r['email']}</p>"
                f"<p>Note: {r['secret_note']}</p><p>Password: {r['password']}</p>")


# VULN #12: command injection
@app.route("/ping", methods=["GET", "POST"])
def ping():
    out = ""
    if request.method == "POST":
        host = request.form.get("host", "")
        import subprocess
        res = subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True)
        out = "<pre>" + res.stdout + "</pre>"
    return page("<form method=post><input name=host placeholder='127.0.0.1'>"
                "<button>Ping</button></form>" + out)


# VULN #13: path traversal
@app.route("/download")
def download():
    name = request.args.get("file", "")
    filename = os.path.basename(name)
    safe_path = os.path.abspath(os.path.join("files", filename))
    if not safe_path.startswith(os.path.abspath("files")):
        return page("Access denied"), 403
    return send_file(safe_path)


# VULN #14: unrestricted file upload (no type check, original filename kept)
@app.route("/upload", methods=["GET", "POST"])
def upload():
    msg = ""
    if request.method == "POST":
        f = request.files["file"]
        from werkzeug.utils import secure_filename
        safe_name = secure_filename(f.filename)
        f.save(os.path.join("uploads", safe_name))
        msg = f"<p>Saved as uploads/{f.filename}</p>"
    return page(msg + "<form method=post enctype=multipart/form-data>"
                "<input type=file name=file><button>Upload</button></form>")


# VULN #15: open redirect
@app.route("/redirect")
def open_redirect():
    target = request.args.get("url", "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    return redirect(target)


# VULN #16: broken access control - admin page has no role check
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return page("Access denied: Admin role required"), 403
def admin():
    users = get_db().execute("SELECT * FROM users").fetchall()
    return page("<h3>Admin panel</h3>" +
                "".join(f"<p>{u['username']} / {u['password']}</p>" for u in users))


# VULN #17: sensitive info exposure
@app.route("/debug/config")
def debug_config():
    return {"status": "ok", "app": "VulnShop"}


# VULN #18: missing security headers + insecure cookie flags
@app.after_request
def headers(resp):
    resp.headers["Server"] = "VulnShop/1.0 (Flask debug)"
    return resp


if __name__ == "__main__":
    init_db()
    # VULN #19: debug mode on (Werkzeug console). Bound to localhost only for safety.
    app.run(host="127.0.0.1", port=5000, debug=False)
