import csv
import tempfile
import unittest
from decimal import Inexact, Rounded, localcontext
from pathlib import Path

from rastro.execucao import ErroIdentidade, executar_snapshot
from rastro.leitor import CAMPOS
from rastro.snapshot import criar_snapshot
from test_leitor import FIXTURE, exemplo


class TestExecucaoReproduzivel(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.raiz = Path(self.pasta.name)
        self.snapshots = self.raiz / "snapshots"

    def criar_snapshot_de_fixture(self):
        origem = self.raiz / "entrada.csv"
        origem.write_bytes(FIXTURE.read_bytes())
        return criar_snapshot(origem, self.snapshots, reserva_bytes=0)

    def criar_snapshot_de_linhas(self, linhas):
        origem = self.raiz / "entrada.csv"
        with origem.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
            escritor.writeheader()
            escritor.writerows(linhas)
        return criar_snapshot(origem, self.snapshots, reserva_bytes=0)

    def test_execucao_liga_resultado_ao_snapshot(self):
        snapshot = self.criar_snapshot_de_fixture()

        resultado = executar_snapshot(snapshot.diretorio)

        self.assertEqual(resultado.snapshot_sha256, snapshot.sha256)
        self.assertEqual(resultado.snapshot_bytes, snapshot.bytes)
        self.assertEqual(resultado.ids_selecionados_unicos, 2)
        self.assertEqual(resultado.resumo, {
            "lidas": 5,
            "selecionadas": 2,
            "fora_do_recorte": 3,
            "rejeitadas": 0,
            "problemas_opcionais": 0,
        })

    def test_duplicata_identica_invalida_execucao(self):
        linha = exemplo()
        snapshot = self.criar_snapshot_de_linhas([linha, linha.copy()])

        with self.assertRaisesRegex(
            ErroIdentidade,
            r"sintetico-001.*linhas 2 e 3.*mesmo conteúdo interpretado",
        ):
            executar_snapshot(snapshot.diretorio)

    def test_mesmo_id_com_conteudo_diferente_invalida_execucao(self):
        primeira = exemplo()
        segunda = exemplo(lat="-4.0000")
        snapshot = self.criar_snapshot_de_linhas([primeira, segunda])

        with self.assertRaisesRegex(
            ErroIdentidade,
            r"sintetico-001.*linhas 2 e 3.*conteúdo diferente",
        ):
            executar_snapshot(snapshot.diretorio)

    def test_snapshot_corrompido_e_recusado_antes_da_execucao(self):
        snapshot = self.criar_snapshot_de_fixture()
        original = snapshot.diretorio / "original.csv"

        original.chmod(0o644)
        original.write_bytes(
            original.read_bytes().replace(b"12.5", b"13.5", 1)
        )

        with self.assertRaisesRegex(ValueError, "Integridade inválida"):
            executar_snapshot(snapshot.diretorio)

    def test_decimais_distintos_apos_28_casas_sao_conflito(self):
        snapshot = self.criar_snapshot_de_linhas([
            exemplo(precipitacao="1.12345678901234567890123456781"),
            exemplo(precipitacao="1.12345678901234567890123456782"),
        ])
        with self.assertRaisesRegex(ErroIdentidade, "conteúdo diferente"):
            executar_snapshot(snapshot.diretorio)

    def test_representacoes_decimais_equivalentes_sao_duplicata_identica(self):
        for valor in ("1", "1.0", "1.000", "1e0", "10e-1"):
            with self.subTest(valor=valor):
                snapshot = self.criar_snapshot_de_linhas([
                    exemplo(precipitacao="1.00"),
                    exemplo(precipitacao=valor),
                ])
                with self.assertRaisesRegex(ErroIdentidade, "mesmo conteúdo interpretado"):
                    executar_snapshot(snapshot.diretorio)

    def test_classificacao_independe_da_precisao_do_contexto(self):
        snapshot = self.criar_snapshot_de_linhas([
            exemplo(precipitacao="1.12345678901234567890123456781"),
            exemplo(precipitacao="1.12345678901234567890123456782"),
        ])
        for precisao in (3, 28, 60):
            with self.subTest(precisao=precisao), localcontext() as contexto:
                contexto.prec = precisao
                contexto.traps[Inexact] = True
                contexto.traps[Rounded] = True
                with self.assertRaisesRegex(ErroIdentidade, "conteúdo diferente"):
                    executar_snapshot(snapshot.diretorio)

    def test_decimal_finito_com_expoente_extremo_nao_interrompe_execucao(self):
        for valor in ("1e1000000", "1e-1000000"):
            with self.subTest(valor=valor):
                snapshot = self.criar_snapshot_de_linhas([exemplo(precipitacao=valor)])
                resultado = executar_snapshot(snapshot.diretorio)
                self.assertEqual(resultado.ids_selecionados_unicos, 1)

    def test_equivalencia_com_expoentes_extremos_independe_dos_limites_do_contexto(self):
        for primeiro, segundo in (("1e1000000", "10e999999"), ("1e-1000000", "10e-1000001")):
            with self.subTest(primeiro=primeiro):
                snapshot = self.criar_snapshot_de_linhas([
                    exemplo(precipitacao=primeiro),
                    exemplo(precipitacao=segundo),
                ])
                with localcontext() as contexto:
                    contexto.prec = 3
                    contexto.Emax = 9
                    contexto.Emin = -9
                    contexto.traps[Inexact] = True
                    contexto.traps[Rounded] = True
                    with self.assertRaisesRegex(ErroIdentidade, "mesmo conteúdo interpretado"):
                        executar_snapshot(snapshot.diretorio)

    def test_valores_extremos_diferentes_continuam_conflito(self):
        for primeiro, segundo in (("1e1000000", "2e1000000"), ("1e-1000000", "2e-1000000")):
            with self.subTest(primeiro=primeiro):
                snapshot = self.criar_snapshot_de_linhas([
                    exemplo(precipitacao=primeiro),
                    exemplo(precipitacao=segundo),
                ])
                with self.assertRaisesRegex(ErroIdentidade, "conteúdo diferente"):
                    executar_snapshot(snapshot.diretorio)

    def test_zeros_de_sinais_e_escalas_diferentes_sao_equivalentes(self):
        for valor in ("-0", "-0.000", "0e1000000", "-0e-1000000"):
            with self.subTest(valor=valor):
                snapshot = self.criar_snapshot_de_linhas([
                    exemplo(precipitacao="0"),
                    exemplo(precipitacao=valor),
                ])
                with self.assertRaisesRegex(ErroIdentidade, "mesmo conteúdo interpretado"):
                    executar_snapshot(snapshot.diretorio)

    def test_opcional_ausente_e_zero_continuam_diferentes(self):
        snapshot = self.criar_snapshot_de_linhas([
            exemplo(precipitacao=""),
            exemplo(precipitacao="0"),
        ])
        with self.assertRaisesRegex(ErroIdentidade, "conteúdo diferente"):
            executar_snapshot(snapshot.diretorio)

    def test_diferencas_municipais_do_mesmo_id_sao_conflitos(self):
        for mudanca in ({"municipio_id": "1300144"}, {"municipio": "OUTRO NOME"}):
            with self.subTest(mudanca=mudanca):
                snapshot = self.criar_snapshot_de_linhas([exemplo(), exemplo(**mudanca)])
                with self.assertRaisesRegex(ErroIdentidade, "conteúdo diferente"):
                    executar_snapshot(snapshot.diretorio)


if __name__ == "__main__":
    unittest.main()
