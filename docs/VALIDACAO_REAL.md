# Validação do CSV real de agosto de 2025

Primeira execução completa do Rastro de Território com dados reais do Programa
Queimadas do INPE. O processamento e a reprodução local produziram os mesmos
hashes e contagens. Este registro descreve os bytes abaixo, não qualquer versão
futura do arquivo disponível na mesma URL.

As primeiras seções preservam a validação histórica das regras 2. A
[validação das regras 3](#agregações-e-cli-com-as-regras-3) está no final,
com o novo comando, as tabelas e o hash atual.

## Fonte, entrada e revisão

| Item | Valor |
| --- | --- |
| Fonte | Programa Queimadas do INPE |
| Arquivo | `focos_mensal_br_202508.csv` |
| Acesso | 09/10/2026, data UTC |
| Tamanho conferido | 93.587.739 bytes |
| Perfil | `mensal` |
| Revisão executada | `7b024e1e77dee230236b9cd8330ef7b12b1ebf83` |
| Versão das regras | 2 |
| Versão do manifesto de execução | 1 |

A [listagem mensal oficial](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/)
disponibiliza o [arquivo utilizado](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/focos_mensal_br_202508.csv).
A referência de acesso usa UTC; não é a data das detecções nem uma data de
publicação atribuída ao arquivo.

SHA-256 dos bytes da entrada:

```text
9420a1babbf627ef80d9b39ba1d8e2b656f88e98e11c622952094704be7106c3
```

SHA-256 do manifesto canônico da execução:

```text
4579d73e23107f882a5965204ad736d1a3c4178da4a4bbba9e3ba574cbfa525c
```

O hash da entrada identifica o CSV preservado. O hash da execução identifica
o manifesto conforme as regras do [contrato de dados](DADOS.md#execução-e-manifesto).
Se a fonte atualizar o arquivo, compare primeiro o hash da entrada; contagens
diferentes precisam ser interpretadas com a revisão e os bytes correspondentes.

## Resultado obtido

O recorte é estado `13`, satélite exatamente `AQUA_M-T` e período UTC de
`2025-08-01T00:00:00Z` inclusive até `2025-09-01T00:00:00Z` exclusive.

| Métrica da implementação | Resultado |
| --- | ---: |
| Linhas lidas | 594.309 |
| Linhas selecionadas | 1.842 |
| Linhas fora do recorte | 592.467 |
| Linhas rejeitadas | 0 |
| Problemas em campos opcionais selecionados | 0 |
| IDs selecionados únicos | 1.842 |

A soma fecha: `594309 = 1842 + 592467 + 0`. A execução foi concluída sem
`ErroIdentidade`, portanto nenhum `source_id` selecionado se repetiu nesta
entrada. Isso não afirma unicidade dos IDs de todas as linhas nacionais,
que ficam fora do controle de identidade quando não são selecionadas.

O cabeçalho recebido contém as 16 colunas esperadas pelo leitor. O arquivo
completo foi aceito pelo perfil mensal e pela verificação de snapshot.
Não houve rejeição de campos essenciais. Campos opcionais são avaliados apenas
nas linhas selecionadas; a ausência de problemas não significa que todos
os valores estejam presentes, pois vazios e sentinelas reconhecidas viram `None`.

## Reprodução

Execute na raiz do projeto usando a revisão registrada acima. O download é
manual com `curl`; não há coletor HTTP implementado no pacote `rastro`.

```bash
mkdir -p dados/originais
curl --fail --location --retry 2 \
  --dump-header dados/originais/focos_mensal_br_202508.headers \
  --output dados/originais/focos_mensal_br_202508.csv.part \
  https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/focos_mensal_br_202508.csv &&
mv dados/originais/focos_mensal_br_202508.csv.part \
   dados/originais/focos_mensal_br_202508.csv
```

Os cabeçalhos HTTP ficam separados do manifesto do snapshot. Este continua
registrando `copia_local`, porque recebe um arquivo que já está no disco.
`Last-Modified` não é tratado como data original de publicação, e o hash não
autentica a procedência. Preserve URL e cabeçalhos junto à entrada local.

```bash
PYTHONPATH=src python3 - <<'PY'
import json
import platform
import subprocess
from pathlib import Path
from rastro.snapshot import criar_snapshot
from rastro.execucao import executar_snapshot

snapshot = criar_snapshot(
    Path("dados/originais/focos_mensal_br_202508.csv"),
    Path("dados/snapshots"),
    perfil="mensal",
)
resultado = executar_snapshot(snapshot.diretorio, perfil="mensal")
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
destino.write_text(
    json.dumps(registro, ensure_ascii=True, indent=2) + "\n",
    encoding="utf-8",
)
print("snapshot_sha256:", resultado.snapshot_sha256)
print("execucao_sha256:", resultado.execucao_sha256)
print("ids_selecionados_unicos:", resultado.ids_selecionados_unicos)
for campo, valor in resultado.resumo.items():
    print(f"{campo}: {valor}")
print("registro:", destino)
PY
```

Guarde entrada, snapshot, registro de execução, revisão e eventuais alterações
locais. Os arquivos em `dados/` continuam fora do Git. Esta documentação
versiona a evidência resumida e os comandos, sem incluir o CSV nacional.

## Alcance da validação e próximo passo

Esta execução confirma compatibilidade operacional do arquivo registrado com
o leitor, com o recorte e com o controle de identidade implementado. Não
comprova cobertura completa, precisão do sensor, validade de unidades e faixas,
estabilidade dos IDs entre arquivos ou coerência territorial das coordenadas.
Nessa revisão histórica, ainda não havia agregações. A validação contra
malha municipal continua pendente.

As 1.842 linhas representam detecções selecionadas, não incêndios distintos
nem hectares queimados. As limitações de interpretação e as referências da
fonte permanecem no [contrato de dados](DADOS.md#interpretação-científica).

O passo seguinte dessa validação foi preservar os campos municipais e agregar
as detecções, conforme registrado abaixo. A edição da malha territorial e as
condições de uso dos dados ainda precisam ser esclarecidas antes de tratar
as tabelas como uma distribuição espacial validada.

## Agregações e CLI com as regras 3

A implementação de agregações foi validada com os mesmos bytes da entrada,
sobre a base `d212f1bc002608bba265f170086c95a726700867` e as alterações do
combo de campos municipais, agregações e CLI. O novo manifesto tem formato 2,
regras 3 e agregações 1. O contexto exportado registra o hash dos arquivos
Python e a presença de alterações locais; essa base isolada não contém o combo.

```bash
PYTHONPATH=src python3 -m rastro \
  --snapshot dados/snapshots/9420a1babbf627ef80d9b39ba1d8e2b656f88e98e11c622952094704be7106c3 \
  --perfil mensal
```

Novo SHA-256 do manifesto canônico da execução:

```text
e64d4e0ec72b9bf1e7e5bc5c718f7622e8357df2bdda479505474d5e8bce4f0c
```

| Resultado | Valor |
| --- | ---: |
| Detecções selecionadas e IDs únicos | 1.842 |
| Dias UTC exportados | 31 |
| Códigos municipais com detecções | 50 |
| Soma das contagens diárias | 1.842 |
| Soma das contagens municipais | 1.842 |
| Detecções sem código municipal utilizável | 0 |
| Códigos com nomes divergentes | 0 |
| Ausências de risco de fogo nos selecionados | 11 |
| Problemas opcionais nos selecionados | 0 |

As 594.309 linhas lidas, 592.467 fora do recorte e zero rejeitadas permanecem
iguais. As ausências reconhecidas de risco de fogo demonstram por que o
contador de problemas não pode ser interpretado como contador de valores vazios.

Uma contagem independente com `csv.DictReader` percorreu o original,
selecionou estado, satélite e período e comparou os dias, códigos, nomes e
contagens às duas tabelas exportadas. As 31 linhas diárias e os 50 grupos
municipais coincidiram. Para inspecionar alguns resultados da implementação:

| Grupo informado na fonte | Detecções |
| --- | ---: |
| `1300144` - APUÍ | 416 |
| `1303304` - NOVO ARIPUANÃ | 269 |
| `1301704` - HUMAITÁ | 210 |
| Dia UTC 2025-08-26 | 335 |

Essas contagens são descritivas do recorte, não uma validação da classificação
territorial de cada ponto nem uma estimativa de área queimada. Os arquivos
produzidos ficam em `dados/resultados/<execucao_sha256>/`, fora do Git.

## Matriz e referência municipal nas regras 4

As mesmas entradas foram reexecutadas com manifesto 3, regras 4 e agregações 2,
incluindo referência IBGE DTB 2025 e matriz município × dia. O hash do snapshot
permanece igual. O novo hash da execução é:

```text
62cd809c8b059aa98decc8640c8a7507a05d204f82529dc6f660a25e8f87ca92
```

As contagens anteriores permanecem: 594.309 lidas, 1.842 selecionadas,
592.467 fora do recorte, zero rejeitadas e zero problemas opcionais.
Os 50 códigos observados foram encontrados nos 62 municípios da referência
DTB 2025, sem nomes divergentes após a normalização registrada. Isso não
converte nomes equivalentes em igualdade literal nem valida a posição espacial.

A matriz tem 1.550 células: 50 grupos × 31 dias, incluindo zeros. Uma leitura
independente do CSV original com `csv.DictReader` e datas UTC coincidiu com
todas as células. As somas das linhas coincidiram com os totais municipais,
e as somas das colunas, com os totais diários.

| Grupo | Total | Máximo diário | Dia UTC do máximo |
| --- | ---: | ---: | --- |
| Apuí (`1300144`) | 416 | 88 | 2025-08-26 |
| Humaitá (`1301704`) | 210 | 32 | 2025-08-16 |

Foram exportados `por_municipio_dia.csv` e `conferencia_municipal.csv`, além
dos quatro arquivos anteriores. Os resultados das regras 3 continuaram
verificáveis com seus hashes originais e não foram modificados.

A referência preservada tem data-base 31/12/2025, posterior ao recorte, e
não identifica a edição territorial usada pelo INPE. Origem, hashes, extração,
classes de comparação e limites estão em
[REFERENCIA_MUNICIPAL.md](REFERENCIA_MUNICIPAL.md). O caderno versão 2 apresenta
seleção de até três grupos com gráfico diário e tabela exata; a conferência de
navegador está em [CADERNO.md](CADERNO.md#validação-desta-etapa).
