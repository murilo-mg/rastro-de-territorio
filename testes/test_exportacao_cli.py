import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rastro.__main__ import main
from rastro.execucao import executar_snapshot
from rastro.exportacao import exportar_resultado
from rastro.leitor import CAMPOS
from rastro.snapshot import criar_snapshot
from test_leitor import FIXTURE, exemplo

RAIZ = Path(__file__).resolve().parent.parent


class TestExportacaoCLI(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        self.snapshot = criar_snapshot(FIXTURE, self.raiz / "snapshots", reserva_bytes=0)
        self.resultado = executar_snapshot(self.snapshot.diretorio)
        self.saida = self.raiz / "resultados"

    def cli(self, *args):
        env = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
        return subprocess.run([sys.executable, "-m", "rastro", *map(str, args)],
                              cwd=RAIZ, env=env, text=True, capture_output=True, timeout=20)

    def test_exporta_json_e_csv_consistentes(self):
        pasta, reutilizado = exportar_resultado(self.resultado, self.saida)
        self.assertFalse(reutilizado)
        registro = json.loads((pasta / "manifesto.json").read_text())
        self.assertEqual(registro["manifesto"], self.resultado.manifesto)
        self.assertEqual(registro["execucao_sha256"], self.resultado.execucao_sha256)
        for nome, tamanho in (("por_dia.csv", 31), ("por_municipio.csv", 1)):
            with (pasta / nome).open(encoding="utf-8", newline="") as f:
                linhas = list(csv.DictReader(f))
            self.assertEqual(len(linhas), tamanho)
            self.assertEqual(sum(int(l["deteccoes"]) for l in linhas), 2)
        self.assertEqual(json.loads(linhas[0]["nomes_json"]), ["MANAUS"])
        contexto = json.loads((pasta / "contexto.json").read_text())
        self.assertEqual(len(contexto["codigo_sha256"]), 64)
        self.assertIn("alteracoes_locais", contexto)

    def test_reutiliza_preservando_contexto_inicial(self):
        pasta, _ = exportar_resultado(self.resultado, self.saida)
        antes = {p.name: p.read_bytes() for p in pasta.iterdir()}
        with patch("rastro.exportacao.contexto_codigo", side_effect=AssertionError("não recriar contexto")):
            mesma, reutilizado = exportar_resultado(self.resultado, self.saida)
        self.assertTrue(reutilizado)
        self.assertEqual(mesma, pasta)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in pasta.iterdir()})

    def test_recusa_resultado_divergente_sem_sobrescrever(self):
        pasta, _ = exportar_resultado(self.resultado, self.saida)
        arquivo = pasta / "por_dia.csv"
        arquivo.write_bytes(b"alterado\n")
        with self.assertRaisesRegex(ValueError, "divergente"):
            exportar_resultado(self.resultado, self.saida)
        self.assertEqual(arquivo.read_bytes(), b"alterado\n")

    def test_recusa_pasta_existente_incompleta(self):
        pasta = self.saida / self.resultado.execucao_sha256
        pasta.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "incompleto"):
            exportar_resultado(self.resultado, self.saida)
        self.assertEqual(list(pasta.iterdir()), [])

    def test_falha_antes_da_publicacao_remove_temporario(self):
        with patch("rastro.exportacao.os.rename", side_effect=OSError("falha simulada")):
            with self.assertRaises(OSError):
                exportar_resultado(self.resultado, self.saida)
        self.assertFalse((self.saida / self.resultado.execucao_sha256).exists())
        self.assertEqual(list(self.saida.glob(".tmp-*")), [])

    def test_recusa_manifesto_modificado_apos_execucao(self):
        self.resultado.manifesto["resultado"]["agregacoes"]["por_dia_utc"][0]["deteccoes"] += 1
        with self.assertRaisesRegex(ValueError, "Manifesto alterado"):
            exportar_resultado(self.resultado, self.saida)
        self.assertFalse(self.saida.exists())

    def test_recusa_link_simbolico_no_destino(self):
        real = self.raiz / "real"
        real.mkdir()
        self.saida.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "link simbólico"):
            exportar_resultado(self.resultado, self.saida)
        self.assertEqual(list(real.iterdir()), [])

    def test_cli_processa_snapshot_e_informa_exportacao(self):
        proc = self.cli("--snapshot", self.snapshot.diretorio, "--saida", self.saida)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("selecionadas: 2", proc.stdout)
        self.assertIn("dias_utc: 31", proc.stdout)
        self.assertIn("exportacao: criada", proc.stdout)
        self.assertTrue((self.saida / self.resultado.execucao_sha256 / "manifesto.json").is_file())

    def test_cli_csv_preserva_entrada_e_exporta(self):
        # A reserva de produção continua 5 GiB; a fixture de teste usa zero.
        def criar(*args, **kwargs):
            return criar_snapshot(*args, **kwargs, reserva_bytes=0)
        with patch("rastro.__main__.criar_snapshot", side_effect=criar), redirect_stdout(io.StringIO()) as texto:
            main(["--csv", str(FIXTURE), "--snapshots", str(self.raiz / "outros-snapshots"),
                  "--saida", str(self.saida)])
        self.assertIn("exportacao: criada", texto.getvalue())
        self.assertTrue((self.raiz / "outros-snapshots" / self.snapshot.sha256 / "original.csv").is_file())

    def test_cli_erros_de_argumentos(self):
        for args in ((), ("--csv", FIXTURE, "--snapshot", self.snapshot.diretorio),
                     ("--snapshot", self.snapshot.diretorio, "--snapshots", self.raiz)):
            with self.subTest(args=args):
                proc = self.cli(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")

    def test_cli_snapshot_corrompido_nao_publica_saida(self):
        original = self.snapshot.diretorio / "original.csv"
        original.chmod(0o644)
        original.write_bytes(b"corrompido")
        proc = self.cli("--snapshot", self.snapshot.diretorio, "--saida", self.saida)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(self.saida.exists())

    def test_cli_duplicata_nao_publica_agregacoes_parciais(self):
        entrada = self.raiz / "duplicata.csv"
        with entrada.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows([exemplo(), exemplo()])
        s = criar_snapshot(entrada, self.raiz / "snapshots", reserva_bytes=0)
        proc = self.cli("--snapshot", s.diretorio, "--saida", self.saida)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("repetido", proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(self.saida.exists())
