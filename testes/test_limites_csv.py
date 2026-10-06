import csv
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rastro.leitor import CAMPOS, ErroLimiteCSV, LimitesCSV, PERFIS, interpretar, ler_csv, resumir

from test_leitor import FIXTURE, exemplo


class TestLimitesCSV(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.arquivo = Path(self.pasta.name) / "teste.csv"
        self.limites = LimitesCSV(bytes_arquivo=10_000, linhas_dados=10)

    def escrever(self, linhas=None, campos=CAMPOS):
        with self.arquivo.open("w", encoding="utf-8", newline="") as entrada:
            escritor = csv.DictWriter(entrada, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows([exemplo()] if linhas is None else linhas)

    def test_perfis_documentados(self):
        self.assertEqual(PERFIS["fixture"].bytes_arquivo, 5 * 1024 * 1024)
        self.assertEqual(PERFIS["fixture"].linhas_dados, 20_000)
        self.assertEqual(PERFIS["mensal"].bytes_arquivo, 512 * 1024 * 1024)
        self.assertEqual(PERFIS["mensal"].linhas_dados, 5_000_000)

    def test_limites_precisam_ser_positivos(self):
        casos = ({"bytes_arquivo": 0}, {"linhas_dados": -1}, {"bytes_linha": True},
                 {"bytes_campo": 1.5}, {"colunas": 0}, {"segundos": float("nan")},
                 {"segundos": float("inf")}, {"segundos": 0})
        for mudanca in casos:
            with self.subTest(mudanca=mudanca), self.assertRaises(ValueError):
                replace(self.limites, **mudanca)

    def test_tamanho_exato_aceito_e_um_byte_a_mais_recusado(self):
        self.escrever()
        tamanho = self.arquivo.stat().st_size
        self.assertEqual(resumir(self.arquivo, limites=replace(self.limites, bytes_arquivo=tamanho))["lidas"], 1)
        with self.assertRaisesRegex(ErroLimiteCSV, "Arquivo excede"):
            resumir(self.arquivo, limites=replace(self.limites, bytes_arquivo=tamanho - 1))

    def test_linha_fisica_exata_e_um_byte_a_mais(self):
        self.escrever()
        maior_linha = max(map(len, self.arquivo.read_bytes().splitlines(keepends=True)))
        self.assertEqual(resumir(self.arquivo, limites=replace(self.limites, bytes_linha=maior_linha))["lidas"], 1)
        with self.assertRaisesRegex(ErroLimiteCSV, "Linha .* excede"):
            resumir(self.arquivo, limites=replace(self.limites, bytes_linha=maior_linha - 1))

    def test_linha_gigante_e_interrompida(self):
        self.arquivo.write_bytes((",".join(CAMPOS) + "\n" + "x" * 500).encode())
        with self.assertRaisesRegex(ErroLimiteCSV, "Linha 2 excede"):
            resumir(self.arquivo, limites=replace(self.limites, bytes_linha=250))

    def test_limite_de_linhas(self):
        self.escrever([exemplo(), exemplo(id="sintetico-002")])
        self.assertEqual(resumir(self.arquivo, limites=replace(self.limites, linhas_dados=2))["lidas"], 2)
        with self.assertRaisesRegex(ErroLimiteCSV, "linhas após o cabeçalho"):
            resumir(self.arquivo, limites=replace(self.limites, linhas_dados=1))

    def test_linhas_vazias_tambem_consumem_limite(self):
        self.escrever()
        with self.arquivo.open("ab") as entrada:
            entrada.write(b"\n")
        with self.assertRaises(ErroLimiteCSV):
            resumir(self.arquivo, limites=replace(self.limites, linhas_dados=1))
        self.assertEqual(resumir(self.arquivo, limites=replace(self.limites, linhas_dados=2))["lidas"], 1)

    def test_campo_utf8_medido_em_bytes(self):
        self.escrever([exemplo(municipio="á" * 50)])
        self.assertEqual(resumir(self.arquivo, limites=replace(self.limites, bytes_campo=100))["lidas"], 1)
        with self.assertRaisesRegex(ErroLimiteCSV, "Campo na linha 2"):
            resumir(self.arquivo, limites=replace(self.limites, bytes_campo=99))

    def test_limite_de_colunas_no_cabecalho(self):
        self.escrever()
        with self.assertRaisesRegex(ErroLimiteCSV, "colunas"):
            resumir(self.arquivo, limites=replace(self.limites, colunas=15))

    def test_limite_de_colunas_em_linha_de_dados(self):
        self.escrever()
        with self.arquivo.open("ab") as entrada:
            entrada.write(b",".join([b"x"] * 33) + b"\n")
        with self.assertRaisesRegex(ErroLimiteCSV, "Linha 3 excede 32 colunas"):
            resumir(self.arquivo, limites=self.limites)

    def test_colunas_extras_dentro_do_limite(self):
        self.escrever([exemplo(novo_campo="texto")], CAMPOS + ("novo_campo",))
        self.assertEqual(resumir(self.arquivo, limites=self.limites)["selecionadas"], 1)

    def test_quantidade_errada_e_rejeicao_comum(self):
        self.escrever()
        with self.arquivo.open("ab") as entrada:
            entrada.write(b"id,incompleto\n")
        resumo = resumir(self.arquivo, limites=self.limites)
        self.assertEqual(resumo["lidas"], 2)
        self.assertEqual(resumo["rejeitadas"], 1)

    def test_campo_com_quebra_de_linha_nao_suportado(self):
        self.escrever([exemplo(municipio="primeira\nsegunda")])
        with self.assertRaisesRegex(ValueError, "quebras de linha"):
            resumir(self.arquivo, limites=self.limites)

    def test_aspas_validas_e_crlf(self):
        self.escrever([exemplo(municipio='Município, "exemplo"')])
        self.assertEqual(resumir(self.arquivo, limites=self.limites)["selecionadas"], 1)

    def test_utf8_invalido_interrompe(self):
        self.escrever()
        with self.arquivo.open("ab") as entrada:
            entrada.write(b"\xff\n")
        with self.assertRaises(UnicodeError):
            resumir(self.arquivo, limites=self.limites)

    def test_tempo_excedido_sem_espera_real(self):
        self.escrever()
        with patch("rastro.leitor.time.monotonic", side_effect=[0, 2]):
            with self.assertRaisesRegex(ErroLimiteCSV, "segundos"):
                resumir(self.arquivo, limites=replace(self.limites, segundos=1))

    def test_crescimento_durante_leitura_nao_burla_limite(self):
        conteudo = FIXTURE.read_bytes()
        falso_stat = type("Stat", (), {"st_size": 1})()
        # Simula metadados antigos: a contagem dos bytes realmente lidos deve prevalecer.
        with patch("rastro.leitor.os.fstat", return_value=falso_stat):
            with self.assertRaisesRegex(ErroLimiteCSV, "durante a leitura"):
                resumir(FIXTURE, limites=replace(self.limites, bytes_arquivo=len(conteudo) - 1))

    def test_diretorio_nao_e_csv(self):
        with self.assertRaisesRegex(ValueError, "arquivo regular"):
            list(ler_csv(Path(self.pasta.name)))

    def test_inteiro_enorme_nao_e_convertido(self):
        resultado = interpretar(exemplo(numero_dias_sem_chuva="1e999999"), 2)
        self.assertEqual(resultado.categoria, "selecionada")
        self.assertIsNone(resultado.foco.dias_sem_chuva)
        self.assertIn("numero_dias_sem_chuva", resultado.problemas)

    def test_offset_que_ultrapassa_calendario_e_rejeitado(self):
        resultado = interpretar(exemplo(data_hora_gmt="0001-01-01T00:00:00+01:00"), 2)
        self.assertEqual(resultado.categoria, "rejeitada")

    def test_cli_sem_resumo_parcial_em_erro(self):
        self.escrever([exemplo(municipio="linha\nquebrada")])
        script = Path(__file__).parents[1] / "src" / "rastro" / "leitor.py"
        resultado = subprocess.run([sys.executable, str(script), str(self.arquivo)],
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 2)
        self.assertEqual(resultado.stdout, "")
        self.assertIn("Não foi possível ler o CSV", resultado.stderr)

    def test_cli_aceita_perfil_mensal(self):
        script = Path(__file__).parents[1] / "src" / "rastro" / "leitor.py"
        resultado = subprocess.run([sys.executable, str(script), str(FIXTURE), "--perfil", "mensal"],
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("selecionadas: 2", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
