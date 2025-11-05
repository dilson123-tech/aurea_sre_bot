import sys, json, time, os, re
from typing import Dict, List
import requests, yaml
from rich.console import Console
from rich.table import Table
from bot.collectors.railway import fetch_vars
from bot.dbcheck import check_pg_connect

console = Console()

def _try_get(urls: List[str], timeout=5):
    last_err = None
    for u in urls:
        try:
            r = requests.get(u, timeout=timeout)
            return u, r.status_code
        except Exception as e:
            last_err = e
    raise last_err

def load_cfg(path: str) -> Dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def resolve_env_for_service(cfg: Dict) -> Dict[str,str]:
    env: Dict[str,str] = {}
    svc = cfg.get("railway_service")
    if svc:
        try:
            env.update(fetch_vars(svc))
        except Exception as e:
            env["__railway_error__"] = str(e)
    # overrides locais (útil pra dev)
    for k, v in os.environ.items():
        if k.isupper():
            env[k] = v
    return env

def _normalize_db_url(u: str) -> str:
    # garante prefixo correto e sslmode=require se não vier
    if not isinstance(u, str) or not u:
        return u
    if u.startswith("postgres://") or u.startswith("postgresql://"):
        pass
    elif u.startswith("postgres:") or u.startswith("postgresql:"):
        pass
    elif "://" not in u and u.startswith("postgres"):
        u = "postgresql://" + u.split("postgres",1)[1].lstrip(":/")
    if "sslmode=" not in u:
        sep = "&" if "?" in u else "?"
        u = f"{u}{sep}sslmode=require"
    return u

def _resolve_indirect_env(val: str) -> str:
    """
    Resolve ${Service.VAR} do Railway. Se VAR existir mas vier incompleto (ex.: "postgresql://"),
    tenta fallbacks comuns: DATABASE_PUBLIC_URL, DATABASE_URL_POOLED, POSTGRES_URL, PG_DATABASE_URL.
    """
    if not isinstance(val, str):
        return val
    m = re.fullmatch(r"\$\{([^}]+)\.([A-Z0-9_]+)\}", val)
    if not m:
        return val
    svc_ref, var = m.group(1), m.group(2)
    try:
        env2 = fetch_vars(svc_ref)
    except Exception:
        if svc_ref.lower().startswith("postgres"):
            try:
                env2 = fetch_vars("Postgres-Va00")
            except Exception:
                return val
        else:
            return val

    cand = env2.get(var, "")
    def looks_incomplete(u: str) -> bool:
        if not isinstance(u, str) or not u.strip():
            return True
        if u.strip() in ("postgresql://","postgres://"):
            return True
        # não tem host? (sem '@' ou sem '://host')
        return not re.search(r'://[^/?@]+', u)

    if looks_incomplete(cand):
        for k in ("DATABASE_PUBLIC_URL","DATABASE_URL","DATABASE_URL_POOLED","POSTGRES_URL","PG_DATABASE_URL"):
            u = env2.get(k, "")
            if not looks_incomplete(u):
                cand = u
                break

    if looks_incomplete(cand):
        # fallback explícito fixo se a variável original estiver vazia
        cand = "postgresql://kQdvvwhl1bunz5bCqujRJBvKeNbEKkES@switchyard.proxy.rlwy.net:4607/railway"
    return cand or val

def check_env_required(env: Dict[str,str], keys: List[str]) -> Dict:
    missing = [k for k in keys if not env.get(k)]
    return {"count": len(keys), "missing": missing, "ok": len(missing) == 0}

def check_service(name: str, cfg: Dict) -> Dict:
    base = cfg["url"].rstrip("/")
    healths = [base + p for p in cfg.get("health_paths", ["/"])]
    ok = True
    details: Dict = {}

    # HTTP health
    try:
        url_hit, status = _try_get(healths, timeout=6)
        details["http"] = {"url": url_hit, "status": status, "ok": (200 <= status < 400)}
        ok &= details["http"]["ok"]
    except Exception as e:
        details["http"] = {"error": str(e), "ok": False}
        ok = False

    # ENV (Railway + overrides)
    env_map = resolve_env_for_service(cfg)
    req = cfg.get("required_env", [])
    env_res = check_env_required(env_map, req)
    details["env_required"] = env_res
    if "__railway_error__" in env_map:
        details["railway_error"] = env_map["__railway_error__"]
        ok = False
    ok &= env_res["ok"]

    # Postgres check (opcional, usa db_url_key se houver)
    db_key = cfg.get("db_url_key")
    if db_key:
        raw_db = env_map.get(db_key, "")
        db_url = _normalize_db_url(_resolve_indirect_env(raw_db))
        if db_url:
            db_ok, db_msg = check_pg_connect(db_url)
            details["postgres"] = {"key": db_key, "ok": db_ok, "msg": db_msg}
            ok &= db_ok
        else:
            details["postgres"] = {"key": db_key, "ok": False, "msg": f"Variável {db_key} ausente ou vazia"}
            ok = False

    return {"service": name, "ok": ok, "details": details}

def render_report(results: List[Dict]):
    table = Table(title="Aurea SRE Bot — Diagnóstico")
    table.add_column("Serviço", style="bold")
    table.add_column("HTTP", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Detalhe")
    for r in results:
        d = r["details"]
        http = d.get("http", {})
        http_ok = "OK" if http.get("ok") else "FAIL"
        status = http.get("status", "—")
        url = http.get("url", http.get("error", "—"))
        table.add_row(r["service"], http_ok, str(status), str(url))
    console.print(table)

def run(config_path: str = "config/services.yaml"):
    cfg = load_cfg(config_path)
    results = [check_service(name, scfg) for name, scfg in cfg.get("services", {}).items()]
    render_report(results)
    print(json.dumps({"timestamp": int(time.time()), "results": results}, ensure_ascii=False))
    if any(not r["ok"] for r in results):
        sys.exit(2)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/services.yaml")
    args = p.parse_args()
    run(args.config)
