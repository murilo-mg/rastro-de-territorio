# Rastro de Território

Caderno de dados ambientais do Amazonas, desenvolvido por Murilo da Mota
Gonçalves, estudante de Ciência da Computação na UFAM. O projeto torna os
resultados exploráveis e registra a origem e as limitações de cada execução.
A etapa atual roda no terminal, localmente, com orçamento zero.

## Pergunta inicial

> Como as detecções do satélite de referência se distribuíram pelo Amazonas em
> agosto de 2025, e quais limitações devemos considerar ao interpretar esses números?

O recorte seleciona estado `13`, satélite exatamente `AQUA_M-T` e datas UTC
de `2025-08-01T00:00:00Z` inclusive até `2025-09-01T00:00:00Z` exclusive.
Detecções não equivalem a incêndios distintos nem a área queimada.

A execução real selecionou **1.842 detecções**, distribuídas em **50 códigos
municipais informados na fonte**, e gerou uma série com os **31 dias UTC**
do mês. O [registro de validação](docs/VALIDACAO_REAL.md) identifica os bytes,
as regras e os limites dessa conclusão.

## Estado atual

- Leitor CSV com limites, validação, recorte e preservação de código e nome municipal.
- Snapshots locais por SHA-256, com verificação de integridade antes da execução.
- Controle de IDs selecionados em SQLite temporário; repetições interrompem a execução.
- Agregações por dia UTC e código municipal, com grupos sem código, nomes
  divergentes e valores ausentes explícitos.
- Manifesto determinístico que inclui recorte, regras, contagens e tabelas.
- CLI que preserva ou reutiliza o snapshot e publica JSON e CSVs completos.
- Testes offline com dados sintéticos e execução registrada com o arquivo real.

A interface interativa, mapa, API web, banco persistente, coletor HTTP e
hospedagem ainda estão planejados. O SQLite é temporário e serve ao controle
de IDs e à acumulação das agregações. Não há dependência de pandas ou de banco externo.

## Requisitos

Python 3.12 e Linux. Todas as dependências Python são da biblioteca padrão,
incluindo `sqlite3` e `fcntl`. As travas POSIX não têm adaptação para Windows.
`PYTHONPATH=src` permite executar o pacote sem instalá-lo. Git é usado quando
disponível para registrar a revisão; a ausência dele não impede a execução.

```bash
git clone https://github.com/murilo-mg/rastro-de-territorio.git
cd rastro-de-territorio
python3 --version
```

## Executar o exemplo sintético

Na raiz do repositório:

```bash
PYTHONPATH=src python3 -m rastro --csv testes/fixtures/focos_sinteticos.csv
```

O comando cria ou verifica o snapshot, processa o CSV e exporta o resultado.
A fixture tem cinco observações inventadas e não descreve eventos reais.
Com as regras atuais, o resumo é:

```text
snapshot_sha256: 82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f
execucao_sha256: 83d3373305d1877832a0309034342df9d6da6f41b8048e542330bd587c52e8bd
ids_selecionados_unicos: 2
lidas: 5
selecionadas: 2
fora_do_recorte: 3
rejeitadas: 0
problemas_opcionais: 0
dias_utc: 31
municipios_com_codigo: 1
sem_municipio_id: 0
municipios_com_nomes_divergentes: 0
```

Na primeira execução aparece `exportacao: criada`; outra execução do mesmo
resultado informa `reutilizada`, após comparar os artefatos determinísticos.
A saída também informa o diretório publicado.

