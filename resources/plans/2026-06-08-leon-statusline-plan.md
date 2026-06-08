# leon-statusline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一個跨平台（mac/Win/Linux）、可散佈的 Claude Code 狀態列 plugin `leon-statusline`，顯示 4 行資訊面板，永不崩潰。

**Architecture:** 純 Node.js ESM。邏輯拆成單一職責純函式模組（`src/*.mjs`），由 `statusline.mjs` 進入點讀 stdin、組裝、永遠 `exit 0`。所有計算在本機、零執行期依賴、零模型 token。git 與設定計數走 `session_id` 快取。

**Tech Stack:** Node.js（ESM `.mjs`）、Vitest（dev-only 測試）、Claude Code plugin/marketplace 機制。

**Repo 位置:** 獨立 git repo `C:/Users/LIN HONG/Desktop/leon-statusline/`（與 Project_01 平行、不巢狀）。以下路徑皆相對此 repo root。

**設計依據:** `Project_01/resources/specs/2026-06-08-leon-statusline-design.md`。

---

## 檔案結構

```
leon-statusline/                       ← repo root（兼 marketplace）
├── .claude-plugin/marketplace.json    ← marketplace 宣告
├── README.md                          ← repo 說明
└── leon-statusline/                   ← plugin 本體（${CLAUDE_PLUGIN_ROOT}）
    ├── .claude-plugin/plugin.json     ← plugin manifest（含 statusLine 命令）
    ├── package.json                   ← dev: vitest
    ├── vitest.config.mjs
    ├── statusline.mjs                 ← 進入點：讀 stdin → buildOutput → exit 0
    ├── src/
    │   ├── color.mjs    colorize / gradientColor / gradientBar
    │   ├── format.mjs   fmtDuration / resetCountdown / shortPath / attr / joinLine
    │   ├── input.mjs    parseInput
    │   ├── cache.mjs    cacheDir / withCache
    │   ├── git.mjs      gitInfo
    │   ├── count.mjs    countInfra
    │   └── render.mjs   renderLine1..4 / buildOutput
    └── tests/
        ├── color.test.mjs
        ├── format.test.mjs
        ├── input.test.mjs
        ├── cache.test.mjs
        ├── git.test.mjs
        ├── count.test.mjs
        ├── render.test.mjs
        └── integration.test.mjs
```

**模組職責邊界**：`color`/`format`/`input` 為零 IO 純函式；`cache`/`git`/`count` 為有 IO（檔案/子程序）但皆容錯回傳；`render` 組裝純函式 + 注入 IO 結果；`statusline.mjs` 只負責 stdin/stdout/exit。

> 註：spec 寫「單檔」，此處為了**可測試性**（你要求完整測試）拆成模組 + 進入點，屬合理細化。

---

## Task 1: Repo scaffold

**Files:**
- Create: `C:/Users/LIN HONG/Desktop/leon-statusline/` 全部骨架

- [ ] **Step 1: 建 repo 與目錄**

Run（PowerShell）:
```powershell
cd "C:/Users/LIN HONG/Desktop"
New-Item -ItemType Directory leon-statusline/leon-statusline/src -Force
New-Item -ItemType Directory leon-statusline/leon-statusline/tests -Force
New-Item -ItemType Directory leon-statusline/leon-statusline/.claude-plugin -Force
New-Item -ItemType Directory leon-statusline/.claude-plugin -Force
cd leon-statusline
git init
```

- [ ] **Step 2: 寫 `leon-statusline/package.json`**

```json
{
  "name": "leon-statusline",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": { "test": "vitest run" },
  "devDependencies": { "vitest": "^2.1.0" }
}
```

- [ ] **Step 3: 寫 `leon-statusline/vitest.config.mjs`**

```js
import { defineConfig } from 'vitest/config'
export default defineConfig({ test: { include: ['tests/**/*.test.mjs'] } })
```

- [ ] **Step 4: 寫 `leon-statusline/.claude-plugin/plugin.json`**（statusLine schema 於 Task 13 再驗證/微調）

```json
{
  "name": "leon-statusline",
  "version": "1.0.0",
  "description": "Cross-platform 4-line Claude Code status line",
  "statusLine": { "type": "command", "command": "node ${CLAUDE_PLUGIN_ROOT}/statusline.mjs" }
}
```

- [ ] **Step 5: 寫 `.claude-plugin/marketplace.json`**（repo root）

```json
{
  "name": "leon-statusline-marketplace",
  "owner": "leon13018",
  "plugins": [ { "name": "leon-statusline", "source": "./leon-statusline" } ]
}
```

- [ ] **Step 6: 寫 `leon-statusline/.gitignore`**

```
node_modules/
```

- [ ] **Step 7: 裝 dev 依賴並確認 vitest 可跑**

