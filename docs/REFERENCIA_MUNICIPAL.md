# Referência cadastral e comparação municipal

A etapa municipal usa a **Divisão Territorial Brasileira do IBGE, edição
2025, data-base 31/12/2025**. Os bytes foram obtidos em 09/10/2026 (UTC), do
[servidor oficial](https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/).
A data-base foi lida na própria tabela; a data da listagem do servidor não é
tratada como data de publicação original.

## Referência preservada

O diretório [referencias/ibge/dtb2025](../referencias/ibge/dtb2025/) contém o
ODS municipal original, sem alterações, o CSV de 62 códigos e nomes do
Amazonas e o manifesto de origem. O hash do manifesto está fixado no código;
ele contém os hashes esperados do ODS e do CSV. Todas as verificações e os
testes funcionam offline.

| Bytes | SHA-256 |
| --- | --- |
| ZIP baixado | `d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27` |
| ODS original | `a0606b9706c248138131511287e582a9293ba786096e0395192be36108d029fa` |
| CSV municipal AM | `2de2aaa24b40c84d83d957a69c4fa1ef5526df3016de3b5ecf8ec7915afeff6d` |
| Manifesto da referência | `3ce4bd162a2bde157d5f8be51992ff0b4bed28098d7c10d0b5c8223e5eef1b68` |

A receita de extração está no [README da referência](../referencias/ibge/dtb2025/README.md#extração-reproduzível).
O script extrai UF 13, coluna `Código Município Completo` e coluna
`Nome_Município`, preserva os nomes e ordena por código. A reprodução foi
comparada byte a byte com o CSV versionado.

## Regras de comparação

O código é comparado diretamente ao cadastro. Não há busca aproximada nem
inferência de código a partir do nome. Um código válido no formato, mas ausente
da referência, continua na contagem e recebe `nao_encontrado`. O grupo sem
código recebe `ausente` e não representa um único município.

Para cada nome distinto associado ao código encontrado:

| Classe | Regra |
| --- | --- |
| `nomes_iguais` | Igualdade literal com o nome no CSV cadastral |
| `nomes_equivalentes` | Igualdade somente depois da normalização documentada |
| `nomes_divergentes` | Nome diferente mesmo após normalização |
| `nomes_sem_referencia` | Não há código reconhecido que permita comparar o nome |

A normalização identificada por `NFKD-sem-marcas-casefold-espacos:v1`
aplica decomposição Unicode NFKD, retira marcas combinantes, usa `casefold`
e consolida espaços. Ela não remove pontuação, não usa similaridade e não
aplica apelidos. Por exemplo, `APUI` e `Apuí` são equivalentes após
normalização, mas não são iguais literalmente. Os nomes originais continuam
nas agregações e no caderno.

Ausência de nome não vira correspondência nem divergência: continua no
diagnóstico `sem_nome`. Múltiplos nomes da fonte para um código permanecem
visíveis mesmo quando todos são equivalentes ao nome oficial. O diagnóstico
de nomes divergentes entre si, já existente nas agregações, é diferente da
comparação com o cadastro.

## Matriz município × dia

As agregações versão 2 incluem `por_municipio_dia_utc`: uma linha por código
observado, na mesma ordem de `por_municipio`, com vetor de 31 inteiros.
As posições correspondem exatamente às datas de `por_dia_utc`; zeros são
incluídos. Um grupo sem código, se existir, fica por último e também recebe
uma série diária. Códigos da referência sem observações não são acrescentados
à matriz nem rotulados como ausência de fogo.

Cada vetor soma o total do respectivo grupo. Cada coluna soma o total do
respectivo dia. Ambas as margens somam as detecções selecionadas. A matriz
vem de agrupamento do SQLite por código e dia; não é inferida dos totais
marginais. O verificador confere dimensão, ordem, tipos, limites e somas.

## Versões e reprodução

Novas execuções usam manifesto 3, regras 4, agregações 2 e conferência
municipal 1. O manifesto inclui a identificação completa da referência e a
conferência. Isso altera o hash da execução, mesmo com os mesmos bytes e
contagens do CSV original. O snapshot continua com o mesmo hash.

As regras 4 publicam seis arquivos: os quatro anteriores e
`por_municipio_dia.csv` e `conferencia_municipal.csv`. O primeiro tem uma
linha por grupo e dia, inclusive zeros; o segundo preserva as listas de nomes
de cada classe em células JSON. A exportação e a importação conferem todos
os arquivos da versão.

Resultados históricos com manifesto 2, regras 3 e agregações 1 continuam
verificáveis e exploráveis. Eles mantêm quatro arquivos e seus hashes
originais. O caderno explica que não possuem matriz nem conferência cadastral;
não os amplia ou modifica automaticamente. Para obter novos resultados,
reexecute o snapshot. O formato de manifesto 1 continua fora do importador.

## Validação com o CSV real

Os bytes originais do INPE mantiveram o hash
`9420a1babbf627ef80d9b39ba1d8e2b656f88e98e11c622952094704be7106c3`.
O novo hash de execução é
`62cd809c8b059aa98decc8640c8a7507a05d204f82529dc6f660a25e8f87ca92`.

| Resultado | Contagem |
| --- | ---: |
| Linhas lidas | 594.309 |
| Detecções selecionadas | 1.842 |
| Códigos municipais observados | 50 |
| Códigos encontrados na DTB 2025 | 50 |
| Códigos não encontrados | 0 |
| Grupos com nomes divergentes da referência após normalização | 0 |
| Células da matriz, incluindo zeros | 1.550 |

Uma contagem independente com `csv.DictReader` e datas UTC percorreu o
original e coincidiu com todas as 1.550 células da matriz. Apuí teve 416
detecções, com máximo diário de 88 em 26/08/2025 UTC. Humaitá teve 210,
com máximo de 32 em 16/08/2025 UTC. Esses resultados foram produzidos pela
implementação e conferidos contra a contagem independente.

## Limites de interpretação

A referência cadastral tem data-base posterior ao recorte. A correspondência
não identifica a edição usada pelo INPE em agosto nem certifica que um ponto
esteja dentro dos limites do município informado. Não foram usadas geometrias
ou teste espacial. Detecções não equivalem a incêndios distintos ou área
queimada; os percentuais do caderno são participações no total selecionado,
sem denominadores de área, população ou exposição.
