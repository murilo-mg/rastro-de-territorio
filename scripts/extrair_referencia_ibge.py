"""Reproduz o CSV cadastral da DTB 2025; execute com PYTHONPATH=src."""

import argparse
from pathlib import Path

from rastro.territorio import extrair_municipios_ods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ods", type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args()
    try:
        if not args.ods.is_file() or args.ods.stat().st_size > 1024 * 1024:
            raise ValueError("ODS precisa ser um arquivo local de até 1 MiB")
        conteudo = extrair_municipios_ods(args.ods.read_bytes())
        with args.saida.open("xb") as arquivo:
            arquivo.write(conteudo)
    except (OSError, ValueError) as erro:
        parser.exit(2, f"Não foi possível extrair a referência: {erro}\n")
    print("arquivo:", args.saida)


if __name__ == "__main__":
    main()
