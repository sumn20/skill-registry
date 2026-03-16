/**
 * Skill Upload API — Cloudflare Worker
 * 
 * POST /upload — 接收 Skill ZIP + metadata → 提交到 GitHub 仓库
 * 
 * 环境变量 (在 Cloudflare Dashboard Settings > Variables and Secrets 配置):
 *   GITHUB_TOKEN  — GitHub Fine-grained Personal Access Token (必须)
 *   UPLOAD_SECRET — 上传密码 (可选, 防止陌生人上传)
 */

const REPO_OWNER = 'sumn20';
const REPO_NAME = 'skill-registry';
const BRANCH = 'main';

export default {
  async fetch(request, env) {
    // CORS
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors() });
    }
    if (request.method !== 'POST') {
      return reply({ error: 'Method not allowed' }, 405);
    }
    if (new URL(request.url).pathname !== '/upload') {
      return reply({ error: 'Not found' }, 404);
    }

    try {
      // Optional upload secret
      if (env.UPLOAD_SECRET) {
        if (request.headers.get('X-Upload-Secret') !== env.UPLOAD_SECRET) {
          return reply({ error: '上传密码错误' }, 403);
        }
      }

      const form = await request.formData();
      const file = form.get('file');
      const metaStr = form.get('metadata');
      if (!file) return reply({ error: '请上传 ZIP 文件' }, 400);
      if (!metaStr) return reply({ error: '缺少 metadata' }, 400);

      let meta;
      try { meta = JSON.parse(metaStr); } catch { return reply({ error: 'metadata JSON 格式无效' }, 400); }

      for (const f of ['name', 'displayName', 'description', 'version', 'author', 'category']) {
        if (!meta[f]) return reply({ error: `metadata 缺少字段: ${f}` }, 400);
      }
      if (!/^[a-z0-9][a-z0-9-]*$/.test(meta.name)) {
        return reply({ error: 'name 只允许小写字母、数字和连字符' }, 400);
      }

      const token = env.GITHUB_TOKEN;
      if (!token) return reply({ error: 'Server config error: no GITHUB_TOKEN' }, 500);

      // ── 1. 用 JSZip 解压 (Workers 没有内置 JSZip, 我们用轻量 ZIP 解析) ──
      const zipBuf = new Uint8Array(await file.arrayBuffer());
      const entries = await unzip(zipBuf);

      const prefix = commonPrefix(entries.filter(e => !e.dir).map(e => e.name));
      const skillName = meta.name;
      const fileList = [];
      const fileContents = []; // { path, data(Uint8Array) }

      for (const entry of entries) {
        if (entry.dir) continue;
        let rel = entry.name;
        if (prefix) rel = rel.slice(prefix.length);
        if (!rel || rel.startsWith('__MACOSX') || rel.startsWith('.DS_Store')) continue;
        fileList.push(rel);
        fileContents.push({ path: `skills/${skillName}/${rel}`, data: entry.data });
      }

      if (fileContents.length === 0) return reply({ error: 'ZIP 中没有有效文件' }, 400);

      // ── 2. GitHub Git Data API: 创建 blobs → tree → commit → update ref ──
      const api = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}`;
      const gh = ghClient(api, token);

      // 2a. 获取当前 HEAD
      const ref = await gh.get(`/git/refs/heads/${BRANCH}`);
      const headSha = ref.object.sha;
      const commit = await gh.get(`/git/commits/${headSha}`);
      const baseTree = commit.tree.sha;

      // 2b. 批量创建 blobs
      const treeItems = [];
      for (const fc of fileContents) {
        const blob = await gh.post('/git/blobs', {
          content: b64(fc.data),
          encoding: 'base64'
        });
        treeItems.push({ path: fc.path, mode: '100644', type: 'blob', sha: blob.sha });
      }

      // 2c. 更新 registry.json
      const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/registry.json`;
      let registry = { version: '1.0.0', lastUpdated: '', skillCount: 0, skills: [] };
      try {
        const r = await fetch(rawUrl);
        if (r.ok) registry = await r.json();
      } catch {}

      registry.skills = registry.skills.filter(s => s.name !== skillName);
      registry.skills.push({
        name: meta.name,
        displayName: meta.displayName,
        description: meta.description,
        version: meta.version,
        author: meta.author,
        category: meta.category,
        tags: meta.tags || [],
        dependencies: meta.dependencies || [],
        requirements: meta.requirements || { python: false, env_vars: [] },
        path: `skills/${skillName}`,
        fileCount: fileList.length,
        files: fileList.sort()
      });
      registry.skillCount = registry.skills.length;
      registry.lastUpdated = new Date().toISOString().split('T')[0];

      const regBlob = await gh.post('/git/blobs', {
        content: JSON.stringify(registry, null, 2) + '\n',
        encoding: 'utf-8'
      });
      treeItems.push({ path: 'registry.json', mode: '100644', type: 'blob', sha: regBlob.sha });

      // 2d. 创建 tree
      const tree = await gh.post('/git/trees', { base_tree: baseTree, tree: treeItems });

      // 2e. 创建 commit
      const msg = `feat: publish skill "${meta.displayName}" (${skillName}) v${meta.version}`;
      const newCommit = await gh.post('/git/commits', {
        message: msg, tree: tree.sha, parents: [headSha]
      });

      // 2f. 更新 ref
      await gh.patch(`/git/refs/heads/${BRANCH}`, { sha: newCommit.sha });

      return reply({
        success: true,
        message: `Skill "${meta.displayName}" 发布成功！`,
        commit: newCommit.sha.slice(0, 7),
        files: fileList.length,
        url: `https://github.com/${REPO_OWNER}/${REPO_NAME}/tree/${BRANCH}/skills/${skillName}`
      });

    } catch (err) {
      console.error('Upload error:', err);
      return reply({ error: `服务器错误: ${err.message}` }, 500);
    }
  }
};

