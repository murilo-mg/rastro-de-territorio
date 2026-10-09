import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from rastro.execucao import executar_snapshot
from rastro.snapshot import criar_snapshot
from test_leitor import FIXTURE


class TestManifestoExecucao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.raiz = Path(self.pasta.name)

    def criar_snapshot(self, conteudo=None):
        origem = self.raiz / "entrada.csv"
        origem.write_bytes(
            FIXTURE.read_bytes() if conteudo is None else conteudo
        )
        return criar_snapshot(
            origem,
            self.raiz / "snapshots",
            reserva_bytes=0,
        )

    def test_manifesto_descreve_entrada_regras_e_resultado(self):
        snapshot = self.criar_snapshot()

        resultado = executar_snapshot(snapshot.diretorio)

        self.assertEqual(
            resultado.manifesto["versao_manifesto_execucao"],
            3,
        )
        self.assertEqual(resultado.manifesto["versao_regras"], 4)
        self.assertEqual(resultado.manifesto["referencia_municipal"]["edicao"], 2025)
        self.assertEqual(resultado.manifesto["recorte"], {
            "estado_id": 13, "satelite": "AQUA_M-T",
            "inicio_inclusive": "2025-08-01T00:00:00+00:00",
            "fim_exclusive": "2025-09-01T00:00:00+00:00",
            "fuso_agregacao": "UTC",
        })
        self.assertEqual(resultado.manifesto["resultado"]["agregacoes"], resultado.agregacoes)

        self.assertEqual(
            resultado.manifesto["snapshot"],
            {
                "sha256": snapshot.sha256,
                "bytes": snapshot.bytes,
            },
        )

        self.assertEqual(resultado.manifesto["perfil"], "fixture")
        self.assertEqual(
            resultado.manifesto["resultado"]["ids_selecionados_unicos"],
            2,
        )
        self.assertEqual(
            resultado.manifesto["resultado"]["resumo"],
            resultado.resumo,
        )

        self.assertEqual(len(resultado.execucao_sha256), 64)
        int(resultado.execucao_sha256, 16)

    def test_mesma_execucao_tem_mesma_identidade(self):
        snapshot = self.criar_snapshot()

        primeira = executar_snapshot(snapshot.diretorio)
        segunda = executar_snapshot(snapshot.diretorio)

        self.assertEqual(primeira.manifesto, segunda.manifesto)
        self.assertEqual(
            primeira.execucao_sha256,
            segunda.execucao_sha256,
        )

    def test_snapshot_diferente_muda_identidade_da_execucao(self):
        primeiro = self.criar_snapshot()
        execucao_1 = executar_snapshot(primeiro.diretorio)

        segundo = self.criar_snapshot(FIXTURE.read_bytes() + b"\n")
        execucao_2 = executar_snapshot(segundo.diretorio)

        self.assertNotEqual(
            execucao_1.snapshot_sha256,
            execucao_2.snapshot_sha256,
        )
        self.assertNotEqual(
            execucao_1.execucao_sha256,
            execucao_2.execucao_sha256,
        )

    def test_perfil_faz_parte_da_identidade(self):
        snapshot = self.criar_snapshot()

        fixture = executar_snapshot(
            snapshot.diretorio,
            perfil="fixture",
        )
        mensal = executar_snapshot(
            snapshot.diretorio,
            perfil="mensal",
        )

        self.assertNotEqual(
            fixture.execucao_sha256,
            mensal.execucao_sha256,
        )

    def test_manifesto_nao_depende_de_caminho_ou_horario(self):
        snapshot = self.criar_snapshot()

        manifesto = executar_snapshot(snapshot.diretorio).manifesto
        texto = str(manifesto)

        self.assertNotIn(str(self.raiz), texto)
        self.assertNotIn("criado_em", manifesto)
        self.assertNotIn("executado_em", manifesto)


    def test_sha_da_execucao_corresponde_ao_manifesto_canonico(self):
        snapshot = self.criar_snapshot()
        resultado = executar_snapshot(snapshot.diretorio)

        canonico = json.dumps(
            resultado.manifesto,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        esperado = hashlib.sha256(canonico).hexdigest()

        self.assertEqual(resultado.execucao_sha256, esperado)

    def test_ordem_das_chaves_nao_altera_identidade(self):
        snapshot = self.criar_snapshot()
        resultado = executar_snapshot(snapshot.diretorio)

        reordenado = dict(reversed(list(resultado.manifesto.items())))

        canonico = json.dumps(
            reordenado,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        self.assertEqual(
            hashlib.sha256(canonico).hexdigest(),
            resultado.execucao_sha256,
        )

    def test_mudancas_relevantes_alteram_identidade(self):
        snapshot = self.criar_snapshot()
        resultado = executar_snapshot(snapshot.diretorio)

        def hash_manifesto(manifesto):
            canonico = json.dumps(
                manifesto,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return hashlib.sha256(canonico).hexdigest()

        casos = []

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["versao_regras"] += 1
        casos.append(("versao_regras", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["snapshot"]["sha256"] = "0" * 64
        casos.append(("snapshot", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["perfil"] = "outro"
        casos.append(("perfil", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["limites"]["bytes_linha"] += 1
        casos.append(("limites", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["politica_identidade"]["duplicata"] = "manter_primeiro"
        casos.append(("politica_identidade", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["resultado"]["resumo"]["selecionadas"] += 1
        casos.append(("resultado", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["resultado"]["agregacoes"]["por_dia_utc"][0]["deteccoes"] += 1
        casos.append(("agregacoes", manifesto))

        manifesto = json.loads(json.dumps(resultado.manifesto))
        manifesto["recorte"]["fuso_agregacao"] = "America/Manaus"
        casos.append(("recorte", manifesto))

        for nome, alterado in casos:
            with self.subTest(campo=nome):
                self.assertNotEqual(
                    hash_manifesto(alterado),
                    resultado.execucao_sha256,
                )


if __name__ == "__main__":
    unittest.main()
