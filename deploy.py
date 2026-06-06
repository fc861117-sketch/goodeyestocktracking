import os, json, urllib.request, base64, hashlib

TOKEN = os.environ.get("GITHUB_PAT", "")
OWNER = 'fc861117-sketch'
REPO = 'goodeyestocktracking'
BRANCH = 'main'
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = [
    'server.py',
    'modules/static_generator.py',
    'static/app.js',
    'templates/dashboard.html',
    'cron_update.py',
    'docs/static/app.js',
    'docs/index.html',
    'docs/data.json',
]

def git_hash(data):
    sha = hashlib.sha1()
    sha.update(('blob ' + str(len(data))).encode() + b'\x00' + data)
    return sha.hexdigest()

def get_remote_sha(path):
    url = 'https://api.github.com/repos/{}/{}/contents/{}?ref={}'.format(OWNER, REPO, path, BRANCH)
    req = urllib.request.Request(url, headers={
        'Authorization': 'token ' + TOKEN,
        'User-Agent': 'python'
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())['sha']
    except Exception:
        return None

def upload(path, content_bytes, sha, msg):
    url = 'https://api.github.com/repos/{}/{}/contents/{}'.format(OWNER, REPO, path)
    payload = {
        'message': msg,
        'content': base64.b64encode(content_bytes).decode(),
        'branch': BRANCH
    }
    if sha:
        payload['sha'] = sha
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': 'token ' + TOKEN,
            'Content-Type': 'application/json',
            'User-Agent': 'python'
        },
        method='PUT'
    )
    try:
        with urllib.request.urlopen(req) as r:
            res = json.loads(r.read())
            commit_sha = res['commit']['sha'][:8]
            print('[OK] {} -> {}'.format(path, commit_sha))
            return True
    except Exception as e:
        print('[FAIL] {}: {}'.format(path, e))
        return False

total_deployed = 0
for rel in FILES:
    local_path = os.path.join(LOCAL_DIR, rel.replace('/', os.sep))
    if not os.path.exists(local_path):
        print('[SKIP] {} not found'.format(rel))
        continue
    with open(local_path, 'rb') as f:
        data = f.read()
    local_sha = git_hash(data)
    remote_sha = get_remote_sha(rel)
    if remote_sha == local_sha:
        print('[SAME] {} unchanged'.format(rel))
        continue
    print('[UPLOADING] {}...'.format(rel))
    success = upload(rel, data, remote_sha, 'auto: update {}'.format(os.path.basename(rel)))
    if success:
        total_deployed += 1

print('Done. {} files deployed.'.format(total_deployed))
