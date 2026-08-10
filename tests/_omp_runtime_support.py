"""Shared stateless helpers for split OMP runtime tests."""
from __future__ import annotations

from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_3_omp_model_menu.py
# ---------------------------------------------------------------------------
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from tests._cli_support import run_cli as test_run_cli
from tests._fake_executable import write_python_executable
from tests._path_support import assert_labeled_path, assert_same_path, paths_identify_same
m1_ROOT = Path(__file__).resolve().parents[1]
m1_TOOLS = m1_ROOT / 'tools'
if str(m1_TOOLS) not in sys.path:
    sys.path.insert(0, str(m1_TOOLS))
m1_INSTALL = m1_ROOT / 'tools' / 'install.py'
m1_ROUTING = m1_ROOT / 'tools' / 'omp_model_routing.py'
m1_PROFILES = m1_ROOT / 'spec' / 'omp-model-routing-profiles.json'
m1_TEMPLATE = m1_ROOT / 'templates' / 'omp-model-routing-profile.json'
m1_VERSION = (m1_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m1_run(command, *, env=None, cwd=m1_ROOT, check=True):
    return test_run_cli(command, cwd=cwd, env=env, check=check)

def m1_run_json(command, *, env=None, cwd=m1_ROOT, check=True):
    result = m1_run(command, env=env, cwd=cwd, check=check)
    return (json.loads(result.stdout), result)

def m1_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding='utf-8')
    raw = text.split('---\n', 2)[1]
    result = {}
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError:
            parsed = value.strip()
        result[key] = parsed
    return result