Run: `cd leon-statusline && npm install`
Expected: 安裝 vitest，無錯。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold leon-statusline plugin + marketplace"
```
> 註：本 repo 為新空 repo，`git add -A` 安全（與 Project_01 的紅線無關，那條紅線只適用 Project_01）。

---

## Task 2: color.mjs（colorize / gradientColor / gradientBar）

**Files:**
- Create: `leon-statusline/src/color.mjs`
- Test: `leon-statusline/tests/color.test.mjs`

- [ ] **Step 1: 寫失敗測試 `tests/color.test.mjs`**

```js
import { describe, it, expect } from 'vitest'
import { colorize, gradientColor, gradientBar } from '../src/color.mjs'

const strip = s => s.replace(/\x1b\[[0-9;]*m/g, '')

describe('colorize', () => {
  it('wraps text in truecolor escape + reset', () => {
    expect(colorize('x', [1, 2, 3])).toBe('\x1b[38;2;1;2;3mx\x1b[0m')
  })
})

describe('gradientColor', () => {
  it('green at 0, red at 1', () => {
    expect(gradientColor(0)).toEqual([0, 200, 80])
    expect(gradientColor(1)).toEqual([220, 40, 40])
  })
})

describe('gradientBar', () => {
  it('returns empty for null pct', () => {
    expect(gradientBar(null)).toBe('')
  })
  it('renders width blocks + percent suffix', () => {
    const out = strip(gradientBar(50, 10))
    expect(out.match(/█/g).length).toBe(5)
    expect(out.match(/░/g).length).toBe(5)
    expect(out.endsWith('50%')).toBe(true)
  })
  it('clamps over 100', () => {
    expect(strip(gradientBar(150, 10))).toContain('100%')
  })
})
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npm test -- tests/color.test.mjs`
Expected: FAIL（找不到模組 / 函式）

- [ ] **Step 3: 實作 `src/color.mjs`**

```js
export function colorize(text, [r, g, b]) {
  return `\x1b[38;2;${r};${g};${b}m${text}\x1b[0m`
}

export function gradientColor(t) {
  const x = Math.max(0, Math.min(1, t))
  const lerp = (a, b, k) => Math.round(a + (b - a) * k)
  if (x <= 0.5) {
    const k = x / 0.5
    return [lerp(0, 220, k), lerp(200, 200, k), lerp(80, 0, k)]
  }
  const k = (x - 0.5) / 0.5
  return [lerp(220, 220, k), lerp(200, 40, k), lerp(0, 40, k)]
}

export function gradientBar(pct, width = 20) {
  if (pct == null || !Number.isFinite(pct)) return ''
  const p = Math.max(0, Math.min(100, pct))
  const filled = Math.round((p / 100) * width)
  let bar = ''
  for (let i = 0; i < width; i++) {
    if (i < filled) {
      const t = width > 1 ? i / (width - 1) : 0
      bar += colorize('█', gradientColor(t))
    } else {
      bar += colorize('░', [60, 60, 60])
    }
  }
  return `${bar} ${Math.round(p)}%`
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `npm test -- tests/color.test.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/color.mjs tests/color.test.mjs
git commit -m "feat: color helpers (colorize, gradient bar)"
```

---

## Task 3: format.mjs（fmtDuration / resetCountdown / shortPath / attr / joinLine）

**Files:**
- Create: `leon-statusline/src/format.mjs`
- Test: `leon-statusline/tests/format.test.mjs`

- [ ] **Step 1: 寫失敗測試 `tests/format.test.mjs`**

```js
import { describe, it, expect } from 'vitest'
import { fmtDuration, resetCountdown, shortPath, attr, joinLine } from '../src/format.mjs'

const strip = s => s.replace(/\x1b\[[0-9;]*m/g, '')

describe('fmtDuration', () => {
  it('under 1 minute -> <1m', () => expect(fmtDuration(30_000)).toBe('<1m'))
  it('minutes only', () => expect(fmtDuration(14 * 60_000)).toBe('14m'))
  it('hours+minutes', () => expect(fmtDuration((2 * 60 + 5) * 60_000)).toBe('2h5m'))
  it('days+hours+minutes', () => expect(fmtDuration(((1 * 24 + 3) * 60 + 5) * 60_000)).toBe('1d3h5m'))
  it('omits zero middle units', () => expect(fmtDuration((24 * 60 + 5) * 60_000)).toBe('1d5m'))
  it('invalid -> empty', () => expect(fmtDuration(null)).toBe(''))
})

describe('resetCountdown', () => {
  it('future -> duration', () => expect(resetCountdown(1000 + 3600 + 23 * 60, 1000)).toBe('1h23m'))
  it('past/now -> 0m', () => expect(resetCountdown(1000, 2000)).toBe('0m'))
  it('invalid -> empty', () => expect(resetCountdown(null, 1000)).toBe(''))
})

describe('shortPath', () => {
  it('replaces home with ~', () =>
    expect(shortPath('/home/leon/Desktop/Project_01', '/home/leon')).toBe('~/Desktop/Project_01'))
  it('collapses when deeper than 3 segments', () =>
    expect(shortPath('/home/leon/a/b/c/proj', '/home/leon')).toBe('~/…/c/proj'))
  it('handles windows backslashes', () =>
    expect(shortPath('C:\\Users\\leon\\Desktop\\Project_01', 'C:\\Users\\leon')).toBe('~/Desktop/Project_01'))
  it('empty -> empty', () => expect(shortPath('', '/home/leon')).toBe(''))
})

describe('attr', () => {
  it('hides when value empty/null', () => {
    expect(attr('token:', '')).toBe('')
    expect(attr('token:', null)).toBe('')
  })
  it('renders label+value, strips to plain', () => {
    expect(strip(attr('token:', '15.5k'))).toBe('token:15.5k')
  })
})

describe('joinLine', () => {
  it('drops empties and 2-space joins', () => expect(joinLine(['a', '', 'b'])).toBe('a  b'))
  it('all empty -> empty', () => expect(joinLine(['', null])).toBe(''))
})
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npm test -- tests/format.test.mjs`
Expected: FAIL

- [ ] **Step 3: 實作 `src/format.mjs`**

```js
import { colorize } from './color.mjs'

export function fmtDuration(ms) {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return ''
  const totalMin = Math.floor(ms / 60_000)
  if (totalMin < 1) return '<1m'
  const d = Math.floor(totalMin / 1440)
  const h = Math.floor((totalMin % 1440) / 60)
  const m = totalMin % 60
  let out = ''
  if (d) out += `${d}d`
  if (h) out += `${h}h`
  if (m) out += `${m}m`
  return out
}

export function resetCountdown(epochSec, nowSec) {
  if (epochSec == null || !Number.isFinite(epochSec)) return ''
  const diffMs = (epochSec - nowSec) * 1000
  if (diffMs <= 0) return '0m'
  return fmtDuration(diffMs) || '0m'
}

export function shortPath(absPath, homeDir) {
  if (!absPath) return ''
  let p = String(absPath).replace(/\\/g, '/').replace(/\/+$/, '')
  if (homeDir) {
    const h = String(homeDir).replace(/\\/g, '/').replace(/\/+$/, '')
    if (h && (p === h || p.startsWith(h + '/'))) p = '~' + p.slice(h.length)
  }
  const tokens = p.split('/').filter(Boolean)
  if (tokens.length <= 3) return p
  return `${tokens[0]}/…/${tokens.slice(-2).join('/')}`
}

// 條件顯示單位：value 為空 => 回 ''（整個 attribute 含標題隱藏）
export function attr(label, value, rgb = null) {
  if (value == null || value === '') return ''
  const text = `${label}${value}`
  return rgb ? colorize(text, rgb) : text
}

export function joinLine(parts) {
  const kept = parts.filter(p => p && p.length)
  return kept.join('  ')
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `npm test -- tests/format.test.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/format.mjs tests/format.test.mjs
git commit -m "feat: format helpers (duration, countdown, path, attr, joinLine)"
```

---

## Task 4: input.mjs（parseInput）

**Files:**
- Create: `leon-statusline/src/input.mjs`
- Test: `leon-statusline/tests/input.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/input.test.mjs`**

```js
import { describe, it, expect } from 'vitest'
import { parseInput } from '../src/input.mjs'

describe('parseInput', () => {
  it('parses valid json', () => expect(parseInput('{"a":1}')).toEqual({ a: 1 }))
  it('bad json -> {}', () => expect(parseInput('not json')).toEqual({}))
  it('empty -> {}', () => expect(parseInput('')).toEqual({}))
})
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npm test -- tests/input.test.mjs` → FAIL

- [ ] **Step 3: 實作 `src/input.mjs`**

```js
export function parseInput(text) {
  try {
    const v = JSON.parse(text)
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}
```

- [ ] **Step 4: 跑測試** → PASS

- [ ] **Step 5: Commit**

```bash
git add src/input.mjs tests/input.test.mjs
git commit -m "feat: parseInput (null-safe stdin json)"
```

---

## Task 5: cache.mjs（cacheDir / withCache）

**Files:**
- Create: `leon-statusline/src/cache.mjs`
- Test: `leon-statusline/tests/cache.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/cache.test.mjs`**

```js
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { withCache } from '../src/cache.mjs'

let dir
beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'lsl-')) })
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

