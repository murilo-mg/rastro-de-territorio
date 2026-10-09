"""Caderno HTML autossuficiente, derivado de uma exportação verificada."""

import base64
import hashlib
import html
import json
import os
import tempfile
from pathlib import Path
from string import Template

from .resultado import verificar_resultado


VERSAO_CADERNO = 1
FIXTURE_SHA256 = "82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f"
LIMITE_GRUPOS = 10_000


CSS = """
:root{color-scheme:light;--papel:#f5f3eb;--fundo:#fffefa;--tinta:#203b36;--muted:#52635d;--linha:#d3dbd2;--rio:#1b6353;--alerta:#785416}
*{box-sizing:border-box}body{margin:0;background:var(--papel);color:var(--tinta);font:16px/1.6 system-ui,sans-serif}
a{color:var(--rio);text-underline-offset:3px}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #af681b;outline-offset:3px}
.pular{position:absolute;top:-100px;background:white;padding:8px}.pular:focus{top:0}
.marca{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--linha);padding:19px 0;font-size:14px;letter-spacing:.02em}
.marca strong{font-weight:750}.local{color:var(--muted)}main,.marca,footer{width:min(1160px,calc(100% - 48px));margin:auto}
header{padding:40px 0 25px}h1{font-size:clamp(30px,5vw,48px);line-height:1.15;letter-spacing:-.04em;margin:10px 0 18px;font-weight:700}
h2{font-size:23px;line-height:1.3;margin:0 0 9px;letter-spacing:-.025em}h3{font-size:17px;margin:0 0 8px}p{margin:8px 0 16px}.subtitulo{max-width:780px;color:var(--muted);font-size:18px}
.etiqueta{font:12px/1.4 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.07em;color:var(--rio)}.aviso{border-left:3px solid #aa7325;background:#eee8d8;padding:14px 18px;margin:0 0 25px}
.indicadores{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--linha);background:var(--fundo);margin-bottom:28px}.indicador{padding:22px;border-right:1px solid var(--linha)}.indicador:last-child{border-right:0}
.numero{display:block;font-size:34px;line-height:1.25;letter-spacing:-.04em;font-variant-numeric:tabular-nums}.indicador span:last-child{display:block;color:var(--muted);font-size:13px;margin-top:8px}
section{border:1px solid var(--linha);background:var(--fundo);padding:26px;margin:0 0 25px}.secao-topo{display:flex;justify-content:space-between;gap:20px;align-items:baseline}.nota{font-size:14px;color:var(--muted)}.selo{font-size:12px;color:var(--rio);white-space:nowrap}
.grafico{overflow-x:auto}.grafico svg{display:block;width:100%;min-width:600px;height:auto}.grade{stroke:var(--linha);stroke-width:1}.barra{fill:var(--rio)}.eixo{fill:var(--muted);font-size:12px}.valor{fill:var(--tinta);font-size:11px}
.filtros{display:flex;gap:18px;align-items:end;flex-wrap:wrap;margin:22px 0 14px}.filtros label{font-size:14px;display:flex;flex-direction:column;gap:5px}.filtros label:first-child{flex:1;min-width:200px}
input,select,button{font:inherit;color:var(--tinta);background:var(--fundo);border:1px solid #8d9f93;border-radius:3px;padding:9px 12px}button{cursor:pointer}button:hover{background:#edf1e9}input{width:100%}input:disabled,select:disabled,button:disabled{opacity:.6;cursor:default}
.tabela{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}caption{text-align:left;color:var(--muted);padding:8px 0 13px}th,td{border-bottom:1px solid var(--linha);text-align:left;padding:12px 10px;vertical-align:top}th{font-weight:650;background:#edf1e9}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.codigo{font:13px ui-monospace,monospace;white-space:nowrap}.nomes{min-width:170px;overflow-wrap:anywhere}.observacao{max-width:220px;color:var(--muted)}
.qualidade{display:grid;grid-template-columns:1fr 1fr;gap:30px}.listas{margin:10px 0;padding-left:20px}.listas li{margin-bottom:9px}details{margin:17px 0}summary{cursor:pointer;font-weight:600;padding:5px 0}code{font:13px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}dl{display:grid;grid-template-columns:200px minmax(0,1fr);gap:10px 22px;font-size:14px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}footer{font-size:13px;color:var(--muted);padding:0 0 28px}.imprimir{float:right;margin:0 0 8px 18px}noscript p{background:#eee8d8;padding:14px}.sem-linhas{text-align:center;padding:28px}.fonte{margin-top:20px}
@media(max-width:700px){main,.marca,footer{width:calc(100% - 28px)}header{padding-top:28px}section{padding:17px}.indicadores{grid-template-columns:repeat(2,1fr)}.indicador:nth-child(2){border-right:0}.indicador:nth-child(-n+2){border-bottom:1px solid var(--linha)}.numero{font-size:28px}.qualidade{grid-template-columns:1fr;gap:20px}.secao-topo{display:block}.marca{font-size:12px}dl{grid-template-columns:1fr;gap:5px}dd{margin-bottom:12px}.imprimir{float:none;margin:0 0 18px}}
@media print{body{background:white;font-size:11px}.marca,main,footer{width:100%}.filtros,.imprimir,.pular,noscript{display:none}header{padding:12px 0}h1{font-size:28px}h2{font-size:19px}section{padding:15px;break-inside:auto}.indicadores,.grafico,.qualidade,dl{break-inside:avoid}.tabela,.grafico{overflow:visible}table{font-size:10px}tr{break-inside:avoid}thead{display:table-header-group}th,td{padding:6px}.grafico svg{min-width:0}.indicador{padding:12px}.numero{font-size:26px}.nota{font-size:11px}a{color:inherit}.observacao{max-width:150px}}
""".strip()


