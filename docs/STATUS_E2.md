# E2 — Baseline: status e validação local

## Estado em 09/11/2026

**Gerador, execução multiprocesso e análise do E2 validados em pilotos locais no Mac. O E2 oficial NÃO foi executado no LAD.**

Os pilotos usaram a mesma carga fechada dos experimentos: operações aleatórias (80% GET, 20% PUT), 10.000 chaves, valores de 256 B, timeout por requisição de 2 s, sementes fixas por processo e timestamps em cada amostra. Foram usados dois processos independentes e os percentis foram calculados sobre a união das amostras na janela temporal comum, não pela média dos percentis individuais.

## Pilotos de baseline no Mac

Ambos os pilotos duraram 30 s, com aquecimento de 3 s e aproximadamente 27 s úteis. **N é provisório, obtido de observações exploratórias do E1 local, e não o N ótimo oficial do LAD.** Os arquivos foram gerados sob o rótulo `PILOTO`, portanto não constituem repetições formais do E2.

| Métrica | Cassandra | etcd |
|---|---:|---:|
| Versão da imagem observada | 4.1.12 | 3.5.21 |
| N total | 8 | 2 |
| Processos × threads | 2 × 4 | 2 × 1 |
| Repetição de piloto (identificador) | r3 | r4 |
| Tempo útil (s) | 26,999828 | 26,999917 |
| Sucessos GET | 165.411 | 53.827 |
| Sucessos PUT | 41.347 | 13.623 |
| Total de sucessos | 206.758 | 67.450 |
| Erros GET/PUT | 0 / 0 | 0 / 0 |
| Vazão total (req/s) | 7.657,7525 | 2.498,1558 |
| GET p50 (ms) | 0,9141 | 0,6250 |
| GET p95 (ms) | 1,7561 | 1,0935 |
| GET p99 (ms) | 3,6148 | 2,0794 |
| PUT p50 (ms) | 0,7813 | 0,8912 |
| PUT p95 (ms) | 1,5330 | 1,6195 |
| PUT p99 (ms) | 3,2019 | 2,9895 |

Configuração: Cassandra com RF=3 e CL=ONE para GET e PUT; etcd com leituras linearizáveis por padrão. Os dois têm topologias de três nós Docker, porém diferentes tecnologias e N diferentes. **Não utilizar esta tabela como demonstração conclusiva de qual sistema é mais rápido.** Os pilotos só comprovam que os caminhos de execução e análise produziram resultados plausíveis sem erros nas amostras observadas.

## Comandos de validação local usados

```bash
# Após subir e preparar cada cluster separadamente:
PROCESSOS=2 DURACAO=30 WARMUP=3 ./scripts/rodar_carga.sh cassandra PILOTO 8 3
PROCESSOS=2 DURACAO=30 WARMUP=3 ./scripts/rodar_carga.sh etcd PILOTO 2 4

python3 analisar.py --input gerador/resultados --output graficos
# Ver linhas GET, PUT e ALL no resumo consolidado:
grep 'PILOTO/cassandra_n8_r3.manifest' graficos/resumo_consolidado.csv
grep 'PILOTO/etcd_n2_r4.manifest' graficos/resumo_consolidado.csv
```

O arquivo `graficos/resumo_por_execucao.csv` traz estatísticas por processo; o `graficos/resumo_consolidado.csv` traz as linhas unificadas para cada repetição e deve ser usado quando `PROCESSOS > 1`.

## E2 oficial: pendências

1. Executar o **E1 no LAD** e determinar o `N_otimo` de cada sistema segundo vazão/p99, após confirmar o platô e excluir gargalo do gerador.
2. Registrar hardware, versão de Docker, configuração de disco/fsync, replicação, versão dos bancos e política de processos.
3. Executar em cada sistema **3 repetições de 180 segundos**, sem falhas e com o N ótimo daquele sistema, documentando o procedimento de limpeza entre execuções. Evitar concorrência com outros trabalhos.
4. Comparar p50, p95 e p99 de GET e PUT, taxa de erro e vazão efetiva. Calcular mediana e variação entre as repetições, não usar uma única rodada como resultado final.
5. Guardar as amostras brutas e metadados fora do Git, de forma recuperável para o relatório e a apresentação (E2 deve ser reproduzido em aula).

Exemplo de execução **após obter o N ótimo no LAD**:

```bash
# Subir/preparar um sistema por vez. Substituir N_OTIMO pelo valor real.
PROCESSOS=2 ./scripts/executar_e2_e4.sh etcd E2 N_OTIMO
PROCESSOS=2 ./scripts/executar_e2_e4.sh cassandra E2 N_OTIMO
```

O segundo comando deve ser executado somente após desligar o cluster etcd, subir e preparar o Cassandra, e usar o **N ótimo próprio do Cassandra**. `PROCESSOS=2` é uma escolha de exemplo: confirmar no LAD e padronizar a política entre os dois sistemas.

**Não incluir dados de piloto como medição oficial do relatório.**
