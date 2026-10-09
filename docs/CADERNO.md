# Caderno local de resultados

O caderno permite explorar uma exportação existente no navegador, sem
servidor e sem reler o CSV nacional. Os dados continuam disponíveis nos
formatos JSON/CSV, e o HTML apresenta as contagens com suas limitações.

## Fluxo

1. `python -m rastro --csv ...` ou `--snapshot ...` gera os quatro artefatos.
2. `python -m rastro verificar PASTA` confere a consistência interna.
3. `python -m rastro caderno PASTA` repete essa conferência e publica o HTML.
4. O usuário abre o HTML no navegador, busca nomes/códigos e consulta o rastro.

Todos os comandos Python usam `PYTHONPATH=src` na raiz do projeto. Os comandos
completos para a fixture e para a execução real estão no
[README](../README.md#abrir-o-caderno-no-navegador).

O verificador não precisa do snapshot. Ele não atesta que as contagens foram
calculadas a partir dele. Para isso, reexecute o snapshot com as regras e o
perfil registrados e compare os resultados.

## Responsabilidades

| Módulo | Responsabilidade |
| --- | --- |
| `resultado.py` | Leitura limitada, esquema suportado, hash, invariantes e igualdade dos CSVs |
| `caderno.py` | HTML, SVG, estilos e interação locais; publicação sem sobrescrita |
| `__main__.py` | Comandos `verificar` e `caderno`, erros e resumo para terminal ou JSON |
| `execucao.py` e `agregacoes.py` | Permanecem responsáveis pelos resultados analíticos |

As regras 3 e os hashes das execuções anteriores permanecem iguais. O HTML
não é colocado na pasta de resultado porque ela tem um contrato de exatamente
quatro arquivos. A pasta padrão é `dados/cadernos/`, já ignorada pelo Git.

## Exploração e interpretação

- A série diária inclui os 31 dias UTC e parte de zero; os valores exatos
  também ficam em uma tabela expansível.
- A tabela municipal pode ser buscada por código ou nome, com ou sem acento,
  e ordenada por detecções ou código. Empates de contagem usam o código.
- A busca informa quantos grupos e detecções continuam visíveis. Os percentuais
  usam o total selecionado, inclusive as observações sem código utilizável.
- Os indicadores gerais e o gráfico diário não mudam com a busca. Não é
  possível derivar uma série por município a partir dessas duas tabelas.
- Todos os nomes distintos são apresentados. Nomes divergentes, códigos
  ausentes e observações sem nome recebem indicação explícita.
- O quadro de qualidade separa valores ausentes de problemas opcionais.
  Um mesmo registro pode contribuir para mais de um problema.
- O contexto da primeira exportação é apresentado como declarado. A data de
  exportação não é usada como data de acesso ao INPE.
- O snapshot da fixture do repositório recebe a indicação de dados sintéticos.
  Outros arquivos sintéticos não são identificados automaticamente.

Contar detecções não equivale a contar incêndios distintos, medir área queimada
ou comparar risco. Os códigos listados não constituem todos os municípios
do Amazonas e ainda não foram cruzados com uma malha oficial.

## Navegação e impressão

O HTML contém CSS e JavaScript próprios, sem bibliotecas de frontend, fontes
remotas, mapas ou chamadas HTTP automáticas. Funciona aberto por `file://`.
As referências externas só usam internet quando o usuário abre seus links.

Busca, ordenação e limpeza são operáveis pelo teclado e têm rótulos. Uma
região de status informa o resultado do filtro. O gráfico tem descrição e
tabela alternativa. Tabelas largas rolam dentro da seção em telas estreitas.
Sem JavaScript, o conteúdo completo permanece legível e os controles ficam
desabilitados.

O botão de impressão chama a impressão do navegador. A busca atual é mantida,
e os detalhes diários e de procedência são abertos durante a impressão.
Limpe a busca para imprimir todos os grupos. A paginação pode variar entre
navegadores; a saída não é um PDF editorial com diagramação fixa.

## Limites e integridade

O importador suporta apenas manifesto 2, regras 3 e agregações 1, no recorte
atual. Limita cada JSON/CSV determinístico a 16 MiB e o contexto a 8 KiB.
O caderno aceita até 10.000 grupos e carrega as agregações em memória.
Esses limites são técnicos e não indicam validação de desempenho no máximo.

Arquivos faltando, inesperados, divergentes ou malformados interrompem a
verificação. O CLI retorna 2 e não publica HTML parcial. Versões novas exigem
suporte explícito no importador. O contrato completo está em
[DADOS.md](DADOS.md#verificação-independente-e-caderno-local).

O HTML é determinístico para os mesmos quatro arquivos e o mesmo gerador.
Não acrescenta horário atual ou caminho local. O contexto da exportação
original faz parte da apresentação, mas não do hash da execução. Para guardar
uma apresentação gerada por outra versão, use um nome novo com `--saida`.

O gerador preserva qualquer destino divergente, recusa links simbólicos no
arquivo final e impede salvar dentro da pasta original. A publicação usa
hard link atômico no mesmo sistema de arquivos, sem substituir arquivo
concorrente. Os limites de concorrência e durabilidade estão no contrato.

## Validação desta etapa

Os 143 testes offline passaram com Python 3.12.14 no Linux. Os novos testes
cobrem importação sem snapshot, corrupção, soma incoerente com hash recalculado,
tipos inválidos, calendário, contexto, arquivos especiais, ausência de código,
nomes divergentes, execução vazia, escape HTML/JSON, CSP, publicação e CLI.

O verificador leu as exportações da fixture e do CSV nacional de agosto de
2025 produzidas pela etapa anterior. O resultado real manteve:

| Item | Resultado |
| --- | --- |
| Detecções selecionadas | 1.842 |
| Dias UTC na série | 31 |
| Códigos municipais | 50 |
| Sem código utilizável | 0 |
| SHA-256 da execução | `e64d4e0ec72b9bf1e7e5bc5c718f7622e8357df2bdda479505474d5e8bce4f0c` |

Essa leitura verifica consistência interna dos artefatos. O registro do
processamento original está em [VALIDACAO_REAL.md](VALIDACAO_REAL.md).

A apresentação do resultado real foi exercitada em Chrome Headless
151.0.7922.34, com viewport de 1440 × 1000 e 390 × 844. Foram conferidos:
busca por `apui` e por código, 416 detecções de Apuí (22,6% do recorte),
busca sem correspondência, limpeza, ordenação, preservação da série diária,
leitura sem JavaScript e abertura/restauração dos detalhes na impressão.
Não houve erros de JavaScript, requisições HTTP automáticas ou transbordamento
horizontal da página; as tabelas e o gráfico possuem rolagem interna quando
necessário. A paginação em outros navegadores e a auditoria completa com
tecnologias assistivas permanecem sem validação sistemática.