JS = r"""
"use strict";
const dados = JSON.parse(document.getElementById("dados").textContent);
const grupos = dados.manifesto.resultado.agregacoes.por_municipio;
const total = dados.manifesto.resultado.resumo.selecionadas;
const formato = new Intl.NumberFormat("pt-BR");
const percentual = new Intl.NumberFormat("pt-BR", {minimumFractionDigits: 1, maximumFractionDigits: 1});
const busca = document.getElementById("busca");
const ordem = document.getElementById("ordem");
const corpo = document.getElementById("municipios");
const estado = document.getElementById("estado-filtro");
const normalizar = texto => texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
const codigo = g => g.municipio_id === null ? "Sem código" : g.municipio_id;
const compararCodigo = (a, b) => (a.municipio_id === null) - (b.municipio_id === null) || (a.municipio_id || "").localeCompare(b.municipio_id || "");
function atualizar() {
  const termo = normalizar(busca.value.trim());
  const linhas = grupos.filter(g => normalizar([codigo(g), ...g.nomes].join(" ")).includes(termo));
  linhas.sort((a,b) => ordem.value === "codigo" ? compararCodigo(a,b) : b.deteccoes - a.deteccoes || compararCodigo(a,b));
  const fragmento = document.createDocumentFragment();
  for (const g of linhas) {
    const tr = document.createElement("tr");
    const notas = [];
    if (g.municipio_id === null) notas.push("Código ausente ou inválido; grupo não territorial");
    if (g.nomes_divergentes) notas.push("Nomes divergentes");
    if (g.sem_nome) notas.push(formato.format(g.sem_nome) + " sem nome");
    const valores = [codigo(g), g.nomes.length ? g.nomes.join(" / ") : "Nome não informado", formato.format(g.deteccoes), total ? percentual.format(100*g.deteccoes/total) + "%" : "—", notas.join("; ") || "—"];
    const classes = ["codigo", "nomes", "num", "num", "observacao"];
    valores.forEach((valor, i) => { const td = document.createElement("td"); td.className=classes[i]; td.textContent=valor; tr.append(td); });
    fragmento.append(tr);
  }
  if (!linhas.length) {
    const tr = document.createElement("tr"), td = document.createElement("td");
    td.colSpan=5; td.className="sem-linhas"; td.textContent=grupos.length ? "Nenhum grupo corresponde à busca." : "Nenhuma detecção selecionada.";
    tr.append(td); fragmento.append(tr);
  }
  corpo.replaceChildren(fragmento);
  const soma = linhas.reduce((n,g) => n + g.deteccoes, 0);
  estado.textContent = formato.format(linhas.length) + " de " + formato.format(grupos.length) + " grupos exibidos · " + formato.format(soma) + " de " + formato.format(total) + " detecções. Percentuais usam o total do recorte.";
}
for (const id of ["busca", "ordem", "limpar", "imprimir"]) document.getElementById(id).disabled=false;
busca.addEventListener("input", atualizar);
ordem.addEventListener("change", atualizar);
document.getElementById("limpar").addEventListener("click", () => {busca.value=""; ordem.value="deteccoes"; atualizar(); busca.focus();});
document.getElementById("imprimir").addEventListener("click", () => window.print());
let detalhesAbertos = null;
window.addEventListener("beforeprint", () => { if (detalhesAbertos !== null) return; detalhesAbertos=[...document.querySelectorAll("details")].map(d=>d.open); document.querySelectorAll("details").forEach(d=>d.open=true); });
window.addEventListener("afterprint", () => { if (detalhesAbertos === null) return; document.querySelectorAll("details").forEach((d,i)=>d.open=detalhesAbertos[i]); detalhesAbertos=null; });
atualizar();
""".strip()


