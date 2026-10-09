"""Leitura e conferência offline das exportações das regras 3 e 4.

Confere consistência interna; não substitui reexecutar o snapshot nem autentica
a origem do arquivo ou o contexto, que não participa do hash canônico.
"""

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .agregacoes import CAMPOS_AUSENTES
from .execucao import ResultadoExecucao, _hash_manifesto
from .exportacao import _artefatos
from .leitor import ESTADO_ID, FIM, INICIO, PERFIS, SATELITE
from .territorio import carregar_referencia, conferir_municipios


LIMITE_ARTEFATO = 16 * 1024 * 1024
ARQUIVOS = {"manifesto.json", "por_dia.csv", "por_municipio.csv", "contexto.json"}
ARQUIVOS_NOVOS = ARQUIVOS | {"por_municipio_dia.csv", "conferencia_municipal.csv"}
PROBLEMAS = {
    "numero_dias_sem_chuva": "dias_sem_chuva", "precipitacao": "precipitacao",
    "risco_fogo": "risco_fogo", "frp": "frp", "municipio_id": "municipio_id",
}


@dataclass(frozen=True)
class ResultadoVerificado:
    diretorio: Path
    execucao: ResultadoExecucao
    contexto: dict


def _exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def _chaves(valor, esperadas, campo):
    _exigir(type(valor) is dict and set(valor) == set(esperadas),
            f"Estrutura inválida: {campo}")


def _inteiro(valor, campo, minimo=0, maximo=5_000_000):
    _exigir(type(valor) is int and minimo <= valor <= maximo,
            f"Contagem inválida: {campo}")


def _sha(valor):
    return type(valor) is str and re.fullmatch(r"[0-9a-f]{64}", valor) is not None


