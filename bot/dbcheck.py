from typing import Tuple
import psycopg, socket, subprocess, shlex
from urllib.parse import urlparse

def _tcp_probe(db_url: str, timeout: float = 5.0) -> Tuple[bool, str]:
    try:
        u = urlparse(db_url)
        host = u.hostname
        port = u.port or 5432
        if not host:
            return False, "URL sem host"
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP ok {host}:{port}"
    except Exception as e:
        return False, f"TCP falhou: {e}"

def _psql_via_railway(service: str = "Postgres-Va00") -> Tuple[bool, str]:
    """
    Fallback quando TCP externo falha: envia 'SELECT 1;' via stdin para o psql do 'railway connect <service>'.
    """
    cmd = ["bash", "-lc", f'echo "SELECT 1; \\\\q" | railway connect {shlex.quote(service)}']
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0 and "1" in out:
            return True, "SELECT 1 ok (via railway connect stdin)"
        return False, f"psql via railway falhou (rc={p.returncode}): {out.strip()[:200]}"
    except Exception as e:
        return False, f"psql via railway erro: {e}"

def check_pg_connect(db_url: str) -> Tuple[bool, str]:
    # 1) Tenta TCP direto
    ok, msg = _tcp_probe(db_url, timeout=6.0)
    if not ok:
        # 2) Fallback via railway connect + psql
        ok2, msg2 = _psql_via_railway("Postgres-Va00")
        return (ok2, msg2) if ok2 else (False, msg2)

    # 3) Se TCP abriu, tenta psycopg direto
    try:
        with psycopg.connect(db_url, connect_timeout=10, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                one = cur.fetchone()
                if one == (1,):
                    return True, "SELECT 1 ok"
                else:
                    return False, f"Retorno inesperado: {one}"
    except Exception as e:
        # Se falhar, ainda tenta o fallback para confirmar saúde via túnel
        ok2, msg2 = _psql_via_railway("Postgres-Va00")
        return (ok2, msg2) if ok2 else (False, str(e))
