#!/usr/bin/env bash
set -euo pipefail

# Structural validation for the Stage C.2 WAF overlay
# (deploy/oracle/docker-compose.waf.yml). Deliberately does NOT require a
# Docker daemon or the `docker` CLI -- this repo's sandbox/CI environments
# can't rely on either being present (same constraint documented across
# every Stage A-E phase). Checks the things that are actually checkable
# without one: the compose file and its acquisition config are valid YAML,
# merging it alongside the base + demo compose files produces no host-port
# conflicts and no dangling depends_on references, and every named volume
# the waf services use is actually declared.
#
# This test intentionally does NOT start any container and does NOT imply
# the WAF overlay is wired into any live deploy path -- see
# deploy/oracle/waf/README.md. Not currently wired into ci.yml (out of
# scope for this phase, same "don't touch what wasn't asked" discipline as
# everywhere else in this project) -- run manually, or ask before adding
# to CI.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

python3 <<'PY'
import sys
import yaml

base = yaml.safe_load(open('docker-compose.yml'))
demo = yaml.safe_load(open('deploy/oracle/docker-compose.demo.yml'))
waf = yaml.safe_load(open('deploy/oracle/docker-compose.waf.yml'))
acquis = yaml.safe_load(open('deploy/oracle/waf/acquis.yaml'))

errors = []

# acquis.yaml sanity: must declare the exact path coraza-waf's ACCESSLOG
# env var writes to, or crowdsec silently tails nothing.
coraza_accesslog = waf['services']['coraza-waf']['environment']['ACCESSLOG']
if coraza_accesslog not in (acquis.get('filenames') or []):
    errors.append(
        f"acquis.yaml doesn't list coraza-waf's ACCESSLOG path ({coraza_accesslog}) "
        f"in its filenames: {acquis.get('filenames')}"
    )

# Every service the waf file's depends_on references must exist somewhere
# across the 3-file merge (base, demo overlay, waf overlay) -- Compose
# fails outright at startup otherwise.
all_services = set(base.get('services', {})) | set(demo.get('services', {})) | set(waf.get('services', {}))
for svc, cfg in waf['services'].items():
    for dep in (cfg.get('depends_on') or {}):
        if dep not in all_services:
            errors.append(f"waf.yml service '{svc}' depends_on unknown service '{dep}'")

# Every named volume a waf service mounts must be declared in waf.yml's
# own top-level volumes: block (or be a bind mount / anonymous -- this
# repo's waf overlay only uses named volumes and bind mounts, checked
# here by excluding anything starting with '.' or '/').
declared_volumes = set(waf.get('volumes', {}) or {})
for svc, cfg in waf['services'].items():
    for v in (cfg.get('volumes') or []):
        if isinstance(v, str) and ':' in v:
            src = v.split(':')[0]
            if not (src.startswith('.') or src.startswith('/')) and src not in declared_volumes:
                errors.append(f"waf.yml service '{svc}' references undeclared volume '{src}'")

# Host-port conflict check across the full 3-file merge -- the actual
# thing that would make `docker compose up` fail loudly if wrong.
host_ports = {}
for fname, doc in [('docker-compose.yml', base), ('demo.yml', demo), ('waf.yml', waf)]:
    for svc, cfg in (doc.get('services') or {}).items():
        for p in (cfg.get('ports') or []):
            if not isinstance(p, str):
                continue
            parts = p.split(':')
            if len(parts) == 3:
                bind, hostport, _ = parts
            elif len(parts) == 2:
                bind, hostport = '0.0.0.0', parts[0]
            else:
                continue
            # Skip entries still containing an unexpanded ${VAR} default --
            # those are the pre-existing base-file ports, already covered
            # by this repo's own YAML validation elsewhere, not this
            # overlay's concern.
            if '$' in hostport:
                continue
            key = (bind, hostport)
            host_ports.setdefault(key, []).append((fname, svc))

conflicts = {k: v for k, v in host_ports.items() if len(v) > 1}
if conflicts:
    errors.append(f"host port conflicts across the merged compose files: {conflicts}")

if errors:
    print("WAF compose validation FAILED:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print("WAF compose validation OK:")
print(f"  services in merged config: {sorted(all_services)}")
print(f"  host ports (excluding unexpanded base-file defaults): {sorted(host_ports.keys())}")
PY

echo "test_waf_compose.sh OK"
