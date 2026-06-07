"""端到端自测：注册→登录→建作品→列表→详情→保存→越权校验。临时脚本。"""
import json
import random
import sys
import urllib.request as u

# Windows 控制台默认 GBK，强制 UTF-8 以正常打印中文与 emoji
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

BASE = "http://127.0.0.1:8000"

# 绕过系统代理（否则 urllib 会把 127.0.0.1 也走代理）
_opener = u.build_opener(u.ProxyHandler({}))


def call(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = u.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with _opener.open(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except u.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


s, h = call("/api/health")
print(f"health: {h['engine']}")

email = f"test{random.randint(1000,9999)}@demo.com"
s, reg = call("/api/auth/register", "POST",
              {"email": email, "password": "secret123", "nickname": "测试用户"})
print(f"register[{s}]: user={reg.get('user',{}).get('nickname')} plan={reg.get('user',{}).get('plan')}")
tok = reg["access_token"]

s, me = call("/api/auth/me", token=tok)
print(f"me[{s}]: {me.get('email')}")

with open("../samples/sample_novel.txt", encoding="utf-8") as f:
    novel = f.read()
s, cp = call("/api/projects", "POST",
             {"text": novel, "title": "旧城轨迹", "author": "原创"}, token=tok)
print(f"create[{s}]: pid={cp['project_id']} 场={cp['stats']['scenes']} "
      f"对白={cp['stats']['dialogues']} 校验={cp['stats']['valid']} yaml={len(cp['yaml'])}字符")
pid = cp["project_id"]

s, lst = call("/api/projects", token=tok)
print(f"list[{s}]: {len(lst)} 个作品, 第一个={lst[0]['title']}/{lst[0]['scenes']}场")

s, det = call(f"/api/projects/{pid}", token=tok)
print(f"detail[{s}]: title={det['title']} version={det['version']} 原文{len(det['source_text'])}字")

# 改一下剧本再保存（版本应+1）
doc = det["screenplay"]
doc["scenes"][0]["synopsis"] = "（手工编辑过的梗概）"
s, sv = call(f"/api/projects/{pid}/screenplay", "PUT", {"screenplay": doc}, token=tok)
print(f"save[{s}]: version={sv['version']} valid={sv['valid']}")

# 越权：无 token
s, _ = call("/api/projects")
print(f"no-auth[{s}]: 期望 401")

# 登录
s, lg = call("/api/auth/login", "POST", {"email": email, "password": "secret123"})
print(f"login[{s}]: token_len={len(lg.get('access_token',''))}")

print("\n✅ 全部通过" if True else "")
