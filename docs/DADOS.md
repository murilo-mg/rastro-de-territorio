# Contrato inicial de dados

Este documento descreve o comportamento implementado no leitor local.
Os testes usam dados sintéticos. A validação com o arquivo real ainda é uma
etapa futura. Há um comando separado de snapshots para preservar os bytes locais.

## Pergunta e recorte

Como as detecções do satélite de referência se distribuíram pelo Amazonas
em agosto de 2025, e quais limitações devemos considerar ao interpretar esses números?

| Critério | Regra do projeto |
| --- | --- |
| Estado | `estado_id` inteiro igual a `13` |
| Satélite | Igualdade exata com `AQUA_M-T` após aparar espaços |
| Início | `2025-08-01T00:00:00Z`, inclusive |
| Fim | `2025-09-01T00:00:00Z`, exclusive |
| Tempo | UTC; horário local do computador não altera o recorte |
| Latitude | Decimal finito de -90 a 90 |
| Longitude | Decimal finito de -180 a 180 |

`AQUA_M-M` e outros satélites ficam fora do recorte. O nome textual do estado
não substitui o código. O recorte por código não equivale a um teste de ponto
dentro de um polígono. A precisão decimal não informa a precisão do sensor.
Não há transformação de CRS nesta etapa.

Contagens representam registros de detecções. Não representam número de incêndios
distintos, hectares queimados, causas, infrações ou previsão de risco.
Uma contagem zero não comprova ausência de fogo.

## Formato aceito

Arquivo local regular, CSV com vírgula, UTF-8, BOM inicial opcional,
terminação de linha LF ou CRLF e um registro por linha física.
Aspas e vírgulas dentro de campos são aceitas quando o CSV é válido.
Campos com quebras de linha internas não são suportados.

O cabeçalho precisa conter estes 16 nomes, sem repetição:

```text
id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp
```

Ordem diferente e espaços nas extremidades dos nomes são aceitos. Colunas
adicionais são permitidas dentro do limite; ainda não são persistidas.
Linhas com quantidade diferente de campos são rejeitadas, salvo quando
ultrapassam um limite, caso em que a leitura inteira é interrompida.

`data_hora_gmt` precisa conter data e hora, com segundos. São aceitos separador
espaço ou `T`, fração de segundo opcional e offset ISO opcional. Sem offset,
o leitor interpreta UTC conforme o nome GMT da coluna. Com offset, converte
para UTC. Data sem hora, data inválida ou conversão fora do calendário é rejeitada.

## Valores ausentes e problemas

| Campo | Tratamento |
| --- | --- |
| Dias sem chuva | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser inteiros não negativos de até 2.147.483.647 |
| Precipitação | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser finitos e não negativos |
| Risco de fogo | Vazio ou valor numérico -999 vira `None`; demais valores precisam ser finitos entre zero e um |
| FRP | Vazio vira `None`; demais valores precisam ser finitos e não negativos |

Variantes `-999.0` e `-999.00` também são reconhecidas. Zero permanece zero.
Opcional inválido vira `None` e gera um problema associado ao campo, preservando
a observação quando os essenciais são válidos. O limite inteiro é uma proteção
técnica de representação, não uma afirmação sobre duração plausível sem chuva.
As faixas meteorológicas são regras iniciais a conferir com a fonte real.

Identificador e satélite precisam ser não vazios. Estado, data e coordenadas
inválidos rejeitam a linha. Os IDs `sintetico-*` são deliberadamente fictícios;
não validamos UUID, estabilidade de IDs ou duplicatas nesta etapa.

## Limites implementados

MiB significa 1.048.576 bytes. KiB significa 1.024 bytes.

| Limite | Perfil `fixture` (padrão) | Perfil `mensal` |
| --- | --- | --- |
| Bytes do arquivo inteiro | 5 MiB | 512 MiB |
| Linhas físicas após o cabeçalho | 20.000 | 5.000.000 |
| Bytes por linha física | 64 KiB | 64 KiB |
| Bytes por campo decodificado em UTF-8 | 4 KiB | 4 KiB |
| Colunas | 32 | 32 |
| Tempo de leitura | 900 segundos | 900 segundos |

Tamanho exato no limite é aceito; acima dele, a leitura é interrompida.
O limite de bytes é conferido no arquivo aberto e nos bytes efetivamente lidos.
Os limites de linha e de campo incluem o cabeçalho. Bytes de linha incluem
aspas, separadores e terminadores. O limite de campo conta o valor extraído
do CSV antes de aparar espaços. Linhas vazias depois do cabeçalho consomem
o limite físico, mas não entram nas contagens de observações.

O tempo usa relógio monotônico e é conferido entre leituras e após cada leitura.
É um limite cooperativo, não um processo externo que encerra I/O bloqueado.
Também inclui o tempo que um consumidor do iterador passa entre chamadas.

O algoritmo usa uma linha limitada por vez. Não há promessa de limite medido
de RAM do processo inteiro nem teste de desempenho do arquivo nacional nesta etapa.
Limite excedido, UTF-8 inválido, cabeçalho inválido ou CSV estruturalmente inválido
interrompem o comando com código 2 e mensagem de erro, sem resumo parcial em stdout.
Um consumidor do iterador deve tratar a exceção e descartar resultados parciais;
a futura importação no banco precisará de uma etapa temporária antes da ativação.

