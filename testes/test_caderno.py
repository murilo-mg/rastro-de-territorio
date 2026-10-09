import base64
import hashlib
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from rastro.caderno import gerar_caderno
from test_leitor import exemplo
from test_resultado import ExportacaoTemporaria


RAIZ = Path(__file__).resolve().parent.parent


class ExtrairHTML(HTMLParser):
    def __init__(self, texto):
        super().__init__()
        self.elementos = []
        self.scripts = []
        self.estilos = []
        self.csp = ""
        self.atual = None
        self.feed(texto)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elementos.append((tag, attrs))
        if tag == "script":
            self.atual = [attrs, ""]
            self.scripts.append(self.atual)
        elif tag == "style":
            self.atual = [attrs, ""]
            self.estilos.append(self.atual)
        elif tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs["content"]

    def handle_data(self, data):
        if self.atual is not None:
            self.atual[1] += data

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.atual = None


class TestCaderno(ExportacaoTemporaria):
    def gerar(self, pasta=None):
        destino = self.raiz / "caderno.html"
        gerar_caderno(pasta or self.pasta, destino)
        return destino, destino.read_text(encoding="utf-8")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "rastro", *map(str, args)],
                              cwd=RAIZ, env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
                              text=True, capture_output=True, timeout=20)

    def test_html_preserva_tabelas_e_manifesto_completos(self):
        _, texto = self.gerar()
        pagina = ExtrairHTML(texto)
        dados = json.loads(next(t for a, t in pagina.scripts if a.get("id") == "dados"))
        self.assertEqual(dados["manifesto"], self.execucao.manifesto)
        self.assertIn("Dados sintéticos de teste", texto)
        self.assertIn("MANAUS", texto)
        self.assertIn("2025-08-31", texto)
        self.assertEqual(sum(tag == "rect" for tag, _ in pagina.elementos), 31)
        self.assertEqual(sum(tag == "tbody" for tag, _ in pagina.elementos), 3)

    def test_csp_permite_apenas_scripts_e_estilos_gerados(self):
        _, texto = self.gerar()
        pagina = ExtrairHTML(texto)
        for atributos, conteudo in pagina.scripts + pagina.estilos:
            if atributos.get("type") == "application/json":
                continue
            digest = base64.b64encode(hashlib.sha256(conteudo.encode()).digest()).decode()
            self.assertIn(f"'sha256-{digest}'", pagina.csp)
        self.assertIn("connect-src 'none'", pagina.csp)
        self.assertNotIn("unsafe-inline", pagina.csp)
        self.assertFalse(any("src" in a for _, a in pagina.elementos))
        self.assertFalse(any(k.startswith("on") for _, a in pagina.elementos for k in a))

    def test_nome_nao_injeta_html_nem_fecha_json(self):
        nome = '</script><script>alert(1)</script><img src=x onerror=alert(2)> & "Apuí"'
        pasta = self.exportar_linhas([exemplo(municipio=nome)])
        _, texto = self.gerar(pasta)
        pagina = ExtrairHTML(texto)
        self.assertEqual(len(pagina.scripts), 2)
        self.assertFalse(any(t == "img" for t, _ in pagina.elementos))
        dados = json.loads(pagina.scripts[0][1])
        self.assertEqual(dados["manifesto"]["resultado"]["agregacoes"]["por_municipio"][0]["nomes"], [nome])
        self.assertNotIn("innerHTML", pagina.scripts[1][1])

    def test_caderno_vazio_nao_divide_por_zero(self):
        pasta = self.exportar_linhas([exemplo(satelite="GOES-19")])
        _, texto = self.gerar(pasta)
        self.assertIn("Nenhuma detecção selecionada", texto)
        self.assertNotIn("NaN", texto)

    def test_percentual_estatico_arredonda_como_navegador(self):
        pasta = self.exportar_linhas([
            exemplo(id=str(i), municipio_id="1300144" if i == 0 else "1302603")
            for i in range(16)
        ])
        _, texto = self.gerar(pasta)
        self.assertIn('<td class="num">6,3%</td>', texto)
        self.assertIn('<td class="num">93,8%</td>', texto)

    def test_exibe_grupo_sem_codigo_e_todos_os_nomes(self):
        pasta = self.exportar_linhas([
            exemplo(id="a", municipio="Manaus"), exemplo(id="b", municipio="MANAUS"),
            exemplo(id="c", municipio_id="", municipio=""),
        ])
        _, texto = self.gerar(pasta)
        self.assertIn("MANAUS / Manaus", texto)
        self.assertIn("Nomes divergentes", texto)
        self.assertIn("grupo não territorial", texto)
        self.assertIn("Nome não informado", texto)

    def test_geracao_deterministica_reutiliza_sem_tocar_exportacao(self):
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir()}
        destino, _ = self.gerar()
        mtime = destino.stat().st_mtime_ns
        _, reutilizado = gerar_caderno(self.pasta, destino)
        self.assertTrue(reutilizado)
        self.assertEqual(destino.stat().st_mtime_ns, mtime)
        outro = self.raiz / "outro.html"
        gerar_caderno(self.pasta, outro)
        self.assertEqual(destino.read_bytes(), outro.read_bytes())
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.pasta.iterdir()})

    def test_recusa_saida_divergente_sem_sobrescrever(self):
        destino = self.raiz / "caderno.html"
        destino.write_text("anotações do usuário")
        with self.assertRaisesRegex(ValueError, "divergente"):
            gerar_caderno(self.pasta, destino)
        self.assertEqual(destino.read_text(), "anotações do usuário")

    def test_recusa_gravar_dentro_do_resultado(self):
        with self.assertRaisesRegex(ValueError, "fora da pasta"):
            gerar_caderno(self.pasta, self.pasta / "caderno.html")
        self.assertEqual(len(list(self.pasta.iterdir())), 4)

    def test_recusa_saida_symlink_e_extensao_incorreta(self):
        alvo = self.raiz / "destino.html"
        atalho = self.raiz / "atalho.html"
        atalho.symlink_to(alvo)
        with self.assertRaisesRegex(ValueError, "link simbólico"):
            gerar_caderno(self.pasta, atalho)
        with self.assertRaisesRegex(ValueError, "extensão"):
            gerar_caderno(self.pasta, self.raiz / "caderno.txt")
        self.assertFalse(alvo.exists())

    def test_limite_do_caderno_nao_modifica_resultado(self):
        with patch("rastro.caderno.LIMITE_GRUPOS", 0):
            with self.assertRaisesRegex(ValueError, "grupos municipais"):
                self.gerar()
        self.assertFalse((self.raiz / "caderno.html").exists())

    def test_falha_na_publicacao_remove_temporario(self):
        with patch("rastro.caderno.os.link", side_effect=OSError("falha simulada")):
            with self.assertRaises(OSError):
                self.gerar()
        self.assertFalse((self.raiz / "caderno.html").exists())
        self.assertEqual(list(self.raiz.glob(".rastro-caderno-*")), [])

    def test_concorrente_nao_substitui_arquivo(self):
        destino = self.raiz / "caderno.html"
        def outro_publicou(origem, final):
            final.write_text("outro resultado")
            raise FileExistsError("ocupado")
        with patch("rastro.caderno.os.link", side_effect=outro_publicou):
            with self.assertRaises(FileExistsError):
                gerar_caderno(self.pasta, destino)
        self.assertEqual(destino.read_text(), "outro resultado")
        self.assertEqual(list(self.raiz.glob(".rastro-caderno-*")), [])

    def test_cli_verifica_json_sem_reprocessar(self):
        p = self.cli("verificar", self.pasta, "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout)
        self.assertEqual(r["selecionadas"], 2)
        self.assertFalse(r["snapshot_reprocessado"])
        self.assertFalse(r["contexto_autenticado"])

    def test_cli_gera_html(self):
        destino = self.raiz / "saida.html"
        p = self.cli("caderno", self.pasta, "--saida", destino)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("caderno: criado", p.stdout)
        self.assertTrue(destino.exists())
        novamente = self.cli("caderno", self.pasta, "--saida", destino)
        self.assertIn("caderno: reutilizado", novamente.stdout)

    def test_cli_exportacao_corrompida_nao_publica_html(self):
        (self.pasta / "por_dia.csv").write_text("alterado")
        for comando in ("verificar", "caderno"):
            with self.subTest(comando=comando):
                args = [comando, self.pasta]
                if comando == "caderno":
                    args += ["--saida", self.raiz / "caderno.html"]
                p = self.cli(*args)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "")
                self.assertNotIn("Traceback", p.stderr)
        self.assertFalse((self.raiz / "caderno.html").exists())

    def test_cli_argumentos_incompativeis(self):
        for args in (("verificar",), ("caderno",), ("caderno", self.pasta, "--json"),
                     ("verificar", self.pasta, "--perfil", "mensal")):
            with self.subTest(args=args):
                p = self.cli(*args)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "")

    def test_cli_ajuda_explica_os_novos_comandos(self):
        p = self.cli("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("verificar PASTA", p.stdout)
        self.assertIn("caderno PASTA", p.stdout)
