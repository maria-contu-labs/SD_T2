"""Adaptadores finos. As operações são equivalentes para etcd e Cassandra."""
import base64
import threading

NODES = {"n1": "172.21.0.11", "n2": "172.21.0.12", "n3": "172.21.0.13"}


class Etcd:
    def __init__(self, timeout=2.0):
        self.timeout = timeout
        self.local = threading.local()

    def _session(self):
        import requests
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
        return self.local.session

    @staticmethod
    def _b(data):
        return base64.b64encode(data).decode("ascii")

    def execute(self, node, op, key, value=None):
        url = f"http://{NODES[node]}:2379/v3/kv"
        if op == "PUT":
            path, payload = "/put", {"key": self._b(key), "value": self._b(value)}
        elif op == "GET":
            path, payload = "/range", {"key": self._b(key)}  # SEM serializable=true
        else:
            raise ValueError(op)
        r = self._session().post(url + path, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        if op == "PUT":
            return None
        rows = data.get("kvs", [])
        return base64.b64decode(rows[0]["value"]) if rows else None

    def close(self):
        pass  # cada worker tem sua Session HTTP; processo termina ao fim da medicao


class Cassandra:
    """CL=ONE, RF=3. Cada Session fica restrita a um nó coordenador."""
    def __init__(self, timeout=2.0):
        from cassandra import ConsistencyLevel
        from cassandra.cluster import Cluster
        from cassandra.policies import HostFilterPolicy, RoundRobinPolicy
        from cassandra.query import SimpleStatement
        self.sessions = {}
        self.clusters = []
        self.timeout = timeout
        for node, address in NODES.items():
            policy = HostFilterPolicy(RoundRobinPolicy(), lambda host, target=address: host.address == target)
            cluster = Cluster([address], load_balancing_policy=policy, protocol_version=4,
                              connect_timeout=10, control_connection_timeout=10)
            self.clusters.append(cluster)
            self.sessions[node] = cluster.connect("lab")
        self.put_stmt = SimpleStatement(
            "INSERT INTO kv (k, v) VALUES (%s, %s)",
            consistency_level=ConsistencyLevel.ONE)
        self.get_stmt = SimpleStatement(
            "SELECT v FROM kv WHERE k = %s",
            consistency_level=ConsistencyLevel.ONE)

    def execute(self, node, op, key, value=None):
        session = self.sessions[node]
        k = key.decode("ascii")
        if op == "PUT":
            session.execute(self.put_stmt, (k, value), timeout=self.timeout)
            return None
        if op == "GET":
            row = session.execute(self.get_stmt, (k,), timeout=self.timeout).one()
            return bytes(row.v) if row and row.v is not None else None
        raise ValueError(op)

    def close(self):
        for cluster in self.clusters:
            cluster.shutdown()


def create_adapter(system, timeout=2.0):
    if system == "etcd":
        return Etcd(timeout)
    if system == "cassandra":
        return Cassandra(timeout)
    raise ValueError(f"Sistema nao suportado: {system}")
