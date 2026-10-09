"""Referência cadastral IBGE DTB 2025 preservada; nenhuma consulta à rede."""

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


RAIZ_REFERENCIA = Path(__file__).resolve().parents[2] / "referencias/ibge/dtb2025"
MANIFESTO_SHA256 = "3ce4bd162a2bde157d5f8be51992ff0b4bed28098d7c10d0b5c8223e5eef1b68"


@dataclass(frozen=True)
class ReferenciaMunicipal:
    descricao: dict
    municipios: dict[str, str]


def _bytes_verificados(arquivo, limite, esperado):
    if arquivo.is_symlink() or not arquivo.is_file() or arquivo.stat().st_size > limite:
        raise ValueError(f"Arquivo de referência inválido: {arquivo.name}")
    with arquivo.open("rb") as f:
        dados = f.read(limite + 1)
    if len(dados) > limite or hashlib.sha256(dados).hexdigest() != esperado:
        raise ValueError(f"Hash da referência divergente: {arquivo.name}")
    return dados


def carregar_referencia(raiz=RAIZ_REFERENCIA):
    """Confere bytes fixados nesta revisão e devolve os 62 códigos e nomes."""
    raiz = Path(raiz)
    if raiz.is_symlink() or not raiz.is_dir():
        raise ValueError("Diretório da referência municipal inválido")
    meta = json.loads(_bytes_verificados(raiz / "manifesto.json", 8192, MANIFESTO_SHA256))
    _bytes_verificados(raiz / "original.ods", 1024 * 1024, meta["ods_sha256"])
    dados = _bytes_verificados(raiz / "municipios_am.csv", 32 * 1024, meta["csv_sha256"])
    leitor = csv.DictReader(io.StringIO(dados.decode("utf-8"), newline=""))
    if leitor.fieldnames != ["municipio_id", "nome"]:
        raise ValueError("Cabeçalho da referência municipal inválido")
    municipios = {}
    for linha in leitor:
        codigo, nome = linha["municipio_id"], linha["nome"]
        if (not re.fullmatch(r"13[0-9]{5}", codigo) or codigo in municipios
                or not nome or nome != nome.strip() or set(linha) != {"municipio_id", "nome"}):
            raise ValueError("Linha da referência municipal inválida")
        municipios[codigo] = nome
    if len(municipios) != meta["quantidade_municipios"] or list(municipios) != sorted(municipios):
        raise ValueError("Quantidade ou ordem da referência municipal divergente")
    return ReferenciaMunicipal({**meta, "manifesto_sha256": MANIFESTO_SHA256}, municipios)


def normalizar_nome(nome):
    texto = unicodedata.normalize("NFKD", nome)
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def conferir_municipios(grupos, referencia):
    """Compara nomes sem trocar os valores originais nem descartar detecções."""
    linhas = []
    for grupo in grupos:
        codigo = grupo["municipio_id"]
        oficial = referencia.municipios.get(codigo)
        situacao = "ausente" if codigo is None else "encontrado" if oficial else "nao_encontrado"
        linha = {"municipio_id": codigo, "nome_referencia": oficial, "situacao_codigo": situacao,
                 "nomes_iguais": [], "nomes_equivalentes": [], "nomes_divergentes": [],
                 "nomes_sem_referencia": []}
        for nome in grupo["nomes"]:
            if oficial is None:
                campo = "nomes_sem_referencia"
            elif nome == oficial:
                campo = "nomes_iguais"
            elif normalizar_nome(nome) == normalizar_nome(oficial):
                campo = "nomes_equivalentes"
            else:
                campo = "nomes_divergentes"
            linha[campo].append(nome)
        linhas.append(linha)
    return {
        "versao_conferencia": 1,
        "codigos_encontrados": sum(x["situacao_codigo"] == "encontrado" for x in linhas),
        "codigos_nao_encontrados": sum(x["situacao_codigo"] == "nao_encontrado" for x in linhas),
        "grupos_com_nomes_divergentes": sum(bool(x["nomes_divergentes"]) for x in linhas),
        "por_municipio": linhas,
    }


def extrair_municipios_ods(conteudo):
    """Extrai o subconjunto AM da planilha DTB 2025 em CSV canônico.

    Usado para reproduzir a referência, não durante cada leitura analítica.
    O documento original continua preservado sem alterações.
    """
    if len(conteudo) > 1024 * 1024:
        raise ValueError("ODS excede o limite de 1 MiB")
    try:
        with ZipFile(io.BytesIO(conteudo)) as z:
            info = z.getinfo("content.xml")
            if info.file_size > 16 * 1024 * 1024:
                raise ValueError("XML do ODS excede 16 MiB")
            xml = z.read(info)
        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
            raise ValueError("Declarações XML não suportadas")
        root = ElementTree.fromstring(xml)
    except (BadZipFile, KeyError, ElementTree.ParseError) as erro:
        raise ValueError("ODS inválido") from erro
    ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    tabelas = root.findall(f".//{{{ns}}}table")
    if len(tabelas) != 1 or tabelas[0].get(f"{{{ns}}}name") != "DTB_Municípios":
        raise ValueError("Planilha municipal DTB não encontrada")
    dados, cabecalho, data_base = {}, False, False
    for row in tabelas[0].findall(f"{{{ns}}}table-row"):
        celulas = []
        for cell in row:
            if len(celulas) >= 10:
                break
            repeticoes = int(cell.get(f"{{{ns}}}number-columns-repeated", "1"))
            if repeticoes <= 0:
                raise ValueError("Repetição de coluna inválida")
            celulas.extend(["".join(cell.itertext())] * min(repeticoes, 10 - len(celulas)))
        if not celulas:
            continue
        if celulas[0] == "DATA BASE: 31/12/2025":
            data_base = True
        if celulas[0] == "UF":
            if celulas[7:9] != ["Código Município Completo", "Nome_Município"]:
                raise ValueError("Cabeçalho DTB não suportado")
            cabecalho = True
        if celulas[0] != "13":
            continue
        if not cabecalho or len(celulas) < 9 or row.get(f"{{{ns}}}number-rows-repeated", "1") != "1":
            raise ValueError("Linha municipal DTB não suportada")
        codigo, nome = celulas[7:9]
        if not re.fullmatch(r"13[0-9]{5}", codigo) or codigo in dados or not nome:
            raise ValueError("Código municipal DTB inválido ou repetido")
        dados[codigo] = nome
    if not cabecalho or not data_base or len(dados) != 62:
        raise ValueError("Data-base ou quantidade municipal DTB divergente")
    texto = io.StringIO(newline="")
    escritor = csv.writer(texto, lineterminator="\n")
    escritor.writerow(["municipio_id", "nome"])
    escritor.writerows(sorted(dados.items()))
    return texto.getvalue().encode("utf-8")
