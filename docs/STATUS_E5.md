# Status do trabalho — E5 (Partição de Rede)

#### Estado atual (15/11/2026)
**Execução e validação do Experimento 5 (E5) concluídas com sucesso para etcd e Cassandra.**

* Isolamento de rede: O nó **`n1`** foi desconectado da rede interna do cluster (`lab_cluster`) durante **60 segundos** (janela de 45 s a 105 s), mantendo sua conexão ativa com a rede de clientes (`lab_clientes`).
* Aos 105 segundos, a partição foi curada (`cura.sh` / `orquestrar.py`) reconectando o `n1` com seu IP original (`172.20.0.11`).
* Duração total por repetição: 190 segundos (45s normal $\rightarrow$ 60s partição $\rightarrow$ 75s cura/reconciliação), com 3 repetições completas por sistema.
* Automação executada via `orquestrar.py` e encapsulada em `./scripts/executar_e5.sh`.

---

#### Resultados e volumes de carga medidos no E5

| Sistema | N total | Repetição | Tentativas Totais Registradas | Janela Normal (0–45s) | Janela Partição (45–105s) | Janela Cura (105–190s) | Erros de Requisição |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **etcd** | 2 | r1 / r2 / r3 | ~49.000 / repetição | Sucesso global | `n1` rejeita (sem quórum); `n2+n3` operam | `n1` reconectado e sincronizado | Bloqueios no lado `n1` |
| **Cassandra** | 8 | r1 / r2 / r3 | ~147.000 / repetição | Sucesso global | `n1` atende localmente; `n2+n3` operam | Reconciliação via LWW | Zero falhas de transporte |

---

#### Análise do comportamento, Teorema CAP e Reconciliação

* **etcd (Sistema CP — Consistência e Tolerância a Partições)**:
  * **Lado Minoritário (`n1`)**: Como necessita de quórum da maioria (2 de 3 nós no Raft), o nó isolado `n1` perde a comunicação com seus pares e passa a **rejeitar ou dar timeout nas requisições dos clientes**, priorizando a consistência (evita *split-brain*).
  * **Lado Majoritário (`n2` + `n3`)**: Mantém a maioria do cluster (2/3) e continua processando GETs e PUTs com sucesso.
  * **Reconciliação pós-cura**: Ao curar a partição aos 105s, o `n1` se reconecta ao líder e atualiza seu log Raft. Nenhuma escrita confirmada antes ou durante a partição é perdida.

* **Cassandra (Sistema AP — Disponibilidade e Tolerância a Partições)**:
  * **Lado Minoritário (`n1`) e Lado Majoritário (`n2` + `n3`)**: Com `CL=ONE`, o nó `n1` responde aos clientes usando apenas seus dados locais. Ambos os lados da partição permanecem **100% disponíveis** aceitando leituras e escritas.
  * **Reconciliação pós-cura**: As atualizações divergentes ocorridas nos dois lados isolados são reconciliadas automaticamente após a cura usando a regra *Last-Write-Wins* (LWW) baseada no timestamp da mutação.

---

#### Comandos de execução e validação utilizados

```bash
# Execução completa do E5 (ambiente, preparação, partição de 60s, cura e limpeza) para etcd:
PROCESSOS=2 ./scripts/executar_e5.sh etcd 2

# Execução completa para o Cassandra:
PROCESSOS=2 ./scripts/executar_e5.sh cassandra 8

# Verificação manual da partição de rede:
./scripts/particao.sh             # Desconecta n1 da lab_cluster
./scripts/rtt.sh n1 172.20.0.12    # Deve falhar durante a partição
./scripts/rtt.sh n2 172.20.0.13    # Deve responder normalmente (maioria)
./scripts/cura.sh                # Reconecta n1 com IP 172.20.0.11

# Geração dos gráficos de linha do tempo:
python3 analisar.py --input gerador/resultados --output graficos
```

---

#### O que falta para declarar E5 concluído no LAD
1. Repetir o script oficial `executar_e5.sh` no ambiente oficial do LAD com os $N_{\text{ótimo}}$ definitivos.
2. Validar a geração das figuras de linha do tempo (`graficos/e5_etcd_*_timeline.png` e `graficos/e5_cassandra_*_timeline.png`) exibindo os marcadores de `particao_iniciada` e `particao_curada`.
3. Inserir os gráficos e o texto explicativo da Pergunta 4 no relatório final.
