#!/usr/bin/env python3
"""
publish_skill.py — 将本地 Skill 目录发布到 GitHub Skill Registry

通过 GitHub Git Data API 实现：
1. 上传所有文件为 blob
2. 创建新 tree
3. 创建 commit
4. 更新分支 ref
5. 更新 registry.json

用法:
  python3 publish_skill.py \
    --skill-dir /tmp/skill-publish-tmp/my-skill \
    --token ghp_xxx \
    --repo sumn20/skill-registry \
    --branch main \
    --author harryxia
"""

import argparse
import base64
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("ERROR: requests 库未安装，请运行: pip3 install requests", file=sys.stderr)
    sys.exit(1)

API_BASE = "https://api.github.com"


def github_request(method, path, token, json_data=None, retry=2):
    """统一的 GitHub API 请求方法，带重试"""
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    for attempt in range(retry + 1):
        resp = getattr(requests, method)(url, headers=headers, json=json_data, timeout=30)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            wait = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60)) - int(time.time())
            print(f"  Rate limited, waiting {max(wait, 1)}s...")
            time.sleep(max(wait, 1))
            continue
        return resp
    return resp


def get_ref(token, repo, branch):
    """获取分支的 commit SHA"""
    resp = github_request("get", f"/repos/{repo}/git/ref/heads/{branch}", token)
    if resp.status_code != 200:
        raise Exception(f"获取分支 ref 失败: {resp.status_code} {resp.text}")
    return resp.json()["object"]["sha"]


def get_commit(token, repo, commit_sha):
    """获取 commit 的 tree SHA"""
    resp = github_request("get", f"/repos/{repo}/git/commits/{commit_sha}", token)
    if resp.status_code != 200:
        raise Exception(f"获取 commit 失败: {resp.status_code} {resp.text}")
    return resp.json()["tree"]["sha"]


def create_blob(token, repo, content_bytes):
    """创建 blob，返回 SHA"""
    encoded = base64.b64encode(content_bytes).decode("ascii")
    resp = github_request("post", f"/repos/{repo}/git/blobs", token, {
        "content": encoded,
        "encoding": "base64"
    })
    if resp.status_code != 201:
        raise Exception(f"创建 blob 失败: {resp.status_code} {resp.text}")
    return resp.json()["sha"]


def create_tree(token, repo, base_tree_sha, tree_items):
    """创建新 tree"""
    resp = github_request("post", f"/repos/{repo}/git/trees", token, {
        "base_tree": base_tree_sha,
        "tree": tree_items
    })
    if resp.status_code != 201:
        raise Exception(f"创建 tree 失败: {resp.status_code} {resp.text}")
    return resp.json()["sha"]


