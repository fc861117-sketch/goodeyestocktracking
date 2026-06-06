import os
import sys
import subprocess
import json
import urllib.request
import base64
import hashlib
from datetime import datetime

# Configuration - token read from environment variable or fallback
TOKEN = os.environ.get("GITHUB_PAT", "")
OWNER = "fc861117-sketch"
REPO = "goodeyestocktracking"
BRANCH = "main"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOCAL_DIR, "data", "cron_run.log")

FILES_TO_CHECK = [
    "modules/stock_data.py",
    "modules/ai_analyzer.py",
    "modules/report_generator.py",
    "modules/transcriber.py",
    "modules/static_generator.py",
    "server.py",
    "static/app.js",
    "templates/dashboard.html",
    "docs/static/app.js",
    "docs/index.html",
    "docs/data.json",
    "docs/watchlist.json"
]

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def git_hash_object(data):
    sha = hashlib.sha1()
    header = f"blob {len(data)}".encode('utf-8') + b'\0'
    sha.update(header + data)
    return sha.hexdigest()

def get_remote_file_sha(path):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Mozilla/5.0"
        }
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        log(f"Error checking remote SHA for {path}: {e}")
        return None
    except Exception as e:
        log(f"Error checking remote SHA for {path}: {e}")
        return None

def upload_file_to_github(path, content_bytes, sha, message):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    encoded_content = base64.b64encode(content_bytes).decode('utf-8')
    
    payload = {
        "message": message,
        "content": encoded_content,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Authorization": f"token {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Mozilla/5.0"
        },
        method="PUT"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            log(f"[DEPLOYED] {path} (Commit: {res_data['commit']['sha'][:8]})")
            return True
    except Exception as e:
        log(f"[ERROR DEPLOY] {path}: {e}")
        return False

def run_analysis():
    log("Starting Gooaye Stock Analyzer update cycle...")
    try:
        # Run main.py analyze
        cmd = [sys.executable, "main.py", "analyze"]
        log(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=LOCAL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        log("Analysis command finished. Output:")
        for line in result.stdout.splitlines():
            log(f"  [main] {line}")
            
        if result.returncode != 0:
            log(f"Warning: analyze command returned non-zero exit code: {result.returncode}")
            
    except Exception as e:
        log(f"Error executing analysis: {e}")

def deploy_changes():
    log("Checking for modified files to deploy to GitHub...")
    deployed_count = 0
    
    for rel_path in FILES_TO_CHECK:
        local_path = os.path.join(LOCAL_DIR, rel_path.replace('/', os.sep))
        if not os.path.exists(local_path):
            continue
            
        with open(local_path, 'rb') as f:
            local_bytes = f.read()
            
        local_sha = git_hash_object(local_bytes)
        remote_sha = get_remote_file_sha(rel_path)
        
        if remote_sha == local_sha:
            continue
            
        log(f"Deploying modified file: {rel_path}")
        message = f"auto: update {os.path.basename(rel_path)} via scheduled task"
        success = upload_file_to_github(rel_path, local_bytes, remote_sha, message)
        if success:
            deployed_count += 1
            
    log(f"Deployment cycle finished. {deployed_count} files updated on GitHub.")

def generate_static():
    log("Generating static site files...")
    try:
        cmd = [sys.executable, "main.py", "generate-static"]
        result = subprocess.run(
            cmd,
            cwd=LOCAL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        for line in result.stdout.splitlines():
            log(f"  [static] {line}")
    except Exception as e:
        log(f"Error generating static site: {e}")

def main():
    run_analysis()
    generate_static()
    deploy_changes()
    log("Update cycle complete.")

if __name__ == "__main__":
    main()
