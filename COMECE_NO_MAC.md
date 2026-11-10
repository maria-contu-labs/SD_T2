# Comecar no Mac (desenvolvimento, sem medições oficiais)

Este guia deixa a implementação validada no Mac. Os resultados do relatório devem ser medidos novamente no LAD, conforme solicitação da professora.

## 1. Preparacao

1. Instalar e **abrir** o Docker Desktop (https://docs.docker.com/desktop/setup/install/mac-install/).
2. Docker Desktop > Settings > Resources: disponibilizar **pelo menos 6 GB** de RAM para o Docker; Cassandra é mais pesado.
3. Extrair este ZIP e, no Terminal do macOS, entrar na pasta `lab`.
4. Verificar:

```bash
uname -m
docker --version
docker compose version
docker info --format '{{.ServerVersion}} / {{.Architecture}}'
```

`arm64` = Mac Apple Silicon; `x86_64` = Mac Intel. Docker Desktop precisa estar aberto para `docker info` funcionar.

## 2. Primeiro teste: etcd

```bash
./scripts/ambiente.sh etcd
./scripts/preparar.sh etcd
docker exec gerador python /app/carga.py etcd --threads 2 --seconds 10 --warmup 1 --output /app/resultados/piloto_etcd.csv.gz
ls -lh gerador/resultados/piloto_etcd.csv.gz
```

Os tres nos devem responder e a verificacao inicial deve mostrar um lider. O arquivo CSV compactado sera gravado no host pela pasta compartilhada `./gerador`.

Para monitorar, em outro terminal:

```bash
docker stats n1 n2 n3 gerador
```

Para parar **sem apagar os arquivos de resultados**:

```bash
docker compose -f etcd.yml down -v
```

`down -v` apaga dados dos containers/volumes, mas nao a pasta `gerador/resultados` montada no host. Nao o execute se tiver dados do cluster que precise preservar.

## 3. Segundo teste: Cassandra

Subir **um cluster por vez**. So depois do `down` do etcd:

```bash
./scripts/ambiente.sh cassandra
./scripts/preparar.sh cassandra
docker exec gerador python /app/carga.py cassandra --threads 2 --seconds 10 --warmup 1 --output /app/resultados/piloto_cassandra.csv.gz
ls -lh gerador/resultados/piloto_cassandra.csv.gz
```

Se falhar, verifique a RAM do Docker e:

```bash
docker compose -f cassandra.yml logs --tail=80
```

Algumas combinacoes de Docker VMM/virtiofs no Mac tem problemas documentados com Cassandra: https://docs.docker.com/desktop/features/vmm/. Nessa situacao, teste um gerenciador de maquina virtual diferente nas Settings do Docker Desktop, quando disponivel. Nao altere a versao da imagem para contornar isso sem documentar a mudanca.

## 4. Depois de ambos funcionarem

Rodar um piloto isolado (nao oficial) com mais threads, por exemplo 4 e 8, e validar os CSVs. Para relatorios graficos locais:

```bash
python3 -m pip install matplotlib
python3 analisar.py --input gerador/resultados --output graficos
```

Evite o teste completo E1 (horas) antes de validar os pilotos. E4 (`tc netem`) pode nao estar disponivel no kernel da maquina virtual Linux do Docker Desktop. Para E4-E6, priorizar validacao e medições completas no LAD, com permissoes apropriadas.