describe('withCache', () => {
  it('runs fn first time, caches within ttl', () => {
    let calls = 0
    const fn = () => (++calls, 'v')
    expect(withCache('sid', 'k', 1000, fn, 5000, dir)).toBe('v')
    expect(withCache('sid', 'k', 1000, fn, 5500, dir)).toBe('v')
    expect(calls).toBe(1)
  })
  it('re-runs after ttl expires', () => {
    let calls = 0
    const fn = () => (++calls, calls)
    withCache('sid', 'k', 1000, fn, 5000, dir)
    expect(withCache('sid', 'k', 1000, fn, 7000, dir)).toBe(2)
  })
  it('fn throw -> returns last cached or null', () => {
    expect(withCache('sid', 'k', 1000, () => { throw new Error() }, 1, dir)).toBe(null)
  })
})
```

- [ ] **Step 2: 跑測試確認失敗** → FAIL

- [ ] **Step 3: 實作 `src/cache.mjs`**

```js
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

export function cacheDir() {
  const base = process.env.CLAUDE_PLUGIN_DATA
    ? join(process.env.CLAUDE_PLUGIN_DATA, 'leon-statusline')
    : join(homedir(), '.claude', 'leon-statusline')
  try { mkdirSync(base, { recursive: true }) } catch {}
  return base
}