def m1_write_minimal_routing_install(*, base: Path, home: Path, scope: str, project: Path | None = None) -> dict[str, Path]:
    """Create the authenticated routing surface without recopying the full BBK package.

    Full user and project installation behavior is covered elsewhere. This
    fixture isolates the OMP scope resolver and mutable-routing contract, which
    otherwise spends most of its runtime copying hundreds of unrelated files
    three times (especially costly on Windows).
    """
    if scope not in {'user', 'project'} or (scope == 'project') != (project is not None):
        raise ValueError('scope/project mismatch')
    if scope == 'user':
        extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'
        agents = home / '.omp' / 'agent' / 'agents'
        state_path = base / 'data' / 'effective-omp-model-routing.json'
        manifest_path = base / 'data' / 'install-manifest.json'
        package_root = base / 'data' / m1_VERSION
    else:
        assert project is not None
        extension = project / '.omp' / 'extensions' / 'bbk'
        agents = project / '.omp' / 'agents'
        state_path = project / '.bbk-kit' / 'effective-omp-model-routing.json'
        manifest_path = project / '.bbk-kit-install.json'
        package_root = project / '.bbk-kit' / m1_VERSION
    extension.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    (package_root / 'spec').mkdir(parents=True, exist_ok=True)
    shutil.copy2(m1_ROOT / 'VERSION', package_root / 'VERSION')
    shutil.copy2(m1_ROOT / 'spec' / 'roles.json', package_root / 'spec' / 'roles.json')
    shutil.copy2(
        m1_ROOT / 'spec' / 'omp-model-routing-profiles.json',
        package_root / 'spec' / 'omp-model-routing-profiles.json',
    )
    for name in ('index.js', 'package.json'):
        shutil.copy2(m1_ROOT / 'omp' / 'extension' / name, extension / name)
    for name in ('omp_model_routing.py', 'path_compat.py', 'strict_json.py'):
        shutil.copy2(m1_ROOT / 'tools' / name, extension / name)
    shutil.copy2(m1_ROOT / 'VERSION', extension / 'VERSION')

    routing = json.loads((m1_ROOT / 'spec' / 'model-routing.json').read_text(encoding='utf-8'))
    routes = {name: value['omp'] for name, value in routing['roles'].items()}
    for role in routes:
        shutil.copy2(m1_ROOT / 'projections' / 'omp' / 'agents' / f'{role}.md', agents / f'{role}.md')
    canonical_routes = json.dumps(routes, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    state = {
        'schema': 'bbk.omp-model-routing-state.v1',
        'package_version': m1_VERSION,
        'active_profile': 'installation-default',
        'source': 'minimal-routing-test-fixture',
        'description': 'Canonical installation-default routing for an isolated OMP scope test.',
        'updated_at': '2026-08-02T00:00:00Z',
        'installation_default': routes,
        'roles': routes,
        'routes_sha256': hashlib.sha256(canonical_routes).hexdigest(),
    }
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')

    owned = [state_path, *(agents / f'{role}.md' for role in routes)]
    records = [
        {
            'path': str(path.resolve()),
            'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source': 'minimal-routing-test-fixture',
        }
        for path in owned
    ]
    manifest = {
        'schema': 'bbk.install-manifest.v1',
        'version': m1_VERSION,
        'scope': scope,
        'project_root': str(project.resolve()) if project else None,
        'omp': True,
        'files': records,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    binding = {
        'schema': 'bbk.omp-package-binding.v3',
        'version': m1_VERSION,
        'path': str(package_root.resolve()),
        'package_root': str(package_root.resolve()),
        'scope': scope,
        'project_root': str(project.resolve()) if project else None,
        'manifest_path': str(manifest_path.resolve()),
        'omp_agents': str(agents.resolve()),
        'state_path': str(state_path.resolve()),
    }
    binding_path = extension / 'bbk-package-root.json'
    binding_path.write_text(json.dumps(binding, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    return {
        'extension': extension,
        'agents': agents,
        'state': state_path,
        'manifest': manifest_path,
        'binding': binding_path,
    }
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from zipfile import ZipFile
m2_ROOT = Path(__file__).resolve().parents[1]
m2_INSTALL = m2_ROOT / 'tools' / 'install.py'
m2_SETUP = m2_ROOT / 'tools' / 'setup.py'
m2_UPDATE_OMP = m2_ROOT / 'tools' / 'update_omp.py'
m2_EXTENSION = m2_ROOT / 'omp' / 'extension' / 'index.js'
m2_BUNDLED = m2_ROOT / 'bundled-language-profiles' / 'packages'
m2_VERSION = (m2_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m2_run(command, *, env=None, cwd=m2_ROOT, check=True):
    return test_run_cli(command, cwd=cwd, env=env, check=check, timeout=180)

def m2_run_json(command, *, env=None, cwd=m2_ROOT, check=True):
    result = m2_run(command, env=env, cwd=cwd, check=check)
    return (json.loads(result.stdout), result)

def m2_file_snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {path.relative_to(root).as_posix(): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in sorted(root.rglob('*')) if path.is_file()}
import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
m3_ROOT = Path(__file__).resolve().parents[1]
m3_EXTENSION = m3_ROOT / 'omp' / 'extension' / 'index.js'
m3_VERSION = (m3_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m3_run_node(source: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / 'test.mjs'
        script.write_text(source, encoding='utf-8')
        result = subprocess.run([shutil.which('node') or 'node', script], cwd=m3_ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', timeout=90)
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        return json.loads(result.stdout)
m3_MOCK_PREFIX = textwrap.dedent('''\
    const chain = () => ({ optional() { return this; } });
    const z = { object: value => value, string: chain, boolean: chain,
      enum: values => chain(), array: value => chain(), any: chain };
    const commands = new Map(), handlers = new Map(), busHandlers = new Map();
    const userMessages = [], customMessages = [], entries = [], notifications = [], statuses = [], widgets = [];
    let branch = [];
    const pi = {
      zod: { z }, setLabel() {}, registerTool() {},
      events: {
        on(name, value) {
          if (!busHandlers.has(name)) busHandlers.set(name, []);
          busHandlers.get(name).push(value);
          return () => {
            const values = busHandlers.get(name) || [];
            busHandlers.set(name, values.filter(item => item !== value));
          };
        },
      },
      registerCommand(name, value) { commands.set(name, value); },
      on(name, value) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); },
      appendEntry(customType, data) {
        entries.push({customType, data});
        branch.push({type: "custom", customType, data});
      },
      sendMessage(value, options) { customMessages.push({value, options}); },
      async sendUserMessage(value, options) { userMessages.push({value, options: options || null}); },
    };
    const notificationsFor = () => notifications.map(item => item.message);
    const ctx = {
      cwd: process.cwd(), hasUI: true,
      isIdle() { return true; },
      sessionManager: { getBranch() { return branch; } },
      ui: {
        notify(message, level) { notifications.push({message, level}); },
        setStatus(key, value) { statuses.push({key, value: value ?? null}); },
        setWidget(key, content, options) { widgets.push({key, content: content ?? null, options: options || null}); },
      },
    };
''')
