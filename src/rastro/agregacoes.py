"""Agregações dos focos aceitos, sem manter a lista de observações em RAM."""

from collections import Counter
from datetime import timedelta

from .leitor import INICIO, FIM


CAMPOS_AUSENTES = (
    "dias_sem_chuva", "precipitacao", "risco_fogo", "frp",
    "municipio_id", "municipio",
)


class AcumuladorAgregacoes:
    """Compartilha o SQLite temporário da execução, após o controle de IDs."""

    def __init__(self, conexao):
        self.conexao = conexao
        self.ausencias = Counter()
        self.problemas = Counter()
        conexao.execute("""
            CREATE TABLE agregados (
                dia TEXT NOT NULL,
                municipio_id TEXT NOT NULL,
                nome TEXT NOT NULL,
                deteccoes INTEGER NOT NULL,
                PRIMARY KEY (dia, municipio_id, nome)
            ) WITHOUT ROWID
        """)

    def adicionar(self, foco, problemas):
        self.conexao.execute("""
            INSERT INTO agregados(dia, municipio_id, nome, deteccoes)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(dia, municipio_id, nome)
            DO UPDATE SET deteccoes = deteccoes + 1
        """, (foco.observado_em.date().isoformat(), foco.municipio_id or "",
              foco.municipio or ""))
        self.ausencias.update(
            campo for campo in CAMPOS_AUSENTES if getattr(foco, campo) is None
        )
        self.problemas.update(problemas)

    def concluir(self, total):
        dias = dict(self.conexao.execute(
            "SELECT dia, SUM(deteccoes) FROM agregados GROUP BY dia"
        ))
        por_dia = []
        dia = INICIO.date()
        while dia < FIM.date():
            chave = dia.isoformat()
            por_dia.append({"dia_utc": chave, "deteccoes": dias.get(chave, 0)})
            dia += timedelta(days=1)

        municipios = {}
        for codigo, nome, quantidade in self.conexao.execute("""
            SELECT municipio_id, nome, SUM(deteccoes)
            FROM agregados GROUP BY municipio_id, nome
            ORDER BY municipio_id, nome
        """):
            grupo = municipios.setdefault(codigo, {
                "municipio_id": codigo or None, "nomes": [],
                "deteccoes": 0, "sem_nome": 0, "nomes_divergentes": False,
            })
            grupo["deteccoes"] += quantidade
            if nome:
                grupo["nomes"].append(nome)
            else:
                grupo["sem_nome"] += quantidade
            # O grupo sem código não representa um único município.
            grupo["nomes_divergentes"] = bool(codigo and len(grupo["nomes"]) > 1)

        por_municipio = [municipios[k] for k in sorted(
            municipios, key=lambda k: (k == "", k)
        )]
        por_codigo_dia = dict(((codigo, dia), quantidade) for codigo, dia, quantidade
                              in self.conexao.execute("""
            SELECT municipio_id, dia, SUM(deteccoes)
            FROM agregados GROUP BY municipio_id, dia
        """))
        matriz = [{"municipio_id": grupo["municipio_id"], "deteccoes_por_dia": [
            por_codigo_dia.get((grupo["municipio_id"] or "", d["dia_utc"]), 0)
            for d in por_dia
        ]} for grupo in por_municipio]
        if (sum(x["deteccoes"] for x in por_dia) != total
                or sum(x["deteccoes"] for x in por_municipio) != total
                or any(sum(x["deteccoes_por_dia"][i] for x in matriz) != d["deteccoes"]
                       for i, d in enumerate(por_dia))):
            raise ValueError("As agregações não correspondem ao total selecionado")

        return {
            "versao_agregacoes": 2,
            "por_dia_utc": por_dia,
            "por_municipio": por_municipio,
            "por_municipio_dia_utc": matriz,
            "municipios_com_codigo": sum(x["municipio_id"] is not None for x in por_municipio),
            "sem_municipio_id": self.ausencias["municipio_id"],
            "municipios_com_nomes_divergentes": sum(x["nomes_divergentes"] for x in por_municipio),
            "ausencias": {k: self.ausencias[k] for k in CAMPOS_AUSENTES},
            "problemas_por_campo": dict(sorted(self.problemas.items())),
        }
