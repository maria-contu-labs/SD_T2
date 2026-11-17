# Laboratório de Sistemas Distribuídos — Consistência, latência e vazão

Trabalho prático da disciplina de Sistemas Distribuídos (PUCRS). Comparamos **etcd (Raft)** e **Apache Cassandra (RF=3, CL=ONE)** em um ambiente local com três nós Docker.

A ideia foi observar a diferença entre consistência forte e consistência eventual em condições normais, com atraso de rede e com falhas. Não implementamos os bancos de dados; configuramos os clusters, os clientes e os testes.

## Como o laboratório funciona

- `etcd.yml` e `cassandra.yml`: clusters de três nós (`n1`, `n2`, `n3`) e contêiner do gerador.
- `gerador/`: cliente Python que executa GETs e PUTs e grava amostras em CSV compactado.
- `scripts/`: preparação do ambiente, emulação de atraso, partição, falha e execução dos testes.
- `orquestrar.py`: coordena cenários que exigem ações durante a carga.
- `analisar.py`: consolida resultados e gera gráficos.

Usamos uma carga em loop fechado, com **80% GET e 20% PUT**, 10.000 chaves, valores de 256 bytes e timeout de 2 segundos. As configurações foram repetidas três vezes. Em alguns cenários usamos dois processos geradores para reduzir a interferência do cliente.

## Preparação

É necessário ter Docker Desktop com Docker Compose e Python 3.

```bash
# Subir somente um cluster por vez
./scripts/ambiente.sh etcd
./scripts/preparar.sh etcd

# Encerrar quando terminar
# docker compose -f etcd.yml down
```

Para o Cassandra, além do status `UN` no `nodetool`, é importante aguardar a abertura da porta CQL nos três nós:

```bash
./scripts/ambiente.sh cassandra
bash scripts/aguardar_cql.sh
./scripts/preparar.sh cassandra
```

O Cassandra pode demorar alguns minutos para subir. Não iniciar medições antes de todos os coordenadores aceitarem conexões.

## Experimentos

| Teste | O que medimos |
|---|---|
| E1 | Aumento da concorrência, vazão efetiva, p99 e saturação |
| E2 | Desempenho normal (baseline) no N escolhido pelo E1 |
| E3 | Leituras desatualizadas após escrita confirmada |
| E4 | Impacto de aproximadamente 100 ms de RTT entre os nós |
| E5 | Comportamento durante partição de rede (`n1` isolado por 60 s) |
| E6 | Falha de líder/seguidor no etcd e de coordenadores no Cassandra |

O N ótimo foi definido pelo critério do enunciado: **maior razão vazão/p99**. Nos dados coletados no Mac, o critério selecionou **N=2** para ambos os sistemas. O ponto de saturação e a vazão máxima são analisados separadamente no relatório.

Exemplo de execução e análise:

```bash
# Exemplo: cenário de partição, 3 repetições
PROCESSOS=2 bash scripts/executar_e5.sh etcd 2

# Consolidar os CSVs já salvos
python3 analisar.py --input gerador/resultados --output graficos
```

**Atenção:** alguns scripts de teste encerram o cluster com `docker compose down -v`, que apaga os volumes de dados. Os CSVs gravados em `gerador/resultados/` não são apagados por esse comando.

## Observações e limitações

- O etcd foi usado com leitura linearizável; no Cassandra, leituras e escritas usaram `CL=ONE` com `RF=3`. Esses modos oferecem garantias diferentes.
- Os resultados refletem também as bibliotecas clientes, a persistência em disco, a configuração do Docker e os recursos limitados do Mac; não são uma comparação isolada de protocolos.
- Nos testes com falha, o **primeiro PUT bem-sucedido** não é necessariamente o instante da eleição de um líder nem da recuperação total da vazão.
- Os registros originais do E5 mostram sucessos e erros, mas não comprovam sozinhos a convergência das réplicas. A verificação de dados após reconexão deve ser documentada separadamente.
- Os gráficos agregados devem ser filtrados por configuração (`N`, sistema e experimento) para não misturar pilotos e medições finais.

Os resultados e a interpretação completa estão no relatório entregue na disciplina.
