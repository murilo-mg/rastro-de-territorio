import copy
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rastro.execucao import _hash_manifesto, executar_snapshot
from rastro.exportacao import _json_bytes, exportar_resultado
from rastro.leitor import CAMPOS
from rastro.resultado import verificar_resultado
from rastro.snapshot import criar_snapshot
from test_leitor import FIXTURE, exemplo


class ExportacaoTemporaria(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        self.snapshot = criar_snapshot(FIXTURE, self.raiz / "snapshots", reserva_bytes=0)
        self.execucao = executar_snapshot(self.snapshot.diretorio)
        self.pasta, _ = exportar_resultado(self.execucao, self.raiz / "resultados")

    def exportar_linhas(self, linhas):
        arquivo = self.raiz / "entrada.csv"
        with arquivo.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows(linhas)
        s = criar_snapshot(arquivo, self.raiz / "snapshots", reserva_bytes=0)
        return exportar_resultado(executar_snapshot(s.diretorio), self.raiz / "resultados")[0]

    def adulterar(self, alterar, recalcular=True):
        registro = {"execucao_sha256": self.execucao.execucao_sha256,
                    "manifesto": copy.deepcopy(self.execucao.manifesto)}
        alterar(registro["manifesto"])
        if recalcular:
            registro["execucao_sha256"] = _hash_manifesto(registro["manifesto"])
        (self.pasta / "manifesto.json").write_bytes(_json_bytes(registro))


class TestResultado(ExportacaoTemporaria):
    def test_verifica_exportacao_sem_acessar_snapshot(self):
        self.snapshot.diretorio.rename(self.raiz / "snapshot-guardado")
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir()}
        resultado = verificar_resultado(self.pasta)
        self.assertEqual(resultado.execucao, self.execucao)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.pasta.iterdir()})

    def test_aceita_copia_em_pasta_renomeada(self):
        nova = self.raiz / "copia"
        self.pasta.rename(nova)
        self.assertEqual(verificar_resultado(nova).execucao.execucao_sha256,
                         self.execucao.execucao_sha256)

    def test_recusa_csv_adulterado(self):
        for nome in ("por_dia.csv", "por_municipio.csv"):
            with self.subTest(nome=nome):
                arquivo = self.pasta / nome
                original = arquivo.read_bytes()
                arquivo.write_bytes(original + b"linha extra\n")
                with self.assertRaisesRegex(ValueError, "Artefato divergente"):
                    verificar_resultado(self.pasta)
                arquivo.write_bytes(original)

    def test_recusa_hash_errado(self):
        self.adulterar(lambda m: m["snapshot"].update(sha256="0" * 64), recalcular=False)
        with self.assertRaisesRegex(ValueError, "Hash da execução divergente"):
            verificar_resultado(self.pasta)

    def test_recusa_somas_incoerentes_mesmo_com_hash_recalculado(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"]["por_dia_utc"][0].update(deteccoes=0))
        with self.assertRaisesRegex(ValueError, "Soma diária"):
            verificar_resultado(self.pasta)

    def test_recusa_dias_duplicados_ou_fora_de_ordem(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"]["por_dia_utc"][1].update(dia_utc="2025-08-01"))
        with self.assertRaisesRegex(ValueError, "Calendário"):
            verificar_resultado(self.pasta)

    def test_recusa_booleano_no_lugar_de_contagem(self):
        self.adulterar(lambda m: m["resultado"]["resumo"].update(rejeitadas=False))
        with self.assertRaisesRegex(ValueError, "Contagem inválida"):
            verificar_resultado(self.pasta)

    def test_recusa_versoes_futuras(self):
        self.adulterar(lambda m: m.update(versao_regras=5))
        with self.assertRaisesRegex(ValueError, "Versões não suportadas"):
            verificar_resultado(self.pasta)

    def test_recusa_diagnostico_municipal_incoerente(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"].update(municipios_com_codigo=0))
        with self.assertRaisesRegex(ValueError, "Diagnóstico divergente"):
            verificar_resultado(self.pasta)

    def test_recusa_problemas_sem_ausencias(self):
        def alterar(m):
            m["resultado"]["agregacoes"]["problemas_por_campo"] = {"precipitacao": 1}
            m["resultado"]["resumo"]["problemas_opcionais"] = 1
        self.adulterar(alterar)
        with self.assertRaisesRegex(ValueError, "Contagem inválida"):
            verificar_resultado(self.pasta)

    def test_recusa_grupo_municipal_duplicado(self):
        def alterar(m):
            grupos = m["resultado"]["agregacoes"]["por_municipio"]
            grupos.append(copy.deepcopy(grupos[0]))
        self.adulterar(alterar)
        with self.assertRaisesRegex(ValueError, "Códigos municipais repetidos"):
            verificar_resultado(self.pasta)

    def test_recusa_json_ambiguo_ou_nao_finito(self):
        arquivo = self.pasta / "manifesto.json"
        for conteudo in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xff'):
            with self.subTest(conteudo=conteudo):
                arquivo.write_bytes(conteudo)
                with self.assertRaises(ValueError):
                    verificar_resultado(self.pasta)

    def test_recusa_json_excessivamente_aninhado(self):
        (self.pasta / "manifesto.json").write_bytes(b"[" * 2000 + b"0" + b"]" * 2000)
        with self.assertRaises(ValueError):
            verificar_resultado(self.pasta)

    def test_recusa_arquivo_excedendo_limite_antes_de_interpretar(self):
        with patch("rastro.resultado.LIMITE_ARTEFATO", 10):
            with self.assertRaisesRegex(ValueError, "excede o limite"):
                verificar_resultado(self.pasta)

    def test_recusa_pasta_incompleta_e_arquivo_extra(self):
        extra = self.pasta / "extra.txt"
        extra.write_text("extra")
        with self.assertRaisesRegex(ValueError, "inesperados"):
            verificar_resultado(self.pasta)
        extra.unlink()
        (self.pasta / "por_dia.csv").unlink()
        with self.assertRaisesRegex(ValueError, "incompleto"):
            verificar_resultado(self.pasta)

    def test_recusa_symlink_no_arquivo_e_na_pasta(self):
        arquivo = self.pasta / "por_dia.csv"
        guardado = self.raiz / "por_dia.csv"
        arquivo.rename(guardado)
        arquivo.symlink_to(guardado)
        with self.assertRaises(OSError):
            verificar_resultado(self.pasta)
        link = self.raiz / "atalho"
        link.symlink_to(self.pasta, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "diretório regular"):
            verificar_resultado(link)

    def test_recusa_fifo_sem_bloquear(self):
        arquivo = self.pasta / "por_dia.csv"
        arquivo.unlink()
        os.mkfifo(arquivo)
        with self.assertRaisesRegex(ValueError, "não regular"):
            verificar_resultado(self.pasta)

    def test_contexto_valido_alterado_nao_muda_identidade(self):
        arquivo = self.pasta / "contexto.json"
        contexto = json.loads(arquivo.read_text())
        contexto["revisao_git"] = "1" * 40
        arquivo.write_bytes(_json_bytes(contexto))
        r = verificar_resultado(self.pasta)
        self.assertEqual(r.execucao.execucao_sha256, self.execucao.execucao_sha256)
        self.assertEqual(r.contexto["revisao_git"], "1" * 40)

    def test_recusa_contexto_malformado(self):
        arquivo = self.pasta / "contexto.json"
        original = json.loads(arquivo.read_text())
        for campo, valor in (("codigo_sha256", "abc"), ("revisao_git", "main"),
                             ("alteracoes_locais", "false"),
                             ("primeira_exportacao_em_utc", "2025-01-01T00:00:00")):
            with self.subTest(campo=campo):
                arquivo.write_bytes(_json_bytes({**original, campo: valor}))
                with self.assertRaises(ValueError):
                    verificar_resultado(self.pasta)

    def test_valida_recorte_vazio(self):
        pasta = self.exportar_linhas([exemplo(satelite="GOES-19")])
        self.assertEqual(verificar_resultado(pasta).execucao.resumo["selecionadas"], 0)

    def test_valida_ausencias_nomes_divergentes_e_problemas(self):
        pasta = self.exportar_linhas([
            exemplo(id="a", municipio="MANAUS", risco_fogo="NaN"),
            exemplo(id="b", municipio="Manaus", frp="-1"),
            exemplo(id="c", municipio="", municipio_id="inválido", numero_dias_sem_chuva="-2"),
        ])
        a = verificar_resultado(pasta).execucao.agregacoes
        self.assertEqual(a["sem_municipio_id"], 1)
        self.assertEqual(a["municipios_com_nomes_divergentes"], 1)

    def test_estrutura_malformada_produz_erro_controlado(self):
        mudancas = [lambda m: m.update(recorte=[]), lambda m: m.update(perfil=[]),
                    lambda m: m.update(resultado=None),
                    lambda m: m["resultado"]["agregacoes"].update(por_dia_utc={}),
                    lambda m: m["resultado"]["agregacoes"]["por_municipio"][0].update(nomes=[1])]
        for alterar in mudancas:
            with self.subTest(alterar=alterar):
                self.adulterar(alterar)
                with self.assertRaises(ValueError):
                    verificar_resultado(self.pasta)