PAGINA = Template("""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="$csp">
<meta name="referrer" content="no-referrer">
<title>$titulo · Rastro de Território</title><style>$css</style></head>
<body><a href="#conteudo" class="pular">Pular para o conteúdo</a>
<div class="marca"><strong>RASTRO DE TERRITÓRIO</strong><span class="local">Caderno local · funciona offline</span></div>
<main id="conteudo"><header><span class="etiqueta">Amazonas / agosto de 2025 / UTC</span>
<h1>$titulo</h1><p class="subtitulo">Como as detecções do satélite AQUA_M-T se distribuíram pelo Amazonas durante o mês?</p></header>
<div class="aviso">$aviso <strong>Detecções não equivalem a incêndios distintos nem a área queimada.</strong></div>
<div class="indicadores" aria-label="Resumo do recorte">
<div class="indicador"><strong class="numero">$total</strong><span>detecções selecionadas</span></div>
<div class="indicador"><strong class="numero">$municipios</strong><span>códigos municipais na fonte</span></div>
<div class="indicador"><strong class="numero">$dias_com_deteccao / 31</strong><span>dias UTC com detecções</span></div>
<div class="indicador"><strong class="numero">$sem_codigo</strong><span>detecções sem código utilizável</span></div>
</div>
<section aria-labelledby="serie-titulo"><div class="secao-topo"><h2 id="serie-titulo">O mês, dia a dia</h2><span class="selo">Total do recorte</span></div>
<p class="nota">Os 31 dias UTC estão representados, incluindo os dias com zero. A busca municipal abaixo não altera esta série.</p>
<div class="grafico">$grafico</div><p class="nota">$pico</p>
<details><summary>Consultar os valores diários</summary><div class="tabela"><table>
<caption>Contagem de detecções por dia UTC</caption><thead><tr><th scope="col">Dia UTC</th><th scope="col" class="num">Detecções</th></tr></thead><tbody>$dias_tabela</tbody></table></div></details></section>
<section aria-labelledby="municipios-titulo"><div class="secao-topo"><h2 id="municipios-titulo">Distribuição por município informado</h2><span class="selo">Agregação por código</span></div>
<p class="nota">Código e nomes vêm do CSV. Não houve conferência com uma malha territorial. Todos os nomes de cada grupo estão preservados.</p>
<noscript><p>JavaScript está desativado. As tabelas completas, os gráficos e a procedência continuam disponíveis; busca e ordenação precisam de JavaScript.</p></noscript>
<div class="filtros"><label for="busca">Buscar código ou nome<input id="busca" type="search" placeholder="Ex.: Apuí ou 1300144" aria-controls="municipios" disabled></label>
<label for="ordem">Ordenar<select id="ordem" aria-controls="municipios" disabled><option value="deteccoes">Mais detecções</option><option value="codigo">Código crescente</option></select></label>
<button id="limpar" type="button" disabled>Limpar busca</button></div>
<p class="nota" id="estado-filtro" role="status" aria-live="polite">$estado_filtro</p>
<div class="tabela"><table><caption>Participação no total de detecções selecionadas; não é taxa por área ou população.</caption>
<thead><tr><th scope="col">Código</th><th scope="col">Nome(s) na fonte</th><th scope="col" class="num">Detecções</th><th scope="col" class="num">% do recorte</th><th scope="col">Observações</th></tr></thead><tbody id="municipios">$municipios_tabela</tbody></table></div></section>
<section aria-labelledby="qualidade-titulo"><h2 id="qualidade-titulo">O que entrou na contagem</h2><div class="qualidade"><div>
<h3>Leitura e seleção</h3><dl>$resumo</dl>
<p class="nota">Problemas opcionais contam ocorrências por campo e podem se acumular na mesma observação. Eles não excluem a detecção selecionada.</p></div><div>
<h3>Valores ausentes no recorte</h3><div class="tabela"><table><caption>Ausências incluem vazios, sentinelas reconhecidas e valores opcionais inválidos.</caption><thead><tr><th scope="col">Campo</th><th scope="col" class="num">Ausentes</th><th scope="col" class="num">Inválidos</th></tr></thead><tbody>$ausencias</tbody></table></div></div></div></section>
<section aria-labelledby="limites-titulo"><h2 id="limites-titulo">Como interpretar</h2><ul class="listas">
<li>O recorte usa o estado <code>13</code>, satélite exato <code>AQUA_M-T</code> e o intervalo de 01/08/2025 inclusive até 01/09/2025 exclusive, em UTC.</li>
<li>Uma contagem maior não mede, sozinha, gravidade, extensão queimada ou risco. Cobertura e condições de observação precisam ser consideradas.</li>
<li>Ausência de detecções não comprova ausência de fogo. A tabela só lista códigos que apareceram entre os selecionados; ela não é um cadastro de todos os municípios do Amazonas.</li>
<li>Os percentuais usam todas as detecções selecionadas, inclusive as sem código. Buscar um município filtra apenas a tabela. Esta exportação não contém o cruzamento município × dia.</li>
<li>Os arquivos passaram por conferência interna. Para reproduzir a análise, preserve o snapshot e execute a revisão correspondente; o hash não comprova a procedência científica.</li></ul>
<p class="nota fonte">Referência do projeto: INPE / Programa Queimadas. As referências abaixo exigem internet quando abertas: <a href="https://data.inpe.br/queimadas/dados-abertos/" target="_blank" rel="noopener noreferrer">dados abertos</a> e <a href="https://data.inpe.br/queimadas/faq/" target="_blank" rel="noopener noreferrer">perguntas frequentes</a>. Consulte as condições de uso antes de publicar derivados. A data da primeira exportação abaixo não é a data de acesso à fonte.</p></section>
<section aria-labelledby="origem-titulo"><button id="imprimir" class="imprimir" type="button" disabled>Imprimir / salvar PDF</button>
<h2 id="origem-titulo">Rastro deste resultado</h2><p class="nota">Verificados na geração: esquema, hash canônico, calendário, somas e correspondência dos CSVs. O contexto é declarado e fica fora do hash da execução.</p><dl>$proveniencia</dl>
<details><summary>Contexto da primeira exportação</summary><dl>$contexto</dl></details>
<p class="nota">O HTML é uma apresentação derivada. Para conferir alterações, gere-o novamente com os mesmos arquivos e a mesma versão do gerador e compare os bytes. Não substitui os quatro arquivos da exportação.</p></section>
</main><footer>Caderno $versao · sem bibliotecas externas, fontes remotas ou coleta de navegação. A impressão mantém a busca atual e inclui os detalhes.</footer>
<script type="application/json" id="dados">$dados</script><script>$js</script></body></html>
""")