const sanitize = s => String(s || 'nosession').replace(/[^a-zA-Z0-9_-]/g, '_')

export function withCache(sessionId, key, ttlMs, fn, now = Date.now(), dir = cacheDir()) {
  const file = join(dir, `cache-${sanitize(sessionId)}.json`)
  let store = {}
  try { store = JSON.parse(readFileSync(file, 'utf8')) || {} } catch {}
  const entry = store[key]
  if (entry && (now - entry.t) < ttlMs) return entry.v
  let v
  try { v = fn() } catch { v = entry ? entry.v : null }
  store[key] = { t: now, v }
  try { writeFileSync(file, JSON.stringify(store)) } catch {}
  return v
}
```

- [ ] **Step 4: 跑測試** → PASS

- [ ] **Step 5: Commit**

```bash
git add src/cache.mjs tests/cache.test.mjs
git commit -m "feat: withCache (session-keyed file cache, ttl, never-throw)"
```

---

## Task 6: git.mjs（gitInfo）

**Files:**
- Create: `leon-statusline/src/git.mjs`
- Test: `leon-statusline/tests/git.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/git.test.mjs`**（注入 runner，不碰真 git）

```js
import { describe, it, expect } from 'vitest'
import { gitInfo } from '../src/git.mjs'

function fakeRunner(map) {
  return (args) => {
    const key = args.join(' ')
    return key in map ? map[key] : null
  }
}

describe('gitInfo', () => {
  it('not a repo -> null', () => {
    expect(gitInfo('/x', fakeRunner({}))).toBe(null)
  })
  it('parses branch, staged, modified, untracked, ahead/behind', () => {
    const r = fakeRunner({
      'rev-parse --abbrev-ref HEAD': 'main',
      'status --porcelain': 'M  a.js\n M b.js\n?? c.js',
      'rev-list --left-right --count @{u}...HEAD': '2\t1',
    })
    expect(gitInfo('/x', r)).toEqual({ branch: 'main', staged: 1, modified: 2, ahead: 1, behind: 2 })
  })
  it('clean repo, no upstream', () => {
    const r = fakeRunner({
      'rev-parse --abbrev-ref HEAD': 'main',
      'status --porcelain': '',
    })
    expect(gitInfo('/x', r)).toEqual({ branch: 'main', staged: 0, modified: 0, ahead: 0, behind: 0 })
  })
})
```

- [ ] **Step 2: 跑測試確認失敗** → FAIL

- [ ] **Step 3: 實作 `src/git.mjs`**

```js
import { spawnSync } from 'node:child_process'

function defaultRunner(args, cwd) {
  const r = spawnSync('git', ['--no-optional-locks', ...args], { cwd, encoding: 'utf8', timeout: 2000 })
  if (r.error || r.status !== 0) return null
  return r.stdout.trim()
}

export function gitInfo(cwd, runner = defaultRunner) {
  try {
    const branch = runner(['rev-parse', '--abbrev-ref', 'HEAD'], cwd)
    if (!branch) return null
    const porcelain = runner(['status', '--porcelain'], cwd) ?? ''
    let staged = 0, modified = 0
    for (const line of porcelain.split('\n')) {
      if (!line) continue
      const x = line[0], y = line[1]
      if (x === '?' && y === '?') { modified++; continue }
      if (x !== ' ' && x !== '?') staged++
      if (y !== ' ' && y !== '?') modified++
    }
    let ahead = 0, behind = 0
    const ab = runner(['rev-list', '--left-right', '--count', '@{u}...HEAD'], cwd)
    if (ab) {
      const [b, a] = ab.split(/\s+/).map(n => parseInt(n, 10) || 0)
      behind = b; ahead = a
    }
    return { branch, staged, modified, ahead, behind }
  } catch {
    return null
  }
}
```

- [ ] **Step 4: 跑測試** → PASS

- [ ] **Step 5: Commit**

```bash
git add src/git.mjs tests/git.test.mjs
git commit -m "feat: gitInfo (branch/staged/modified/ahead/behind, injectable runner)"
```

---

## Task 7: count.mjs（countInfra）

**Files:**
- Create: `leon-statusline/src/count.mjs`
- Test: `leon-statusline/tests/count.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/count.test.mjs`**（建臨時 fixture 目錄）

```js
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { countClaudeMd, countDirFiles, countMemory } from '../src/count.mjs'

let root
beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'lslc-')) })
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

function touch(rel) {
  const f = join(root, rel)
  mkdirSync(join(f, '..'), { recursive: true })
  writeFileSync(f, '')
}

