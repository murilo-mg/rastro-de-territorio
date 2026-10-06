import csv
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
