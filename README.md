# Rastro de Território

Projeto de um caderno interativo de dados ambientais do Amazonas, desenvolvido
por Murilo da Mota Gonçalves, estudante de Ciência da Computação na UFAM.
O objetivo é tornar os resultados exploráveis e explicar sua origem e suas
limitações. O orçamento é zero; a etapa atual roda localmente, sem serviços pagos.

## Pergunta inicial

> Como as detecções do satélite de referência se distribuíram pelo Amazonas em
> agosto de 2025, e quais limitações devemos considerar ao interpretar esses números?

O recorte implementado seleciona `estado_id = 13`, satélite exatamente
`AQUA_M-T` e datas UTC de `2025-08-01T00:00:00Z` (inclusive) até
`2025-09-01T00:00:00Z` (exclusive). Detecções não equivalem a incêndios distintos
nem a área queimada. A pergunta ainda não foi respondida com dados reais.

## Estado atual

Funcionam atualmente:

- Leitor de CSV local com validação, recorte fixo, limites de leitura e resumo
  de linhas selecionadas, fora do recorte e rejeitadas.
- Criação, reutilização e verificação de snapshots locais por SHA-256.
- API Python que verifica o snapshot, processa o CSV e recusa IDs repetidos
  entre as linhas selecionadas, usando SQLite temporário.
- Manifesto de execução retornado em memória e hash determinístico desse
  manifesto, incluindo identidade da entrada, perfil, limites e contagens.
- Testes offline com dados sintéticos e workflow de testes no GitHub Actions.
- Execução validada com o CSV nacional real de agosto de 2025: 594.309 linhas
  lidas e 1.842 detecções selecionadas, sem rejeições ou IDs selecionados repetidos.
  Os hashes e comandos estão em [validação real](docs/VALIDACAO_REAL.md).

A interface interativa, mapas, agregações por município ou dia, banco persistente,
API web, coleta HTTP e hospedagem permanecem planejados. O SQLite atual serve
somente ao controle temporário de IDs. Não há dependência de pandas, serviço
de banco ou biblioteca de mapas.

O [contrato de dados](docs/DADOS.md) detalha validação, identidade, limites,
procedência e interpretação. O código está em [src/rastro](src/rastro),
e os testes em [testes](testes).

## Requisitos e instalação

Use Python 3.12, versão configurada no CI, e Linux para o fluxo completo.
O módulo de snapshots depende de `fcntl` e de travas POSIX; não há suporte
implementado para Windows. O Python precisa incluir o módulo `sqlite3`.
Todas as dependências são da biblioteca padrão: não há pacote para instalar
com `pip`, `requirements.txt` ou configuração de instalação do projeto.

Para uma cópia nova:

```bash
git clone https://github.com/murilo-mg/rastro-de-territorio.git
cd rastro-de-territorio
```

Na cópia local indicada, comece por:

```bash
cd ~/Documentos/rastro-de-territorio
python3 --version
python3 -c "import csv, decimal, fcntl, hashlib, json, sqlite3; print('dependências disponíveis')"
```

Execute os comandos abaixo na raiz do repositório, na revisão que contém
[src/rastro/execucao.py](src/rastro/execucao.py). `PYTHONPATH=src` permite
importar os módulos sem instalar um pacote. Uma cópia de outra branch pode
não conter a mesma implementação; registre a revisão usada.

## Ler a fixture sintética

A [fixture](testes/fixtures/focos_sinteticos.csv) contém cinco observações
inventadas, inclusive os IDs. Seus resultados não descrevem eventos reais.

```bash
python3 src/rastro/leitor.py testes/fixtures/focos_sinteticos.csv
python3 src/rastro/leitor.py testes/fixtures/focos_sinteticos.csv --perfil mensal
```

Ambos os comandos produzem:

```text
lidas: 5
selecionadas: 2
fora_do_recorte: 3
rejeitadas: 0
problemas_opcionais: 0
```

Entram `sintetico-001` e `sintetico-002`. As outras linhas têm satélite diferente,
estado diferente ou data no limite final excluído. Este comando simples não
controla repetições de IDs. Para isso, use a execução sobre snapshot abaixo.

