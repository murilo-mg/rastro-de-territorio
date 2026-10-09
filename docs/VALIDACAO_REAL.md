# Validação do CSV real de agosto de 2025

Primeira execução completa do Rastro de Território com dados reais do Programa
Queimadas do INPE. O processamento e a reprodução local produziram os mesmos
hashes e contagens. Este registro descreve os bytes abaixo, não qualquer versão
futura do arquivo disponível na mesma URL.

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
Ainda não há validação contra malha municipal nem agregações implementadas.

As 1.842 linhas representam detecções selecionadas, não incêndios distintos
nem hectares queimados. As limitações de interpretação e as referências da
fonte permanecem no [contrato de dados](DADOS.md#interpretação-científica).

O próximo passo é preservar os campos municipais e agregar detecções por dia
UTC e por identificador municipal informado na fonte, explicitando dados
ausentes e mantendo as somas consistentes com o total selecionado. A edição
da malha territorial e as condições de uso dos dados ainda precisam ser
esclarecidas antes de tratá-los como uma distribuição espacial validada.
