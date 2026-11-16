# Status do trabalho — E4 (Rede com Latência Elevada)

#### Estado atual (15/11/2026)
**Execução e validação do Experimento 4 (E4) concluídas com sucesso para etcd e Cassandra em ambiente de testes.**

* Clusters Docker de 3 nós executados isoladamente: etcd 3.5.21 (líder/seguidores) e Cassandra 4.1.12 (RF=3, CL=ONE).
* Latência emulada: **50 ms por sentido** na rede interna (`lab_cluster`) via `netem`, resultando em um RTT medido inter-nós de **~100 ms** (`rtt.sh`). A rede de clientes (`lab_clientes`) permaneceu sem atraso.
* Carga fechada: 180 segundos por repetição (30 s de aquecimento descartados), 80% GET e 20% PUT sobre 10.000 chaves de 256 B, com sementes fixas e 3 repetições completas.
* Automação executada via script otimizado `./scripts/executar_e4.sh`.

---

#### Métricas agregadas do Experimento E4 (Mediana das 3 repetições)

| Sistema | N total | Condição de Rede | Vazão Efetiva (req/s) | GET p50 (ms) | GET p99 (ms) | PUT p50 (ms) | PUT p99 (ms) | Taxa de Erro |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | 2 | Latência +50ms (RTT ~100ms) | **11,73** | 202,88 | 207,45 | 203,81 | 209,21 | 0,0% |
| **Cassandra** | 8 | Latência +50ms (RTT ~100ms) | **920,30** | 6,87 | 31,83 | 6,60 | 29,80 | 0,0% |

---

#### Análise do comportamento e validação funcional

* **etcd (Consenso Raft — Consistência Forte)**:
  * A latência mediana (p50) saltou para **~203 ms** (contra <2 ms no baseline E2), e a vazão efetiva caiu para **~11,7 req/s**.
  * **Fundamentação teórica**: Para confirmar uma operação de escrita (PUT) ou leitura linearizável (GET), o líder Raft necessita enviar mensagens de proposta e receber ACKs da maioria de quórum (2 de 3 nós). Com RTT inter-nós de 100 ms, essa troca exige **duas rodadas completas de mensagens de rede ($2 \times \text{RTT} \approx 200\text{ ms}$)**.

* **Cassandra (Consistência Eventual — CL=ONE)**:
  * A latência mediana (p50) permaneceu baixa (**6,7 ms a 8,8 ms**), sustentando vazão acima de **900 req/s**.
  * **Fundamentação teórica**: Com `CL=ONE`, o nó coordenador local responde imediatamente ao cliente assim que grava na sua réplica local e envia as mutações de forma assíncrona aos outros nós, evitando bloquear a requisição nas duas rodadas de rede atrasada.

---

#### Comandos de execução e validação utilizados

```bash
# Subida, aplicação da latência (+50ms), carga e limpeza automatizada para etcd:
PROCESSOS=2 ./scripts/executar_e4.sh etcd 2

# Subida, aplicação da latência (+50ms), carga e limpeza automatizada para Cassandra:
PROCESSOS=2 ./scripts/executar_e4.sh cassandra 8

# Validação do RTT entre nós durante o teste:
./scripts/rtt.sh n1 172.20.0.12

# Consolidação dos gráficos comparativos E2 vs E4:
python3 analisar.py --input gerador/resultados --output graficos
```

---

#### O que falta para declarar E4 concluído no LAD
1. Executar os mesmos scripts no ambiente oficial do LAD utilizando o $N_{\text{ótimo}}$ definitivo determinado no E1.
2. Confirmar o RTT inter-nós via `rtt.sh` no kernel Linux do LAD antes de iniciar a medição oficial.
3. Gerar os gráficos comparativos finais `e2_e4_get.png` e `e2_e4_put.png` para inclusão no relatório.
