# E5 — Revisão da partição de rede

**Estado:** dados de três repetições por sistema presentes no ZIP; interpretação qualitativa plausível, mas comprovação de convergência pendente.

Resultados brutos de sucesso/erro por repetição (190 s):

| Sistema | r1 | r2 | r3 |
|---|---:|---:|---:|
| etcd | 48.282 / 76 | 49.381 / 74 | 49.374 / 72 |
| Cassandra | 122.472 / 0 | 164.109 / 0 | 155.591 / 0 |

Em E5 r1, durante a partição: Cassandra concluiu 12.650 operações em n1 e aproximadamente 12.645 em cada um dos outros nós sem erros. O etcd apresentou 60 erros em n1, nenhum em n2 e n3 nessa janela. Os 6 sucessos de n1 registrados na janela nominal exigem atenção ao instante de corte real: `orquestrar.py` escreve o evento **antes** de executar o comando de desconexão.

**Não afirmar que todas as réplicas convergiram ou que nenhuma escrita confirmada foi perdida sem validação pós-cura de valores/versões.** Last-write-wins, hints e Raft explicam a possibilidade de recuperação, mas precisam de evidência experimental.

Falta: comparar leituras de todas as réplicas após a cura; verificar escritas confirmadas, registrar possíveis valores divergentes e tempo de reconvergência; uniformizar processos e CPU com E2; repetir no LAD com N ótimo oficial.
