import copy
import csv
import json
from dataclasses import replace

from rastro.caderno import gerar_caderno
from rastro.execucao import _hash_manifesto
from rastro.exportacao import exportar_resultado
from rastro.resultado import verificar_resultado
from test_caderno import ExtrairHTML
from test_leitor import exemplo
from test_resultado import ExportacaoTemporaria


class TestAnaliseMunicipal(ExportacaoTemporaria):
    def legado(self):
        m = copy.deepcopy(self.execucao.manifesto)
        m["versao_manifesto_execucao"], m["versao_regras"] = 2, 3
        del m["referencia_municipal"]
        del m["resultado"]["conferencia_municipal"]
        a = m["resultado"]["agregacoes"]
        a["versao_agregacoes"] = 1
        del a["por_municipio_dia_utc"]
        r = replace(self.execucao, manifesto=m, agregacoes=a, execucao_sha256=_hash_manifesto(m))
        return exportar_resultado(r, self.raiz / "historicos")[0]

    def test_exporta_matriz_e_conferencia_com_csvs_consistentes(self):
        with (self.pasta / "por_municipio_dia.csv").open(encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
        self.assertEqual(len(linhas), 31)
        self.assertEqual(sum(int(x["deteccoes"]) for x in linhas), 2)
        self.assertEqual(linhas[1]["deteccoes"], "0")
        self.assertEqual(linhas[-1]["dia_utc"], "2025-08-31")
        with (self.pasta / "conferencia_municipal.csv").open(encoding="utf-8", newline="") as f:
            c = list(csv.DictReader(f))
        self.assertEqual(c[0]["nome_referencia"], "Manaus")
        self.assertEqual(json.loads(c[0]["nomes_equivalentes_json"]), ["MANAUS"])

    def test_matriz_vazia_e_exportada_com_cabecalho(self):
        pasta = self.exportar_linhas([exemplo(satelite="GOES-19")])
        r = verificar_resultado(pasta)
        self.assertEqual(r.execucao.agregacoes["por_municipio_dia_utc"], [])
        self.assertEqual((pasta / "por_municipio_dia.csv").read_text(), "municipio_id,dia_utc,deteccoes\n")

    def test_recusa_matriz_com_soma_municipal_alterada(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"]["por_municipio_dia_utc"][0]["deteccoes_por_dia"].__setitem__(0, 0))
        with self.assertRaisesRegex(ValueError, "Soma por município/dia"):
            verificar_resultado(self.pasta)

    def test_recusa_matriz_que_preserva_total_mas_troca_dia(self):
        def alterar(m):
            valores = m["resultado"]["agregacoes"]["por_municipio_dia_utc"][0]["deteccoes_por_dia"]
            valores[0], valores[1] = 0, 1
        self.adulterar(alterar)
        with self.assertRaisesRegex(ValueError, "Somas diárias da matriz"):
            verificar_resultado(self.pasta)

    def test_recusa_matriz_com_calendario_incompleto(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"]["por_municipio_dia_utc"][0]["deteccoes_por_dia"].pop())
        with self.assertRaisesRegex(ValueError, "Calendário municipal"):
            verificar_resultado(self.pasta)

    def test_recusa_matriz_com_codigo_divergente(self):
        self.adulterar(lambda m: m["resultado"]["agregacoes"]["por_municipio_dia_utc"][0].update(municipio_id="1300144"))
        with self.assertRaisesRegex(ValueError, "Ordem da matriz"):
            verificar_resultado(self.pasta)

    def test_recusa_diagnostico_oficial_adulterado_com_hash_recalculado(self):
        self.adulterar(lambda m: m["resultado"]["conferencia_municipal"].update(codigos_encontrados=0))
        with self.assertRaisesRegex(ValueError, "Conferência municipal divergente"):
            verificar_resultado(self.pasta)

    def test_recusa_referencia_de_outra_edicao(self):
        self.adulterar(lambda m: m["referencia_municipal"].update(edicao=2024))
        with self.assertRaisesRegex(ValueError, "Referência municipal"):
            verificar_resultado(self.pasta)

    def test_csv_municipal_diario_adulterado_e_recusado(self):
        (self.pasta / "por_municipio_dia.csv").write_text("modificado")
        with self.assertRaisesRegex(ValueError, "Artefato divergente"):
            verificar_resultado(self.pasta)

    def test_conferencia_csv_adulterada_e_recusada(self):
        (self.pasta / "conferencia_municipal.csv").write_text("modificado")
        with self.assertRaisesRegex(ValueError, "Artefato divergente"):
            verificar_resultado(self.pasta)

    def test_resultado_novo_sem_csvs_adicionais_e_recusado(self):
        for nome in ("por_municipio_dia.csv", "conferencia_municipal.csv"):
            (self.pasta / nome).unlink()
        with self.assertRaisesRegex(ValueError, "incompatível"):
            verificar_resultado(self.pasta)

    def test_leitura_legada_preserva_hash_original(self):
        pasta = self.legado()
        r = verificar_resultado(pasta).execucao
        self.assertEqual(r.execucao_sha256, "83d3373305d1877832a0309034342df9d6da6f41b8048e542330bd587c52e8bd")
        self.assertEqual(len(list(pasta.iterdir())), 4)
        self.assertNotIn("por_municipio_dia_utc", r.agregacoes)

    def test_caderno_legado_explica_ausencia_de_matriz(self):
        destino = self.raiz / "legado.html"
        gerar_caderno(self.legado(), destino)
        texto = destino.read_text()
        self.assertIn("resultado histórico não contém", texto)
        pagina = ExtrairHTML(texto)
        self.assertFalse(any(a.get("id") == "comparar-1" for _, a in pagina.elementos))
        self.assertIn("Manifesto 2 · regras 3 · agregações 1", texto)

    def test_html_novo_tem_tres_seletores_e_matriz_completa(self):
        destino = self.raiz / "novo.html"
        gerar_caderno(self.pasta, destino)
        texto = destino.read_text()
        pagina = ExtrairHTML(texto)
        for i in (1, 2, 3):
            self.assertTrue(any(t == "select" and a.get("id") == f"comparar-{i}"
                                for t, a in pagina.elementos))
        self.assertIn("Matriz completa município × dia", texto)
        self.assertIn("31/12/2025", texto)
        self.assertIn("equivalente após normalização", texto)
        dados = json.loads(pagina.scripts[0][1])
        self.assertEqual(len(dados["manifesto"]["resultado"]["agregacoes"]["por_municipio_dia_utc"][0]["deteccoes_por_dia"]), 31)

    def test_novo_html_mostra_codigos_desconhecidos_sem_inferir(self):
        pasta = self.exportar_linhas([
            exemplo(id="a", municipio_id="1399999", municipio="Manaus"),
            exemplo(id="b", municipio_id="", municipio="Apuí"),
        ])
        destino = self.raiz / "nomes.html"
        gerar_caderno(pasta, destino)
        texto = destino.read_text()
        self.assertIn("Código não encontrado na DTB 2025", texto)
        self.assertIn("Sem código para conferir", texto)
        self.assertIn('value="@sem_codigo"', texto)