def _esc(valor):
    return html.escape(str(valor), quote=True)


def _numero(valor):
    return f"{valor:,}".replace(",", ".")


def _lista_definicoes(pares):
    return "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in pares)


def _grafico(dias):
    maximo = max(d["deteccoes"] for d in dias)
    teto = max(maximo, 1)
    partes = ['<svg viewBox="0 0 1080 285" role="img" aria-labelledby="grafico-titulo grafico-descricao">',
              '<title id="grafico-titulo">Detecções diárias em agosto de 2025</title>',
              '<desc id="grafico-descricao">31 barras com eixo iniciando em zero. Os valores exatos estão na tabela diária abaixo.</desc>']
    for valor, y in ((0, 225), (teto, 40)):
        partes.append(f'<line x1="46" x2="1064" y1="{y}" y2="{y}" class="grade"/>')
        partes.append(f'<text x="38" y="{y+4}" text-anchor="end" class="eixo">{_numero(valor)}</text>')
    for i, dia in enumerate(dias):
        n = dia["deteccoes"]
        altura = 185 * n / teto
        x = 53 + i * 32.5
        partes.append(f'<rect x="{x:.2f}" y="{225-altura:.2f}" width="22" height="{altura:.2f}" class="barra"><title>{dia["dia_utc"]}: {n} detecções</title></rect>')
        partes.append(f'<text x="{x+11:.2f}" y="249" text-anchor="middle" class="eixo">{i+1:02}</text>')
        partes.append(f'<text x="{x+11:.2f}" y="{217-altura:.2f}" text-anchor="middle" class="valor">{n}</text>')
    partes.append('<text x="1064" y="277" text-anchor="end" class="eixo">Dia de agosto (UTC)</text></svg>')
    return "".join(partes)


