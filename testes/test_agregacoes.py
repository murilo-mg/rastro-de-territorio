import csv
import tempfile
import unittest
from pathlib import Path

from rastro.execucao import executar_snapshot
from rastro.leitor import CAMPOS
from rastro.snapshot import criar_snapshot
from test_leitor import exemplo


class TestAgregacoes(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)

    def executar(self, linhas):
        arquivo = self.raiz / "entrada.csv"
        with arquivo.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CAMPOS)
            writer.writeheader()
            writer.writerows(linhas)
        snapshot = criar_snapshot(arquivo, self.raiz / "snapshots", reserva_bytes=0)
        return executar_snapshot(snapshot.diretorio)

    def test_calendario_completo_e_conversao_para_utc(self):
        resultado = self.executar([
            exemplo(id="a", data_hora_gmt="2025-08-02T00:30:00+01:00"),
            exemplo(id="b", data_hora_gmt="2025-08-01T22:30:00-04:00"),
            exemplo(id="c", data_hora_gmt="2025-08-31T23:59:59Z"),
        ])
        dias = resultado.agregacoes["por_dia_utc"]
        self.assertEqual(len(dias), 31)
        self.assertEqual(dias[0], {"dia_utc": "2025-08-01", "deteccoes": 1})
        self.assertEqual(dias[1]["deteccoes"], 1)
        self.assertEqual(dias[-1], {"dia_utc": "2025-08-31", "deteccoes": 1})
        self.assertEqual(dias[2]["deteccoes"], 0)
        self.assertEqual(sum(d["deteccoes"] for d in dias), 3)

    def test_codigos_distintos_nao_sao_unidos_por_nome(self):
        r = self.executar([
            exemplo(id="a", municipio_id="1302603", municipio="NOME IGUAL"),
            exemplo(id="b", municipio_id="1300144", municipio="NOME IGUAL"),
        ])
        grupos = r.agregacoes["por_municipio"]
        self.assertEqual([g["municipio_id"] for g in grupos], ["1300144", "1302603"])
        self.assertEqual([g["deteccoes"] for g in grupos], [1, 1])

    def test_divergencias_de_nome_ficam_visiveis(self):
        r = self.executar([
            exemplo(id="a", municipio="Manaus"),
            exemplo(id="b", municipio="MANAUS"),
            exemplo(id="c", municipio=""),
        ])
        grupo = r.agregacoes["por_municipio"][0]
        self.assertEqual(grupo["nomes"], ["MANAUS", "Manaus"])
        self.assertEqual(grupo["sem_nome"], 1)
        self.assertTrue(grupo["nomes_divergentes"])
        self.assertEqual(r.agregacoes["municipios_com_nomes_divergentes"], 1)
        self.assertEqual(r.agregacoes["ausencias"]["municipio"], 1)

    def test_sem_codigo_entra_no_total_e_tem_diagnostico(self):
        r = self.executar([
            exemplo(id="a", municipio_id="", municipio="NOME A"),
            exemplo(id="b", municipio_id="abc", municipio="NOME B"),
            exemplo(id="c"),
        ])
        grupos = r.agregacoes["por_municipio"]
        self.assertEqual(grupos[-1]["municipio_id"], None)
        self.assertEqual(grupos[-1]["deteccoes"], 2)
        self.assertFalse(grupos[-1]["nomes_divergentes"])
        self.assertEqual(r.agregacoes["sem_municipio_id"], 2)
        self.assertEqual(r.agregacoes["problemas_por_campo"], {"municipio_id": 1})
        self.assertEqual(r.resumo["problemas_opcionais"], 1)
        self.assertEqual(sum(g["deteccoes"] for g in grupos), 3)

    def test_ausencias_e_problemas_sao_contagens_diferentes(self):
        r = self.executar([
            exemplo(id="a", risco_fogo="-999", frp=""),
            exemplo(id="b", risco_fogo="NaN", frp="-1"),
            exemplo(id="c", risco_fogo="0", frp="0"),
        ])
        self.assertEqual(r.agregacoes["ausencias"]["risco_fogo"], 2)
        self.assertEqual(r.agregacoes["ausencias"]["frp"], 2)
        self.assertEqual(r.agregacoes["problemas_por_campo"], {"frp": 1, "risco_fogo": 1})

    def test_recorte_vazio_tem_calendario_e_totais_zero(self):
        r = self.executar([exemplo(satelite="GOES-19")])
        self.assertEqual(len(r.agregacoes["por_dia_utc"]), 31)
        self.assertTrue(all(d["deteccoes"] == 0 for d in r.agregacoes["por_dia_utc"]))
        self.assertEqual(r.agregacoes["por_municipio"], [])
        self.assertEqual(r.agregacoes["municipios_com_codigo"], 0)

    def test_agregacoes_independem_da_ordem_da_entrada(self):
        linhas = [exemplo(id="a", municipio="Manaus"), exemplo(id="b", municipio="MANAUS"),
                  exemplo(id="c", municipio_id="1300144", municipio="APUÍ")]
        primeiro = self.executar(linhas)
        segundo = self.executar(list(reversed(linhas)))
        self.assertEqual(primeiro.agregacoes, segundo.agregacoes)
        self.assertNotEqual(primeiro.snapshot_sha256, segundo.snapshot_sha256)

    def test_rejeitados_e_fora_do_recorte_nao_entram_nas_tabelas(self):
        r = self.executar([exemplo(id="a"), exemplo(id="b", lat="NaN"),
                           exemplo(id="c", estado_id="15"), exemplo(id="d", satelite="GOES-19")])
        self.assertEqual(r.resumo["lidas"], 4)
        self.assertEqual(r.resumo["rejeitadas"], 1)
        self.assertEqual(r.resumo["fora_do_recorte"], 2)
        self.assertEqual(sum(d["deteccoes"] for d in r.agregacoes["por_dia_utc"]), 1)
        self.assertEqual(sum(m["deteccoes"] for m in r.agregacoes["por_municipio"]), 1)
