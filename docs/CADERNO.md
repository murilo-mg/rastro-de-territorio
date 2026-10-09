# Caderno local de resultados

O caderno permite explorar uma exportação existente no navegador, sem
servidor e sem reler o CSV nacional. JSON/CSV preservam os resultados; o HTML
apresenta contagens, comparação municipal, procedência e limitações.

## Fluxo

1. `python -m rastro --csv ...` ou `--snapshot ...` gera os seis arquivos das regras 4.
2. `python -m rastro verificar PASTA` confere a consistência interna.
3. `python -m rastro caderno PASTA` repete a conferência e publica o HTML.
4. O usuário abre o HTML, seleciona grupos, busca nomes/códigos e consulta o rastro.

Todos os comandos Python usam `PYTHONPATH=src` na raiz do projeto. Os comandos
completos para a fixture e o resultado real estão no
[README](../README.md#abrir-o-caderno-no-navegador).

O verificador não precisa do snapshot e não atesta que as contagens foram
calculadas a partir dele. Para reproduzir, reexecute o snapshot com as regras
e o perfil registrados e compare os resultados.

## Responsabilidades

| Módulo | Responsabilidade |
| --- | --- |
| `resultado.py` | Leitura limitada, esquema, hash, invariantes, matriz e igualdade dos CSVs |
| `territorio.py` | Referência IBGE preservada e conferência cadastral de código/nome |
| `caderno.py` | HTML, SVG, estilos e interação locais; publicação sem sobrescrita |
| `__main__.py` | Comandos, erros e resumo para terminal ou JSON |
| `execucao.py` e `agregacoes.py` | Resultados analíticos, matriz e manifesto |

Novas execuções usam regras 4 e novos hashes, incluindo matriz e referência.
Resultados das regras 3 permanecem legíveis, com quatro arquivos e seus
hashes originais. O HTML fica fora da exportação. O caderno versão 2 usa
`dados/cadernos/v2/`, já ignorado pelo Git, preservando os HTMLs anteriores.

## Exploração e interpretação

A série geral mostra os 31 dias UTC, inclusive zeros, com eixo começando em
zero e tabela de valores exatos. Os indicadores gerais permanecem ligados
ao recorte completo.

Na comparação, selecione de um a três grupos. As séries vêm da matriz
município × dia calculada na execução, sem inferência a partir dos totais.
O gráfico usa contagens absolutas e o mesmo eixo para todas as séries.
Cores e padrões de linha distintos, legenda e tabela exata identificam os
grupos. O resumo apresenta total, participação no recorte, dias com detecções,
máximo diário e todas as datas UTC empatadas no máximo. Grupos repetidos são
desabilitados nos demais seletores.

O grupo sem código, se existir, pode ser consultado, mas é identificado como
não territorial. Códigos cadastrados sem observações não são acrescentados.
Resultados históricos sem matriz explicam a indisponibilidade da comparação.

A busca por código/nome, com ou sem acento, filtra somente a tabela municipal.
Ela não altera a comparação nem o gráfico geral. A ordenação usa contagem ou
código; empates de contagem usam código. O status informa grupos e detecções
visíveis. Todos os percentuais usam o total selecionado, inclusive sem código.

Todos os nomes da fonte são preservados. A coluna IBGE apresenta o nome
cadastral e distingue igualdade literal, equivalência após normalização,
divergência e código não encontrado. O quadro de qualidade separa ausências
de problemas opcionais; uma observação pode ter mais de um problema.

A referência é DTB 2025, data-base 31/12/2025, posterior ao recorte. Ela não
identifica a edição usada pelo INPE nem testa a localização espacial dos
pontos. Contagens não são incêndios distintos, área queimada ou risco.
Detalhes em [REFERENCIA_MUNICIPAL.md](REFERENCIA_MUNICIPAL.md).

## Navegação e impressão

O HTML contém CSS e JavaScript próprios, sem bibliotecas de frontend, fontes
remotas, mapas ou chamadas HTTP automáticas. Funciona aberto por `file://`.
Links de referências só usam internet quando abertos pelo usuário.

Busca, ordenação, seleção e limpeza têm rótulos e são operáveis pelo teclado.
Regiões de status informam filtros e comparação. Tabelas e gráficos largos
rolam dentro da seção em telas estreitas. Sem JavaScript, todas as tabelas,
inclusive a matriz completa de 31 dias por grupo, permanecem legíveis;
os controles ficam desabilitados.

A impressão mantém busca e comparação atuais. Os detalhes diários e de
procedência são abertos, inclusive a tabela diária da comparação. A matriz
completa não entra na impressão por sua largura; permanece no HTML e CSV.
Limpe a busca para imprimir todos os grupos. A paginação pode variar entre
navegadores; não é um PDF editorial com diagramação fixa.

## Limites e integridade

São suportados manifesto/regras/agregações `2/3/1` e `3/4/2`, no recorte atual.
Cada JSON/CSV determinístico tem limite de 16 MiB; o contexto, 8 KiB.
O caderno aceita até 10.000 grupos e carrega as agregações em memória.
Esses limites técnicos não indicam avaliação de desempenho no máximo.

Arquivos faltando, inesperados, divergentes ou malformados interrompem a
verificação. O CLI retorna 2 sem publicar HTML parcial. O contrato completo
está em [DADOS.md](DADOS.md#verificação-independente-e-caderno-local).

O HTML é determinístico para os mesmos arquivos exportados e gerador, sem
acrescentar horário atual ou caminho local. O contexto da primeira exportação
faz parte da apresentação, mas fica fora do hash da execução. Destinos
idênticos são reutilizados; divergentes são preservados e exigem outro nome.

A publicação usa arquivo temporário, `fsync` do arquivo e hard link atômico
no mesmo sistema de arquivos, sem substituir destino concorrente. Links
simbólicos no arquivo final e saída dentro da exportação são recusados.
Limites de concorrência e durabilidade permanecem descritos no contrato.

## Validação desta etapa

Os 169 testes offline passaram com Python 3.12.14 no Linux. Cobrem limites,
snapshots, identidade, agregações, referência adulterada, extração ODS
reproduzível, matriz com margens incoerentes, conferência cadastral alterada,
novos CSVs, leitura histórica, HTML/JSON, CSP, publicação, falhas e CLI.

| Resultado real nas regras 4 | Valor |
| --- | --- |
| Detecções selecionadas | 1.842 |
| Dias UTC | 31 |
| Códigos observados e encontrados na DTB 2025 | 50 |
| Sem código utilizável | 0 |
| Células da matriz, inclusive zeros | 1.550 |
| SHA-256 da execução | `62cd809c8b059aa98decc8640c8a7507a05d204f82529dc6f660a25e8f87ca92` |

Uma contagem independente coincidiu com todas as células da matriz. O
registro do processamento original e da nova execução está em
[VALIDACAO_REAL.md](VALIDACAO_REAL.md).

A apresentação foi exercitada em Chrome Headless 151.0.7922.34, em viewports
1440 × 1000 e 390 × 844. Apuí, Humaitá e Novo Aripuanã foram selecionados
juntos; as 93 contagens diárias exibidas coincidiram com os vetores exportados.
Foram conferidos totais, percentuais, máximos, seleção repetida desabilitada,
limpeza, independência entre busca e comparação, matriz sem JavaScript e
preservação da seleção na impressão. Não houve erros de JavaScript,
requisições HTTP automáticas ou transbordamento horizontal da página.
A paginação em outros navegadores e uma auditoria completa com tecnologias
assistivas permanecem sem validação sistemática.