def _linha_municipio(g, total):
    notas = []
    if g["municipio_id"] is None:
        notas.append("Código ausente ou inválido; grupo não territorial")
    if g["nomes_divergentes"]:
        notas.append("Nomes divergentes")
    if g["sem_nome"]:
        notas.append(f'{_numero(g["sem_nome"])} sem nome')
    # Arredonda metade para cima, como Intl.NumberFormat no navegador.
    decimos = (2000 * g["deteccoes"] + total) // (2 * total) if total else 0
    percentual = f"{decimos // 10},{decimos % 10}%" if total else "—"
    valores = (g["municipio_id"] or "Sem código", " / ".join(g["nomes"]) or "Nome não informado",
               _numero(g["deteccoes"]), percentual, "; ".join(notas) or "—")
    classes = ("codigo", "nomes", "num", "num", "observacao")
    return "<tr>" + "".join(f'<td class="{c}">{_esc(v)}</td>' for c, v in zip(classes, valores)) + "</tr>"


def _hash_csp(texto):
    return base64.b64encode(hashlib.sha256(texto.encode("utf-8")).digest()).decode("ascii")


def _renderizar(verificado):
    r, contexto = verificado.execucao, verificado.contexto
    a, m = r.agregacoes, r.manifesto
    grupos = a["por_municipio"]
    if len(grupos) > LIMITE_GRUPOS:
        raise ValueError("O caderno suporta até 10.000 grupos municipais")
    dias = a["por_dia_utc"]
    total = r.resumo["selecionadas"]
    sintetico = r.snapshot_sha256 == FIXTURE_SHA256
    titulo = "Exemplo sintético de detecções" if sintetico else "Detecções no Amazonas"
    aviso = ("<strong>Dados sintéticos de teste.</strong> Esta fixture não descreve eventos reais. "
             if sintetico else "Entrada local. Confira a origem do snapshot antes de interpretar os números. ")
    maximo = max(d["deteccoes"] for d in dias)
    pico = ("Nenhuma detecção selecionada neste recorte." if not maximo else
            f'Maior contagem diária: {_numero(maximo)} detecções. Dia(s) UTC: ' +
            ", ".join(d["dia_utc"] for d in dias if d["deteccoes"] == maximo) + ".")
    grupos_ordenados = sorted(grupos, key=lambda g: (-g["deteccoes"], g["municipio_id"] is None, g["municipio_id"] or ""))
    tabela = "".join(_linha_municipio(g, total) for g in grupos_ordenados)
    if not tabela:
        tabela = '<tr><td colspan="5" class="sem-linhas">Nenhuma detecção selecionada.</td></tr>'
    campos = (("dias_sem_chuva", "Dias sem chuva", "numero_dias_sem_chuva"),
              ("precipitacao", "Precipitação", "precipitacao"),
              ("risco_fogo", "Risco de fogo", "risco_fogo"), ("frp", "FRP", "frp"),
              ("municipio_id", "Código municipal", "municipio_id"), ("municipio", "Nome municipal", None))
    ausencias = "".join(f'<tr><td>{nome}</td><td class="num">{_numero(a["ausencias"][campo])}</td><td class="num">{_numero(a["problemas_por_campo"].get(problema, 0)) if problema else "—"}</td></tr>' for campo, nome, problema in campos)
    dados = json.dumps({"execucao_sha256": r.execucao_sha256, "manifesto": m}, ensure_ascii=True,
                       sort_keys=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    csp = f"default-src 'none'; script-src 'sha256-{_hash_csp(JS)}'; style-src 'sha256-{_hash_csp(CSS)}'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    rotulos = {"lidas": "Linhas lidas", "selecionadas": "Selecionadas", "fora_do_recorte": "Fora do recorte",
               "rejeitadas": "Rejeitadas", "problemas_opcionais": "Problemas opcionais"}
    alterado = {True: "Sim", False: "Não", None: "Não informado"}[contexto["alteracoes_locais"]]
    return PAGINA.substitute(
        titulo=_esc(titulo), aviso=aviso, css=CSS, js=JS, dados=dados, csp=_esc(csp),
        total=_numero(total), municipios=_numero(a["municipios_com_codigo"]),
        dias_com_deteccao=sum(d["deteccoes"] > 0 for d in dias), sem_codigo=_numero(a["sem_municipio_id"]),
        grafico=_grafico(dias), pico=_esc(pico), municipios_tabela=tabela,
        estado_filtro=f'{_numero(len(grupos))} de {_numero(len(grupos))} grupos exibidos · {_numero(total)} de {_numero(total)} detecções. Percentuais usam o total do recorte.',
        dias_tabela="".join(f'<tr><td>{d["dia_utc"]}</td><td class="num">{_numero(d["deteccoes"])}</td></tr>' for d in dias),
        resumo=_lista_definicoes((titulo_campo, _numero(r.resumo[campo]))
                                 for campo, titulo_campo in rotulos.items()),
        ausencias=ausencias, versao=VERSAO_CADERNO,
        proveniencia=_lista_definicoes((
            ("SHA-256 da execução", r.execucao_sha256), ("SHA-256 do snapshot", r.snapshot_sha256),
            ("Tamanho do snapshot", f"{_numero(r.snapshot_bytes)} bytes"),
            ("Perfil de leitura", m["perfil"]), ("Versões", "Manifesto 2 · regras 3 · agregações 1"),
            ("IDs selecionados únicos", _numero(r.ids_selecionados_unicos)),
            ("Códigos com nomes divergentes", _numero(a["municipios_com_nomes_divergentes"])),
        )),
        contexto=_lista_definicoes((
            ("Primeira exportação (UTC)", contexto["primeira_exportacao_em_utc"]),
            ("Revisão Git declarada", contexto["revisao_git"] or "Não informada"),
            ("Alterações locais declaradas", alterado), ("SHA-256 do código declarado", contexto["codigo_sha256"]),
            ("Python declarado", contexto["python"]), ("Sistema declarado", contexto["plataforma"]),
        )),
    ).encode("utf-8")


