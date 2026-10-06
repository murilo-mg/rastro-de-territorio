"""Protótipo de leitura e recorte. Sem banco, rede ou deduplicação."""

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


CAMPOS = (
    "id", "lat", "lon", "data_hora_gmt", "satelite", "municipio", "estado",
    "pais", "municipio_id", "estado_id", "pais_id", "numero_dias_sem_chuva",
    "precipitacao", "risco_fogo", "bioma", "frp",
)
INICIO = datetime(2025, 8, 1, tzinfo=timezone.utc)
FIM = datetime(2025, 9, 1, tzinfo=timezone.utc)
FORMATO_DATA = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)


@dataclass(frozen=True)
class Foco:
    source_id: str
    latitude: Decimal
    longitude: Decimal
    observado_em: datetime
    satelite: str
    estado_id: int
    dias_sem_chuva: int | None
    precipitacao: Decimal | None
    risco_fogo: Decimal | None
    frp: Decimal | None


@dataclass(frozen=True)
class ResultadoLinha:
    linha: int
    categoria: str
    foco: Foco | None = None
    problemas: tuple[str, ...] = ()


def numero_finito(valor):
    try:
        numero = Decimal(valor)
    except InvalidOperation as erro:
        raise ValueError("número inválido") from erro
    if not numero.is_finite():
        raise ValueError("número não finito")
    return numero


def data_utc(valor):
    if not FORMATO_DATA.fullmatch(valor):
        raise ValueError("data e hora inválidas")
    data = datetime.fromisoformat(valor)
    # O nome data_hora_gmt declara UTC quando não há offset explícito.
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc)


def opcional(valor, campo, problemas, *, sentinela=False,
             inteiro=False, maximo=None):
    if valor == "":
        return None
    try:
        numero = numero_finito(valor)
        if sentinela and numero == Decimal("-999"):
            return None
        if numero < 0 or (maximo is not None and numero > maximo):
            raise ValueError("fora dos limites")
        if inteiro:
            if numero != numero.to_integral_value():
                raise ValueError("inteiro esperado")
            return int(numero)
        return numero
    except ValueError:
        problemas.append(campo)
        return None


def interpretar(linha, numero_linha):
    if None in linha or any(valor is None for valor in linha.values()):
        return ResultadoLinha(numero_linha, "rejeitada", problemas=("colunas",))
    valores = {campo: valor.strip() for campo, valor in linha.items()}
    try:
        if not valores["id"] or not valores["satelite"]:
            raise ValueError("id ou satélite vazio")
        estado_id = int(valores["estado_id"])
        if estado_id <= 0:
            raise ValueError("código de estado inválido")
        observado_em = data_utc(valores["data_hora_gmt"])
        latitude = numero_finito(valores["lat"])
        longitude = numero_finito(valores["lon"])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("coordenadas fora dos limites")
    except ValueError as erro:
        return ResultadoLinha(numero_linha, "rejeitada", problemas=(str(erro),))

    if not (valores["satelite"] == "AQUA_M-T" and estado_id == 13
            and INICIO <= observado_em < FIM):
        return ResultadoLinha(numero_linha, "fora_do_recorte")

    problemas = []
    foco = Foco(
        source_id=valores["id"], latitude=latitude, longitude=longitude,
        observado_em=observado_em, satelite=valores["satelite"],
        estado_id=estado_id,
        dias_sem_chuva=opcional(valores["numero_dias_sem_chuva"],
                               "numero_dias_sem_chuva", problemas,
                               sentinela=True, inteiro=True),
        precipitacao=opcional(valores["precipitacao"], "precipitacao",
                             problemas, sentinela=True),
        risco_fogo=opcional(valores["risco_fogo"], "risco_fogo",
                           problemas, sentinela=True, maximo=1),
        frp=opcional(valores["frp"], "frp", problemas),
    )
    return ResultadoLinha(numero_linha, "selecionada", foco, tuple(problemas))


def ler_csv(caminho):
    """Entrega uma linha por vez; o chamador não precisa acumular o arquivo."""
    with Path(caminho).open(encoding="utf-8-sig", newline="") as entrada:
        leitor = csv.DictReader(entrada, strict=True)
        if leitor.fieldnames is None:
            raise ValueError("CSV vazio: cabeçalho ausente")
        campos = [campo.strip() for campo in leitor.fieldnames]
        if len(set(campos)) != len(campos):
            raise ValueError("Cabeçalho com campos repetidos")
        ausentes = set(CAMPOS) - set(campos)
        if ausentes:
            raise ValueError("Campos ausentes: " + ", ".join(sorted(ausentes)))
        leitor.fieldnames = campos
        for linha in leitor:
            yield interpretar(linha, leitor.line_num)


def resumir(caminho):
    contagens = Counter()
    problemas_opcionais = 0
    for resultado in ler_csv(caminho):
        contagens["lidas"] += 1
        contagens[resultado.categoria] += 1
        if resultado.categoria == "selecionada":
            problemas_opcionais += len(resultado.problemas)
    return {
        "lidas": contagens["lidas"],
        "selecionadas": contagens["selecionada"],
        "fora_do_recorte": contagens["fora_do_recorte"],
        "rejeitadas": contagens["rejeitada"],
        "problemas_opcionais": problemas_opcionais,
    }


def main():
    parser = argparse.ArgumentParser(description="Recorte inicial: AM, agosto/2025, AQUA_M-T")
    parser.add_argument("csv", type=Path)
    argumentos = parser.parse_args()
    try:
        resumo = resumir(argumentos.csv)
    except (OSError, UnicodeError, csv.Error, ValueError) as erro:
        parser.exit(2, f"Não foi possível ler o CSV: {erro}\n")
    for nome, valor in resumo.items():
        print(f"{nome}: {valor}")


if __name__ == "__main__":
    main()
