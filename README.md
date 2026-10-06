# Rastro de Território

Um caderno interativo para explorar dados ambientais do Amazonas e explicar
a origem e as limitações de cada resultado. Projeto em desenvolvimento.

## Primeira pergunta

Como as detecções do satélite de referência se distribuíram pelo Amazonas
em agosto de 2025, e quais limitações devemos considerar ao interpretar esses números?

O primeiro recorte usa o código de estado `13`, o satélite exato `AQUA_M-T`
e o intervalo UTC de `2025-08-01 00:00:00` até antes de `2025-09-01 00:00:00`.
Contar detecções não equivale a contar incêndios distintos ou medir área queimada.

## Estado atual

Etapa atual: leitor CSV local com validação básica, recorte, limites de entrada,
snapshots identificados por hash e testes offline.
As regras estão em [docs/DADOS.md](docs/DADOS.md).
Ainda não há banco, API, mapa ou versão pública. Nenhum dado real está incluído.
O arquivo `testes/fixtures/focos_sinteticos.csv` contém cinco observações inventadas,
inclusive seus identificadores. Os exemplos não representam eventos reais.

## Executar

Requer Python 3.12 ou superior. Esta etapa usa somente a biblioteca padrão;
não há dependências para instalar.
Os comandos de snapshot desta etapa usam trava de arquivo POSIX e são
implementados e testados para Linux, incluindo o runner Ubuntu do GitHub Actions.

```bash
python src/rastro/leitor.py testes/fixtures/focos_sinteticos.csv
```

O perfil padrão `fixture` aceita até 5 MiB e 20 mil linhas após o cabeçalho.
O perfil `mensal` aceita até 512 MiB e 5 milhões de linhas. Para testar a seleção
do perfil com o mesmo exemplo sintético:

```bash
python src/rastro/leitor.py testes/fixtures/focos_sinteticos.csv --perfil mensal
```

Resultado esperado:

```text
lidas: 5
selecionadas: 2
fora_do_recorte: 3
rejeitadas: 0
problemas_opcionais: 0
```

## Guardar e conferir uma cópia do arquivo

```bash
PYTHONPATH=src python -m rastro.snapshot criar testes/fixtures/focos_sinteticos.csv
```

O comando guarda `original.csv` e `manifesto.json` em `dados/snapshots/<sha256>/`.
A repetição com os mesmos bytes verifica e reutiliza a cópia existente.
Para conferir novamente, substitua `<sha256>` pelo hash exibido:

```bash
PYTHONPATH=src python -m rastro.snapshot verificar dados/snapshots/<sha256>
```

Arquivos de snapshot ficam fora do Git. A quota local padrão é 3 GiB, com
reserva de 5 GiB livres no disco. Não há exclusão automática de snapshots.
O hash comprova identidade dos bytes; não valida a interpretação científica.

## Testar

Na raiz do projeto:

```bash
PYTHONPATH=src python -m unittest discover -s testes -p 'test_*.py' -v
```

## Regras desta etapa

- Leitura linha a linha; o resumo não acumula todas as observações na memória.
- Limites de bytes totais, linha física, campo UTF-8, colunas, linhas e tempo.
- Validação do cabeçalho, ID não vazio, satélite, código de estado, data e coordenadas.
- Coordenadas com espaços são aparadas e lidas como números decimais finitos.
- A coluna `data_hora_gmt` sem offset é interpretada em UTC; offsets explícitos
  são convertidos para UTC. Data sem hora não é aceita.
- `-999`, incluindo variantes decimais, vira `None` nos três campos meteorológicos.
- Campo opcional vazio vira `None`. Zero permanece zero.
- Campo opcional inválido vira `None` e gera um problema associado ao campo;
  a observação continua selecionada se seus campos essenciais forem válidos.
- Dias sem chuva: inteiro não negativo; precipitação e FRP: não negativos;
  risco de fogo: entre zero e um; dias sem chuva também precisa caber em inteiro
  de 32 bits. Os limites meteorológicos ainda precisam ser conferidos
  com a documentação e o arquivo real antes da integração.
- As categorias são exclusivas: lidas = selecionadas + fora do recorte + rejeitadas.
  Campos essenciais inválidos são rejeitados antes de avaliar o recorte.
  Campos opcionais só são verificados nas observações selecionadas.
- O resumo conta problemas opcionais por campo, não por observação.

## Limitações e próximas etapas

O leitor ainda não valida o formato UUID dos IDs e não detecta IDs repetidos.
O comando de snapshots é separado do leitor e não valida o conteúdo do CSV.
Erros estruturais de CSV interrompem a execução, sem resumo parcial.
Linhas vazias são ignoradas pela biblioteca CSV.

Antes de usar o arquivo nacional real: conferir o contrato documentado com a fonte,
definir identidade e duplicatas por execução e testar a integração do snapshot
com o leitor. Depois entram banco, API e interface.

Os arquivos reais ficarão em `dados/`, fora do Git. Fonte planejada:
[Programa Queimadas do INPE](https://data.inpe.br/queimadas/dados-abertos/).
As condições de redistribuição dos dados reais serão verificadas separadamente.

## Desenvolvimento

Murilo da Mota Gonçalves — Ciência da Computação, UFAM.