def _ler_regular(caminho, limite):
    # O_NONBLOCK evita bloquear em FIFO; O_NOFOLLOW recusa symlink no arquivo.
    with os.fdopen(os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as f:
        info = os.fstat(f.fileno())
        _exigir(stat.S_ISREG(info.st_mode), f"Arquivo não regular: {caminho.name}")
        _exigir(info.st_size <= limite, f"Arquivo excede o limite: {caminho.name}")
        conteudo = f.read(limite + 1)
        _exigir(len(conteudo) <= limite, f"Arquivo excede o limite: {caminho.name}")
        return conteudo


def _json_estrito(conteudo):
    def objeto(pares):
        resultado = {}
        for chave, valor in pares:
            _exigir(chave not in resultado, f"Chave JSON repetida: {chave}")
            resultado[chave] = valor
        return resultado

    def constante(valor):
        raise ValueError(f"Constante JSON inválida: {valor}")

    try:
        return json.loads(conteudo.decode("utf-8"), object_pairs_hook=objeto,
                          parse_constant=constante)
    except (RecursionError, UnicodeError, json.JSONDecodeError) as erro:
        raise ValueError("JSON inválido ou excessivamente aninhado") from erro


def _validar_manifesto(m):
    _exigir(type(m) is dict, "Estrutura inválida: manifesto")
    novo = m.get("versao_manifesto_execucao") == 3
    campos = ["versao_manifesto_execucao", "versao_regras", "recorte", "snapshot",
              "perfil", "limites", "politica_identidade", "resultado"]
    _chaves(m, campos + (["referencia_municipal"] if novo else []), "manifesto")
    _exigir(type(m["versao_manifesto_execucao"]) is int and type(m["versao_regras"]) is int
            and (m["versao_manifesto_execucao"], m["versao_regras"]) in ((2, 3), (3, 4)),
            "Versões não suportadas: esperado manifesto/regras 2/3 ou 3/4")
    _exigir(m["recorte"] == {
        "estado_id": ESTADO_ID, "satelite": SATELITE,
        "inicio_inclusive": INICIO.isoformat(), "fim_exclusive": FIM.isoformat(),
        "fuso_agregacao": "UTC",
    } and type(m["recorte"]["estado_id"]) is int, "Recorte não suportado")
    perfil = m["perfil"]
    _exigir(type(perfil) is str and perfil in PERFIS, "Perfil não suportado")
    limites = asdict(PERFIS[perfil])
    _chaves(m["limites"], limites, "limites")
    _exigir(m["limites"] == limites and all(
        type(m["limites"][k]) is int for k in limites if k != "segundos"
    ) and type(m["limites"]["segundos"]) in (int, float), "Limites não suportados")
    _exigir(m["politica_identidade"] == {
        "campo": "source_id", "duplicata": "erro", "distingue_conteudo": True,
    } and m["politica_identidade"]["distingue_conteudo"] is True,
            "Política de identidade não suportada")
    _chaves(m["snapshot"], ("sha256", "bytes"), "snapshot")
    _exigir(_sha(m["snapshot"]["sha256"]), "Hash do snapshot inválido")
    _inteiro(m["snapshot"]["bytes"], "snapshot.bytes", maximo=limites["bytes_arquivo"])
    resultado = m["resultado"]
    _chaves(resultado, ["ids_selecionados_unicos", "resumo", "agregacoes"]
            + (["conferencia_municipal"] if novo else []), "resultado")
    resumo = resultado["resumo"]
    _chaves(resumo, ("lidas", "selecionadas", "fora_do_recorte", "rejeitadas",
                     "problemas_opcionais"), "resumo")
    for campo, valor in resumo.items():
        multiplicador = len(PROBLEMAS) if campo == "problemas_opcionais" else 1
        _inteiro(valor, campo, maximo=limites["linhas_dados"] * multiplicador)
    total = resumo["selecionadas"]
    _inteiro(resultado["ids_selecionados_unicos"], "ids_selecionados_unicos")
    _exigir(resultado["ids_selecionados_unicos"] == total, "Total de IDs divergente")
    _exigir(resumo["lidas"] == total + resumo["fora_do_recorte"] + resumo["rejeitadas"],
            "Categorias não somam as linhas lidas")
    _validar_agregacoes(resultado["agregacoes"], total, resumo["problemas_opcionais"], 2 if novo else 1)
    if novo:
        referencia = carregar_referencia()
        _exigir(_hash_manifesto(m["referencia_municipal"]) == _hash_manifesto(referencia.descricao),
                "Referência municipal não corresponde à edição preservada")
        conferida = conferir_municipios(resultado["agregacoes"]["por_municipio"], referencia)
        _exigir(_hash_manifesto(resultado["conferencia_municipal"]) == _hash_manifesto(conferida),
                "Conferência municipal divergente")


def _validar_agregacoes(a, total, problemas, versao):
    campos = ["versao_agregacoes", "por_dia_utc", "por_municipio",
                "municipios_com_codigo", "sem_municipio_id",
                "municipios_com_nomes_divergentes", "ausencias", "problemas_por_campo"]
    _chaves(a, campos + (["por_municipio_dia_utc"] if versao == 2 else []),
            "agregacoes")
    _exigir(type(a["versao_agregacoes"]) is int and a["versao_agregacoes"] == versao,
            "Versão de agregações não suportada")
    dias = a["por_dia_utc"]
    n_dias = (FIM.date() - INICIO.date()).days
    _exigir(type(dias) is list and len(dias) == n_dias, "Calendário incompleto")
    for indice, dia in enumerate(dias):
        _chaves(dia, ("dia_utc", "deteccoes"), "dia")
        _exigir(dia["dia_utc"] == (INICIO.date() + timedelta(days=indice)).isoformat(),
                "Calendário fora de ordem ou com dia inválido")
        _inteiro(dia["deteccoes"], "deteccoes por dia", maximo=total)
    _exigir(sum(d["deteccoes"] for d in dias) == total, "Soma diária divergente")
    grupos = a["por_municipio"]
    _exigir(type(grupos) is list, "Tabela municipal inválida")
    codigos = []
    for g in grupos:
        _chaves(g, ("municipio_id", "nomes", "deteccoes", "sem_nome", "nomes_divergentes"),
                "grupo municipal")
        codigo = g["municipio_id"]
        _exigir(codigo is None or (type(codigo) is str and
                re.fullmatch(r"13[0-9]{5}", codigo) is not None), "Código municipal inválido")
        codigos.append(codigo)
        _inteiro(g["deteccoes"], "deteccoes por município", minimo=1, maximo=total)
        _inteiro(g["sem_nome"], "sem_nome", maximo=g["deteccoes"])
        nomes = g["nomes"]
        _exigir(type(nomes) is list and all(type(n) is str and n and n == n.strip()
                and len(n.encode("utf-8")) <= 4096 for n in nomes), "Nomes municipais inválidos")
        _exigir(nomes == sorted(set(nomes)), "Nomes municipais repetidos ou fora de ordem")
        com_nome = g["deteccoes"] - g["sem_nome"]
        _exigir(len(nomes) <= com_nome and bool(nomes) == bool(com_nome),
                "Contagem de nomes municipais incoerente")
        _exigir(type(g["nomes_divergentes"]) is bool and
                g["nomes_divergentes"] == bool(codigo and len(nomes) > 1),
                "Diagnóstico de nomes divergente")
    _exigir(codigos == sorted(set(codigos), key=lambda c: (c is None, c or "")),
            "Códigos municipais repetidos ou fora de ordem")
    _exigir(sum(g["deteccoes"] for g in grupos) == total, "Soma municipal divergente")
    esperados = {
        "municipios_com_codigo": sum(c is not None for c in codigos),
        "sem_municipio_id": sum(g["deteccoes"] for g in grupos if g["municipio_id"] is None),
        "municipios_com_nomes_divergentes": sum(g["nomes_divergentes"] for g in grupos),
    }
    for campo, valor in esperados.items():
        _inteiro(a[campo], campo, maximo=total)
        _exigir(a[campo] == valor, f"Diagnóstico divergente: {campo}")
    _chaves(a["ausencias"], CAMPOS_AUSENTES, "ausencias")
    for campo, valor in a["ausencias"].items():
        _inteiro(valor, f"ausencias.{campo}", maximo=total)
    _exigir(a["ausencias"]["municipio_id"] == a["sem_municipio_id"] and
            a["ausencias"]["municipio"] == sum(g["sem_nome"] for g in grupos),
            "Ausências municipais divergentes")
    por_campo = a["problemas_por_campo"]
    _exigir(type(por_campo) is dict and set(por_campo) <= set(PROBLEMAS),
            "Campos de problemas inválidos")
    for campo, valor in por_campo.items():
        _inteiro(valor, f"problemas.{campo}", minimo=1, maximo=a["ausencias"][PROBLEMAS[campo]])
    _exigir(sum(por_campo.values()) == problemas, "Total de problemas divergente")
    if versao == 2:
        matriz = a["por_municipio_dia_utc"]
        _exigir(type(matriz) is list and len(matriz) == len(grupos), "Matriz municipal incompleta")
        somas_diarias = [0] * n_dias
        for linha, grupo in zip(matriz, grupos):
            _chaves(linha, ("municipio_id", "deteccoes_por_dia"), "matriz municipal")
            _exigir(linha["municipio_id"] == grupo["municipio_id"], "Ordem da matriz municipal divergente")
            valores = linha["deteccoes_por_dia"]
            _exigir(type(valores) is list and len(valores) == n_dias, "Calendário municipal incompleto")
            for i, n in enumerate(valores):
                _inteiro(n, "deteccoes município/dia", maximo=grupo["deteccoes"])
                somas_diarias[i] += n
            _exigir(sum(valores) == grupo["deteccoes"], "Soma por município/dia divergente")
        _exigir(somas_diarias == [d["deteccoes"] for d in dias], "Somas diárias da matriz divergentes")


def _validar_contexto(c):
    _chaves(c, ("primeira_exportacao_em_utc", "python", "plataforma", "revisao_git",
                "alteracoes_locais", "codigo_sha256"), "contexto")
    _exigir(_sha(c["codigo_sha256"]), "Hash de código inválido no contexto")
    for campo in ("python", "plataforma", "primeira_exportacao_em_utc"):
        _exigir(type(c[campo]) is str and bool(c[campo]), f"Contexto inválido: {campo}")
    try:
        data = datetime.fromisoformat(c["primeira_exportacao_em_utc"])
        _exigir(data.utcoffset() == timedelta(0), "Data do contexto precisa estar em UTC")
    except ValueError as erro:
        raise ValueError("Data inválida no contexto") from erro
    _exigir(c["alteracoes_locais"] is None or type(c["alteracoes_locais"]) is bool,
            "Indicador de alterações locais inválido")
    revisao = c["revisao_git"]
    _exigir(revisao is None or (type(revisao) is str and
            re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revisao) is not None),
            "Revisão Git inválida no contexto")


