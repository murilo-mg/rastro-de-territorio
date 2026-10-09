# Contrato de dados e reprodução

Este documento descreve o comportamento de [leitor.py](../src/rastro/leitor.py),
[snapshot.py](../src/rastro/snapshot.py) e [execucao.py](../src/rastro/execucao.py),
com referência nos [testes existentes](../testes). A validação inclui dados
sintéticos e uma [execução registrada com o CSV nacional real de agosto de 2025](VALIDACAO_REAL.md).
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
O projeto calcula agregações por código municipal informado na fonte;
a distribuição territorial ainda não foi validada contra uma malha oficial.

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

`estado`, `pais`, `pais_id` e `bioma` precisam existir como colunas, mas seus
valores não são validados nem preservados em `Foco`. Não há conferência do país.
Os IDs `sintetico-*` da fixture são fictícios; não há validação de UUID ou
comprovação da estabilidade do identificador fornecido pela fonte.

Desde a versão 3 das regras, `municipio_id` e `municipio` são preservados em
`Foco`. O código é texto com sete dígitos ASCII e prefixo igual ao `estado_id`.
Essa checagem usa a [estrutura documentada pelo IBGE](https://www.ibge.gov.br/explica/codigos-dos-municipios.php),
consultada em 09/10/2026 (UTC): sete dígitos, com os dois primeiros indicando a UF.
Não é uma consulta à lista oficial nem validação de malha ou ponto em polígono.
Código vazio vira `None`; código malformado ou com prefixo de outra UF vira
`None` e gera um problema `municipio_id`, sem descartar a detecção. O nome é
aparado e preservado com maiúsculas, acentos e grafia originais; vazio vira `None`.
O nome não é usado para inferir um código ausente. Os valores brutos originais
continuam preservados no snapshot, inclusive códigos que não foram aceitos.
Nas regras 4, a execução acrescenta uma comparação cadastral separada contra
a DTB 2025 preservada. Essa comparação não altera a classificação do leitor,
os códigos aceitos ou os nomes originais e não testa pontos em polígonos.

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
ID, latitude, longitude, data UTC, satélite, estado, quatro opcionais
meteorológicos/FRP, código municipal e nome municipal.
Campos descartados, como bioma, e a lista de problemas opcionais
não participam. Portanto, textos distintos podem produzir a mesma assinatura,
inclusive um opcional inválido e um ausente, pois ambos viram `None`.

Desde a versão 2 das regras, a assinatura decimal usa sinal, dígitos e expoente
obtidos por `Decimal.as_tuple()`, sem operações de arredondamento do contexto.
Retira apenas zeros finais do coeficiente e ajusta o expoente com inteiros.
Assim, `1`, `1.00` e `10e-1` são equivalentes; valores que diferem além de
28 casas significativas permanecem diferentes. Todos os zeros, inclusive
`-0`, têm a mesma representação numérica; `None` continua distinto de zero.

O coeficiente e o expoente ficam compactos: um valor finito como `1e1000000`
não é expandido em um milhão de caracteres nem causa `decimal.Overflow`
na assinatura. A classificação é independente da precisão, dos limites de
expoente e das armadilhas de arredondamento do contexto decimal. Isso não
valida a plausibilidade científica de valores extremos; as regras do leitor
e a necessidade de conferir unidades e faixas com a fonte permanecem.

A correção substitui o uso anterior de `Decimal.normalize()`, que podia
arredondar valores diferentes ou falhar com expoentes extremos. A versão das
regras passou de 1 para 2, alterando a identidade da execução mesmo quando
as contagens são iguais. Registros antigos devem ser reproduzidos com a
revisão original, sem reescrever seu hash ou sua versão.

Na versão 3, código e nome municipal interpretados também participam da
assinatura. O mesmo ID associado a outro código ou outro nome é conflito.
Um código inválido e um ausente podem continuar equivalentes após ambos
virarem `None`, caso os demais campos interpretados sejam iguais.

## Agregações

Somente observações selecionadas e aprovadas no controle de identidade entram
nas agregações. Cada observação incrementa o dia UTC e o par código/nome
municipal em SQLite temporário, usando o mesmo banco da execução. A lista
de focos não é mantida em memória; as tabelas finais são materializadas no resultado.

- `por_dia_utc` tem todos os dias do recorte em ordem, inclusive contagens zero.
  A conversão para UTC ocorre antes de extrair o dia; não é o calendário de Manaus.
- `por_municipio` agrupa por código, não pelo nome. Códigos distintos com o
  mesmo nome continuam separados. Os códigos são ordenados; o grupo `null`,
  quando existe, vem por último e reúne observações sem código utilizável.
- Cada grupo municipal expõe todos os `nomes` distintos ordenados, `deteccoes`,
  `sem_nome` e `nomes_divergentes`. Dois nomes não vazios para o mesmo código
  sinalizam divergência, sem escolher silenciosamente um nome preferido.
  O grupo `null` não representa um único município e não sinaliza divergência.
- `ausencias` conta valores `None` em seis campos selecionados, incluindo
  município e código. `problemas_por_campo` conta inválidos; ausentes e
  sentinelas reconhecidas não são problemas. Um inválido convertido em `None`
  participa das duas contagens, que não devem ser somadas como categorias exclusivas.

Cada uma das tabelas precisa somar exatamente `ids_selecionados_unicos`.
Recorte vazio gera 31 dias com zero e lista municipal vazia. Uma repetição de
ID ou falha de leitura impede a conclusão; o CLI não publica tabelas parciais.
Zero detecções em um dia não comprova ausência de fogo ou cobertura completa.

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
temporário, sem manter um conjunto completo em memória. Grupos por dia,
código e nome também são acumulados no SQLite. O resultado final depende
do número de grupos e nomes distintos. Não há limite medido
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
com hash e tamanho do snapshot, IDs selecionados únicos, resumo, agregações,
manifesto e `execucao_sha256`. Essa API não grava arquivos nem cria banco
persistente. `exportar_resultado` publica o resultado; o
[CLI do README](../README.md#executar-o-exemplo-sintético) combina as duas APIs.

O manifesto de execução contém:

- `versao_manifesto_execucao = 3` e `versao_regras = 4`.
- `snapshot`: SHA-256 e tamanho da entrada.
- `recorte`: estado, satélite, início inclusivo, fim exclusivo e fuso UTC da agregação.
- `perfil` e `limites`: os seis limites efetivos do leitor.
- `politica_identidade`: campo `source_id`, duplicata como erro e intenção
  de distinguir conteúdo (`distingue_conteudo = true`, sujeita às limitações acima).
- `referencia_municipal`: origem IBGE, edição 2025, data-base 31/12/2025,
  data de acesso, arquivos/hashes e regra explícita de normalização de nomes.
- `resultado`: IDs selecionados únicos, cinco contagens do resumo e as
  agregações versão 2, incluindo matriz município × dia, ausências,
  problemas por campo e conferência municipal versão 1.

`execucao_sha256` é o SHA-256 do manifesto serializado em JSON com
`ensure_ascii=True`, `sort_keys=True`, `separators=(",", ":")`, codificado
em UTF-8. Não é hash do código, dos objetos `Foco` ou dos bytes do JSON
formatado exportado. A assinatura interna de um foco serve somente
à classificação de repetições; não é publicada no manifesto.

Mesmo snapshot, regras e perfil produzem a mesma identidade nas condições
testadas. Outro perfil altera o manifesto e o hash, mesmo que as contagens
sejam iguais. Mudar um byte do original altera a identidade da entrada, mesmo
que seja só uma linha vazia. Caminho, data da cópia e horário de execução não
fazem parte do hash da execução.

Para reproduzir, preserve `original.csv`, `manifesto.json` do snapshot,
manifesto e hash da execução, perfil, revisão do código e ambiente Python.
O CLI guarda revisão Git, presença de alterações locais, versão do Python,
sistema, data UTC e hash dos arquivos Python do pacote em `contexto.json`.
Esse contexto pertence à primeira exportação e fica fora do manifesto canônico.
Se o código tiver alterações locais, guarde-as também: o commit sozinho não
as descreve. O hash de código percorre os `*.py` do pacote em ordem de nome,
concatenando nome UTF-8, byte nulo, tamanho em oito bytes big-endian e conteúdo.
Ele não cobre documentação, testes, dependências do sistema ou o ambiente inteiro.

O manifesto inclui o recorte explícito, mas não commit, versão do Python ou
hash do código. A versão das regras é uma constante manual. Assim, igualdade
de `execucao_sha256` não comprova que dois códigos diferentes executaram o
mesmo processamento nem certifica igualdade de todos os focos interpretados.
A comparação após reexecução confere os cinco artefatos determinísticos
das regras 4 (três nas regras 3).
Também existe leitura independente por `verificar_resultado(diretorio)`:
ela valida os arquivos exportados sem reler ou reexecutar o snapshot.

Identidade dos bytes permite conferir a entrada preservada; reprodução exige
entrada, código, parâmetros e ambiente; validade científica exige ainda
metodologia, procedência, qualidade e interpretação adequadas. São verificações
distintas, e nenhuma substitui as demais.

## CLI e exportação

`PYTHONPATH=src python3 -m rastro` recebe `--csv` ou `--snapshot`,
`--perfil fixture|mensal` e `--saida`. No modo CSV, `--snapshots` define a
raiz de cópias. O padrão de saída é `dados/resultados/<execucao_sha256>/`.
Os erros de argumentos, leitura, identidade ou publicação terminam com código
2 e mensagem em stderr; stdout só recebe o resumo após a conclusão.

O diretório das regras 4 contém `manifesto.json` (manifesto e hash),
`por_dia.csv`, `por_municipio.csv`, `por_municipio_dia.csv`,
`conferencia_municipal.csv` e `contexto.json`. CSVs são UTF-8 com LF,
vírgula e cabeçalho. `nomes_json` é uma lista JSON dentro da célula CSV,
preservando aspas, vírgulas, acentos e todos os nomes distintos do grupo.
O código ausente é vazio no CSV e `null` no JSON. Os CSVs contêm agregações,
não a lista das observações selecionadas.
O CSV diário municipal tem exatamente uma linha por grupo observado e dia,
incluindo zeros. O CSV de conferência contém código, nome cadastral, situação
do código e quatro listas JSON de nomes: iguais, equivalentes após normalização,
divergentes ou sem referência. As duas conferências de divergência de nomes
(entre variantes da fonte e contra o IBGE) permanecem distintas.

A publicação usa trava POSIX não bloqueante na raiz de saída, grava os seis
arquivos em pasta temporária, executa `fsync` nos arquivos e renomeia a pasta
completa. Falhas normais removem o temporário; interrupção abrupta pode deixar
`.tmp-*`. Não há `fsync` dos diretórios, quota da exportação ou garantia de
durabilidade após queda de energia. A trava coordena publicações na mesma raiz,
não limita execuções simultâneas nem gravações externas não cooperantes.

Ao encontrar o mesmo resultado, a exportação compara manifesto e CSVs byte
a byte e exige exatamente os arquivos esperados da versão. Uma divergência ou pasta
incompleta é recusada, sem substituir arquivos. O contexto inicial é preservado
e conferido apenas quanto ao formato básico; não é autenticado nem incluído
no hash da execução. Links simbólicos no destino direto e nos arquivos
existentes são recusados, sem promessa de proteção contra troca de ancestrais.

As versões anteriores dos manifestos continuam sendo registros históricos.
Preserve-as e use a revisão correspondente para reproduzi-las. O snapshot
não muda de formato; os novos resultados ficam em outro hash de execução.

## Verificação independente e caderno local

`rastro.resultado.verificar_resultado()` aceita duas combinações: manifesto
2/regras 3/agregações 1 com quatro arquivos, e manifesto 3/regras 4/agregações
2 com seis arquivos. A pasta pode ter outro nome: a identidade é lida do
manifesto. O recorte e os perfis precisam corresponder aos implementados.
Outras versões, incluindo manifesto 1, são recusadas. A leitura histórica
não modifica resultados nem cria matriz ou conferência retroativamente.

O verificador confere estrutura, tipos, limites das contagens, SHA-256
canônico, igualdade entre IDs e selecionadas, partição das linhas lidas,
31 datas ordenadas, somas diárias e municipais, códigos únicos e ordenados,
nomes, ausências e problemas por campo. Nas regras 4, confere também códigos
e dimensão da matriz, somas de linhas/colunas e identidade da referência;
recalcula a conferência cadastral a partir dos nomes preservados. Reconstitui
todos os artefatos determinísticos da versão e exige igualdade byte a byte. Até uma mudança de formatação
nos JSON/CSVs determinísticos é recusada. O contexto recebe validação de
estrutura e tipos, mas continua fora do hash e sem autenticação.

Cada artefato determinístico tem limite de 16 MiB para importação; o contexto,
8 KiB. São recusados arquivos não regulares, links simbólicos nos arquivos
e no diretório final, chaves JSON repetidas e constantes como `NaN` e
`Infinity`. A leitura usa descritores com `O_NOFOLLOW`, `O_NONBLOCK` e `fstat`
em Linux. Isso não protege contra troca de diretórios ancestrais ou escrita
externa concorrente. Os arquivos importados não são modificados.

Uma adulteração coerente de manifesto, hash e CSVs pode passar: a conferência
é de consistência interna, não de autenticidade. Reproduzir continua exigindo
snapshot, código, parâmetros e ambiente. O verificador tampouco permite
validar a associação de cada observação ao município sem reprocessar a entrada.

`rastro.caderno.gerar_caderno()` verifica a exportação e gera um HTML completo
fora da pasta original. A apresentação não altera o manifesto, o hash da
execução ou as versões das regras. O formato visual tem versão própria,
atualmente 2, salvo por padrão em `dados/cadernos/v2/`. Mesmos arquivos
exportados e gerador produzem os mesmos bytes;
mudanças de contexto alteram o HTML mesmo sem alterar o hash da execução.

A saída usa arquivo temporário no destino, `fsync` do arquivo e criação de
hard link com `os.link`, sem sobrescrever um destino criado por outro processo.
O temporário é removido em falhas ordinárias. Uma publicação concorrente pode
falhar com código 2; execute novamente para conferir/reutilizar. Arquivos
existentes idênticos são reutilizados; divergentes exigem outro caminho.
O sistema de arquivos precisa suportar hard links. Não há `fsync` do diretório,
quota de HTML ou garantia após queda de energia. Interrupções abruptas podem
deixar `.rastro-caderno-*`.

O HTML carrega todos os grupos em memória, com limite de 10.000 grupos,
e contém a tabela completa também sem JavaScript. Há busca por código/nome
e ordenação, série diária com origem em zero e tabela de valores exatos.
O gráfico geral e os indicadores gerais não mudam com a busca municipal.
Nas regras 4, controles próprios selecionam até três grupos para um segundo
gráfico baseado na matriz município × dia, com eixo comum começando em zero.
O resumo mostra total, participação no recorte, dias com detecções, máximo
diário e todas as datas UTC empatadas no máximo. A matriz completa permanece
consultável sem JavaScript. Resultados históricos mostram a indisponibilidade
desse cruzamento explicitamente.
Percentuais são participações nas detecções selecionadas; não são taxas por
área ou população. Nomes não são convertidos em geometrias. A conferência
cadastral separa igualdade literal de equivalência normalizada, sem corrigir
a fonte. O grupo sem código não representa um único município.

Nomes são escapados no HTML e no JSON embutido; a interação escreve texto
com `textContent`. Uma CSP permite apenas o script e estilo gerados por hash
e bloqueia conexões da página. O caderno não usa dependências externas,
armazenamento de navegação ou servidor. Isso não autentica um HTML alterado
depois de gerado. A fixture conhecida é reconhecida pelo hash; outras entradas
sintéticas não são detectadas automaticamente. Detalhes em [CADERNO.md](CADERNO.md).

## Referência municipal preservada

`referencias/ibge/dtb2025/` versiona o ODS municipal original (206.091 bytes),
o CSV com 62 municípios do Amazonas e o manifesto. O hash do manifesto é
fixado em `territorio.py`; hashes de ODS e CSV são conferidos antes de usar
a referência. Não há consulta HTTP durante a execução. A receita reproduz
o CSV diretamente do ODS, sem bibliotecas externas de planilhas.

A referência é IBGE DTB 2025, data-base 31/12/2025, posterior ao recorte de
agosto de 2025. A comparação não identifica a edição territorial usada pelo
INPE nem valida coordenadas contra limites espaciais. Código desconhecido
permanece selecionado, com diagnóstico; nomes não inferem códigos.

Nomes iguais são separados dos equivalentes após NFKD, retirada de marcas
combinantes, `casefold` e consolidação de espaços. Pontuação não é retirada.
Nomes originais, variantes e ausências permanecem visíveis. Origem, hashes,
reprodução e limites estão em [REFERENCIA_MUNICIPAL.md](REFERENCIA_MUNICIPAL.md).

## Procedência e condições de uso

As referências oficiais foram consultadas inicialmente em 6 de outubro de 2026.
Em 9 de outubro de 2026 (UTC), o CSV nacional de agosto de 2025 foi baixado e
processado na revisão `7b024e1e77dee230236b9cd8330ef7b12b1ebf83`, com reprodução
local de hashes e contagens. O registro está em [VALIDACAO_REAL.md](VALIDACAO_REAL.md).
A fonte é o [Programa Queimadas do INPE](https://data.inpe.br/queimadas/dados-abertos/),
que disponibiliza CSVs de focos. O
[índice mensal do Brasil](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/)
lista [focos_mensal_br_202508.csv](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/focos_mensal_br_202508.csv),
usado na validação de agosto de 2025. Para os bytes registrados, o cabeçalho
é compatível e a execução terminou sem rejeições ou IDs selecionados repetidos.
Isso não confirma unidades, completude da cobertura, estabilidade dos IDs,
CRS ou plausibilidade científica de todos os campos.
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

O arquivo real já foi processado com o recorte e os limites documentados.
As agregações por dia e código municipal, exportação, verificação independente,
matriz município × dia, conferência cadastral e interface HTML local estão implementadas.
Para avançar na análise, falta aprofundar a conferência de metodologia e unidades
com a fonte, avaliar a estabilidade dos IDs e medir recursos e desempenho de
forma sistemática. Persistência em banco, outros períodos, mapa e
interface web hospedada ainda são etapas futuras.
O comportamento atual não determina a edição da malha municipal usada pela fonte.
