"""Execução reproduzível ligada a um snapshot íntegro."""

import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .leitor import Foco, PERFIS, ler_csv
from .snapshot import verificar_snapshot


class ErroIdentidade(ValueError):
    """Um source_id selecionado apareceu mais de uma vez na mesma execução."""


@dataclass(frozen=True)
class ResultadoExecucao:
    snapshot_sha256: str
    snapshot_bytes: int
    ids_selecionados_unicos: int
    resumo: dict[str, int]
    execucao_sha256: str
    manifesto: dict[str, object]


def _decimal_canonico(valor):
    if valor is None:
        return None
    return str(valor.normalize())


def _assinatura_foco(foco: Foco) -> bytes:
    """
    Gera uma assinatura estável do conteúdo interpretado do foco.

    A identidade externa continua sendo source_id. A assinatura serve apenas
    para distinguir uma duplicata idêntica de um mesmo ID associado a dados
    diferentes.
    """
    conteudo = [
        foco.source_id,
        _decimal_canonico(foco.latitude),
        _decimal_canonico(foco.longitude),
        foco.observado_em.isoformat(),
        foco.satelite,
        foco.estado_id,
        foco.dias_sem_chuva,
        _decimal_canonico(foco.precipitacao),
        _decimal_canonico(foco.risco_fogo),
        _decimal_canonico(foco.frp),
    ]
    serializado = json.dumps(
        conteudo,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(serializado).digest()


def _criar_manifesto_execucao(
    snapshot,
    *,
    perfil,
    limites,
    ids_selecionados_unicos,
    resumo,
):
    return {
        "versao_manifesto_execucao": 1,
        "versao_regras": 1,
        "snapshot": {
            "sha256": snapshot.sha256,
            "bytes": snapshot.bytes,
        },
        "perfil": perfil,
        "limites": {
            "bytes_arquivo": limites.bytes_arquivo,
            "linhas_dados": limites.linhas_dados,
            "bytes_linha": limites.bytes_linha,
            "bytes_campo": limites.bytes_campo,
            "colunas": limites.colunas,
            "segundos": limites.segundos,
        },
        "politica_identidade": {
            "campo": "source_id",
            "duplicata": "erro",
            "distingue_conteudo": True,
        },
        "resultado": {
            "ids_selecionados_unicos": ids_selecionados_unicos,
            "resumo": dict(resumo),
        },
    }


def _hash_manifesto(manifesto):
    canonico = json.dumps(
        manifesto,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonico).hexdigest()


def executar_snapshot(diretorio, *, perfil="fixture"):
    """
    Verifica o snapshot e executa o leitor sobre os bytes preservados.

    IDs selecionados são registrados em SQLite temporário para evitar manter
    um conjunto potencialmente grande inteiro na memória.
    """
    snapshot = verificar_snapshot(diretorio, perfil=perfil)
    original = Path(snapshot.diretorio) / "original.csv"
    limites = PERFIS[perfil]

    contagens = Counter()
    problemas_opcionais = 0
    ids_selecionados_unicos = 0

    with tempfile.TemporaryDirectory(prefix="rastro-execucao-") as pasta:
        banco = Path(pasta) / "identidades.sqlite3"

        with sqlite3.connect(banco) as conexao:
            conexao.execute("""
                CREATE TABLE identidades (
                    source_id TEXT PRIMARY KEY,
                    linha INTEGER NOT NULL,
                    assinatura BLOB NOT NULL
                ) WITHOUT ROWID
            """)

            for resultado in ler_csv(original, limites=limites):
                contagens["lidas"] += 1
                contagens[resultado.categoria] += 1

                if resultado.categoria != "selecionada":
                    continue

                problemas_opcionais += len(resultado.problemas)
                foco = resultado.foco
                assinatura = _assinatura_foco(foco)

                try:
                    conexao.execute(
                        """
                        INSERT INTO identidades(source_id, linha, assinatura)
                        VALUES (?, ?, ?)
                        """,
                        (
                            foco.source_id,
                            resultado.linha,
                            assinatura,
                        ),
                    )
                except sqlite3.IntegrityError:
                    anterior = conexao.execute(
                        """
                        SELECT linha, assinatura
                        FROM identidades
                        WHERE source_id = ?
                        """,
                        (foco.source_id,),
                    ).fetchone()

                    linha_anterior, assinatura_anterior = anterior
                    tipo = (
                        "mesmo conteúdo interpretado"
                        if assinatura_anterior == assinatura
                        else "conteúdo diferente"
                    )

                    raise ErroIdentidade(
                        f"source_id {foco.source_id!r} repetido nas linhas "
                        f"{linha_anterior} e {resultado.linha}: {tipo}"
                    ) from None

                ids_selecionados_unicos += 1

    resumo = {
        "lidas": contagens["lidas"],
        "selecionadas": contagens["selecionada"],
        "fora_do_recorte": contagens["fora_do_recorte"],
        "rejeitadas": contagens["rejeitada"],
        "problemas_opcionais": problemas_opcionais,
    }

    manifesto = _criar_manifesto_execucao(
        snapshot,
        perfil=perfil,
        limites=limites,
        ids_selecionados_unicos=ids_selecionados_unicos,
        resumo=resumo,
    )
    execucao_sha256 = _hash_manifesto(manifesto)

    return ResultadoExecucao(
        snapshot_sha256=snapshot.sha256,
        snapshot_bytes=snapshot.bytes,
        ids_selecionados_unicos=ids_selecionados_unicos,
        resumo=resumo,
        execucao_sha256=execucao_sha256,
        manifesto=manifesto,
    )
