# E4 — Revisão da medição com latência elevada

**Status:** três repetições para cada sistema constam no ZIP (ambiente de execução não comprovado). Falta validação oficial no LAD e correção da interpretação de rounds.

Os valores abaixo são as **medianas das três repetições existentes**, calculadas separadamente para GET, PUT e ALL a partir de `graficos/resumo_consolidado.csv`:

| Sistema | Operação | Vazão (req/s) | p50 (ms) | p99 (ms) |
|---|---|---:|---:|---:|
| etcd | GET | 9,3545 | 202,9437 | 207,0709 |
| etcd | PUT | 2,3936 | 203,8600 | 209,2136 |
| etcd | ALL | 11,7283 | 203,0049 | 207,8817 |
| Cassandra | GET | 736,2323 | 6,9395 | 32,3094 |
| Cassandra | PUT | 184,0664 | 6,6014 | 30,7154 |
| Cassandra | ALL | 920,2987 | 6,8727 | 31,8340 |

Aproximadamente 200 ms no etcd é o **resultado observado**, não prova de duas rodadas obrigatórias de consenso por requisição. Leitura linearizável usa quórum/ReadIndex e a rota via seguidor pode adicionar round-trips. A escrita Raft exige replicação e confirmação de maioria, mas não equivale a uma regra universal de `2 × RTT`. Nos dados de Cassandra, `CL=ONE` exige apenas uma confirmação, embora a escrita seja enviada às réplicas.

O script passou a salvar o ping inicial como `gerador/resultados/E4/<sistema>_rtt_inicial.log` e deixa de ignorar erros desse comando. **Ainda é necessário confirmar se o RTT observado está próximo de 100 ms**, guardar logs de `tc` e comparar com E2 do mesmo ambiente e N.