def create_commit(token, repo, message, tree_sha, parent_sha, author_name):
    """创建 commit"""
    resp = github_request("post", f"/repos/{repo}/git/commits", token, {
        "message": message,
        "tree": tree_sha,
        "parents": [parent_sha],
        "author": {
            "name": author_name,
            "email": f"{author_name}@tencent.com",
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "committer": {
            "name": "harryxia",
            "email": "harryxia@tencent.com",
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    })
    if resp.status_code != 201:
        raise Exception(f"创建 commit 失败: {resp.status_code} {resp.text}")
    return resp.json()["sha"]


def update_ref(token, repo, branch, commit_sha):
    """更新分支指向新 commit"""
    resp = github_request("patch", f"/repos/{repo}/git/refs/heads/{branch}", token, {
        "sha": commit_sha
    })
    if resp.status_code != 200:
        raise Exception(f"更新 ref 失败: {resp.status_code} {resp.text}")
    return resp.json()


def get_file_content(token, repo, path, branch="main"):
    """获取仓库中某个文件的内容"""
    resp = github_request("get", f"/repos/{repo}/contents/{path}?ref={branch}", token)
    if resp.status_code != 200:
        return None
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8")


def collect_files(skill_dir):
    """收集 skill 目录下所有文件"""
    files = []
    for root, _dirs, filenames in os.walk(skill_dir):
        for fname in filenames:
            if fname.startswith(".") or fname == "__pycache__" or fname.endswith(".pyc"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, skill_dir)
            files.append((rel_path, full_path))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="发布 Skill 到 GitHub Registry")
    parser.add_argument("--skill-dir", required=True, help="本地 Skill 目录路径")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token")
    parser.add_argument("--repo", default="sumn20/skill-registry", help="目标 GitHub 仓库")
    parser.add_argument("--branch", default="main", help="目标分支")
    parser.add_argument("--author", default="harryxia", help="作者名称")
    args = parser.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)
    skill_name = os.path.basename(skill_dir)

    if not os.path.isdir(skill_dir):
        print(f"ERROR: 目录不存在: {skill_dir}", file=sys.stderr)
        sys.exit(1)

    # 检查 metadata.json 存在
    metadata_path = os.path.join(skill_dir, "metadata.json")
    if not os.path.isfile(metadata_path):
        print("ERROR: 缺少 metadata.json，请先生成", file=sys.stderr)
        sys.exit(1)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    print(f"=== 发布 Skill: {skill_name} ===")
    print(f"  仓库: {args.repo}")
    print(f"  分支: {args.branch}")
    print(f"  作者: {args.author}")
    print()

    # 1. 收集文件
    files = collect_files(skill_dir)
    print(f"[1/6] 收集到 {len(files)} 个文件:")
    for rel, _ in files:
        print(f"  skills/{skill_name}/{rel}")
    print()

    # 2. 获取当前分支状态
    print("[2/6] 获取仓库当前状态...")
    commit_sha = get_ref(args.token, args.repo, args.branch)
    tree_sha = get_commit(args.token, args.repo, commit_sha)
    print(f"  当前 commit: {commit_sha[:12]}")
    print(f"  当前 tree:   {tree_sha[:12]}")
    print()

    # 3. 上传文件为 blob
    print(f"[3/6] 上传文件到 GitHub...")
    tree_items = []
    for i, (rel_path, full_path) in enumerate(files, 1):
        with open(full_path, "rb") as f:
            content = f.read()
        blob_sha = create_blob(args.token, args.repo, content)
        github_path = f"skills/{skill_name}/{rel_path}"
        tree_items.append({
            "path": github_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha
        })
        print(f"  [{i}/{len(files)}] {rel_path} ({len(content)} bytes) -> {blob_sha[:12]}")
    print()

    # 4. 创建 tree 和 commit (skill 文件)
    print("[4/6] 创建 commit (skill 文件)...")
    new_tree_sha = create_tree(args.token, args.repo, tree_sha, tree_items)
    skill_commit_sha = create_commit(
        args.token, args.repo,
        f"feat: add skill '{metadata.get('displayName', skill_name)}' by {args.author}",
        new_tree_sha, commit_sha, args.author
    )
    update_ref(args.token, args.repo, args.branch, skill_commit_sha)
    print(f"  Commit: {skill_commit_sha[:12]}")
    print()

    # 5. 更新 registry.json
    print("[5/6] 更新 registry.json...")
    registry_content = get_file_content(args.token, args.repo, "registry.json", args.branch)

    if registry_content:
        registry = json.loads(registry_content)
    else:
        registry = {"version": "1.0.0", "lastUpdated": "", "skillCount": 0, "skills": []}

    # 移除同名旧条目（如果是更新）
    registry["skills"] = [s for s in registry["skills"] if s["name"] != skill_name]

    # 添加新条目
    entry = dict(metadata)
    entry["path"] = f"skills/{skill_name}"
    entry["fileCount"] = len(files)
    entry["files"] = sorted([rel for rel, _ in files])
    registry["skills"].append(entry)
    registry["skills"].sort(key=lambda s: s["name"])
    registry["skillCount"] = len(registry["skills"])
    registry["lastUpdated"] = time.strftime("%Y-%m-%d")

    registry_json = json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    registry_blob_sha = create_blob(args.token, args.repo, registry_json.encode("utf-8"))

    # 新 commit 更新 registry.json
    commit_sha2 = get_ref(args.token, args.repo, args.branch)
    tree_sha2 = get_commit(args.token, args.repo, commit_sha2)
    registry_tree_sha = create_tree(args.token, args.repo, tree_sha2, [{
        "path": "registry.json",
        "mode": "100644",
        "type": "blob",
        "sha": registry_blob_sha
    }])
    registry_commit_sha = create_commit(
        args.token, args.repo,
        f"chore: update registry.json (add {skill_name})",
        registry_tree_sha, commit_sha2, "harryxia"
    )
    update_ref(args.token, args.repo, args.branch, registry_commit_sha)
    print(f"  Registry 更新完成: {registry_commit_sha[:12]}")
    print(f"  当前 skill 总数: {registry['skillCount']}")
    print()

    # 6. 完成
    print("[6/6] 发布完成！")
    print(f"  仓库: https://github.com/{args.repo}/tree/{args.branch}/skills/{skill_name}")
    print(f"  商店: https://sumn20.github.io/skill-registry/")
    print()

    # 输出 JSON 结果供调用方解析
    result = {
        "success": True,
        "skill_name": skill_name,
        "display_name": metadata.get("displayName", skill_name),
        "description": metadata.get("description", ""),
        "category": metadata.get("category", "tool"),
        "tags": metadata.get("tags", []),
        "file_count": len(files),
        "repo_url": f"https://github.com/{args.repo}/tree/{args.branch}/skills/{skill_name}",
        "store_url": "https://sumn20.github.io/skill-registry/",
        "commit_sha": registry_commit_sha
    }
    print("--- JSON_RESULT ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
