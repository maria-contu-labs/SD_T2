# Laboratório de Consistência — etcd × Cassandra

Código para os experimentos E1–E6 da disciplina de Sistemas Distribuídos.

**Status:** E1/E2/E3 possuem pilotos de desenvolvimento; E4/E5/E6 possuem registros de teste no pacote original, mas o código e a interpretação desses experimentos ainda precisam ser corrigidos e validados no LAD. Consulte `REVISAO_TECNICA.md` antes de apresentar conclusões.

## Pré-requisitos

Docker Engine + Compose v2, Python 3.12+, memória suficiente para três nós Cassandra e permissão para administrar redes Docker. Executar no nó/VM autorizado do LAD; não lançar contêineres no nó de login de um cluster com scheduler sem autorização.

## Primeira validação

```bash
./scripts/ambiente.sh etcd
./scripts/preparar.sh etcd
PROCESSOS=2 DURACAO=30 WARMUP=3 ./scripts/rodar_carga.sh etcd PILOTO 2 1
python3 analisar.py --input gerador/resultados --output graficos
```

Depois encerrar (`docker compose -f etcd.yml down -v`) antes de subir Cassandra. `E1` e `E2` exigem o N ótimo coletado **no LAD**, não o N dos pilotos de Mac.

## Scripts

- `scripts/executar_e1.sh`: saturação, requer três repetições por N e checagem do platô.
- `scripts/executar_e2_e4.sh`: baseline, requer N ótimo do E1.
- `scripts/executar_e3.sh`: leituras desatualizadas, precisa ser repetido para rede normal e elevada.
- `scripts/executar_e4.sh`: atraso entre nós, validar RTT e manter prova de ping.
- `scripts/executar_e5.sh`: partição de rede; **a verificação pós-cura ainda não está implementada**.
- `scripts/executar_e6.sh`: falha de nó; **a variante seguidor e o failover do cliente Cassandra ainda estão pendentes**.

Os dados brutos não devem ser apagados: armazená-los em pacote/armazenamento separado e preservá-los com metadados de configuração. `.gitignore` impede apenas novos arquivos não rastreados de entrarem no Git; para retirar arquivos já versionados, usar `git rm --cached` com cautela.