def gerar_caderno(diretorio_resultado, destino=None):
    """Verifica a exportação e publica HTML completo; nunca sobrescreve outro arquivo.

    Mesmos arquivos e gerador produzem os mesmos bytes. A saída fica fora da
    exportação. Retorna (caminho, reutilizado), sem abrir navegador.
    """
    verificado = verificar_resultado(diretorio_resultado)
    conteudo = _renderizar(verificado)
    destino = Path(destino) if destino is not None else Path("dados/cadernos") / f"{verificado.execucao.execucao_sha256}.html"
    if destino.suffix.lower() != ".html":
        raise ValueError("O destino do caderno precisa ter extensão .html")
    if destino.is_symlink():
        raise ValueError("O destino do caderno não pode ser link simbólico")
    if destino.resolve().is_relative_to(verificado.diretorio.resolve()):
        raise ValueError("Salve o caderno fora da pasta do resultado verificado")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        if not destino.is_file() or destino.stat().st_size != len(conteudo) or destino.read_bytes() != conteudo:
            raise ValueError("Caderno existente divergente; escolha outro caminho de saída")
        return destino, True
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".rastro-caderno-", dir=destino.parent, delete=False) as f:
            temporario = Path(f.name)
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        # Link atômico, sem substituição se outro processo publicou primeiro.
        os.link(temporario, destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return destino, False
