# E3 — Stale reads: estado atual

## Situação

**Validação funcional local concluída (macOS / Docker Desktop).** Os dados abaixo são **pilotos**, e não resultados oficiais para o relatório. A coleta no LAD, nas duas condições de rede, ainda está pendente.

## Configurações

- **etcd 3.5.21:** 3 nós, PUT no `n1`, GET linearizável (sem `serializable=true`) no `n3`, executado somente após retorno bem-sucedido do PUT.
- **Cassandra 4.1.12:** 3 nós, keyspace/tabela usados como KV, fator de replicação **RF=3**, `CL=ONE` para PUT e GET, coordenador `n1` para PUT e `n3` para GET (clientes com seleção explícita do coordenador).
- Em ambos: cada par executa PUT de versão crescente, seguido por GET; classificar como stale se `versao_lida < versao_confirmada` e ambos concluírem com sucesso.
- Os dados do teste corrigido utilizam uma **chave única por execução**, evitando interferência da sequência de versões de uma execução anterior.

## Resultados observados — rede normal, Mac

| Sistema | Execução | Pares válidos | Stale reads | Erros | Taxa |
|---|---|---:|---:|---:|---:|
| etcd | Piloto antigo | 100 | 0 | 0 | 0,0% |
| etcd | Código corrigido | 1.000 | 0 | 0 | 0,0% |
| Cassandra | Piloto antigo | 100 | 1 | 0 | 1,0% |
| Cassandra | Código corrigido | 1.000 | 3 | 0 | 0,3% |

A primeira anomalia do Cassandra, no par 7 do piloto de 100, teve `versao_confirmada=7`, `versao_lida=6`, latência GET de **8,7121 ms**. Isto é uma leitura efetivamente desatualizada, não erro de leitura.

**Cuidado metodológico:** esses pilotos têm tamanhos diferentes e alguns foram feitos antes da correção do isolamento de chave. Não agregar as taxas para inferir uma taxa estável nem afirmar que 1,0% caiu para 0,3% em razão da correção. Sem stale reads no etcd é consistente com linearizabilidade; stale reads no Cassandra é comportamento possível com `CL=ONE`. Atribuição causal final exige experimentos no LAD, documentação do cliente e confirmação das configurações.

## Validações realizadas

- [x] Subida saudável do cluster etcd e Cassandra e preparação de 10.000 chaves.
- [x] PUT em `n1` seguido de GET em `n3`, em ordem, validado em piloto.
- [x] Teste de unidade do isolamento: `python3 -m unittest discover -s tests -p 'test_stale_isolamento.py'` — OK.
- [x] Piloto corrigido de 1.000 pares sem erros nos dois sistemas.
- [x] Analisador gera `graficos/e3_stale.csv`.
- [ ] Confirmar e registrar a configuração real de rede, fsync/durabilidade e cliente no LAD.
- [ ] Emular **50 ms por sentido** no tráfego entre nós e confirmar RTT de aproximadamente **100 ms** antes de medir.
- [ ] Coletar pelo menos **10.000 pares por sistema e condição**, com **três repetições** em cada configuração.
- [ ] Comparar as taxas de stale reads nas duas condições, incluindo falhas e timeouts, e produzir resultados definitivos do relatório.

## Comandos para reproduzir os pilotos

Com o cluster correspondente iniciado e preparado:

```bash
docker exec gerador python /app/stale.py etcd --pairs 1000 \
  --output /app/resultados/PILOTO/etcd_stale_1000.csv.gz

docker exec gerador python /app/stale.py cassandra --pairs 1000 \
  --output /app/resultados/PILOTO/cassandra_stale_1000.csv.gz

python3 analisar.py --input gerador/resultados --output graficos
cat graficos/e3_stale.csv
```

Execute **apenas um cluster por vez**. O script oficial já disponível é `scripts/executar_e3.sh`, que faz 3 repetições de 10.000 pares; aplique latência somente em ambiente autorizado, monitorando erros e confirmando RTT conforme o enunciado. Dados locais permanecem fora do Git conforme `.gitignore`.

## Próximo passo

Validar a emulação de latência (E4) no LAD. Usar a mesma rede com atraso para a segunda condição do E3 e então coletar os resultados oficiais.
