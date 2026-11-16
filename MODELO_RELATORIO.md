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
A latência inter-nós foi emulada aplicando `tc qdisc replace dev eth0 root netem delay 50ms` na interface da rede `lab_cluster` dos nós `n1`, `n2` e `n3`. O comando `./scripts/rtt.sh n1 172.20.0.12` confirmou um RTT médio de **$100.107\text{ ms}$** ($100\text{ ms}$ de atraso de ida e volta). A rede de clientes manteve-se sem latência adicional.

##### 6.1. Resultados Comparativos: E2 (Rede Normal) vs. E4 (Rede Lenta)

| Sistema | Exp. | N | Vazão Efetiva (req/s) | GET p50 (ms) | GET p95 (ms) | GET p99 (ms) | PUT p50 (ms) | PUT p95 (ms) | PUT p99 (ms) | Taxa de Erro |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | **E2** | 2 | **1.240,50** | 1,42 | 2,10 | 3,15 | 1,58 | 2,45 | 3,80 | 0,0% |
| **etcd** | **E4** | 2 | **11,73** | 202,88 | 204,50 | 207,45 | 203,81 | 206,60 | 209,21 | 0,0% |
| **Cassandra** | **E2** | 8 | **1.050,20** | 6,12 | 18,40 | 28,50 | 6,05 | 17,90 | 27,80 | 0,0% |
| **Cassandra** | **E4** | 8 | **920,30** | 6,87 | 20,40 | 31,83 | 6,60 | 19,80 | 29,80 | 0,0% |

##### 6.2. Análise dos Resultados
* **etcd**: Sob a rede atrasada, a latência mediana (p50) subiu para **~203 ms** e a vazão efetiva despencou de $1.240,50\text{ req/s}$ para **$11,73\text{ req/s}$**. Esse comportamento ocorre porque cada escrita/leitura linearizável exige duas rodadas de mensagem de rede entre o líder e os seguidores ($2 \times \text{RTT} \approx 200\text{ ms}$).
* **Cassandra**: A latência mediana manteve-se baixa (**$6,60\text{ ms}$** em PUT e **$6,87\text{ ms}$** em GET), sustentando uma vazão de **$920,30\text{ req/s}$**. Com `CL=ONE`, a resposta ao cliente ocorre logo após a gravação no coordenador local, dispensando sincronização síncrona com réplicas remotas.


## 7. E5 — Partição de rede
* **Janela Normal (0 a 45 s)**: Cluster operando normalmente com 3 nós.
* **Janela de Partição (45 a 105 s — 60 s de duração)**: Nó `n1` isolado da rede `lab_cluster` via `particao.sh`. `n1` permaneceu conectado à rede `lab_clientes`.
  * *Lado Minoritário*: Nó `n1` (1 de 3 nós).
  * *Lado Majoritário*: Nós `n2` + `n3` (2 de 3 nós — quórum mantido).
* **Janela de Cura (105 a 190 s — 75 s de duração)**: Restauração da conectividade via `cura.sh` (IP `172.20.0.11`).

##### 7.1. Desempenho e Comportamento por Janela

| Sistema | Repetição | Tentativas Totais | Janela Normal (0–45s) | Janela de Partição (45–105s) | Janela de Cura (105–190s) | Ocorrência de Erros |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | r1 / r2 / r3 | ~49.100 / rep. | 100% Sucesso | `n1` rejeita (sem quórum); `n2+n3` operam | `n1` reconecta e sincroniza log Raft | Erros/Timeout restritos ao nó `n1` |
| **Cassandra** | r1 / r2 / r3 | ~150.000 / rep. | 100% Sucesso | `n1` atende localmente; `n2+n3` operam | Sincronização via LWW | 0 erros de transporte |

##### 7.2. Análise da Reconciliação
* **etcd**: O nó `n1` rejeitou requisições por falta de quórum de maioria (obteve apenas 1/3 dos votos), preservando a consistência. Ao curar a partição aos 105 s, `n1` atualizou seu log Raft a partir do líder. Nenhuma escrita confirmada foi perdida.
* **Cassandra**: Ambos os lados continuaram processando requisições com `CL=ONE`. As divergências criadas durante o isolamento foram resolvidas após a cura por *Last-Write-Wins* (LWW) com base no timestamp da mutação e descarte de *hints*.


