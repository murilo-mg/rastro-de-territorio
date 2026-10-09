"""python -m rastro: preserva, processa e exporta uma entrada local."""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from .execucao import executar_snapshot
from .exportacao import exportar_resultado
from .leitor import PERFIS
from .snapshot import criar_snapshot
from .resultado import verificar_resultado
from .caderno import gerar_caderno


def _consultar(argv):
    comando = argv[0]
    parser = argparse.ArgumentParser(prog=f"python -m rastro {comando}", description=(
        "Confere a consistência interna de uma exportação local."
        if comando == "verificar" else "Gera um caderno HTML offline de uma exportação verificada."
    ))
    parser.add_argument("resultado", type=Path, help="Pasta com os quatro arquivos exportados")
    if comando == "verificar":
        parser.add_argument("--json", action="store_true", help="Resumo verificável por outro programa")
    else:
        parser.add_argument("--saida", type=Path, help="Arquivo .html fora da pasta do resultado")
    args = parser.parse_args(argv[1:])
    try:
        if comando == "caderno":
            caminho, reutilizado = gerar_caderno(args.resultado, args.saida)
            print("caderno:", "reutilizado" if reutilizado else "criado")
            print("arquivo:", caminho)
            print("Abra o arquivo .html no navegador; não é necessário servidor.")
            return
        r = verificar_resultado(args.resultado).execucao
    except (OSError, ValueError) as erro:
        parser.exit(2, f"Não foi possível concluir {comando}: {erro}\n")
    resumo = {
        "versao_verificacao": 1, "verificacao": "consistencia_interna",
        "execucao_sha256": r.execucao_sha256, "snapshot_sha256": r.snapshot_sha256,
        "selecionadas": r.resumo["selecionadas"], "dias_utc": len(r.agregacoes["por_dia_utc"]),
        "municipios_com_codigo": r.agregacoes["municipios_com_codigo"],
        "sem_municipio_id": r.agregacoes["sem_municipio_id"],
        "snapshot_reprocessado": False, "contexto_autenticado": False,
    }
    if args.json:
        print(json.dumps(resumo, ensure_ascii=True, sort_keys=True))
    else:
        for campo, valor in resumo.items():
            print(f"{campo}: {valor}")
        print("Esquema, hash, somas e CSVs conferidos. A origem não foi autenticada.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("verificar", "caderno"):
        return _consultar(argv)
    parser = argparse.ArgumentParser(
        description="Detecções do INPE: Amazonas, agosto/2025, AQUA_M-T.",
        epilog="Outros comandos: verificar PASTA [--json]; caderno PASTA [--saida ARQUIVO.html].",
    )
    entrada = parser.add_mutually_exclusive_group(required=True)
    entrada.add_argument("--csv", type=Path, help="CSV local a preservar em snapshot")
    entrada.add_argument("--snapshot", type=Path, help="Diretório de snapshot já existente")
    parser.add_argument("--perfil", choices=PERFIS, default="fixture")
    parser.add_argument("--snapshots", type=Path, help="Raiz de snapshots para --csv")
    parser.add_argument("--saida", type=Path, default=Path("dados/resultados"))
    argumentos = parser.parse_args(argv)
    if argumentos.snapshot is not None and argumentos.snapshots is not None:
        parser.error("--snapshots só pode ser usado com --csv")
    try:
        diretorio = argumentos.snapshot
        if argumentos.csv is not None:
            diretorio = criar_snapshot(
                argumentos.csv,
                argumentos.snapshots or Path("dados/snapshots"),
                perfil=argumentos.perfil,
            ).diretorio
        resultado = executar_snapshot(diretorio, perfil=argumentos.perfil)
        saida, reutilizado = exportar_resultado(resultado, argumentos.saida)
    except (OSError, ValueError, UnicodeError, csv.Error, sqlite3.Error) as erro:
        parser.exit(2, f"Não foi possível concluir a execução: {erro}\n")
    print("snapshot_sha256:", resultado.snapshot_sha256)
    print("execucao_sha256:", resultado.execucao_sha256)
    print("ids_selecionados_unicos:", resultado.ids_selecionados_unicos)
    for campo, valor in resultado.resumo.items():
        print(f"{campo}: {valor}")
    print("dias_utc:", len(resultado.agregacoes["por_dia_utc"]))
    for campo in ("municipios_com_codigo", "sem_municipio_id", "municipios_com_nomes_divergentes"):
        print(f"{campo}: {resultado.agregacoes[campo]}")
    print("exportacao:", "reutilizada" if reutilizado else "criada")
    print("diretorio_resultado:", saida)


if __name__ == "__main__":
    main()