O perfil padrão `fixture` permite 5 MiB e 20.000 linhas físicas após o cabeçalho;
`mensal` permite 512 MiB e 5.000.000. Ambos têm outros
[limites de leitura](docs/DADOS.md#limites-implementados). Selecionar `mensal`
altera os limites, sem alterar estado, satélite ou período.

## Preservar e verificar a entrada

```bash
PYTHONPATH=src python3 -m rastro.snapshot criar testes/fixtures/focos_sinteticos.csv
PYTHONPATH=src python3 -m rastro.snapshot verificar dados/snapshots/82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f
```

Na validação desta documentação, a cópia já existia e foi reutilizada:

```text
snapshot: reutilizado
sha256: 82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f
bytes: 731
diretorio: dados/snapshots/82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f
```

Na primeira criação, a primeira linha informa `snapshot: criado`; na verificação,
`snapshot: integridade conferida`. Hash e tamanho acima correspondem aos bytes
da fixture versionada. Para outra entrada, use o diretório exibido pelo comando.

`criar` aceita `--destino dados/snapshots` e `--perfil mensal`; `verificar`
também aceita `--perfil mensal`. Para arquivos acima de 5 MiB, use esse perfil
na criação, na verificação e na execução.

A pasta de snapshots tem quota padrão de 3 GiB e exige uma reserva de 5 GiB
livres no disco ao criar uma nova cópia, mesmo para uma fixture pequena.
Não há exclusão automática. Veja as [regras de armazenamento](docs/DADOS.md#snapshots-locais).

## Reproduzir o processamento

`rastro.execucao` oferece `executar_snapshot`; não tem uma interface de linha
de comando. O exemplo completo abaixo chama a API e salva o resultado em
`dados/execucoes/`, fora do Git. A gravação e o registro de revisão e versão
do Python são feitos pelo exemplo, não automaticamente pela API.

```bash
PYTHONPATH=src python3 - <<'PY'
import json
import platform
import subprocess
from pathlib import Path

from rastro.execucao import executar_snapshot

diretorio = Path("dados/snapshots/82d677fe686df80c69a5dffab3988446c640580f01cdc160a7c489101032e23f")
resultado = executar_snapshot(diretorio, perfil="fixture")
registro = {
    "execucao_sha256": resultado.execucao_sha256,
    "manifesto": resultado.manifesto,
    "contexto": {
        "revisao_codigo": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "python": platform.python_version(),
    },
}
destino = Path("dados/execucoes") / (resultado.execucao_sha256 + ".json")
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(json.dumps(registro, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
print("execucao_sha256:", resultado.execucao_sha256)
print("ids_selecionados_unicos:", resultado.ids_selecionados_unicos)
for nome, valor in resultado.resumo.items():
    print(f"{nome}: {valor}")
print("registro:", destino)
PY
```

Saída obtida com a fixture e o perfil `fixture`:

```text
execucao_sha256: 2f2a8492456c5572b10e0d67c59ea4420625d10f557cfb90ef2009a94c459b5c
ids_selecionados_unicos: 2
lidas: 5
selecionadas: 2
fora_do_recorte: 3
rejeitadas: 0
problemas_opcionais: 0
registro: dados/execucoes/2f2a8492456c5572b10e0d67c59ea4420625d10f557cfb90ef2009a94c459b5c.json
```

Reexecutar o exemplo mantém esse hash e regrava o registro no mesmo caminho.
Guarde os dois arquivos do snapshot, o registro de execução, o código da revisão
usada e eventuais alterações locais de código. O manifesto não registra commit,
versão do Python ou os valores explícitos do recorte; `versao_regras = 2`
precisa ser interpretada junto ao código. Não existe comando de importação ou
verificação de um manifesto de execução salvo. Veja
[identidade e reprodução](docs/DADOS.md#execução-e-manifesto).

O hash do snapshot identifica os bytes do CSV; o da execução identifica o
manifesto canônico. Nenhum deles certifica a procedência ou a validade científica
do resultado. Um ID repetido interrompe a execução, sem resultado completo;
não é removido silenciosamente nem contado em uma quarta categoria.

## Testes

```bash
PYTHONPATH=src python3 -m unittest discover -s testes -p 'test_*.py' -v
```

Na correção da assinatura decimal, os 78 testes passaram com Python 3.12.14 no Linux.
O [workflow](.github/workflows/testes.yml) executa a mesma descoberta de testes
em pushes e pull requests, com Python 3.12 no Ubuntu e limite de cinco minutos
para o job. Os testes não baixam dados ambientais.

## Limitações e próximos passos

O leitor não valida UUID, estabilidade de IDs, CRS ou coerência territorial das
coordenadas. A assinatura usada para classificar repetições preserva os valores
decimais sem arredondar e sem depender do contexto global de `Decimal`.
As [regras de identidade](docs/DADOS.md#ids-repetidos-e-conflitos) ainda se
referem apenas aos campos preservados em `Foco`.
Não há avaliação sistemática de RAM ou desempenho com o arquivo nacional, quota para o SQLite
temporário nem controle global de execuções concorrentes.

O CSV real já passou pelo leitor e pela execução com controle de IDs na
[validação registrada](docs/VALIDACAO_REAL.md). O próximo passo é preservar os
campos municipais e produzir agregações por dia UTC e município, mantendo
visíveis os dados ausentes e as limitações da fonte. Ainda falta aprofundar a
verificação de metodologia e registrar melhor a revisão das regras. As condições
de redistribuição de dados reais ainda precisam ser confirmadas. A
[procedência e as referências consultadas](docs/DADOS.md#procedência-e-condições-de-uso)
estão centralizadas no contrato de dados.