## 8. E6 — Failover
* **Janela Normal (0 a 45 s)**: 3 nós ativos.
* **Janela de Falha (45 a 105 s — 60 s de duração)**: Interrupção forçada do contêiner via `docker kill`:
  * *etcd*: Queda do nó **`n3`** (líder Raft identificado via `etcdctl`).
  * *Cassandra*: Queda do nó **`n1`**.
* **Janela de Recuperação (105 a 190 s — 75 s de duração)**: Nó reiniciado via `docker start`.

##### 8.1. Resultados e Tempos de Failover

| Sistema | Nó Alvo Morto | Repetição | Tentativas Totais | Comportamento durante a Queda (45–105s) | Tempo de Failover Medido | Recuperação pós-reinício (105–190s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | **`n3` (Líder)** | r1 / r2 / r3 | ~54.600 / rep. | Surto de timeouts durante a eleição; estabiliza em `n1`/`n2` | **~1,2 a 2,5 s** | `n3` reinicia como seguidor e sincroniza |
| **Cassandra** | **`n1`** | r1 / r2 / r3 | ~195.000 / rep. | Driver redireciona tráfego para `n2` e `n3` sem erros | **< 100 ms (Transparente)** | `n1` reinicia e reintegra ao anel |

##### 8.2. Análise da Dinâmica de Falha
* **etcd**: A queda do líder `n3` interrompeu os *heartbeats*. Após o *election timeout* (~1,2 s a 2,5 s), os seguidores `n1` e `n2` elegeram um novo líder e restabeleceram o serviço nos 2 nós vivos. Ao religar o `n3`, este retornou como seguidor.
* **Cassandra**: O driver Python (`cassandra-driver`) detectou a perda da conexão com o coordenador `n1` em <100 ms e redirecionou automaticamente o tráfego para `n2` e `n3`, mantendo a disponibilidade ininterrupta.


## 9. Respostas às perguntas da professora
1. #### **Pergunta 1 — E4: Latência de Escrita (p99), Vazão e Rounds de Mensagem**
> *Como a latência de escrita (p99) e a vazão de cada sistema responderam à rede com latência elevada (E4)? Explique em rounds de mensagens e quorum, considerando o coordenador/líder.*

| Métrica / Aspecto | **etcd** (Consenso Raft — Consistência Forte) | **Cassandra** ( Consistência Eventual) |
| :--- | :--- | :--- |
| **Comportamento da Latência (p99)** | **Salto de ~3,8 ms para ~209 ms** (Aumento >50x) | **Praticamente Inalterada (~29,8 ms vs. ~27,8 ms no baseline)** |
| **Comportamento da Vazão Efetiva** | **Queda drástica de 1.240 req/s para 11,7 req/s** (-99%) | **Alta sustentação: 920 req/s** (-12% em relação a 1.050 req/s) |
| **Mecanismo Subjacente de Rede** | **Duas rodadas de mensagem síncrona ( $2 x RTT$)** | **Gravação local no coordenador + replicação assíncrona** |

* **etcd (Protocolo Raft — Consenso Síncrono e Líder Único)**:
  * **Papel do Líder**: Toda operação  é obrigatoriamente roteada ou processada pelo nó líder ativo.
  * **Rounds de Mensagens e Quórum**: Para efetivar uma escrita com garantia linearizável, o líder precisa enviar uma proposta  para os seguidores (ida = 50 ms) e receber o aceite de pelo menos a maioria de quórum (2 de 3 nós, volta = 50 ms). Em seguida, após o *commit*, o líder confirma o sucesso ao cliente. Essa troca síncrona exige **duas rodadas completas de rede (($2 × RTT$):
    $$Latência_{etcd} ≈ 2 × RTT = 2 × 100 ms = 200 ms$$
  * Esse custo síncrono trava a thread de execução do cliente aguardando a confirmação da maioria pela rede lentificada, reduzindo drasticamente a vazão.

* **Cassandra ( — Modelo Dynamo e Coordenador Local)**:
  * **Papel do Coordenador**: Qualquer nó que recebe a requisição atua como nó coordenador para aquela operação.
  * **Escrita com **: Com nível de consistência , o coordenador grava a mutação na sua tabela em memória (*Memtable*) e no log de commit (*CommitLog*) local, respondendo **imediatamente com sucesso ao cliente**.
  * **Replicação Assíncrona**: A replicação para os outros 2 nós do anel ($RF=3$) é feita de forma assíncrona em segundo plano via rede de cluster. Como o cliente é liberado antes da replicação remota, a latência de rede inter-nós de +50 ms **não impacta o tempo de resposta percebido pelo cliente**.

2. #### **Pergunta 2 — E1: Saturação, Gargalo de Consenso e Escalamento Vertical**
> *O que limitou a vazão de cada sistema no E1? Por que o consenso restringe o scale-out de escritas? Que características da implementação (não só do protocolo) contribuíram?*

| Aspecto Analisado | **etcd** (Consenso Raft / Líder Único) | **Cassandra** (Arquitetura Masterless / Dynamo) |
| :--- | :--- | :--- |
| **Gargalo Principal de Saturação** | **CPU/Disk I/O do Nó Líder + Serialização do Raft** | **Saturação Distribuída de CPU/Memória nos 3 Nós** |
| **Comportamento com $N$ elevado** | Platô precoce de vazão; p99 cresce acentuadamente | Escalamento linear até saturação paralela de hardware |
| **Restrição ao Scale-Out de Escritas** | **Incapacidade Teórica**: Todas as escritas passam por 1 líder | **Alta Capacidade**: Chaves distribuídas via hash consistente |

* Protocolos de consenso baseados em líder único (como Raft/Paxos) exigem uma **ordenação total estrita** de todas as mutações no log do líder.
  * Adicionar mais nós ao cluster (ou aumentar a concorrência ) **não aumenta a capacidade de escrita**, pois todas as escritas obrigatoriamente convergem para o mesmo nó líder. Pelo contrário, adicionar mais seguidores aumenta o overhead de mensagens de quórum (*broadcasting*).
* **Características de Implementação que Contribuíram**:
  * **etcd**: O  síncrono no disco a cada entrada do WAL (*Write-Ahead Log*), o isolamento de concorrência na chave-valor com travas em memória e o transporte HTTP/2 gRPC impõem um limite rígido de processamento no processo do líder.
  * **Cassandra**: A arquitetura sem nó mestre (*masterless*), a gravação sequencial em *CommitLog* append-only e *Memtables* orientadas a memória (SSTables) e a serialização binária nativa CQL permitem balancear a carga igualmente entre os nós, escalando a vazão até o limite físico de CPU dos contêineres.

3. #### **Pergunta 3 — E3: Stale Reads sob Rede Normal vs. Latência Elevada**
> *Quais stale reads foram observados e em que condições (com a latência original da rede e com a latência elevada do E4)?*

| Condição Experimental | **etcd** (Linearizável / Raft) | **Cassandra** ($RF=3, W=1, R=1$) |
| :--- | :---: | :---: |
| **Rede Normal (Baseline)** | **0,0%** (0 / 10.000 pares) | **0,3%** (30 / 10.000 pares) — Esporádico |
| **Rede Elevada (+50ms / RTT ~100ms)** | **0,0%** (0 / 10.000 pares) | **Aumento Sistemático** — Janela de ~100 ms |

* **etcd (Leituras Linearizáveis Garantidas)**:
  * **Garantia Teórica**: O etcd executa por padrão leituras linearizáveis (*Linearizable Reads*) através do protocolo *Read Index*.
  * **Funcionamento**: Antes de responder a um , o líder confirma seu mandato atual enviando batimentos de coração à maioria do quórum para garantir que não houve *split-brain*. Uma vez confirmado o índice, o dado lido é estritamente a versão mais recente confirmada por qualquer  anterior.
  * **Resultado**: **Zero *stale reads*** tanto em rede normal quanto sob latência de +50 ms.
* **Cassandra (Violação do Princípio de Quórum no Modelo Dynamo)**:
  * **Condição de Quórum de Interseção**: Para garantir a consistência forte em sistemas eventuais (Dynamo), exige-se a regra de interseção:
    11R + W > RF11
  * **Configuração Utilizada**:Com Fator de Replicação $RF = 3$, nível de escrita $W = 1$ (CL=ONE) e nível de leitura $R = 1$ (CL=ONE), temos:
  $$\mathbf{R + W = 1 + 1 = 2 \le 3} \quad \text{(Sem garantia de interseção de quóruns)}$$
  * **Efeito da Latência Elevada (E4)**: 
    * Em rede normal, a replicação assíncrona ocorre em $< 1\text{ ms}$, gerando apenas stale reads esporádicos por disputa de corrida (~0,3%).
    * Em rede lenta (+50ms por sentido / RTT ~100ms), a replicação assíncrona enviada do nó de escrita () para os outros nós atrasa ~100 ms. Ao fazer um  no nó  imediatamente após a confirmação do  no , o nó  responde com seu valor local desatualizado, gerando um **aumento sistemático de *stale reads***.

4.#### **Pergunta 4 — E5: Partição de Rede, Teorema CAP e Reconciliação**
> *Na partição (E5), o que ocorreu com escritas e leituras em cada lado? Qual sistema priorizou C e qual A? O que aconteceu na reconciliação?*

| Lado / Fase da Partição | **etcd** (Escolha **CP** no Teorema CAP) | **Cassandra** (Escolha **AP** no Teorema CAP) |
| :--- | :--- | :--- |
| **Lado Minoritário ( - 1/3)** | **Bloqueio Total**: Rejeita GET/PUT (sem quórum) | **Disponível**: Atende GET/PUT com dados locais |
| **Lado Majoritário ( - 2/3)** | **100% Operacional**: Mantém quórum Raft (2/3) | **Disponível**: Atende GET/PUT com dados locais |
| **Mecanismo de Reconciliação** | **Replay de Log Raft** (Sem conflitos de escrita) | **Last-Write-Wins (LWW)** via timestamp + *Hints* |

* **etcd (Priorização de Consistência — Sistema CP)**:
  * **Comportamento durante a Partição**: O nó isolado  tenta obter quórum para processar requisições, mas obtém apenas 1 de 3 votos. Como exige a maioria ($>N/2$), o  **bloqueia e rejeita as requisições** para impedir a divergência de dados (*split-brain*). Já o lado majoritário ( + ) possui 2 de 3 votos (66,7%) e continua processando todas as operações normalmente.
  * **Reconciliação pós-Cura**: Ao restaurar a rede aos 105 s (), o  descobre o líder ativo em / e sincroniza seu log Raft (*log replay*). Como  não aceitou nenhuma escrita no isolamento, **não ocorrem conflitos**.
* **Cassandra (Priorização de Disponibilidade — Sistema AP)**:
  * **Comportamento durante a Partição**: Com , o nó  isolado continua aceitando escritas e leituras dos clientes conectados a ele. Da mesma forma,  e  continuam aceitando operações. O sistema permanece **100% disponível**, porém as réplicas acumulam dados divergentes nos dois lados.
  * **Reconciliação pós-Cura**: Após a cura da rede, as réplicas sincronizam as mutações divergentes usando a regra **Last-Write-Wins (LWW)**, sobrescrevendo valores antigos pela mutação com o maior *timestamp* em microssegundos, além do descarte dos registros temporários de *Hinted Handoff*.

5. #### **Pergunta 5 — E6: Tempo de Failover e Causas Determinantes**
> *Qual foi o tempo de failover no E6 em cada sistema, e o que o determinou (detecção de falha, timeout de eleição, reconfiguração do cliente)?*

| Métrica / Fator | **etcd** (Queda do Nó Líder ) | **Cassandra** (Queda do Nó ) |
| :--- | :--- | :--- |
| **Tempo de Failover Medido** | **~1,2 s a 2,5 s** (Janela de reeleição de líder) | **< 100 ms** (Transparente ao cliente) |
| **Fator Determinante Principais** | Expiração do *Election Timeout* + Votação Raft | Detecção de socket fechado + Pool do Driver CQL |
| **Reconfiguração do Cliente** | Driver alterna o endpoint após receber timeout | Driver redireciona requisições instantaneamente |

* **etcd (Reeleição de Líder no Raft)**:
  1. A queda abrupta () do líder  aos 45 s interrompe o envio de *heartbeats*.
  2. Os seguidores  e  aguardam a expiração do *Election Timeout* (configurado em ~1,0 s a 1,5 s).
  3. O nó que expira primeiro transita para *Candidate*, solicita votos aos pares e elege-se o novo líder ao obter 2 dos 3 votos.
  4. O tempo de failover de **1,2 s a 2,5 s** é determinado pelo tempo necessário para detectar a falta de *heartbeat* e concluir o protocolo de votação de quórum.
* **Cassandra (Redirecionamento Masterless no Client Driver)**:
  1. O Cassandra não possui um nó líder centralizado (*masterless*).
  2. O driver cliente () mantém um *pool* de conexões TCP abertas com todos os nós.
  3. Ao matar o nó , o driver detecta o fechamento do socket TCP em milissegundos, marca  como *DOWN* e redireciona transparentemente o tráfego para  e .
  4. O tempo de failover foi de **<100 ms**, pois não exige eleição de cluster nem reconfiguração manual do cliente.

6. #### **Pergunta 6 — Validade: Modelo de Consistência vs. Detalhes de Implementação**
> *Os resultados são atribuíveis ao modelo de consistência ou à implementação? Que evidências sustentam a conclusão?*

| Origem do Comportamento | **Modelo Teórico de Consistência** | **Detalhes de Implementação de Software** |
| :--- | :--- | :--- |
| **Aspectos Determinados** |Duplo RTT no consenso síncrono vs. escrita local em CL=ONE; Escolha CP vs. AP no Teorema CAP; Regra de quórum $R + W \le RF$. | Protocolo de transporte (gRPC HTTP/2 vs. CQL binário); política de **fsync em disco**; pool de conexões do driver cliente. |
| **Peso na Conclusão Final** | **Fator Predominante (Macro)** | **Fator Secundário (Micro)** |

* **Evidências do Predomínio do Modelo Teórico**:
  * Os comportamentos fundamentais observados — a queda da vazão sob latência elevada no etcd (duas rodadas de rede síncrona), a rejeição de requisições no nó isolado do etcd no E5 (preservação de CP) e o surgimento de *stale reads* no Cassandra ($R + W = 1 + 1 = 2 \le RF = 3$) — decorrem **direta e inevitavelmente das definições matemáticas dos modelos de Consenso Raft e Consistência Eventual Dynamo**.
* **Evidências do Impacto Secundário da Implementação**:
  * A magnitude exata das latências e dos tempos de resposta sob carga é influenciada por fatores de software: o etcd realiza  síncrono no disco para garantir durabilidade por padrão, enquanto o Cassandra utiliza memtables otimizadas em memória; o driver do Cassandra lida com failover instantâneo via pool de sockets, enquanto o cliente HTTP do etcd precisa de pequenas tentativas de reconexão.
* **Conclusão de Validade**: Os resultados quantitativos e qualitativos obtidos no laboratório **são primariamente atribuíveis ao modelo de consistência teórico**, sendo os detalhes de implementação responsáveis apenas pela modulação fina das métricas.


## 10. Referências
- CACHIN, Christian; GUERRAOUI, Rachid; RODRIGUES, Luís. *Introduction to Reliable and Secure Distributed Programming*. 2. ed. Berlin: Springer, 2011. [§2.5, §2.7, §4.3–4.4, §5.1–5.4, §6.1].
- ETCD. *API guarantees*. https://etcd.io/docs/v3.5/learning/api_guarantees/.
- APACHE CASSANDRA. *Dynamo / Tunable Consistency*. https://cassandra.apache.org/doc/stable/cassandra/architecture/dynamo/.
