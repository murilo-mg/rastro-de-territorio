import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from rastro.snapshot import criar_snapshot, verificar_snapshot
from test_leitor import FIXTURE


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.raiz = Path(self.pasta.name) / "snapshots"
        self.origem = Path(self.pasta.name) / "entrada.csv"
        self.origem.write_bytes(FIXTURE.read_bytes())

    def criar(self, **kwargs):
        return criar_snapshot(self.origem, self.raiz, reserva_bytes=0, **kwargs)

    def test_copia_original_hash_e_manifesto(self):
        resultado = self.criar()
        self.assertTrue(resultado.criado)
        self.assertEqual(resultado.sha256, hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual((resultado.diretorio / "original.csv").read_bytes(), FIXTURE.read_bytes())
        manifesto = json.loads((resultado.diretorio / "manifesto.json").read_text())
        self.assertEqual(manifesto["sha256"], resultado.sha256)
        self.assertEqual(manifesto["bytes"], self.origem.stat().st_size)
        self.assertEqual(manifesto["nome_arquivo_origem"], "entrada.csv")
        self.assertNotIn(str(self.pasta.name), json.dumps(manifesto))
        self.assertEqual(datetime.fromisoformat(manifesto["coletado_em_utc"]).utcoffset().total_seconds(), 0)
        self.assertIsNone(manifesto["url_origem"])
        self.assertIsNone(manifesto["last_modified_servidor"])
        self.assertEqual(verificar_snapshot(resultado.diretorio).sha256, resultado.sha256)

    def test_mesmos_bytes_reutilizam_sem_alterar_manifesto(self):
        primeiro = self.criar()
        original_manifesto = (primeiro.diretorio / "manifesto.json").read_bytes()
        segundo = self.criar()
        self.assertFalse(segundo.criado)
        self.assertEqual(segundo.diretorio, primeiro.diretorio)
        self.assertEqual((segundo.diretorio / "manifesto.json").read_bytes(), original_manifesto)
        self.assertEqual(len([p for p in self.raiz.iterdir() if p.is_dir()]), 1)

    def test_bytes_diferentes_preservam_anterior(self):
        primeiro = self.criar()
        self.origem.write_bytes(FIXTURE.read_bytes() + b"\n")
        segundo = self.criar()
        self.assertNotEqual(primeiro.sha256, segundo.sha256)
        self.assertTrue(segundo.criado)
        self.assertEqual((primeiro.diretorio / "original.csv").read_bytes(), FIXTURE.read_bytes())

    def test_modificacao_do_original_e_detectada(self):
        resultado = self.criar()
        arquivo = resultado.diretorio / "original.csv"
        arquivo.chmod(0o644)
        arquivo.write_bytes(arquivo.read_bytes().replace(b"12.5", b"13.5"))
        with self.assertRaisesRegex(ValueError, "Integridade inválida"):
            verificar_snapshot(resultado.diretorio)
        with self.assertRaises(ValueError):
            self.criar()

    def test_manifesto_com_hash_incorreto_e_recusado(self):
        resultado = self.criar()
        arquivo = resultado.diretorio / "manifesto.json"
        dados = json.loads(arquivo.read_text())
        dados["sha256"] = "0" * 64
        arquivo.chmod(0o644)
        arquivo.write_text(json.dumps(dados))
        with self.assertRaisesRegex(ValueError, "Identidade"):
            verificar_snapshot(resultado.diretorio)

    def test_manifesto_excessivo_e_recusado(self):
        resultado = self.criar()
        arquivo = resultado.diretorio / "manifesto.json"
        arquivo.chmod(0o644)
        arquivo.write_bytes(b"x" * 8193)
        with self.assertRaisesRegex(ValueError, "8192"):
            verificar_snapshot(resultado.diretorio)

    def test_data_de_coleta_sem_utc_e_recusada(self):
        resultado = self.criar()
        arquivo = resultado.diretorio / "manifesto.json"
        dados = json.loads(arquivo.read_text())
        dados["coletado_em_utc"] = "2025-08-01T00:00:00"
        arquivo.chmod(0o644)
        arquivo.write_text(json.dumps(dados))
        with self.assertRaisesRegex(ValueError, "UTC"):
            verificar_snapshot(resultado.diretorio)

    def test_quota_nao_apaga_snapshot_anterior(self):
        primeiro = self.criar()
        self.origem.write_bytes(FIXTURE.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Quota"):
            self.criar(quota_bytes=1)
        self.assertTrue(primeiro.diretorio.is_dir())
        self.assertEqual(len([p for p in self.raiz.iterdir() if p.is_dir()]), 1)

    def test_reutilizacao_funciona_mesmo_sem_espaco_para_nova_copia(self):
        primeiro = self.criar()
        with patch("rastro.snapshot.shutil.disk_usage", side_effect=AssertionError("Não deve reservar outra cópia")):
            segundo = self.criar(quota_bytes=1)
        self.assertEqual(segundo.sha256, primeiro.sha256)
        self.assertFalse(segundo.criado)

    def test_espaco_livre_insuficiente(self):
        espaco = type("Espaco", (), {"free": 0})()
        with patch("rastro.snapshot.shutil.disk_usage", return_value=espaco):
            with self.assertRaisesRegex(ValueError, "Espaço livre"):
                self.criar()
        self.assertFalse(any(p.is_dir() for p in self.raiz.iterdir()))

    def test_origem_vazia(self):
        self.origem.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "entre 1"):
            self.criar()

    def test_arquivo_maior_que_perfil(self):
        with self.origem.open("wb") as arquivo:
            arquivo.truncate(5 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            self.criar()

    def test_mudanca_entre_leituras_cancela_e_limpa_temporario(self):
        from rastro.snapshot import copiar_e_hash

        def mudar_depois_primeira_leitura(caminho, **kwargs):
            resultado = copiar_e_hash(caminho, **kwargs)
            if kwargs.get("destino") is None:
                self.origem.write_bytes(FIXTURE.read_bytes() + b"\n")
            return resultado

        with patch("rastro.snapshot.copiar_e_hash", side_effect=mudar_depois_primeira_leitura):
            with self.assertRaisesRegex(ValueError, "entre as leituras"):
                self.criar()
        self.assertEqual([p.name for p in self.raiz.iterdir() if p.is_dir()], [])

    def test_erro_de_publicacao_limpa_temporario(self):
        with patch("rastro.snapshot.Path.rename", side_effect=OSError("falha simulada")):
            with self.assertRaises(OSError):
                self.criar()
        self.assertFalse(any(p.is_dir() for p in self.raiz.iterdir()))

    def test_arquivo_original_e_manifesto_sem_permissao_de_escrita(self):
        resultado = self.criar()
        for nome in ("original.csv", "manifesto.json"):
            self.assertEqual((resultado.diretorio / nome).stat().st_mode & 0o222, 0)

    def test_links_simbolicos_nao_sao_reutilizados(self):
        resultado = self.criar()
        manifesto = resultado.diretorio / "manifesto.json"
        manifesto.unlink()
        manifesto.symlink_to(self.origem)
        with self.assertRaises(ValueError):
            self.criar()

    def test_origem_link_simbolico_e_recusada(self):
        link = Path(self.pasta.name) / "link.csv"
        link.symlink_to(self.origem)
        with self.assertRaises(ValueError):
            criar_snapshot(link, self.raiz, reserva_bytes=0)

    def test_criacoes_concorrentes_nao_se_sobrepoem(self):
        import fcntl

        self.raiz.mkdir()
        with (self.raiz / ".snapshot.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "Outra criação"):
                self.criar()

    def test_tempo_do_hash_sem_espera_real(self):
        with patch("rastro.snapshot.time.monotonic", side_effect=[0, 901]):
            with self.assertRaisesRegex(ValueError, "Tempo limite"):
                self.criar()

    def test_mutacao_durante_leitura_e_detectada(self):
        import os
        from types import SimpleNamespace

        antes = os.stat(self.origem)
        alterado = SimpleNamespace(st_dev=antes.st_dev, st_ino=antes.st_ino,
                                  st_size=antes.st_size + 1, st_mtime_ns=antes.st_mtime_ns,
                                  st_ctime_ns=antes.st_ctime_ns)
        with patch("rastro.snapshot.os.fstat", side_effect=[antes, alterado]):
            with self.assertRaisesRegex(ValueError, "mudou durante a leitura"):
                self.criar()

    def test_perfil_e_limites_invalidos(self):
        with self.assertRaisesRegex(ValueError, "Perfil"):
            self.criar(perfil="inexistente")
        with self.assertRaises(ValueError):
            self.criar(quota_bytes=0)


if __name__ == "__main__":
    unittest.main()