/* ═══════ Helpers ═══════ */

function cors() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Upload-Secret',
    'Access-Control-Max-Age': '86400',
  };
}

function reply(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...cors() }
  });
}

function ghClient(api, token) {
  const hdrs = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'skill-upload-worker',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  async function req(method, path, body) {
    const opts = { method, headers: { ...hdrs } };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(`${api}${path}`, opts);
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`GitHub ${method} ${path} → ${r.status}: ${t}`);
    }
    return r.json();
  }

  return {
    get: (p) => req('GET', p),
    post: (p, b) => req('POST', p, b),
    patch: (p, b) => req('PATCH', p, b),
  };
}

function b64(uint8) {
  let s = '';
  for (let i = 0; i < uint8.length; i++) s += String.fromCharCode(uint8[i]);
  return btoa(s);
}

/* ═══════ Minimal ZIP Parser (async, supports deflate via DecompressionStream) ═══════ */

async function unzip(data) {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);

  // Find EOCD
  let eocd = -1;
  for (let i = data.length - 22; i >= Math.max(0, data.length - 65558); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd === -1) throw new Error('无效的 ZIP 文件 (找不到 EOCD)');

  const cdOffset = view.getUint32(eocd + 16, true);
  const cdCount = view.getUint16(eocd + 10, true);

  const entries = [];
  let pos = cdOffset;

  for (let i = 0; i < cdCount; i++) {
    if (view.getUint32(pos, true) !== 0x02014b50) break;

    const method = view.getUint16(pos + 10, true);
    const compSize = view.getUint32(pos + 20, true);
    const nameLen = view.getUint16(pos + 28, true);
    const extraLen = view.getUint16(pos + 30, true);
    const commentLen = view.getUint16(pos + 32, true);
    const localOff = view.getUint32(pos + 42, true);
    const name = new TextDecoder().decode(data.slice(pos + 46, pos + 46 + nameLen));

    pos += 46 + nameLen + extraLen + commentLen;

    if (name.endsWith('/')) {
      entries.push({ name, dir: true, data: null });
      continue;
    }

    // Read local header to find data offset
    const lNameLen = view.getUint16(localOff + 26, true);
    const lExtraLen = view.getUint16(localOff + 28, true);
    const dataStart = localOff + 30 + lNameLen + lExtraLen;
    const raw = data.slice(dataStart, dataStart + compSize);

    let fileData;
    if (method === 0) {
      fileData = raw;
    } else if (method === 8) {
      fileData = await inflate(raw);
    } else {
      continue; // skip unsupported
    }

    entries.push({ name, dir: false, data: fileData });
  }

  return entries;
}

async function inflate(compressed) {
  const ds = new DecompressionStream('deflate-raw');
  const writer = ds.writable.getWriter();
  writer.write(compressed);
  writer.close();

  const reader = ds.readable.getReader();
  const chunks = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((a, c) => a + c.length, 0);
  const result = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { result.set(c, off); off += c.length; }
  return result;
}

function commonPrefix(paths) {
  if (paths.length === 0) return '';
  const parts = paths[0].split('/');
  let prefix = '';
  for (let i = 0; i < parts.length - 1; i++) {
    const cand = parts.slice(0, i + 1).join('/') + '/';
    if (paths.every(p => p.startsWith(cand))) prefix = cand;
    else break;
  }
  return prefix;
}
