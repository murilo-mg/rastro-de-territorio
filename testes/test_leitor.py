import csv
import tempfile
import unittest
from datetime import timezone
from decimal import Decimal
from pathlib import Path

from rastro.leitor import CAMPOS, interpretar, ler_csv, resumir

FIXTURE = Path(__file__).parent / "fixtures" / "focos_sinteticos.csv"


def exemplo(**mudancas):
    with FIXTURE.open(encoding="utf-8", newline="") as arquivo:
        linha = next(csv.DictReader(arquivo))
    linha.update(mudancas)
    return linha


class TestLeitor(unittest.TestCase):
    def test_preserva_codigo_e_nome_municipais(self):
        resultado = interpretar(exemplo(municipio_id=" 1302603 ", municipio="  Manaus "), 2)
        self.assertEqual(resultado.foco.municipio_id, "1302603")
        self.assertEqual(resultado.foco.municipio, "Manaus")
        self.assertEqual(resultado.problemas, ())

    def test_codigo_municipal_invalido_preserva_deteccao(self):
        for codigo in ("abc", "130260", "13026030", "1501402", "１３０２６０３", "1302603.0"):
            with self.subTest(codigo=codigo):
                resultado = interpretar(exemplo(municipio_id=codigo), 2)
                self.assertEqual(resultado.categoria, "selecionada")
                self.assertIsNone(resultado.foco.municipio_id)
                self.assertEqual(resultado.foco.municipio, "MANAUS")
                self.assertEqual(resultado.problemas, ("municipio_id",))

    def test_municipio_ausente_nao_vira_codigo_inferido(self):
        resultado = interpretar(exemplo(municipio_id="", municipio="MANAUS"), 2)
        self.assertIsNone(resultado.foco.municipio_id)
        self.assertEqual(resultado.problemas, ())
        sem_nome = interpretar(exemplo(municipio="  "), 2)
        self.assertIsNone(sem_nome.foco.municipio)
        self.assertEqual(sem_nome.foco.municipio_id, "1302603")

    def test_municipio_fora_do_recorte_nao_e_avaliado(self):
        resultado = interpretar(exemplo(satelite="GOES-19", municipio_id="abc"), 2)
        self.assertEqual(resultado.categoria, "fora_do_recorte")
        self.assertEqual(resultado.problemas, ())

    def test_recorte_e_contagens(self):
        self.assertEqual(resumir(FIXTURE), {
            "lidas": 5, "selecionadas": 2, "fora_do_recorte": 3,
            "rejeitadas": 0, "problemas_opcionais": 0,
        })
        resultados = list(ler_csv(FIXTURE))
        self.assertEqual([r.foco.source_id for r in resultados if r.foco],
                         ["sintetico-001", "sintetico-002"])

    def test_satelite_exato(self):
        for satelite in ("AQUA_M-M", "AQUA_M-T-extra", "GOES-19"):
            with self.subTest(satelite=satelite):
                self.assertEqual(interpretar(exemplo(satelite=satelite), 2).categoria,
                                 "fora_do_recorte")

    def test_estado_por_codigo(self):
        self.assertEqual(interpretar(exemplo(estado_id="15", estado="AMAZONAS"), 2).categoria,
                         "fora_do_recorte")

    def test_limites_do_periodo(self):
        casos = {
            "2025-07-31 23:59:59": "fora_do_recorte",
            "2025-08-01 00:00:00": "selecionada",
            "2025-08-31 23:59:59": "selecionada",
            "2025-09-01 00:00:00": "fora_do_recorte",
        }
        for data, esperado in casos.items():
            with self.subTest(data=data):
                self.assertEqual(interpretar(exemplo(data_hora_gmt=data), 2).categoria, esperado)

    def test_normalizacao_de_offset_para_utc(self):
        resultado = interpretar(exemplo(data_hora_gmt="2025-07-31T21:00:00-03:00"), 2)
        self.assertEqual(resultado.categoria, "selecionada")
        self.assertEqual(resultado.foco.observado_em.tzinfo, timezone.utc)
        self.assertEqual(resultado.foco.observado_em.day, 1)

    def test_coordenadas_com_espacos_e_precisao(self):
        foco = interpretar(exemplo(lat="  -3.1000 ", lon=" -60.02 "), 2).foco
        self.assertEqual(foco.latitude, Decimal("-3.1"))
        self.assertEqual(foco.longitude, Decimal("-60.02"))

    def test_coordenadas_invalidas(self):
        for mudancas in ({"lat": "91"}, {"lon": "-181"}, {"lat": "NaN"},
                         {"lon": "Infinity"}, {"lat": ""}, {"lat": "abc"}):
            with self.subTest(mudancas=mudancas):
                self.assertEqual(interpretar(exemplo(**mudancas), 2).categoria, "rejeitada")

    def test_essenciais_invalidos(self):
        for mudancas in ({"id": ""}, {"satelite": ""}, {"estado_id": "abc"},
                         {"estado_id": "0"}, {"data_hora_gmt": "2025-08-32 12:00:00"},
                         {"data_hora_gmt": "2025-08-01"}):
            with self.subTest(mudancas=mudancas):
                self.assertEqual(interpretar(exemplo(**mudancas), 2).categoria, "rejeitada")

    def test_sentinelas_numericas(self):
        for sentinela in ("-999", "-999.0", " -999.00 "):
            with self.subTest(sentinela=sentinela):
                resultado = interpretar(exemplo(numero_dias_sem_chuva=sentinela,
                                               precipitacao=sentinela, risco_fogo=sentinela,
                                               frp=""), 2)
                self.assertEqual(resultado.categoria, "selecionada")
                self.assertEqual(resultado.problemas, ())
                for campo in ("dias_sem_chuva", "precipitacao", "risco_fogo", "frp"):
                    self.assertIsNone(getattr(resultado.foco, campo))

    def test_opcionais_invalidos_nao_descartam_foco(self):
        resultado = interpretar(exemplo(numero_dias_sem_chuva="2.5", precipitacao="NaN",
                                       risco_fogo="1.1", frp="-1"), 2)
        self.assertEqual(resultado.categoria, "selecionada")
        self.assertEqual(len(resultado.problemas), 4)
        self.assertIsNone(resultado.foco.dias_sem_chuva)
        self.assertIsNone(resultado.foco.precipitacao)
        self.assertIsNone(resultado.foco.risco_fogo)
        self.assertIsNone(resultado.foco.frp)

    def test_zero_e_valido(self):
        resultado = interpretar(exemplo(numero_dias_sem_chuva="0", precipitacao="0",
                                       risco_fogo="0", frp="0"), 2)
        self.assertEqual(resultado.foco.dias_sem_chuva, 0)
        self.assertEqual(resultado.foco.frp, Decimal("0"))
        self.assertEqual(resultado.problemas, ())

    def test_falta_ou_excesso_de_colunas(self):
        for linha in (exemplo(frp=None), {**exemplo(), None: ["extra"]}):
            self.assertEqual(interpretar(linha, 2).categoria, "rejeitada")

    def test_cabecalhos_invalidos(self):
        cabecalhos = ("", "id,lat\n", ",".join(CAMPOS + ("id",)) + "\n")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "teste.csv"
            for cabecalho in cabecalhos:
                with self.subTest(cabecalho=cabecalho):
                    caminho.write_text(cabecalho, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        list(ler_csv(caminho))

    def test_bom_e_cabecalhos_com_espacos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "teste.csv"
            with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
                escritor = csv.writer(arquivo)
                escritor.writerow([f" {campo} " for campo in CAMPOS])
                escritor.writerow([exemplo()[campo] for campo in CAMPOS])
            self.assertEqual(resumir(caminho)["selecionadas"], 1)

    def test_particao_inclui_rejeicoes(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "teste.csv"
            with caminho.open("w", encoding="utf-8", newline="") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
                escritor.writeheader()
                escritor.writerows([exemplo(), exemplo(satelite="GOES-19"), exemplo(lat="NaN")])
            resumo = resumir(caminho)
            self.assertEqual(resumo["lidas"], 3)
            self.assertEqual(resumo["selecionadas"], 1)
            self.assertEqual(resumo["fora_do_recorte"], 1)
            self.assertEqual(resumo["rejeitadas"], 1)


if __name__ == "__main__":
    unittest.main()
