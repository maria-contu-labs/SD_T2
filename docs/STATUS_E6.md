# E6 — Revisão dos resultados (16/11/2026)

**Estado: execuções preliminares existentes; interpretação precisa ser corrigida. E6 não está concluído para entrega.**

O ZIP possui três arquivos de repetição para etcd (queda documentada do líder n3) e Cassandra (queda de n1), cada um com janela de 190 s e eventos de desligamento/reinício após ~45/~105 s.

## Contagens reais de sucessos / erros, todas as operações

| Sistema | r1 | r2 | r3 |
|---|---:|---:|---:|
| etcd | 54.172 / 85 | 54.388 / 94 | 55.066 / 91 |
| Cassandra | 110.850 / 45.523 | 145.233 / 57.662 | 162.808 / 63.642 |

No Cassandra, a taxa geral de erros variou entre **28,10% e 29,11%** nas repetições. Na r1, durante a falha, 21.454 operações destinadas a n1 falharam; após religar n1, outras 24.069 operações direcionadas a ele falharam. Os nós n2 e n3 continuaram recebendo operações bem-sucedidas. O erro predominante foi `NoHostAvailable`.

A explicação mais provável está em `gerador/clientes.py`: sessões Cassandra foram construídas com `HostFilterPolicy` apontando para um host, **sem failover transparente dessa sessão**. Não afirmar failover `<100ms` nem 0 erros; não existe tempo de failover validado nos dados apresentados.

## Pendências obrigatórias

1. Executar variante **(b) falha de seguidor** no etcd (e documentar variante alternativa no Cassandra), repetida três vezes; identificar papel do alvo em cada rodada.
2. Separar client Cassandra fixo (útil em E3/E5) de cliente tolerante a falha em E6 e documentar como muda a semântica das requisições.
3. Quantificar intervalo entre falha e recuperação de PUTs por destino com eventos sincronizados, distinguindo sucesso em nós remanescentes de redirecionamento efetivo.
4. Corrigir reconexão depois da reinicialização, executar novamente e guardar logs/CPU.
5. Refazer no LAD após determinar N ótimo no E1.
