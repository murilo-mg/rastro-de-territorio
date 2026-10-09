# Referência municipal IBGE — DTB 2025

Fonte: Instituto Brasileiro de Geografia e Estatística (IBGE), Divisão
Territorial Brasileira, edição 2025, tabela municipal com data-base
**31/12/2025**. Acesso em **09/10/2026 (UTC)**.

O arquivo [DTB_2025.zip](https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/DTB_2025.zip)
foi obtido no [diretório oficial de 2025](https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/),
que identifica os arquivos como públicos. A página do
[produto DTB](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/23701-divisao-territorial-brasileira.html)
explica a relação anual de municípios, distritos e subdistritos.

| Arquivo preservado | Conteúdo |
| --- | --- |
| `original.ods` | Bytes originais do membro `RELATORIO_DTB_BRASIL_2025_MUNICIPIOS.ods`, sem alterações |
| `municipios_am.csv` | Subconjunto com UF 13, código municipal completo e nome: 62 municípios, ordenados por código |
| `manifesto.json` | Origem, edição, data-base, acesso, nome do membro e hashes do ZIP, ODS e CSV |

O ZIP completo não é versionado; seu hash está registrado. O ODS original
contém o Brasil inteiro; apenas o CSV derivado seleciona o Amazonas. O CSV
não remove acentos nem altera nomes. O membro original tem 206.091 bytes.

## Extração reproduzível

Na raiz do projeto, escolha um arquivo de saída ainda inexistente:

```bash
mkdir -p dados
PYTHONPATH=src python3 scripts/extrair_referencia_ibge.py \
  referencias/ibge/dtb2025/original.ods \
  --saida dados/municipios-am-reproduzido.csv &&
cmp referencias/ibge/dtb2025/municipios_am.csv dados/municipios-am-reproduzido.csv
```

O extrator usa `zipfile` e `xml.etree.ElementTree`, da biblioteca padrão,
confere tabela, cabeçalho, data-base, códigos únicos e quantidade. Não
consulta rede e não regrava o ODS. Limita a entrada a 1 MiB e o XML a 16 MiB.

O módulo `territorio.py` fixa o hash do manifesto e confere os três arquivos
antes de usá-los. Atualizar a referência requer revisar dados, hashes,
documentação e a versão das regras; a execução não baixa atualizações.

## Alcance da conferência

A data-base é posterior ao recorte de agosto de 2025. Esta referência permite
uma comparação cadastral explícita, sem demonstrar qual edição territorial
o INPE usou nem verificar a posição espacial de cada detecção. A comparação
de nomes registra igualdade literal, equivalência após normalização ou
divergência; nenhum nome da fonte é substituído. Mais detalhes em
[REFERENCIA_MUNICIPAL.md](../../../docs/REFERENCIA_MUNICIPAL.md).

Esta referência mantém a atribuição ao IBGE. A indicação de arquivo público
não é convertida pelo projeto em uma licença específica presumida.
