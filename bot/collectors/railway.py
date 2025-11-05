import json, re, subprocess
from typing import Dict

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

ANSI = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")

def _strip_ansi(s: str) -> str:
    return ANSI.sub("", s)

def _parse_table(text: str) -> Dict[str,str]:
    txt = _strip_ansi(text)
    env: Dict[str,str] = {}

    # remove linhas de borda/cabeçalho
    border = re.compile(r'^[\s\|\-\=\+\╔╚╦╩╣╠╬╔╗╚╝\─\═\║]+$')

    for line in txt.splitlines():
        if border.match(line):
            continue
        # remove bordas laterais como "║ ... ║"
        line = line.strip()
        if line.startswith("║"):
            line = line[1:]
        if line.endswith("║"):
            line = line[:-1]
        line = line.strip()

        # tenta split por colunas com │ ou |
        parts = [p.strip() for p in re.split(r"[│|]", line) if p.strip()]
        if len(parts) < 2:
            continue
        key = parts[0]
        val = parts[1]
        # valida chave estilo ENV
        if re.fullmatch(r"[A-Z0-9_]+", key):
            env[key] = val
    return env

def fetch_vars(service: str) -> Dict[str,str]:
    # 1) tenta JSON
    p = _run(["railway", "variables", "--service", service, "--json"])
    if p.returncode == 0 and p.stdout.strip():
        try:
            arr = json.loads(p.stdout)
            return {it.get("key",""): it.get("value","") for it in arr if it.get("key")}
        except Exception:
            pass
    # 2) fallback: tabela
    p2 = _run(["railway", "variables", "--service", service])
    if p2.returncode != 0:
        raise RuntimeError(f"Falha ao obter variáveis do Railway para '{service}': {p2.stderr.strip()}")
    env = _parse_table(p2.stdout)
    if not env:
        raise RuntimeError(f"Nenhuma variável encontrada para '{service}'.")
    return env
