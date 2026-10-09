"""Publicação local de um resultado completo em JSON e CSV."""

import csv
import fcntl
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .execucao import _hash_manifesto


def contexto_codigo():
    pacote = Path(__file__).resolve().parent
    assinatura = hashlib.sha256()
    for arquivo in sorted(pacote.glob("*.py")):
        conteudo = arquivo.read_bytes()
        assinatura.update(arquivo.name.encode("utf-8") + b"\0")
        assinatura.update(len(conteudo).to_bytes(8, "big"))
        assinatura.update(conteudo)
    revisao = None
    alteracoes = None
    try:
        raiz = pacote.parent.parent
        revisao = subprocess.check_output(
            ["git", "-C", str(raiz), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
        alteracoes = bool(subprocess.check_output(
            ["git", "-C", str(raiz), "status", "--porcelain", "--untracked-files=normal"],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {
        "primeira_exportacao_em_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "plataforma": platform.system(),
        "revisao_git": revisao,
        "alteracoes_locais": alteracoes,
        "codigo_sha256": assinatura.hexdigest(),
    }


def _json_bytes(valor):
    return (json.dumps(valor, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _csv_bytes(cabecalho, linhas):
    texto = io.StringIO(newline="")
    escritor = csv.writer(texto, lineterminator="\n")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return texto.getvalue().encode("utf-8")


def _artefatos(resultado):
    if _hash_manifesto(resultado.manifesto) != resultado.execucao_sha256:
        raise ValueError("Manifesto alterado após a execução")
    agregacoes = resultado.manifesto["resultado"]["agregacoes"]
    artefatos = {
        "manifesto.json": _json_bytes({
            "execucao_sha256": resultado.execucao_sha256,
            "manifesto": resultado.manifesto,
        }),
        "por_dia.csv": _csv_bytes(
            ["dia_utc", "deteccoes"],
            ((x["dia_utc"], x["deteccoes"]) for x in agregacoes["por_dia_utc"]),
        ),
        "por_municipio.csv": _csv_bytes(
            ["municipio_id", "nomes_json", "deteccoes", "sem_nome", "nomes_divergentes"],
            ((x["municipio_id"] or "", json.dumps(x["nomes"], ensure_ascii=False),
              x["deteccoes"], x["sem_nome"], str(x["nomes_divergentes"]).lower())
             for x in agregacoes["por_municipio"]),
        ),
    }
    if resultado.manifesto["versao_manifesto_execucao"] == 3:
        artefatos["por_municipio_dia.csv"] = _csv_bytes(
            ["municipio_id", "dia_utc", "deteccoes"],
            ((g["municipio_id"] or "", dia["dia_utc"], g["deteccoes_por_dia"][i])
             for g in agregacoes["por_municipio_dia_utc"]
             for i, dia in enumerate(agregacoes["por_dia_utc"])),
        )
        conferidos = resultado.manifesto["resultado"]["conferencia_municipal"]["por_municipio"]
        campos_nomes = ["nomes_iguais", "nomes_equivalentes", "nomes_divergentes", "nomes_sem_referencia"]
        artefatos["conferencia_municipal.csv"] = _csv_bytes(
            ["municipio_id", "nome_referencia", "situacao_codigo", *[k + "_json" for k in campos_nomes]],
            ((g["municipio_id"] or "", g["nome_referencia"] or "", g["situacao_codigo"],
              *[json.dumps(g[k], ensure_ascii=False) for k in campos_nomes]) for g in conferidos),
        )
    return artefatos


def _verificar_existente(diretorio, esperados):
    if diretorio.is_symlink() or not diretorio.is_dir():
        raise ValueError("O destino do resultado não é um diretório regular")
    nomes = {x.name for x in diretorio.iterdir()}
    if nomes != set(esperados) | {"contexto.json"}:
        raise ValueError("Resultado existente incompleto ou com arquivos inesperados")
    for nome, conteudo in esperados.items():
        arquivo = diretorio / nome
        if (arquivo.is_symlink() or not arquivo.is_file()
                or arquivo.stat().st_size != len(conteudo)
                or arquivo.read_bytes() != conteudo):
            raise ValueError(f"Resultado existente divergente: {nome}")
    contexto = diretorio / "contexto.json"
    if contexto.is_symlink() or not contexto.is_file() or contexto.stat().st_size > 8192:
        raise ValueError("Contexto existente inválido")
    try:
        dados = json.loads(contexto.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or not isinstance(dados.get("codigo_sha256"), str):
            raise ValueError("Contexto existente inválido")
    except (UnicodeError, json.JSONDecodeError) as erro:
        raise ValueError("Contexto existente inválido") from erro


def exportar_resultado(resultado, destino=Path("dados/resultados")):
    """Retorna (diretório, reutilizado); preserva o contexto da primeira publicação.

    Os artefatos determinísticos precisam coincidir byte a byte para
    reutilizar um diretório. Nenhum arquivo divergente é substituído.
    """
    esperados = _artefatos(resultado)
    destino = Path(destino)
    if destino.is_symlink():
        raise ValueError("O destino não pode ser um link simbólico")
    destino.mkdir(parents=True, exist_ok=True)
    final = destino / resultado.execucao_sha256
    trava = destino / ".exportacao.lock"
    if trava.is_symlink():
        raise ValueError("A trava não pode ser um link simbólico")
    with trava.open("a+b") as arquivo_trava:
        try:
            fcntl.flock(arquivo_trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erro:
            raise ValueError("Outra exportação está publicando nesta pasta") from erro
        if final.exists() or final.is_symlink():
            _verificar_existente(final, esperados)
            return final, True
        temporario = Path(tempfile.mkdtemp(prefix=".tmp-", dir=destino))
        try:
            conteudos = {**esperados, "contexto.json": _json_bytes(contexto_codigo())}
            for nome, conteudo in conteudos.items():
                with (temporario / nome).open("xb") as arquivo:
                    arquivo.write(conteudo)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
            os.rename(temporario, final)
        finally:
            if temporario.exists():
                shutil.rmtree(temporario)
        return final, False