describe('countClaudeMd', () => {
  it('counts recursively, excludes node_modules/.git', () => {
    touch('CLAUDE.md'); touch('sub/CLAUDE.md')
    touch('node_modules/pkg/CLAUDE.md'); touch('.git/CLAUDE.md')
    expect(countClaudeMd(root)).toBe(2)
  })
  it('missing dir -> 0', () => expect(countClaudeMd(join(root, 'nope'))).toBe(0))
})

describe('countDirFiles', () => {
  it('counts files matching predicate', () => {
    touch('agents/a.md'); touch('agents/b.md'); touch('agents/notes.txt')
    expect(countDirFiles(join(root, 'agents'), n => n.endsWith('.md'))).toBe(2)
  })
})

describe('countMemory', () => {
  it('counts *.md including MEMORY.md', () => {
    touch('memory/MEMORY.md'); touch('memory/a.md'); touch('memory/b.txt')
    expect(countMemory(join(root, 'memory'))).toBe(2)
  })
})
```

- [ ] **Step 2: 跑測試確認失敗** → FAIL

- [ ] **Step 3: 實作 `src/count.mjs`**

```js
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

const EXCLUDE = new Set(['.git', 'node_modules', 'vendor', '.venv', 'dist', 'build'])

export function countClaudeMd(root) {
  let n = 0
  const stack = [root]
  while (stack.length) {
    const d = stack.pop()
    let entries
    try { entries = readdirSync(d, { withFileTypes: true }) } catch { continue }
    for (const e of entries) {
      if (e.isDirectory()) {
        if (!EXCLUDE.has(e.name)) stack.push(join(d, e.name))
      } else if (e.name === 'CLAUDE.md') n++
    }
  }
  return n
}

export function countDirFiles(dir, predicate) {
  try {
    return readdirSync(dir, { withFileTypes: true })
      .filter(e => !e.isDirectory() && predicate(e.name)).length
  } catch { return 0 }
}

export function countSkillDirs(skillsDir) {
  // 每個含 SKILL.md 的子目錄算 1
  let n = 0
  try {
    for (const e of readdirSync(skillsDir, { withFileTypes: true })) {
      if (e.isDirectory() && existsSync(join(skillsDir, e.name, 'SKILL.md'))) n++
    }
  } catch {}
  return n
}

export function countMemory(memDir) {
  return countDirFiles(memDir, n => n.endsWith('.md'))
}

function readJson(file) {
  try { return JSON.parse(readFileSync(file, 'utf8')) } catch { return null }
}

export function countHooks(settingsObjs) {
  let n = 0
  for (const s of settingsObjs) {
    const hooks = s && s.hooks
    if (!hooks) continue
    for (const event of Object.keys(hooks)) {
      const arr = hooks[event]
      if (!Array.isArray(arr)) continue
      for (const matcher of arr) n += (matcher.hooks?.length || 0)
    }
  }
  return n
}

export function countEnabledPlugins(settings) {
  const ep = settings && settings.enabledPlugins
  if (!ep) return 0
  if (Array.isArray(ep)) return ep.length
  return Object.values(ep).filter(Boolean).length
}

export function countMcp(claudeJson, projectMcp) {
  const set = new Set()
  for (const k of Object.keys(claudeJson?.mcpServers || {})) set.add(k)
  for (const k of Object.keys(projectMcp?.mcpServers || {})) set.add(k)
  return set.size
}

// 由 cwd 推導本 session 的 memory 目錄（CC 將專案路徑非英數字元換成 '-'）
export function memoryDirFor(cwd, home = homedir()) {
  const enc = String(cwd).replace(/[^a-zA-Z0-9]/g, '-')
  return join(home, '.claude', 'projects', enc, 'memory')
}

// 彙總（全程容錯；缺項回 0，render 端 0 仍顯示，缺整體才隱藏由 render 決定）
export function countInfra(cwd, home = homedir()) {
  const proj = cwd
  const userClaude = join(home, '.claude')
  const userSettings = readJson(join(userClaude, 'settings.json'))
  const projSettings = readJson(join(proj, '.claude', 'settings.json'))
  const projSettingsLocal = readJson(join(proj, '.claude', 'settings.local.json'))
  return {
    claudeMd: countClaudeMd(proj),
    memory: countMemory(memoryDirFor(cwd, home)),
    mcp: countMcp(readJson(join(home, '.claude.json')), readJson(join(proj, '.mcp.json'))),
    agent: countDirFiles(join(proj, '.claude', 'agents'), n => n.endsWith('.md'))
         + countDirFiles(join(userClaude, 'agents'), n => n.endsWith('.md')),
    skill: countSkillDirs(join(proj, '.claude', 'skills'))
         + countSkillDirs(join(userClaude, 'skills')),
    hook: countHooks([userSettings, projSettings, projSettingsLocal].filter(Boolean)),
    plugin: countEnabledPlugins(userSettings),
    workflow: countDirFiles(join(proj, '.claude', 'workflows'), n => n.endsWith('.js'))
            + countDirFiles(join(userClaude, 'workflows'), n => n.endsWith('.js')),
  }
}
```

- [ ] **Step 4: 跑測試** → PASS（單元測試覆蓋 countClaudeMd/countDirFiles/countMemory；`countInfra` 為彙總，整合測試於 Task 9 覆蓋）

- [ ] **Step 5: Commit**

```bash
git add src/count.mjs tests/count.test.mjs
git commit -m "feat: countInfra (claude.md/memory/mcp/agent/skill/hook/plugin/workflow)"
```

---

## Task 8: render.mjs（renderLine1..4 / buildOutput）

**Files:**
- Create: `leon-statusline/src/render.mjs`
- Test: `leon-statusline/tests/render.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/render.test.mjs`**

```js
import { describe, it, expect } from 'vitest'
import { renderLine2, renderLine3, renderLine4, buildOutput } from '../src/render.mjs'

