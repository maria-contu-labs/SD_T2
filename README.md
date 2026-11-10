# Laboratório de Consistência, Latência e Vazão

**No Mac?** Comece por `COMECE_NO_MAC.md` (pilotos locais; resultados oficiais no LAD).

**Base:** arquivos `etcd.yml`, `cassandra.yml` e scripts de `lab-compose.zip` fornecido pela professora.
**Implementação adicional:** gerador de carga, teste de stale reads, scripts de execução, orquestrador de E5/E6 e análise de dados.
**Importante:** nenhum resultado experimental está incluído ou foi inventado. Execute e registre na sua máquina.

## 0. Decisões e requisitos

- **Forte:** etcd v3.5.21, 3 nós, Raft, PUT confirmado por consenso, `range` linearizável por padrão. Chaves/valores via API HTTP v3 base64. `serializable=true` NÃO é utilizado.
- **Eventual:** Cassandra 4.1.12, 3 nós, tabela `lab.kv(k text PRIMARY KEY, v blob)`, RF=3, `SimpleStrategy`, **CL=ONE nas duas operações**. É um uso de tabela CQL como KV, conforme enunciado.
- **Tolerância a falhas:** crash-stop/temporário e partição; os programas não simulam falhas bizantinas. Modelo de tempo real com atrasos variáveis e timeout operacional de 2s (timeout não prova crash).
- **Rede:** `lab_cluster`: 172.20.0.0/24 (replicação); `lab_clientes`: 172.21.0.0/24 (clientes). E4/E5 modificam somente `lab_cluster`.
- **Carga fechada:** cada thread executa uma operação, aguarda resposta/timeout e imediatamente inicia a próxima. Uniforme em 10.000 chaves, 80% GET / 20% PUT, valores de 256 bytes, semente fixa 2026, amostras UTC e epoch, erros sem latência no CSV.
- **Timeout de requisição:** 2s no Python; as bibliotecas podem ter timeouts internos adicionais ou retry de driver. Caracterize isso no relatório.
- **Reprodutibilidade:** gerador pode virar gargalo e logging de todas as operações também gera carga. Monitorar CPU, uso de memória, rede, I/O e versão exata das imagens. Rodar os dois clusters **um por vez**.

## 1. Preparar a máquina

Instalar Docker Desktop com Compose v2, Docker em funcionamento e Python 3 no host (para `analisar.py` e `orquestrar.py`). Preferir terminal Bash no Linux/WSL2 ou Git Bash para `.sh`; `orquestrar.py` funciona via Python e CLI do Docker no host.

Reservar **pelo menos 6 GB de memória para o Docker**. Com Cassandra, a subida dos 3 nós pode demorar minutos. O comando `docker version` e `docker compose version` deve funcionar.

**No diretório `lab`:**

```bash
# Etcd: ambiente 1
./scripts/ambiente.sh etcd
# Aguardar a tabela com 3 membros saudáveis e um líder.
./scripts/preparar.sh etcd
# Confirmar exemplo rápido
 docker exec gerador python /app/carga.py etcd --threads 2 --seconds 10 --warmup 1 --output /app/resultados/piloto_etcd.csv.gz
```

Subir Cassandra **após** desligar etcd:

```bash
 docker compose -f etcd.yml down -v
 ./scripts/ambiente.sh cassandra
 # Aguardar `docker exec n1 nodetool status` mostrar n1,n2,n3 como UN.
 ./scripts/preparar.sh cassandra
 docker exec gerador python /app/carga.py cassandra --threads 2 --seconds 10 --warmup 1 --output /app/resultados/piloto_cassandra.csv.gz
```

Os resultados são salvos em `gerador/resultados/` no host. Recomenda-se mover os arquivos de cada sistema para backup antes de executar `down -v`; `down -v` não apaga os CSVs do bind mount.

## 2. E1 — Saturação

Para **cada sistema**, prepare as chaves antes de medir. Teste a sequência de N prescrita: `1,2,4,8,16,32,64,128,256,512`. Cada ponto dura **120s**, mas os **primeiros 30s são excluídos** da análise. O script executa **3 repetições** por N.

```bash
 ./scripts/executar_e1.sh etcd 1 2 4 8 16 32 64 128 256 512
```

Para um teste piloto curto, rode um N isolado manualmente (não use dados piloto no relatório final):

```bash
 docker exec gerador python /app/carga.py etcd --threads 4 --seconds 10 --warmup 1 --output /app/resultados/PILOTO/etcd_n4.csv.gz
```

Em outro terminal, monitore a CPU de processos e do gerador:

```bash
 docker stats n1 n2 n3 gerador
```