O perfil `fixture` aceita até 5 MiB; `mensal`, até 512 MiB. Ambos têm limites
de linhas, campos e tempo descritos no [contrato](docs/DADOS.md#limites-implementados).
Criar uma nova cópia exige 5 GiB livres de reserva e respeita a quota padrão
de 3 GiB da raiz de snapshots, inclusive com uma fixture pequena.

## Executar o CSV real

O arquivo nacional é obtido manualmente conforme os
[comandos de download](docs/VALIDACAO_REAL.md#reprodução). Depois de baixá-lo:

```bash
PYTHONPATH=src python3 -m rastro \
  --csv dados/originais/focos_mensal_br_202508.csv \
  --perfil mensal
```

Para usar o snapshot já preservado na primeira validação:

```bash
PYTHONPATH=src python3 -m rastro \
  --snapshot dados/snapshots/9420a1babbf627ef80d9b39ba1d8e2b656f88e98e11c622952094704be7106c3 \
  --perfil mensal
```

`--csv` e `--snapshot` são alternativas. `--snapshots CAMINHO` altera a raiz
de snapshots somente no modo `--csv`; `--saida CAMINHO` altera a raiz das
exportações. O padrão é `dados/resultados`. Use `python3 -m rastro --help`
com `PYTHONPATH=src` para consultar os argumentos.

Para os mesmos bytes reais, as regras 3 geram:

```text
execucao_sha256: e64d4e0ec72b9bf1e7e5bc5c718f7622e8357df2bdda479505474d5e8bce4f0c
lidas: 594309
selecionadas: 1842
fora_do_recorte: 592467
rejeitadas: 0
problemas_opcionais: 0
dias_utc: 31
municipios_com_codigo: 50
sem_municipio_id: 0
municipios_com_nomes_divergentes: 0
```

## Consultar os arquivos produzidos

Cada resultado ocupa `dados/resultados/<execucao_sha256>/`:

| Arquivo | Conteúdo |
| --- | --- |
| `manifesto.json` | Hash da execução e manifesto completo, incluindo tabelas e diagnósticos |
| `por_dia.csv` | Uma linha por dia UTC do recorte, inclusive contagens zero |
| `por_municipio.csv` | Código, lista JSON de nomes, contagem, ausências de nome e indicação de divergência |
| `contexto.json` | Contexto da primeira exportação: Python, sistema, revisão Git, alterações locais e hash dos arquivos Python do pacote |

`nomes_json` preserva todos os nomes distintos associados ao código. Um código
sem nome continua contabilizado; uma observação sem código utilizável entra
no grupo de código vazio no CSV (`null` no JSON). Código com formato correto
não significa município conferido contra uma malha ou tabela oficial.

O manifesto usa `versao_manifesto_execucao = 2` e `versao_regras = 3`.
As somas de cada tabela precisam ser iguais ao total selecionado. Os arquivos
são preparados em uma pasta temporária e publicados juntos após o sucesso.
Uma saída existente divergente é recusada. A reutilização preserva o contexto
da primeira exportação; não cria um histórico de todas as chamadas do comando.

O contexto fica fora do hash da execução. Para reproduzir, guarde a entrada,
os manifestos, o código da revisão e suas alterações locais. As regras atuais
mudam os hashes em relação à validação antiga, sem alterar os bytes do snapshot.

## Interfaces Python e comandos anteriores

`rastro.execucao.executar_snapshot()` continua disponível e retorna
`ResultadoExecucao`, agora também com `agregacoes`. Essa API não grava arquivos;
`rastro.exportacao.exportar_resultado()` publica o resultado. O CLI combina ambas.

Os comandos anteriores continuam disponíveis:

```bash
python3 src/rastro/leitor.py testes/fixtures/focos_sinteticos.csv
PYTHONPATH=src python3 -m rastro.snapshot criar testes/fixtures/focos_sinteticos.csv
PYTHONPATH=src python3 -m rastro.snapshot verificar dados/snapshots/82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f
```

O comando simples do leitor não controla IDs repetidos nem gera agregações.

## Testes e próximos passos

```bash
PYTHONPATH=src python3 -m unittest discover -s testes -p 'test_*.py' -v
```

Os 103 testes passaram com Python 3.12.14 no Linux. Cobrem limites, snapshots,
identidade decimal e municipal, fusos, dias vazios, nomes divergentes, ausências,
exportação, falhas e CLI. O workflow executa os testes offline; não baixa dados reais.

As tabelas do CSV real foram comparadas com uma contagem independente do arquivo:
31 dias, 50 códigos e soma 1.842 em ambas. A execução também identificou
11 valores ausentes de risco de fogo entre os selecionados, tratados pelas regras
de ausência, sem gerar problemas opcionais.

Os próximos passos são conferir a referência territorial e as condições de uso
da fonte, explorar visualmente as tabelas e definir a primeira interface do
caderno. Ainda faltam avaliação sistemática de recursos, quota do SQLite
temporário e controle global de execuções concorrentes. Detalhes de validação,
identidade e interpretação estão em [docs/DADOS.md](docs/DADOS.md).
