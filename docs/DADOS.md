# Contrato de dados e reprodução

Este documento descreve o comportamento de [leitor.py](../src/rastro/leitor.py),
[snapshot.py](../src/rastro/snapshot.py) e [execucao.py](../src/rastro/execucao.py),
com referência nos [testes existentes](../testes). A validação usa dados
sintéticos; o arquivo nacional real ainda não foi processado nesta revisão.
Os comandos completos e as saídas da fixture estão no [README](../README.md).

## Pergunta e recorte

Como as detecções do satélite de referência se distribuíram pelo Amazonas
em agosto de 2025, e quais limitações devemos considerar ao interpretar esses números?

| Critério | Regra implementada |
| --- | --- |
| Estado | `estado_id` inteiro positivo, selecionado quando igual a `13` |
| Satélite | Igualdade exata com `AQUA_M-T` após aparar espaços |
| Início | `2025-08-01T00:00:00Z`, inclusive |
| Fim | `2025-09-01T00:00:00Z`, exclusive |
| Tempo | UTC; o horário local do computador não altera o recorte |
| Latitude | `Decimal` finito entre -90 e 90, inclusive |
| Longitude | `Decimal` finito entre -180 e 180, inclusive |

Esses critérios estão fixos no código; não são parâmetros da linha de comando.
`AQUA_M-M` e outros satélites ficam fora do recorte. O nome textual do estado
não substitui o código. Não há conferência de códigos com uma tabela oficial,
teste de ponto dentro de polígono, validação de datum ou transformação de CRS.
A precisão decimal não informa a precisão do sensor.

### Interpretação científica