const strip = s => s.replace(/\x1b\[[0-9;]*m/g, '')

const deps = {
  home: '/home/leon',
  now: () => 1000,
  git: () => ({ branch: 'main', staged: 2, modified: 1, ahead: 1, behind: 0 }),
  counts: () => ({ claudeMd: 7, memory: 5, mcp: 3, agent: 1, skill: 2, hook: 13, plugin: 2, workflow: 1 }),
}

describe('renderLine2 (conditional)', () => {
  it('hides absent repo/worktree/PR, shows git + lines', () => {
    const d = { cost: { total_lines_added: 156, total_lines_removed: 23 } }
    const out = strip(renderLine2(d, deps))
    expect(out).toContain('git:main +2 ~1 ↑1')
    expect(out).toContain('+156 -23')
    expect(out).not.toContain('repo:')
    expect(out).not.toContain('PR:')
  })
})

describe('renderLine3', () => {
  it('hides rate limits when absent; api <1m', () => {
    const d = { cost: { total_api_duration_ms: 3000, total_duration_ms: 14 * 60000, total_cost_usd: 0.42 } }
    const out = strip(renderLine3(d, deps))
    expect(out).toContain('api:<1m')
    expect(out).toContain('wall:14m')
    expect(out).toContain('cost:$0.42')
    expect(out).not.toContain('5h:')
  })
  it('shows rate limits with countdown for Pro/Max', () => {
    const d = { rate_limits: { five_hour: { used_percentage: 24, resets_at: 1000 + 3600 + 23 * 60 } } }
    const out = strip(renderLine3(d, deps))
    expect(out).toContain('5h:24%(reset 1h23m)')
  })
})

describe('renderLine4', () => {
  it('renders all counts with labels', () => {
    const out = strip(renderLine4({ workspace: { project_dir: '/p' } }, deps))
    expect(out).toContain('CLAUDE.md:7')
    expect(out).toContain('workflow:1')
  })
})

describe('buildOutput', () => {
  it('drops fully-empty lines, joins with newline', () => {
    const out = buildOutput({ model: { display_name: 'Opus' }, workspace: { current_dir: '/home/leon/p' } }, deps)
    const lines = strip(out).split('\n')
    expect(lines[0]).toContain('Opus')
    expect(lines.every(l => l.length > 0)).toBe(true)
  })
})
```

- [ ] **Step 2: 跑測試確認失敗** → FAIL

- [ ] **Step 3: 實作 `src/render.mjs`**

```js
import { attr, joinLine, fmtDuration, resetCountdown, shortPath } from './format.mjs'
import { gradientBar, colorize } from './color.mjs'

const BLUE = [86, 156, 214], MAGENTA = [197, 134, 192], DIM = [130, 130, 130]
const GREEN = [0, 200, 80], YELLOW = [220, 200, 0], RED = [220, 40, 40], CYAN = [86, 182, 194]

const tierColor = p => (p >= 90 ? RED : p >= 70 ? YELLOW : GREEN)

export function renderLine1(d, deps) {
  const cw = d.context_window || {}
  const model = d.model?.display_name
  const tok = cw.total_input_tokens
  const parts = [
    d.workspace?.current_dir ? colorize(shortPath(d.workspace.current_dir, deps.home), BLUE) : '',
    model ? colorize(model, MAGENTA) : '',
    attr('effort:', d.effort?.level, DIM),
    d.thinking?.enabled ? attr('think:', 'on', DIM) : '',
    attr('token:', tok != null ? `${(tok / 1000).toFixed(1)}k` : '', DIM),
    gradientBar(cw.used_percentage),
    attr('session:', d.session_name, DIM),
  ]
  return joinLine(parts)
}

export function renderLine2(d, deps) {
  const g = deps.git(d.workspace?.current_dir)
  let gitStr = ''
  if (g) {
    const status = (g.staged || g.modified)
      ? `+${g.staged} ~${g.modified}`.trim()
      : 'clean'
    const ab = `${g.ahead ? `↑${g.ahead}` : ''}${g.behind ? `↓${g.behind}` : ''}`
    gitStr = [g.branch, status, ab].filter(Boolean).join(' ')
  }
  const c = d.cost || {}
  const lines = (c.total_lines_added != null || c.total_lines_removed != null)
    ? `+${c.total_lines_added || 0} -${c.total_lines_removed || 0}`
    : ''
  const pr = d.pr ? `#${d.pr.number} ${d.pr.review_state || ''}`.trim() : ''
  const parts = [
    attr('repo:', d.workspace?.repo?.name, DIM),
    attr('worktree:', d.workspace?.git_worktree, DIM),
    gitStr ? colorize('git:' + gitStr, g.staged || g.modified ? YELLOW : GREEN) : '',
    lines ? colorize(lines, DIM) : '',
    attr('PR:', pr, YELLOW),
  ]
  return joinLine(parts)
}

export function renderLine3(d, deps) {
  const c = d.cost || {}
  const rl = d.rate_limits || {}
  const now = deps.now()
  const rlStr = (label, obj) => {
    if (!obj || obj.used_percentage == null) return ''
    const cd = obj.resets_at ? resetCountdown(obj.resets_at, now) : ''
    const val = `${Math.round(obj.used_percentage)}%${cd ? `(reset ${cd})` : ''}`
    return colorize(`${label}${val}`, tierColor(obj.used_percentage))
  }
  const parts = [
    attr('api:', c.total_api_duration_ms != null ? fmtDuration(c.total_api_duration_ms) : '', DIM),
    attr('wall:', c.total_duration_ms != null ? fmtDuration(c.total_duration_ms) : '', DIM),
    attr('cost:', c.total_cost_usd != null ? `$${c.total_cost_usd.toFixed(2)}` : '', YELLOW),
    rlStr('5h:', rl.five_hour),
    rlStr('7d:', rl.seven_day),
  ]
  return joinLine(parts)
}

export function renderLine4(d, deps) {
  const c = deps.counts(d.workspace?.project_dir || d.workspace?.current_dir)
  if (!c) return ''
  const parts = [
    attr('CLAUDE.md:', c.claudeMd, DIM),
    attr('memory:', c.memory, DIM),
    attr('mcp:', c.mcp, DIM),
    attr('agent:', c.agent, DIM),
    attr('skill:', c.skill, DIM),
    attr('hook:', c.hook, DIM),
    attr('plugin:', c.plugin, DIM),
    attr('workflow:', c.workflow, DIM),
  ]
  return joinLine(parts)
}

export function buildOutput(d, deps) {
  const lines = [renderLine1(d, deps), renderLine2(d, deps), renderLine3(d, deps), renderLine4(d, deps)]
  return lines.filter(l => l && l.length).join('\n')
}
```

> 註：`attr` 對 `0` 不視為空（`0 !== ''` 且 `0 != null`），故計數為 0 仍顯示（如 `agent:0`）。若要「0 也隱藏」可日後調整 `attr`。

- [ ] **Step 4: 跑測試** → PASS

- [ ] **Step 5: Commit**

```bash
git add src/render.mjs tests/render.test.mjs
git commit -m "feat: render 4 lines with conditional display + colors"
```

---

## Task 9: statusline.mjs 進入點 + 整合/永不崩潰測試

**Files:**
- Create: `leon-statusline/statusline.mjs`
- Test: `leon-statusline/tests/integration.test.mjs`

- [ ] **Step 1: 失敗測試 `tests/integration.test.mjs`**（以子程序跑真進入點，驗證 exit 0 + 至少一行）

```js
import { describe, it, expect } from 'vitest'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { join, dirname } from 'node:path'

const entry = join(dirname(fileURLToPath(import.meta.url)), '..', 'statusline.mjs')
const run = stdin => spawnSync('node', [entry], { input: stdin, encoding: 'utf8' })

describe('statusline entry (never crash)', () => {
  it('valid input -> exit 0, non-empty', () => {
    const r = run(JSON.stringify({ model: { display_name: 'Opus' }, workspace: { current_dir: '/tmp/x' } }))
    expect(r.status).toBe(0)
    expect(r.stdout.length).toBeGreaterThan(0)
  })
  it('empty input -> exit 0', () => {
    const r = run('')
    expect(r.status).toBe(0)
  })
  it('garbage input -> exit 0', () => {
    const r = run('}{not json')
    expect(r.status).toBe(0)
  })
})
```

- [ ] **Step 2: 跑測試確認失敗** → FAIL（無 statusline.mjs）

- [ ] **Step 3: 實作 `statusline.mjs`**

```js
import { homedir } from 'node:os'
import { parseInput } from './src/input.mjs'
import { buildOutput } from './src/render.mjs'
import { gitInfo } from './src/git.mjs'
import { countInfra } from './src/count.mjs'
import { withCache } from './src/cache.mjs'

async function main() {
  let out = ''
  try {
    const raw = await new Promise(res => {
      let buf = ''
      process.stdin.on('data', c => (buf += c))
      process.stdin.on('end', () => res(buf))
      process.stdin.on('error', () => res(buf))
      setTimeout(() => res(buf), 1500) // 永不卡死
    })
    const d = parseInput(raw)
    const sid = d.session_id
    const home = homedir()
    const deps = {
      home,
      now: () => Math.floor(Date.now() / 1000),
      git: cwd => cwd ? withCache(sid, 'git', 2000, () => gitInfo(cwd)) : null,
      counts: cwd => cwd ? withCache(sid, 'counts', 60000, () => countInfra(cwd, home)) : null,
    }
    out = buildOutput(d, deps)
    if (!out) out = d.model?.display_name || 'claude'
  } catch {
    out = 'claude'
  }
  process.stdout.write(out)
  process.exit(0)
}

main()
```

> 註：`now` 在 deps 回傳「秒」，與 `resetCountdown(epochSec, nowSec)` 一致；`rate_limits.resets_at` 為 epoch 秒。

- [ ] **Step 4: 跑測試** → PASS（exit 0、非空）

- [ ] **Step 5: 手動實機測試**

Run（PowerShell）:
```powershell
'{"model":{"display_name":"Opus"},"workspace":{"current_dir":"C:/Users/LIN HONG/Desktop/Project_01"},"context_window":{"used_percentage":42,"total_input_tokens":15500},"cost":{"total_cost_usd":0.42,"total_duration_ms":840000,"total_api_duration_ms":3000,"total_lines_added":156,"total_lines_removed":23},"session_id":"test"}' | node statusline.mjs
```
Expected: 印出多行彩色狀態列、行尾無錯、結束碼 0。

- [ ] **Step 6: Commit**

```bash
git add statusline.mjs tests/integration.test.mjs
git commit -m "feat: entry point (stdin -> 4 lines -> exit 0, never crash)"
```

---

## Task 10: 全測試綠燈 + README + 安裝/分享說明

**Files:**
- Create: `leon-statusline/README.md`、repo root `README.md`

- [ ] **Step 1: 跑全部測試**

Run: `npm test`
Expected: 全 PASS。

- [ ] **Step 2: 寫 `leon-statusline/README.md`**（plugin 說明 + 本機開發）

````markdown
# leon-statusline

Cross-platform 4-line Claude Code status line (Node, zero runtime deps).

## Develop
```
npm install
npm test
```

## Layout
Line1 dir / model+effort+thinking / token / context bar / session
Line2 repo / worktree / git / +added -removed / PR
Line3 api / wall / cost / 5h / 7d
Line4 CLAUDE.md / memory / mcp / agent / skill / hook / plugin / workflow counts
````

- [ ] **Step 3: 寫 repo root `README.md`**（安裝/分享）

````markdown
# leon-statusline marketplace

## Install
```
/plugin marketplace add <this repo url>
/plugin install leon-statusline
```
Requires Node.js on PATH.
````

- [ ] **Step 4: Commit**

```bash
git add README.md leon-statusline/README.md
git commit -m "docs: readme + install/share instructions"
```

- [ ] **Step 5: 建 GitHub repo 並 push**（散佈用）

Run:
```bash
gh repo create leon-statusline --public --source=. --remote=origin --push
```

---

## Task 11: 實機安裝驗證

- [ ] **Step 1: 在本機安裝此 plugin**

在 Claude Code 輸入：
```
/plugin marketplace add C:/Users/LIN HONG/Desktop/leon-statusline
/plugin install leon-statusline
```
（或用 push 後的 GitHub URL）

- [ ] **Step 2: 確認狀態列出現且無錯**

Expected: 底部出現 4 行（依當前 session 條件顯示）；若空白或報錯，用 `claude --debug` 看 exit code/stderr，回頭修。

- [ ] **Step 3: 驗證確認後，回報使用者效果**（此步交付，非 commit）

---

## Self-Review（撰寫者已核對）

- **Spec coverage**：版面 4 行 ✅(Task 8)、每 attribute 來源/格式/條件 ✅(Task 8)、條件顯示規則 ✅(render+format 測試)、第4行計數定義 ✅(Task 7)、快取 ✅(Task 5/9)、永不崩潰 ✅(Task 9)、跨平台路徑 ✅(format/cache 用 os.homedir/正斜線、command 用 `${CLAUDE_PLUGIN_ROOT}`)、測試 ✅(各 Task + 整合)、plugin 封裝 ✅(Task 1/10)。
- **型別一致**：`gitInfo` 回 `{branch,staged,modified,ahead,behind}` 於 render 一致使用；`countInfra` 鍵 `{claudeMd,memory,mcp,agent,skill,hook,plugin,workflow}` 與 `renderLine4` 一致；`deps`（home/now/git/counts）於 render 與 entry 一致。
- **Placeholder 掃描**：無 TBD/TODO；所有步驟含實際程式碼與指令。
- **待實作驗證項**（不阻擋）：plugin.json/marketplace.json schema、`${CLAUDE_PLUGIN_DATA}` 可用性、memory 目錄編碼規則跨版本——皆以容錯（缺則隱藏/回 0）設計。

---

## Execution Handoff（撰寫者交付）

Plan 完成。執行請見 README 末「兩種執行方式」。
