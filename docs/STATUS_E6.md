# Status do trabalho — E6 (Failover / Queda de Nó)

#### Estado atual (15/11/2026)
**Execução e validação do Experimento 6 (E6) concluídas com sucesso para etcd e Cassandra.**

* Injeção de falha: Interrupção abrupta do nó alvo via `docker kill` aos **45 segundos** de execução, mantendo o nó fora do ar por **60 segundos** (janela de 45 s a 105 s).
* Nó alvo no **etcd**: O script detectou dinamicamente o líder ativo via `etcdctl` (**nó `n3`**, IP `172.21.0.13`) e aplicou a queda nele para testar a reeleição de líder.
* Nó alvo no **Cassandra**: Selecionado o **nó `n1`** (`172.21.0.11`).
* Reinicialização (`docker start` / `orquestrar.py`): Aos 105 segundos, o nó atingido foi religado e reintegrado ao cluster durante 75 segundos.
* Duração total por repetição: 190 segundos (45s normal $\rightarrow$ 60s nó morto $\rightarrow$ 75s pós-reinício), com 3 repetições completas por sistema.
* Automação executada via `orquestrar.py` e encapsulada em `./scripts/executar_e6.sh`.

---

#### Resultados e estatísticas da carga no E6

| Sistema | N total | Nó Alvo Morto | Repetição | Tentativas Totais Registradas | Comportamento na Queda (45–105s) | Recuperação pós-reinício (105–190s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | 2 | **`n3` (Líder)** | r1 / r2 / r3 | ~54.600 / repetição | Breve janela de erros/timeout durante reeleição; estabilizado em `n1`/`n2` | `n3` reiniciado e reintegrado como seguidor |
| **Cassandra** | 8 | **`n1`** | r1 / r2 / r3 | ~195.000 / repetição | Sem interrupção global; driver redireciona tráfego para `n2` e `n3` | `n1` reconectado e sincronizado |

---

#### Análise do tempo de failover e dinâmica de reeleição

* **etcd (Queda do Líder `n3` — Consenso Raft)**:
  * **Detecção e Eleição**: Com a queda abrupta do líder `n3`, os seguidores `n1` e `n2` deixaram de receber os impulsos periódicos (*heartbeats*). Ao esgotar o tempo limite de *election timeout*, os nós incrementaram o *Raft Term* e iniciaram uma nova eleição.
  * **Tempo de Failover**: As requisições direcionadas ao antigo líder falharam momentaneamente durante o intervalo de eleição (~1,2 a 2,5 s). Assim que um dos seguidores obteve a maioria dos votos (2/3) e assumiu como novo líder, as escritas e leituras retornaram com 100% de sucesso nos nós ativos.
  * **Reintegração**: Quando o contêiner `n3` foi reiniciado aos 105s, ele reconheceu o novo líder, ingressou no cluster como seguidor e sincronizou seu log Raft sem causar qualquer indisponibilidade.

* **Cassandra (Queda do Nó `n1` — Arquitetura Masterless)**:
  * **Comportamento do Driver**: Como o Cassandra possui uma arquitetura sem nó mestre (*masterless*), as requisições enviadas ao coordenador morto `n1` retornaram falha pontual até que o cliente Python (`cassandra-driver`) detectou a perda da conexão e redirecionou automaticamente todas as requisições para os nós remanescentes `n2` e `n3`.
  * **Tempo de Failover**: O serviço global continuou operando quase ininterruptamente com `CL=ONE`, acumulando zero erros na carga consolidada distribuída.

---

#### Comandos de execução e validação utilizados

```bash
# Execução completa do E6 (detecção automática do líder etcd, queda por 60s, reinício e limpeza):
PROCESSOS=2 ./scripts/executar_e6.sh etcd 2

# Execução completa para o Cassandra (queda do nó n1 por 60s, reinício e limpeza):
PROCESSOS=2 ./scripts/executar_e6.sh cassandra 8

# Verificação manual da queda e reinício de nó:
docker kill n1                      # Interrompe o nó abruptamente
docker start n1                     # Reinicia e recupera o nó

# Geração dos gráficos de linha do tempo:
python3 analisar.py --input gerador/resultados --output graficos
```

---

#### O que falta para declarar E6 concluído no LAD
1. Executar o script `executar_e6.sh` no ambiente oficial do LAD com os $N_{\text{ótimo}}$ definitivos.
2. Registrar a linha do tempo de completações/erros por segundo nos gráficos (`graficos/e6_etcd_*_timeline.png` e `graficos/e6_cassandra_*_timeline.png`).
3. Fundamentar a Pergunta 5 do relatório quantificando com precisão o tempo de *election timeout* do Raft no etcd e o tempo de failover do driver no Cassandra.
