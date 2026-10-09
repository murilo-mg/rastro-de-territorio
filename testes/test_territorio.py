import io
import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from rastro.territorio import (
    RAIZ_REFERENCIA, carregar_referencia, conferir_municipios,
    extrair_municipios_ods, normalizar_nome,
)


class TestTerritorio(unittest.TestCase):
    def test_referencia_preservada_tem_62_codigos_e_edicao_explicita(self):
        r = carregar_referencia()
        self.assertEqual(len(r.municipios), 62)
        self.assertEqual(r.municipios["1300144"], "Apuí")
        self.assertEqual(r.municipios["1302603"], "Manaus")
        self.assertEqual(r.descricao["data_base"], "2025-12-31")
        self.assertEqual(r.descricao["edicao"], 2025)

    def test_extracao_do_ods_reproduz_csv_byte_a_byte(self):
        original = (RAIZ_REFERENCIA / "original.ods").read_bytes()
        self.assertEqual(extrair_municipios_ods(original),
                         (RAIZ_REFERENCIA / "municipios_am.csv").read_bytes())

    def test_adulteracao_dos_tres_arquivos_e_recusada(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta) / "ref"
            shutil.copytree(RAIZ_REFERENCIA, raiz)
            for nome in ("manifesto.json", "original.ods", "municipios_am.csv"):
                with self.subTest(nome=nome):
                    arquivo = raiz / nome
                    antes = arquivo.read_bytes()
                    arquivo.write_bytes(antes + b"alterado")
                    with self.assertRaisesRegex(ValueError, "Hash da referência"):
                        carregar_referencia(raiz)
                    arquivo.write_bytes(antes)

    def test_arquivo_e_diretorio_symlink_sao_recusados(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta) / "ref"
            shutil.copytree(RAIZ_REFERENCIA, raiz)
            csv = raiz / "municipios_am.csv"
            csv.unlink()
            csv.symlink_to(RAIZ_REFERENCIA / "municipios_am.csv")
            with self.assertRaises(ValueError):
                carregar_referencia(raiz)
            link = Path(pasta) / "link"
            link.symlink_to(RAIZ_REFERENCIA, target_is_directory=True)
            with self.assertRaises(ValueError):
                carregar_referencia(link)

    def test_normalizacao_preserva_pontuacao_e_distingue_nomes(self):
        self.assertEqual(normalizar_nome("  APUÍ  "), normalizar_nome("Apuí"))
        self.assertEqual(normalizar_nome("Careiro  da Várzea"), normalizar_nome("CAREIRO DA VARZEA"))
        self.assertNotEqual(normalizar_nome("Novo Airão"), normalizar_nome("Novo Aripuanã"))
        self.assertNotEqual(normalizar_nome("Nome-A"), normalizar_nome("Nome A"))

    def test_classifica_igual_equivalente_e_divergente_sem_corrigir(self):
        grupo = {"municipio_id": "1300144", "nomes": ["APUI", "Apuí", "Outro nome"]}
        antes = dict(grupo)
        c = conferir_municipios([grupo], carregar_referencia())
        linha = c["por_municipio"][0]
        self.assertEqual(linha["nomes_iguais"], ["Apuí"])
        self.assertEqual(linha["nomes_equivalentes"], ["APUI"])
        self.assertEqual(linha["nomes_divergentes"], ["Outro nome"])
        self.assertEqual(c["grupos_com_nomes_divergentes"], 1)
        self.assertEqual(grupo, antes)

    def test_codigo_desconhecido_nao_e_inferido_pelo_nome(self):
        c = conferir_municipios([{"municipio_id": "1399999", "nomes": ["Manaus"]}], carregar_referencia())
        self.assertEqual(c["codigos_nao_encontrados"], 1)
        g = c["por_municipio"][0]
        self.assertIsNone(g["nome_referencia"])
        self.assertEqual(g["nomes_sem_referencia"], ["Manaus"])

    def test_sem_codigo_e_sem_nome_nao_viram_correspondencia(self):
        c = conferir_municipios([
            {"municipio_id": None, "nomes": ["Manaus"]},
            {"municipio_id": "1302603", "nomes": []},
        ], carregar_referencia())
        self.assertEqual(c["por_municipio"][0]["situacao_codigo"], "ausente")
        self.assertEqual(c["por_municipio"][1]["nomes_iguais"], [])
        self.assertEqual(c["codigos_encontrados"], 1)

    def test_ods_invalido_ou_xml_com_entidades_e_recusado(self):
        with self.assertRaises(ValueError):
            extrair_municipios_ods(b"arquivo invalido")
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as z:
            z.writestr("content.xml", '<!DOCTYPE a [<!ENTITY x "teste">]><a/>')
        with self.assertRaisesRegex(ValueError, "Declarações XML"):
            extrair_municipios_ods(buffer.getvalue())

    def test_ods_com_xml_excessivo_e_recusado(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=8) as z:
            z.writestr("content.xml", b" " * (16 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "excede 16 MiB"):
            extrair_municipios_ods(buffer.getvalue())