**Importante sobre o reinício do ambiente:** o apêndice recomenda ambiente limpo antes de cada execução. Para as medições formais, reinicie o cluster com `docker compose -f etcd.yml down -v`, `up --build -d`, aguarde saúde e rode `scripts/preparar.sh` antes de cada repetição. O script `executar_e1.sh` faz uma série contínua para facilitar o piloto. Para **reset automático de cada repetição do E1**, use `RESETAR=1 ./scripts/executar_e1.sh etcd ...` (muito mais demorado, sobretudo com Cassandra). Para os demais experimentos, reinicie manualmente antes de cada repetição, reaplique o netem no E4, prepare as chaves e registre tudo. Não misture séries limpas com séries contínuas sem declarar no relatório.

**Joelho:** máximo de `(mediana da vazão efetiva)/(mediana p99)`. **Platô:** ao menos dois valores sucessivos de N sem crescimento significativo da vazão, com p99 ainda crescente. Se 512 não confirmar platô, não invente um.

## 3. E2 — Baseline

Escolher, para cada sistema, o `N_otimo` do E1. Carga durante **180s**, 3 repetições.

```bash
 ./scripts/executar_e2_e4.sh etcd E2 16
```

Substitua `16` pelo seu N medido (não é um N recomendado ou esperado). Coletam-se percentis GET/PUT e vazão efetiva.

## 4. E3 — Stale reads

Coordenador executa `PUT(chave_e3, versão)` em **n1** e, **após receber sucesso**, chama `GET(chave_e3)` em **n3**. Valor da versão tem prefixo numérico crescente e 256 bytes totais. A definição é `versao_lida < ultima_versao_confirmada`. Apenas pares com PUT e GET bem-sucedidos são usados no denominador; operações com erro são registradas separadamente.

```bash
 # Rede original, 3 repetições de 10.000 pares válidos
 ./scripts/executar_e3.sh etcd original
 # Rede com atraso 50 ms por sentido (depois de aplicar E4)
 ./scripts/latencia_on.sh 50ms n1 n2 n3
 ./scripts/rtt.sh n1 172.20.0.12
 ./scripts/executar_e3.sh etcd alta
 ./scripts/latencia_off.sh n1 n2 n3
```

Repetir com Cassandra, sempre com somente um cluster ativo. Não espere obrigatoriamente observar stale no Cassandra: probabilidade e condições de replicação local podem fazer a taxa ser zero. Investigue sem fabricar anomalias. Se etcd apresentar stale confirmado, verifique se o `GET` foi realmente linearizável e se os clientes não inverteram a ordem das operações.

## 5. E4 — Latência elevada

O atraso é apenas no tráfego **entre os nós** (não no tráfego com os clientes). Se o kernel tiver `sch_netem`, o script aplica 50ms por sentido. Espere RTT entre nós de aproximadamente **100ms**, confirme com `rtt.sh`, e não prossiga se esse teste falhar.

```bash
 ./scripts/latencia_on.sh 50ms n1 n2 n3
 ./scripts/rtt.sh n1 172.20.0.12
 ./scripts/executar_e2_e4.sh etcd E4 16
 ./scripts/latencia_off.sh n1 n2 n3
```

Usar o **mesmo N do E2**, 180s por repetição, descartar os primeiros 30s. Faça `latencia_off` mesmo em caso de erro. `tc netem` pode não existir em alguns kernels de Windows/WSL2/Mac Docker Desktop. Use Linux/VM com `sch_netem` ou Toxiproxy devidamente configurado, conforme apêndice. Não substitua a verificação do RTT por mera suposição.

## 6. E5 — Partição de rede por 60s

Use o orquestrador no **host**. Ele inicia a carga, aguarda 45s, desconecta `n1` de `lab_cluster` durante 60s, reconecta com IP fixo e continua mais 75s (a execução total é 190s, incluindo margem de 10s). A rede de clientes permanece ativa.

```bash
 python orquestrar.py E5 etcd 16 --rep 1
 python orquestrar.py E5 etcd 16 --rep 2
 python orquestrar.py E5 etcd 16 --rep 3
```

Repetir com Cassandra, usando seu N ótimo. O programa guarda um `.eventos.csv` ao lado do `.csv.gz` e registra timestamps UTC para alinhas com a série de completações/erros. **Antes de confiar no E5**, conferir que n2→n3 permanece alcançável, n1→n2 fica inacessível e clientes ainda alcançam n1; o enunciado exige essas verificações. Para inspeção manual, use os scripts originais `particao.sh` / `cura.sh` e `rtt.sh`.

## 7. E6 — Matar líder e seguidor (variantes separadas)

Etcd: localizar qual nó é o líder (coluna `IS LEADER`):

```bash
 docker exec n1 etcdctl --endpoints=http://172.21.0.11:2379 endpoint status --cluster -w table
```

Passe o **nome real do líder** em `--node`, por exemplo:

```bash
 python orquestrar.py E6 etcd 16 --rep 1 --node n2
```

**Exemplo apenas:** no comando acima `n2` é hipotético; não assuma que é o líder. Depois faça outras 3 repetições matando um **seguidor** (também identifique qual é). **Não sobrescreva** os arquivos: separe em pastas/identificadores ou use repetições `4,5,6` para variante seguidor. Execute quando o cluster estiver totalmente recuperado.

No Cassandra **não há líder Raft**. Faça duas variantes documentadas: matar um nó que recebeu uma parcela importante da carga (p. ex. n1) e matar outro nó (p. ex. n3); evite chamar de líder/seguidor. O orquestrador mata o nó por 60s e o reinicia. O tempo de recuperação global pode ser zero se outros nós já estiverem servindo requisições; registre também erros por nó e o momento em que o nó reiniciado volta a aceitar operações.

## 8. Gerar estatísticas e gráficos

No host, instalar biblioteca para gráficos:

```bash
 python -m pip install matplotlib
 python analisar.py --input gerador/resultados --output graficos
```

O analisador gera, quando os dados estão presentes:

- `resumo_por_execucao.csv` — GET/PUT/ALL, p50, p95, p99, erros, vazão.
- `e1_mediana.csv` e `e1_curva.png` — uma curva por sistema, cada ponto N com mediana das repetições.
- `e2_e4_mediana.csv`, `e2_e4_get.png`, `e2_e4_put.png` — comparação de latência.
- `e3_stale.csv` — pares, erros e porcentagem de stale reads.
- Imagens de timeline do E5 e E6 — sucessos e erros por segundo, separado por nó e com marcação de eventos quando disponível.

**Para comparar sistemas no mesmo gráfico**, reúna os arquivos gerados nos dois clusters em `gerador/resultados` sem sobrescrevê-los.

## 9. O que registrar no relatório

Metadados: CPU, quantidade de núcleos, memória RAM, SSD/HDD, versão OS, Docker, imagens (etcd/Cassandra), drivers, configuração de fsync (etcd padrão; Cassandra commitlog/armazenamento padrão), RF/CL, timeout, N, duração, três repetições, CPU do gerador. Armazene logs dos comandos e screenshots `docker stats`, `endpoint status` e `nodetool status`. No E6, avalie a recuperação usando timestamps do evento e da primeira escrita bem-sucedida pertinente (cuidado: se a maioria já continuava atendendo, não houve parada global).

## 10. Fundamentação teórica

Na **2a edição (2011)** de Cachin, Guerraoui e Rodrigues, ver:

- §2.5 — Timing Assumptions; §2.7 — Distributed-System Models.
- §4.3 e §4.4 — Atomic Registers (memória compartilhada, leituras e escritas).
- §5.1–5.4 — Regular Consensus, Uniform Consensus, líder e consenso com recuperação (detectar crash, acordar decisões, persistir log).
- §6.1 — Total-Order Broadcast (ordenação consistente de operações).

**Atenção:** nesta edição, o capítulo 7 se chama *Concluding Remarks*. O enunciado cita “CGR, cap. 5 e 7”; confirme com a professora se ela usa outra numeração/referência. Não atribua CAP ao capítulo 7 sem verificar.

Documentação para verificar a semântica (links oficiais):

- https://etcd.io/docs/v3.5/learning/api_guarantees/
- https://etcd.io/docs/v3.5/install/
- https://cassandra.apache.org/doc/stable/cassandra/architecture/dynamo/
- https://cassandra.apache.org/_/download.html
- https://distributedprogramming.net/content.shtml

## 11. Restrições e verificações importantes

1. **Sem execução real aqui**: arquivos compilados/checados estaticamente, mas Docker não estava disponível no ambiente de elaboração. Execute o piloto no seu computador e ajuste problemas dependentes do sistema operacional/driver.
2. **CL=ONE não é consenso**; a maioria/quórum do Raft só está no etcd. Nem todas as diferenças medidas se devem ao modelo de consistência (cliente HTTP vs driver CQL, armazenamento, fsync, CPU, cache etc.).
3. **Não comparar em mesmo N no E1** como se fosse mesmo throughput: a comparação principal é a curva p99 × vazão efetiva.
4. **E5 e E6**: guardar timeline, não só percentis. A falha pode interromper mensagens que já estavam em trânsito; timeout não indica necessariamente que uma escrita não foi aplicada.
5. **Limpeza**: o apêndice pede reset entre execuções. Os scripts para séries grandes favorecem praticidade, então documente o método exato e, para rodadas formais, use ambiente limpo por configuração.
6. **Segurança**: serviços de laboratório sem autenticação/TLS e redes Docker fixas; não os exponha à Internet.