## Contagens

As categorias são exclusivas:

```text
lidas = selecionadas + fora_do_recorte + rejeitadas
```

Primeiro são validados os campos essenciais. Uma linha com essencial inválido
é rejeitada, mesmo que também pudesse estar fora do recorte. Uma linha válida
que não corresponde a estado, satélite ou período fica fora do recorte.
Campos opcionais só são avaliados nas linhas selecionadas.
`problemas_opcionais` conta campos inválidos, não registros inválidos.
Valores vazios e sentinelas reconhecidas não aumentam esse contador.

## Origem e reprodução

Fonte planejada: [dados abertos do Programa Queimadas do INPE](https://data.inpe.br/queimadas/dados-abertos/).
Arquivo mensal escolhido para a integração posterior:
[Brasil, agosto de 2025](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/focos_mensal_br_202508.csv).
Referência metodológica: [FAQ do Programa Queimadas](https://terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_informacoes/faq/index.html).

A documentação histórica pode usar nomes diferentes dos arquivos atuais.
O cabeçalho efetivo e a metodologia precisam ser conferidos na integração.
Nenhum arquivo real foi baixado ou validado nesta etapa do código.
Dados locais permanecem em `dados/`, ignorado pelo Git.
Disponibilidade gratuita não é confirmação automática de licença de redistribuição.
O projeto mantém fixture sintética versionada até esclarecer essas condições.

## Snapshots locais

O comando `python -m rastro.snapshot criar` preserva uma cópia exata de um arquivo
regular local, calcula SHA-256 em blocos de 64 KiB e registra um manifesto JSON.
Não faz download e não interpreta os registros do CSV.

Cada snapshot publicado tem o diretório `dados/snapshots/<sha256>/`, contendo
`original.csv` e `manifesto.json`. Os bytes originais não são normalizados:
BOM, espaços e terminadores de linha participam do hash.

O manifesto registra versão, hash, tamanho, data UTC da criação da cópia,
método de coleta local e nome do arquivo original sem caminho absoluto.
`url_origem` e `last_modified_servidor` ficam nulos porque não houve coleta HTTP.
A data da criação não é a data da observação nem a data de publicação do INPE.
A futura coleta HTTP deverá registrar URL e Last-Modified sem confundir a última
modificação do recurso com sua publicação original.

### Publicação, identidade e integridade

- O original é lido para determinar sua identidade e lido novamente para a cópia.
  Metadados de arquivo antes e depois de cada leitura e hashes entre as duas
  leituras são comparados. Mudança detectada cancela o snapshot.
- A cópia e o manifesto são escritos em pasta temporária dentro do mesmo destino,
  sincronizados com `fsync` e publicados por renomeação da pasta completa.
  Não há pasta final com somente metade dos arquivos.
- Falhas normais removem a pasta temporária. Interrupção abrupta do processo pode
  deixar pasta `.tmp-*`; ela não é um snapshot publicado e ocupa espaço da quota.
- Uma trava POSIX impede duas criações cooperantes de escrever simultaneamente.
  Outra criação concorrente falha com mensagem clara, sem esperar indefinidamente.
- Mesmos bytes reutilizam o snapshot existente somente depois de conferir hash,
  tamanho e manifesto. A data da primeira cópia é preservada; uma nova coleta
  ainda não gera histórico separado de execuções nesta etapa.
- Bytes diferentes geram outro diretório. Nenhuma revisão existente é sobrescrita.
- `verificar` recalcula o hash do original e compara com o nome do diretório e o
  manifesto. Corrupção é recusada; o comando não repara ou substitui a cópia.
- Original e manifesto são gravados sem bits de escrita. Isso evita alterações
  acidentais, mas não impede o proprietário do computador de mudar permissões
  ou substituir arquivos. Não há assinatura digital nem garantia contra um
  atacante que controle o armazenamento. Hash não prova a origem científica.

### Espaço e limites

A quota padrão da pasta é 3 GiB, incluindo manifestos e temporários. Antes de
gravar outra cópia, o comando exige espaço para os novos bytes e uma reserva
de 5 GiB livres no disco. Essa verificação não reserva espaço contra outros
programas; uma falha de escrita cancela a operação normal sem publicar a pasta.
A reutilização de um snapshot íntegro não exige espaço para outra cópia.
Não há limpeza automática, compressão ou política de retenção implementada.

Tamanho máximo e tempo por passagem de leitura usam o perfil `fixture` ou
`mensal`. Cada passagem do hash tem limite cooperativo de 900 segundos;
a operação completa pode fazer mais de uma passagem. Arquivo vazio não é aceito.
Os limites de colunas e de linhas pertencem ao leitor CSV, não ao comando de
snapshot. Links simbólicos de origem, destino direto e arquivos de snapshots
são recusados. A pasta de dados deve ser controlada pelo usuário local.

## Próximo passo

Definir tratamento de IDs repetidos por execução, integrar snapshot e leitura
e validar o parser com o arquivo real. Hash garante identidade dos bytes; não certifica
a correção científica dos dados. O cabeçalho atual, as coordenadas e os códigos
também não comprovam a edição da malha municipal usada pela fonte.
