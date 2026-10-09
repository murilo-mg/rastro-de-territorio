"""python -m rastro: preserva, processa e exporta uma entrada local."""

import argparse
import csv
import sqlite3
from pathlib import Path

from .execucao import executar_snapshot
from .exportacao import exportar_resultado
from .leitor import PERFIS
from .snapshot import criar_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Detecções do INPE: Amazonas, agosto/2025, AQUA_M-T."
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
