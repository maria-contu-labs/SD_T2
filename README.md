# Laboratório de Sistemas Distribuídos — etcd e Cassandra

Trabalho prático da disciplina de Sistemas Distribuídos da PUCRS. O objetivo é comparar latência, vazão e disponibilidade de dois sistemas chave-valor replicados: **etcd 3.5.21** (Raft, leitura linearizável) e **Cassandra 4.1.12** (RF=3 e CL=ONE para GET e PUT).

## Ambiente

Três nós (`n1`, `n2`, `n3`) em Docker Compose e um contêiner para o gerador de carga. Os testes foram executados em um MacBook Air Apple M2, 8 núcleos e 8 GB de RAM. Cada cliente usa loop fechado, 80% GET e 20% PUT, 10.000 chaves, valores de 256 B, timeout de 2 s e semente fixa.

O código implementa os clientes, a geração de carga e a orquestração dos experimentos; os bancos de dados são imagens oficiais.

## Preparar o ambiente

É necessário Docker Desktop, Docker Compose e Python 3. Execute somente um cluster por vez.

```bash
./scripts/ambiente.sh etcd
./scripts/preparar.sh etcd
```

Para usar Cassandra, encerre o cluster anterior antes:

```bash
docker compose -f etcd.yml down -v
./scripts/ambiente.sh cassandra
./scripts/preparar.sh cassandra
```

O script de ambiente aguarda os três nós Cassandra e suas portas CQL estarem acessíveis. A preparação inicializa as 10.000 chaves e pode demorar alguns minutos.

## Experimentos

| Teste | Medição |
| --- | --- |
| E1 | Saturação variando N de 1 a 512, 120 s por ponto e 30 s de aquecimento |
| E2 | Baseline de 180 s com N ótimo de E1 |
| E3 | GET após PUT confirmado, medindo leituras desatualizadas |
| E4 | Mesmo N de E2, com atraso entre nós de 50 ms por sentido |
| E5 | Isolamento de `n1` por aproximadamente 60 s |
| E6 | Falha de líder/seguidor (etcd) ou coordenadores (Cassandra) |

No E1, a maior razão vazão/p99 ocorreu em **N=2** nos dois sistemas. Foram feitas três repetições por configuração nos testes oficiais.

### Reproduzir o E2

Com o cluster preparado, executar a carga completa de 180 s:

```bash
./scripts/demo_e2.sh cassandra
# ou, com o cluster etcd preparado:
./scripts/demo_e2.sh etcd
```

O script usa N=2, dois processos geradores e salva a coleta separada em `gerador/resultados/PILOTO/`, sem sobrescrever as repetições oficiais do E2. Exibe GET/PUT, vazão, percentis e erros ao terminar. Para uma conferência rápida, use `DURACAO=25 ./scripts/demo_e2.sh cassandra`.

Para executar as três repetições oficiais do E2, use `PROCESSOS=2 ./scripts/executar_e2_e4.sh cassandra E2 2` (3 × 180 s). O cluster deve estar preparado antes.

Os scripts dos demais testes estão em `scripts/`. E3 usa `gerador/stale.py`, E5 usa `orquestrar.py` e a variante atual do E6 usa `scripts/executar_e6_v2.sh`.

## Resultados e análise

- `resultados/`: CSVs consolidados de E1, E2/E4, E3 e E6, sem as amostras brutas.
- `docs/figuras/`: gráficos para consulta.
- `docs/relatorio.pdf`: relatório entregue, com as análises de E1 a E6.
- `analisar.py` e `analise_e6_final.py`: análise de amostras brutas, quando disponíveis.
- `scripts/graficos_entrega.py`: recria os gráficos E1 e E2/E4 a partir dos CSVs resumidos.

Recriar os gráficos resumidos:

```bash
python3 -m pip install matplotlib
python3 scripts/graficos_entrega.py
```

Os arquivos originais de cada requisição são grandes e ficam locais em `gerador/resultados/`; não foram incluídos neste ZIP.

## Limitações

Os resultados também dependem de bibliotecas clientes, recursos do Docker, cache e persistência; não podem ser atribuídos somente ao protocolo. O primeiro PUT bem-sucedido após uma falha no E6 não prova recuperação sustentada. Na verificação complementar do E5, duas escritas confirmadas no Cassandra foram lidas com CL=ALL após a reconexão, mas isso não prova convergência espontânea das três réplicas nem ausência de perdas nos testes originais.

**Atenção:** alguns scripts executam `docker compose down -v` e apagam os volumes do cluster. Confira os dados antes de executar novamente.