def verificar_resultado(diretorio):
    """Lê a exportação, valida esquema/hash/somas e compara todos os CSVs.

    Aceita pasta renomeada para permitir cópias. A identidade vem do manifesto.
    Não acessa rede, snapshot, Git nem o ambiente registrado na exportação.
    """
    diretorio = Path(diretorio)
    _exigir(not diretorio.is_symlink() and diretorio.is_dir(),
            "O resultado precisa ser um diretório regular")
    arquivos = {p.name for p in diretorio.iterdir()}
    _exigir(arquivos == ARQUIVOS or arquivos == ARQUIVOS_NOVOS,
            "Resultado incompleto ou com arquivos inesperados")
    conteudos = {nome: _ler_regular(diretorio / nome, 8192 if nome == "contexto.json"
                                   else LIMITE_ARTEFATO) for nome in sorted(arquivos)}
    registro = _json_estrito(conteudos["manifesto.json"])
    _chaves(registro, ("execucao_sha256", "manifesto"), "registro")
    _exigir(_sha(registro["execucao_sha256"]), "Hash da execução inválido")
    m = registro["manifesto"]
    _validar_manifesto(m)
    _exigir(arquivos == (ARQUIVOS_NOVOS if m["versao_manifesto_execucao"] == 3 else ARQUIVOS),
            "Conjunto de arquivos incompatível com a versão do manifesto")
    _exigir(_hash_manifesto(m) == registro["execucao_sha256"], "Hash da execução divergente")
    r = m["resultado"]
    execucao = ResultadoExecucao(
        m["snapshot"]["sha256"], m["snapshot"]["bytes"], r["ids_selecionados_unicos"],
        r["resumo"], registro["execucao_sha256"], m, r["agregacoes"],
    )
    for nome, esperado in _artefatos(execucao).items():
        _exigir(conteudos[nome] == esperado, f"Artefato divergente: {nome}")
    contexto = _json_estrito(conteudos["contexto.json"])
    _validar_contexto(contexto)
    return ResultadoVerificado(diretorio, execucao, contexto)
