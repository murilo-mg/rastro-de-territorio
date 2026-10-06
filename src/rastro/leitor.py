"""Protótipo de leitura e recorte. Sem banco, rede ou deduplicação."""

import argparse
import csv
import math
import os
import re
import stat
import time
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
class LimitesCSV:
    bytes_arquivo: int
    linhas_dados: int
    bytes_linha: int = 64 * 1024
    bytes_campo: int = 4 * 1024
    colunas: int = 32
    segundos: float = 15 * 60

    def __post_init__(self):
        for nome in ("bytes_arquivo", "linhas_dados", "bytes_linha", "bytes_campo", "colunas"):
            valor = getattr(self, nome)
            if type(valor) is not int or valor <= 0:
                raise ValueError(f"Limite {nome} deve ser um inteiro positivo")
        if (isinstance(self.segundos, bool) or not isinstance(self.segundos, (int, float))
                or not math.isfinite(self.segundos) or self.segundos <= 0):
            raise ValueError("Limite segundos deve ser um número finito positivo")


PERFIS = {
    "fixture": LimitesCSV(bytes_arquivo=5 * 1024 * 1024, linhas_dados=20_000),
    "mensal": LimitesCSV(bytes_arquivo=512 * 1024 * 1024, linhas_dados=5_000_000),
}


class ErroLimiteCSV(ValueError):
    """A leitura foi interrompida; nenhum resumo completo deve ser publicado."""


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
            # Limite técnico de inteiro de 32 bits, antes de converter Decimal.
            if numero > 2_147_483_647 or numero != numero.to_integral_value():
                raise ValueError("inteiro fora do formato suportado")
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
    except (ValueError, OverflowError) as erro:
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


def ler_csv(caminho, *, limites=PERFIS["fixture"]):
    """Lê CSV UTF-8 com um registro por linha física, usando memória limitada."""
    caminho = Path(caminho)
    metadados = caminho.stat()
    if not stat.S_ISREG(metadados.st_mode):
        raise ValueError("A entrada deve ser um arquivo regular local")
    inicio_leitura = time.monotonic()
    with caminho.open("rb") as entrada:
        tamanho = os.fstat(entrada.fileno()).st_size
        if tamanho > limites.bytes_arquivo:
            raise ErroLimiteCSV(f"Arquivo excede {limites.bytes_arquivo} bytes")
        campos = None
        total_bytes = 0
        numero_linha = 0
        while True:
            if time.monotonic() - inicio_leitura >= limites.segundos:
                raise ErroLimiteCSV(f"Leitura excede {limites.segundos:g} segundos")
            bruto = entrada.readline(limites.bytes_linha + 1)
            if time.monotonic() - inicio_leitura >= limites.segundos:
                raise ErroLimiteCSV(f"Leitura excede {limites.segundos:g} segundos")
            if not bruto:
                break
            numero_linha += 1
            total_bytes += len(bruto)
            if total_bytes > limites.bytes_arquivo:
                raise ErroLimiteCSV(f"Arquivo excede {limites.bytes_arquivo} bytes durante a leitura")
            if len(bruto) > limites.bytes_linha:
                raise ErroLimiteCSV(f"Linha {numero_linha} excede {limites.bytes_linha} bytes")
            # A contagem inclui linhas vazias após o cabeçalho.
            if numero_linha > 1 and numero_linha - 1 > limites.linhas_dados:
                raise ErroLimiteCSV(f"Arquivo excede {limites.linhas_dados} linhas após o cabeçalho")
            codificacao = "utf-8-sig" if numero_linha == 1 else "utf-8"
            texto = bruto.decode(codificacao)
            try:
                valores = next(csv.reader([texto], strict=True))
            except csv.Error as erro:
                raise ValueError(
                    f"CSV inválido na linha {numero_linha}; campos com quebras de linha não são suportados"
                ) from erro
            if len(valores) > limites.colunas:
                raise ErroLimiteCSV(f"Linha {numero_linha} excede {limites.colunas} colunas")
            for valor in valores:
                if len(valor.encode("utf-8")) > limites.bytes_campo:
                    raise ErroLimiteCSV(f"Campo na linha {numero_linha} excede {limites.bytes_campo} bytes")
            if campos is None:
                campos = [campo.strip() for campo in valores]
                if not campos:
                    raise ValueError("CSV vazio: cabeçalho ausente")
                if len(set(campos)) != len(campos):
                    raise ValueError("Cabeçalho com campos repetidos")
                ausentes = set(CAMPOS) - set(campos)
                if ausentes:
                    raise ValueError("Campos ausentes: " + ", ".join(sorted(ausentes)))
            elif not valores:
                continue
            elif len(valores) != len(campos):
                yield ResultadoLinha(numero_linha, "rejeitada", problemas=("colunas",))
            else:
                yield interpretar(dict(zip(campos, valores)), numero_linha)
        if campos is None:
            raise ValueError("CSV vazio: cabeçalho ausente")


def resumir(caminho, *, limites=PERFIS["fixture"]):
    contagens = Counter()
    problemas_opcionais = 0
    for resultado in ler_csv(caminho, limites=limites):
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
    parser.add_argument("--perfil", choices=PERFIS, default="fixture",
                        help="fixture: 5 MiB; mensal: 512 MiB (padrão: fixture)")
    argumentos = parser.parse_args()
    try:
        resumo = resumir(argumentos.csv, limites=PERFIS[argumentos.perfil])
    except (OSError, UnicodeError, csv.Error, ValueError) as erro:
        parser.exit(2, f"Não foi possível ler o CSV: {erro}\n")
    for nome, valor in resumo.items():
        print(f"{nome}: {valor}")


if __name__ == "__main__":
    main()
