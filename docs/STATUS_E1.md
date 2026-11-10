# Status do trabalho — E1 (Saturação)

## Estado atual (09/11/2026)

**Implementação preparada e testada em pilotos locais; experimento E1 oficial ainda NÃO executado no LAD.**

- Clusters etcd 3.5.21 (3 nós Raft) e Cassandra 4.1.12 (3 nós, RF=3 e CL=ONE) subiram localmente no Docker Desktop.
- As 10.000 chaves foram preparadas nos dois sistemas; gerador faz carga fechada, 80% GET e 20% PUT, valor de 256 bytes, semente fixa e timeout de 2 s.
- Foram realizados pilotos curtos no Mac para N=2, 4, 8, 16, 32, com ausência de erros de requisição nos registros analisados.
- Um piloto de Cassandra com N=32 foi executado com 2 processos de 16 threads, e a consolidação multiprocesso retornou p50/p95/p99 e vazão a partir das amostras reunidas.
- Há script para E1 completo: `scripts/executar_e1.sh` (N=1..512, 120 s/ponto, descarte de 30 s, 3 repetições, monitoramento de CPU). Ainda precisa ser validado integralmente e executado no LAD.

## Pilotos no Mac: métricas agregadas (1 processo por execução)

| Sistema | N | Vazão efetiva (req/s) | p99 global (ms) | Erros |
|---|---:|---:|---:|---:|
| etcd | 2 | 2251,89 | 1,828 | 0 |
| etcd | 4 | 2447,11 | 4,736 | 0 |
| etcd | 8 | 2957,17 | 6,562 | 0 |
| etcd | 16 | 2728,83 | 16,770 | 0 |
| etcd | 32 | 2810,83 | 33,814 | 0 |
| Cassandra | 2 | 2055,44 | 4,549 | 0 |
| Cassandra | 4 | 4233,83 | 3,851 | 0 |
| Cassandra | 8 | 6236,72 | 3,411 | 0 |
| Cassandra | 16 | 5202,17 | 11,520 | 0 |
| Cassandra | 32 | 6644,50 | 14,420 | 0 |

**Importante:** N=2 foi medido por 9 segundos úteis; N=4..32 por 18 segundos úteis. Um teste curto, com apenas uma repetição e executado no Mac, não permite estimar de forma confiável saturação e ponto ótimo.

## Validação da consolidação multiprocesso (Cassandra)

- N=32 (2 processos de 16 threads; 20 s, 2 s de aquecimento): **8.607,59 req/s**; p99 global **13,884 ms**; **0 erros**.
- CPU em amostras durante a carga: gerador cerca de **166%**; três nós Cassandra próximos de **80–96%** cada. Docker Desktop relatou **6 CPUs** e **3,825 GiB** disponíveis na VM, com memória apertada para Cassandra.
- Piloto com etcd e 2 processos indicou aumento substancial da vazão em comparação com um processo. A comparação não substitui repetição controlada. Manter a mesma política de processos para ambos na coleta oficial.

## O que falta para declarar E1 concluído

1. Verificar as permissões de Docker e rede no ambiente autorizado do LAD; registrar CPU, memória, disco, SO, Docker e versões.
2. Validar execução multiprocesso e monitoramento de CPU nesse ambiente.
3. Para cada sistema, executar N = 1, 2, 4, ..., 512 com 120 s/ponto, descartar 30 s, repetir ao menos 3 vezes, preferencialmente resetando o estado entre repetições e documentando os comandos usados.
4. Calcular medianas e variação por N, construir o gráfico **p99 × vazão efetiva** com os dois sistemas e identificar o maior valor de **vazão/p99**.
5. Confirmar ao menos dois pontos no platô e que não foi o gerador que saturou. Se não houver platô até N=512, reportar explicitamente e ampliar a faixa conforme viabilidade.

## Verificações rápidas

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
python3 -m py_compile analisar.py orquestrar.py gerador/*.py
```

Para a coleta formal: `PROCESSOS=2 RESETAR=1 ./scripts/executar_e1.sh etcd` e posteriormente Cassandra (depois de trocar de cluster e preparar as chaves). O número de processos deve ser escolhido com base na CPU do LAD e mantido comparável entre sistemas; não é obrigatório que seja 2.

**Não incluir os pilotos locais como resultados oficiais do relatório.** As métricas acima servem apenas para desenvolvimento, conferência e discussão com a dupla.