Contagens representam registros de detecções, não incêndios distintos, hectares
queimados, causas ou infrações. Um evento pode gerar várias detecções e um pixel
pode abranger mais de uma frente de fogo. Nuvens, cobertura vegetal e horários
de passagem podem limitar a detecção; zero registros não comprova ausência de
fogo. Essas distinções estão na [FAQ do INPE, itens 9 a 11](https://data.inpe.br/queimadas/faq/).

A escolha de `AQUA_M-T` segue a referência descrita no item 7 da mesma FAQ.
A página contém textos históricos: sua consulta não valida o conteúdo do CSV
de agosto de 2025, a cobertura daquele período ou a malha territorial usada.
O projeto ainda não calcula uma distribuição espacial com dados reais.

## Formato aceito

Arquivo local regular, CSV com vírgula, UTF-8, BOM inicial opcional,
terminação LF ou CRLF e um registro por linha física. Aspas e vírgulas dentro
de campos são aceitas quando o CSV é válido. Campos com quebras de linha
internas não são suportados.

O cabeçalho precisa conter estes 16 nomes, sem repetição:

```text
id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp
```

Ordem diferente e espaços nas extremidades dos nomes são aceitos. Colunas
adicionais são permitidas dentro do limite, mas não entram no objeto `Foco`.
Linhas com quantidade diferente de campos são rejeitadas, salvo quando
ultrapassam um limite, caso em que a leitura inteira é interrompida.

Todos os valores são aparados antes da interpretação. As colunas são
obrigatórias no cabeçalho, mas isso não significa que todos os valores sejam
obrigatórios. `id`, `satelite`, `estado_id`, `data_hora_gmt`, `lat` e `lon`
são essenciais. `id` vira `source_id` no objeto interpretado. Identificador
e satélite precisam ser não vazios; estado deve ser inteiro positivo; data
e coordenadas devem ser válidas. Falhas nesses campos rejeitam a linha.

`municipio`, `estado`, `pais`, `municipio_id`, `pais_id` e `bioma` precisam
existir como colunas, mas seus valores não são validados nem preservados em
`Foco`. Não há agregação municipal ou conferência do país nesta etapa.
Os IDs `sintetico-*` da fixture são fictícios; não há validação de UUID ou
comprovação da estabilidade do identificador fornecido pela fonte.

`data_hora_gmt` precisa conter data e hora com segundos. São aceitos separador
espaço ou `T`, fração de segundo opcional e offset `Z` ou `±HH:MM`. Sem offset,
o leitor interpreta UTC conforme o nome GMT da coluna. Com offset, converte
para UTC antes do recorte. Data sem hora, data inválida ou conversão fora do
calendário é rejeitada. O objeto `datetime` tem resolução de microssegundos;
frações com mais casas não preservam toda a precisão textual.

## Valores ausentes e problemas

| Campo | Tratamento |
| --- | --- |
| `numero_dias_sem_chuva` | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser inteiros não negativos até 2.147.483.647 |
| `precipitacao` | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser finitos e não negativos |
| `risco_fogo` | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser finitos entre zero e um |
| `frp` | Vazio vira `None`; demais valores precisam ser finitos e não negativos |

Variantes `-999.0` e `-999.00` também são reconhecidas nos três campos
meteorológicos. Em `frp`, -999 é inválido, não uma sentinela reconhecida.
Zero permanece zero. Opcional inválido vira `None` e gera um problema associado
ao campo, preservando a observação quando os essenciais são válidos.

O limite inteiro é uma proteção técnica de representação, não uma afirmação
sobre duração plausível sem chuva. As faixas, sentinelas, unidades e significados
meteorológicos precisam ser conferidos com a fonte e o arquivo real.

## Contagens

As categorias de linhas são exclusivas:

```text
lidas = selecionadas + fora_do_recorte + rejeitadas
```

`lidas` conta registros devolvidos pelo leitor, sem cabeçalho ou linhas vazias.
Primeiro são validados os campos essenciais. Uma linha com essencial inválido
é rejeitada, mesmo que também pudesse estar fora do recorte. Uma linha válida
que não corresponde a estado, satélite ou período fica fora do recorte.
Campos opcionais só são avaliados nas linhas selecionadas.
`problemas_opcionais` conta campos inválidos, não observações inválidas.
Valores vazios e sentinelas reconhecidas não aumentam esse contador.

O resumo simples do leitor conta linhas repetidas normalmente. A API de
execução acrescenta `ids_selecionados_unicos` e o controle de identidade abaixo;
em uma execução concluída, esse número é igual a `selecionadas`.
Não existe contador ou categoria `repetidas`: uma repetição selecionada
invalida a execução, sem devolver resumo ou manifesto completos.

## IDs repetidos e conflitos

`executar_snapshot` verifica a integridade do snapshot antes de chamar o leitor.
Cada `source_id` selecionado é inserido como chave primária em um SQLite
temporário. A comparação distingue maiúsculas de minúsculas e usa o ID após
aparar espaços. IDs de linhas rejeitadas ou fora do recorte não são registrados.
O controle vale para aquela execução; não compara outros arquivos ou execuções.

Na primeira repetição selecionada, `ErroIdentidade` informa o ID, os números
das duas linhas físicas e uma classificação: `mesmo conteúdo interpretado` ou
`conteúdo diferente`. Ambas interrompem o processamento. Não há política de
manter a primeira linha, consolidar dados ou eliminar duplicatas automaticamente.
IDs diferentes não são agrupados por proximidade nem tratados como um incêndio.

A classificação compara hashes SHA-256 de uma lista JSON dos campos de `Foco`:
ID, latitude, longitude, data UTC, satélite, estado e os quatro opcionais.
Campos descartados, como município e bioma, e a lista de problemas opcionais
não participam. Portanto, textos distintos podem produzir a mesma assinatura,
inclusive um opcional inválido e um ausente, pois ambos viram `None`.

Há uma limitação adicional confirmada na revisão: a assinatura usa
`Decimal.normalize()`, que depende do contexto decimal e pode arredondar.
Por exemplo, precipitações `1.12345678901234567890123456781` e
`1.12345678901234567890123456782` são valores interpretados diferentes, mas
geram a mesma assinatura no contexto padrão. Isso pode classificar um conflito
como `mesmo conteúdo interpretado`; a repetição ainda é recusada.
Um opcional finito extremo, como precipitação `1e1000000`, é aceito pelo leitor,
mas provoca `decimal.Overflow` ao gerar a assinatura. Essa falha ainda não tem
tratamento específico na API. A revisão de documentação não altera esses comportamentos.

## Limites implementados

MiB significa 1.048.576 bytes; KiB, 1.024 bytes; GiB, 1.073.741.824 bytes.

| Limite | Perfil `fixture` (padrão) | Perfil `mensal` |
| --- | --- | --- |
| Bytes do arquivo inteiro | 5 MiB | 512 MiB |
| Linhas físicas após o cabeçalho | 20.000 | 5.000.000 |
| Bytes por linha física | 64 KiB | 64 KiB |
| Bytes por campo decodificado em UTF-8 | 4 KiB | 4 KiB |
| Colunas | 32 | 32 |
| Tempo de leitura do CSV | 900 segundos | 900 segundos |

Tamanhos e quantidades exatamente no limite são aceitos. O tempo é interrompido
quando atinge ou ultrapassa 900 segundos. Bytes totais são conferidos no arquivo
aberto e nos bytes efetivamente lidos. Os limites de linha, campo e colunas
incluem o cabeçalho. Bytes de linha incluem aspas, separadores e terminadores.
O limite de campo conta o valor extraído do CSV antes de aparar espaços.
Linhas vazias após o cabeçalho consomem o limite físico, sem entrar nas contagens.

O tempo usa relógio monotônico, conferido entre leituras e após cada leitura.
É cooperativo: não encerra I/O bloqueado por um processo externo. Inclui o tempo
que um consumidor do iterador passa entre chamadas, como as inserções de IDs.
Verificação do snapshot e leitura do CSV têm cronômetros separados; não há
prazo total de 900 segundos para toda a execução.

O leitor trabalha com uma linha limitada por vez. O controle de IDs usa disco
temporário, sem manter um conjunto completo em memória. Não há limite medido
de RAM, quota ou reserva de disco para o SQLite temporário, medição de desempenho
do arquivo nacional ou limite global de execuções concorrentes. Cada chamada
usa seu próprio banco temporário, normalmente removido ao terminar ou falhar;
interrupção abrupta pode deixar arquivos temporários.

Limite excedido, UTF-8 inválido, cabeçalho inválido ou CSV estruturalmente inválido
interrompem o CLI do leitor com código 2 e erro em stderr, sem resumo parcial
em stdout. A API propaga exceções; consumidores de `ler_csv` devem descartar
resultados parciais se ocorrer uma falha. A futura importação persistente ainda
precisa definir como ativar apenas resultados concluídos.

## Snapshots locais

O comando de snapshots preserva um arquivo regular local, calcula SHA-256 em
blocos de 64 KiB e registra um manifesto JSON. Não baixa arquivos nem interpreta
o CSV. Cada diretório `dados/snapshots/<sha256>/` contém `original.csv` e
`manifesto.json`. BOM, espaços e terminadores não são normalizados e participam
do hash. A extensão `.csv` não comprova conteúdo válido.

| Campo do manifesto do snapshot | Significado |
| --- | --- |
| `versao_manifesto` | Formato do manifesto, atualmente 1 |
| `sha256` e `bytes` | Hash dos bytes de `original.csv` e seu tamanho |
| `coletado_em_utc` | Horário UTC registrado na primeira criação local, antes da cópia |
| `metodo_coleta` | `copia_local` |
| `nome_arquivo_origem` | Nome da primeira origem local, sem caminho absoluto |
| `url_origem` | `null`: não houve coleta HTTP |
| `last_modified_servidor` | `null`: não houve consulta HTTP |

A data local não é a data da observação, da publicação do INPE ou de execução
do processamento. Reutilizar os mesmos bytes preserva o manifesto inicial,
inclusive nome e data; não cria histórico de coletas. Uma futura coleta HTTP
precisará registrar URL e metadados sem confundir Last-Modified com publicação.

### Publicação e integridade

- A criação lê a origem para calcular sua identidade e a lê novamente para
  copiar. Compara metadados antes e depois de cada leitura e hashes entre
  as passagens; mudança detectada cancela a operação.
- Original e manifesto são gravados em pasta temporária no destino, com `fsync`
  nos arquivos, e publicados por renomeação da pasta completa. Isso não equivale
  a uma garantia de durabilidade após queda de energia: não há `fsync` dos diretórios.
- Falhas normais removem a pasta temporária. Interrupção abrupta pode deixar
  `.tmp-*`, que não é snapshot publicado e ocupa espaço da quota.
- Uma trava POSIX em `.snapshot.lock` impede criações cooperantes simultâneas
  na mesma raiz. Outra criação falha sem esperar. Verificação e processamento
  não mantêm essa trava; não há trava global entre raízes ou execuções.
- Mesmos bytes reutilizam a cópia somente após verificar sua integridade;
  bytes diferentes geram outro diretório. Corrupção é recusada, sem reparação
  ou substituição automática.
- A verificação confere formato básico do manifesto, versão, hash, tamanho,
  data com offset UTC e hash recalculado do original. O manifesto é limitado
  a 8 KiB. Não autentica origem, método ou nome do arquivo.
- Original e manifesto são gravados sem bits de escrita. O proprietário pode
  mudar permissões ou substituir arquivos. Não há assinatura digital nem
  proteção absoluta contra alterações por quem controla o armazenamento.

O processamento verifica a entrada e depois a reabre para ler o CSV; não faz
uma nova comparação de hash ao final nem trava contra edição externa durante
a leitura. Mantenha o armazenamento sob controle local. O hash do CSV não
cobre o manifesto do snapshot e não prova procedência científica.

### Espaço e tempo

A quota padrão da raiz é 3 GiB, incluindo arquivos de manifestos, trava e
temporários. Antes de outra cópia, exige espaço para os novos arquivos e
reserva de 5 GiB livres no disco. Isso não reserva espaço contra outros programas.
A reutilização íntegra não exige espaço para uma segunda cópia.
Não há limpeza automática, compressão ou política de retenção.

Cada passagem de hash tem limite cooperativo de 900 segundos e usa o limite
de bytes do perfil escolhido. Arquivo vazio não é aceito. A operação pode ter
mais de uma passagem. Limites de campos, colunas e linhas pertencem ao leitor,
não ao comando de snapshot. A API de criação permite configurar quota e reserva;
o CLI expõe apenas origem, destino e perfil. Links simbólicos de origem, raiz
direta, diretório final e arquivos do snapshot são recusados; isso não é uma
garantia geral contra trocas concorrentes de caminhos ou links em ancestrais.

## Execução e manifesto

`executar_snapshot(diretorio, perfil="fixture")` retorna `ResultadoExecucao`
com hash e tamanho do snapshot, IDs selecionados únicos, resumo, manifesto e
`execucao_sha256`. Não salva o manifesto, exporta focos, cria banco persistente
ou registra uma data de execução. O [exemplo do README](../README.md#reproduzir-o-processamento)
salva um registro JSON com o manifesto e contexto adicional.

O manifesto de execução contém:

- `versao_manifesto_execucao = 1` e `versao_regras = 1`.
- `snapshot`: SHA-256 e tamanho da entrada.
- `perfil` e `limites`: os seis limites efetivos do leitor.
- `politica_identidade`: campo `source_id`, duplicata como erro e intenção
  de distinguir conteúdo (`distingue_conteudo = true`, sujeita às limitações acima).
- `resultado`: IDs selecionados únicos e as cinco contagens do resumo.

`execucao_sha256` é o SHA-256 do manifesto serializado em JSON com
`ensure_ascii=True`, `sort_keys=True`, `separators=(",", ":")`, codificado
em UTF-8. Não é hash do código, dos objetos `Foco` ou dos bytes do JSON
formatado salvo pelo exemplo. A assinatura interna de um foco serve somente
à classificação de repetições; não é publicada no manifesto.

Mesmo snapshot, regras e perfil produzem a mesma identidade nas condições
testadas. Outro perfil altera o manifesto e o hash, mesmo que as contagens
sejam iguais. Mudar um byte do original altera a identidade da entrada, mesmo
que seja só uma linha vazia. Caminho, data da cópia e horário de execução não
fazem parte do hash da execução.

Para reproduzir, preserve `original.csv`, `manifesto.json` do snapshot,
manifesto e hash da execução, perfil, revisão do código e ambiente Python.
O exemplo guarda revisão e versão em `contexto`, fora do manifesto canônico.
Se o código tiver alterações locais, guarde-as também: o commit sozinho não
as descreve. Não existe leitor ou verificador de manifesto de execução salvo;
a comparação é feita ao reexecutar a API com a revisão e o perfil correspondentes.

O manifesto não inclui commit, versão do Python, os valores explícitos de
estado/satélite/período ou hash das regras. A versão das regras é uma constante
manual. Assim, igualdade de `execucao_sha256` não comprova que dois códigos
diferentes executaram o mesmo processamento nem certifica igualdade de todos
os focos interpretados: o resultado registrado é um resumo.

Identidade dos bytes permite conferir a entrada preservada; reprodução exige
entrada, código, parâmetros e ambiente; validade científica exige ainda
metodologia, procedência, qualidade e interpretação adequadas. São verificações
distintas, e nenhuma substitui as demais.

## Procedência e condições de uso

Consulta das referências oficiais em 6 de outubro de 2026, sem baixar o CSV
nacional. A fonte prevista é o [Programa Queimadas do INPE](https://data.inpe.br/queimadas/dados-abertos/),
que disponibiliza CSVs de focos. O
[índice mensal do Brasil](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/)
lista [focos_mensal_br_202508.csv](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/focos_mensal_br_202508.csv),
candidato à integração de agosto de 2025. A existência na listagem não confirma
cabeçalho, unidades, completude, IDs, CRS ou compatibilidade com este parser.
Datas da listagem não são tratadas como datas de publicação original.

A [FAQ do INPE, itens 3, 5 e 36](https://data.inpe.br/queimadas/faq/) confirma
acesso sem custo e orienta citar o INPE e registrar a data de acesso.
Não foi confirmada nesta revisão uma licença específica de redistribuição
do arquivo mensal. Não se atribui uma licença presumida aos dados reais.
O repositório versiona a fixture sintética; condições de uso e atribuição
devem ser verificadas antes de redistribuir dados reais ou publicar derivados.

## Arquivos fora do Git e pendências

O [.gitignore](../.gitignore) exclui `/dados/` inteiro: entradas reais,
snapshots, manifestos e registros salvos pelo exemplo. Também exclui `.venv/`,
`__pycache__/`, arquivos Python compilados, caches de pytest e Ruff e `.env*`
(com exceção de `.env.example`). O SQLite temporário usa a pasta temporária
do sistema, fora dos artefatos versionados; a fixture permanece no Git.

Antes da análise real, falta conferir o contrato e a metodologia com a fonte,
revisar a assinatura decimal, avaliar a estabilidade dos IDs, registrar melhor
a revisão das regras e medir recursos e desempenho. Agregações, persistência
e interface ainda são etapas futuras. O comportamento atual não determina
a edição da malha municipal usada pela fonte nem responde à pergunta científica.
