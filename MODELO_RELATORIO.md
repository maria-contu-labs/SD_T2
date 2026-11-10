# Relatório de Laboratório — Consistência, Latência e Vazão

> **Modelo para preencher após executar os experimentos.** Não substitua medições por números da figura hipotética do enunciado.

## 1. Objetivo
Comparar os efeitos de modelos de consistência, latência entre réplicas, falhas de nó e partição sobre latência de operações KV, vazão efetiva, stale reads e disponibilidade.

## 2. Ambiente e reprodutibilidade
- Hardware: [CPU, núcleos, RAM, SSD/HDD]
- Sistema operacional / Docker Engine / Docker Compose: [versões]
- Containers: etcd [tag/digest], Cassandra [tag/digest], Python [tag/digest]
- Persistência: etcd [fsync padrão e storage local]; Cassandra [commitlog e disco, configurações]
- Replicação: etcd 3 membros, Raft/quórum; Cassandra RF=3, CL ONE para GET/PUT
- Rede: cluster e clientes separadas, endereços conforme apêndice
- Gerador: 80/20 GET/PUT, 10.000 chaves uniformes, 256B, seed=2026, timeout=2s, N threads, loop fechado
- Repetições: 3 por condição; preparação de dados e aquecimento declarados
- Monitoramento CPU: [prints/logs, saturação ou não]

## 3. E1 — Saturação
Inserir `graficos/e1_curva.png` e dados de `graficos/e1_mediana.csv`.
- etcd: N ótimo [ ], razão vazão/p99 [ ], vazão sustentada no platô [ ].
- Cassandra: N ótimo [ ], razão vazão/p99 [ ], vazão sustentada no platô [ ].
- Foi verificado >=2 pontos no platô? [ ]. Gerador saturou? [ ].

## 4. E2 — Baseline
Inserir tabela e percentis GET/PUT de `graficos/e2_e4_mediana.csv` para E2. Informar N de cada sistema e vazão efetiva total.

## 5. E3 — Stale reads
| Sistema | Rede | Pares válidos | Stale reads | Taxa | Erros |
|---|---|---:|---:|---:|---:|
| etcd | normal | [ ] | [ ] | [ ] | [ ] |
| etcd | +50ms/sentido | [ ] | [ ] | [ ] | [ ] |
| Cassandra | normal | [ ] | [ ] | [ ] | [ ] |
| Cassandra | +50ms/sentido | [ ] | [ ] | [ ] | [ ] |

Explicar que PUT confirmado por consenso no etcd seguido de GET linearizável não deve retornar versão antiga. No Cassandra, CL ONE para leitura/escrita não garante interseção de quóruns (`R+W=2 <= RF=3`). Distinguir valores `None`, erros e versões desatualizadas.

## 6. E4 — Rede de latência elevada
- Comandos exatos do `tc`, interface, RTT de ping normal/alterado: [ ].
- Inserir gráficos E2×E4 GET/PUT e tabela das diferenças (p50/p95/p99/vazão).
- Discutir rounds de mensagens, leader/followers no Raft e ACK de uma réplica no Cassandra (CL ONE).

## 7. E5 — Partição de rede
- Procedimento de isolar n1 por 60s, verificações de rede: [ ].
- Inserir timeline do `E5` para etcd e Cassandra.
- Lado n1 (minoria): GET/PUT [ ]; lado n2+n3: GET/PUT [ ].
- Reconciliou? [ ]; escritas confirmadas perdidas? [ ]; que evidências? [ ].
- Interpretar CAP com cuidado: disponibilidade e consistência referem-se a propriedades rigorosas, não apenas a “respondeu mais rápido”.

## 8. E6 — Failover
- Etcd: líder real no início [ ]; seguidor escolhido [ ].
- Cassandra: nós escolhidos e critério [ ].
- Linha do tempo falha→erros→retomada→reinício: [ ].
- Tempo de recuperação (métrica claramente definida): [ ].
- O cliente foi reconfigurado? [ ]; detecção de falha, eleição, reconexão: [ ].

## 9. Respostas às perguntas da professora
1. **E4** — [Comparar p99 de PUT e vazão; rounds e quorum, papel do líder.]
2. **E1** — [Identificar saturação com evidências de CPU/disco/rede e por que Raft usa líder/log.]
3. **E3** — [Comparar taxas reais nos dois níveis de latência; não inventar stale.]
4. **E5** — [Comportamento dos dois lados, CP/AP nesta configuração, reconciliação, durabilidade.]
5. **E6** — [Tempo de failover por variante e causas.]
6. **Validade** — [Diferenças de implementação e evidências das atribuições.]

## 10. Referências
- CACHIN, Christian; GUERRAOUI, Rachid; RODRIGUES, Luís. *Introduction to Reliable and Secure Distributed Programming*. 2. ed. Berlin: Springer, 2011. [§2.5, §2.7, §4.3–4.4, §5.1–5.4, §6.1].
- ETCD. *API guarantees*. https://etcd.io/docs/v3.5/learning/api_guarantees/.
- APACHE CASSANDRA. *Dynamo / Tunable Consistency*. https://cassandra.apache.org/doc/stable/cassandra/architecture/dynamo/.
