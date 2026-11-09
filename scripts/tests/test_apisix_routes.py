"""apisix_routes: check and restore the APISIX gateway's routes in etcd (B239 finding 18).

The old seed (`routes-init.sh`, run in the gateway pod by `deploy-apisix.sh`) could not work: the gateway image has
no curl and the admin API listens only on the pod's localhost. APISIX reads its config from etcd, so the routes are
now defined here and compared against / written to etcd with `etcdctl` in the etcd pod. The desired records are
copied from the live etcd values observed 2026-11-08 (upstream 1 + routes 1-5).
"""
import json

import apisix_routes as ar

NOW = 1794200000


def _live():
    """etcd as observed 2026-11-08 (timestamps differ from what restore would write; they must be ignored)."""
    out = {}
    for key, rec in ar.desired_records(1780874578).items():
        out[key] = json.dumps(rec)
    return out


class FakeEtcd:
    def __init__(self, data):
        self.data = dict(data)
        self.puts = []

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.puts.append(key)
        self.data[key] = value


def test_desired_state_is_one_upstream_and_five_prefix_routes():
    recs = ar.desired_records(NOW)
    assert sorted(recs) == ["/apisix/routes/1", "/apisix/routes/2", "/apisix/routes/3", "/apisix/routes/4",
                            "/apisix/routes/5", "/apisix/upstreams/1"]
    assert recs["/apisix/upstreams/1"]["nodes"] == {"weyland-tool-server.weyland.svc.cluster.local:8080": 1}
    assert [recs[f"/apisix/routes/{i}"]["uri"] for i in range(1, 6)] == [
        "/context/*", "/pipeline/*", "/qdrant/*", "/weaviate/*", "/neo4j/*"]
    assert all(recs[f"/apisix/routes/{i}"]["upstream_id"] == "1" for i in range(1, 6))


def test_live_state_with_other_timestamps_is_in_sync():
    assert ar.drift(FakeEtcd(_live()).get) == []


def test_a_missing_route_is_drift():
    live = _live()
    del live["/apisix/routes/3"]
    assert ar.drift(FakeEtcd(live).get) == [("/apisix/routes/3", "missing")]


def test_a_changed_route_is_drift_and_names_the_field():
    live = _live()
    rec = json.loads(live["/apisix/routes/1"])
    rec["uri"] = "/ctx/*"
    live["/apisix/routes/1"] = json.dumps(rec)
    assert ar.drift(FakeEtcd(live).get) == [("/apisix/routes/1", "differs: uri")]


def test_unparseable_value_is_drift_not_a_crash():
    live = _live()
    live["/apisix/upstreams/1"] = "not json"
    assert ar.drift(FakeEtcd(live).get) == [("/apisix/upstreams/1", "unreadable value")]


def test_restore_writes_only_what_drifted():
    live = _live()
    del live["/apisix/routes/3"]
    etcd = FakeEtcd(live)
    written = ar.restore(etcd.get, etcd.put, NOW)
    assert written == ["/apisix/routes/3"] and etcd.puts == ["/apisix/routes/3"]
    assert ar.drift(etcd.get) == []
    assert json.loads(etcd.data["/apisix/routes/3"])["create_time"] == NOW


def test_restore_on_an_empty_etcd_writes_the_upstream_before_the_routes():
    etcd = FakeEtcd({})
    written = ar.restore(etcd.get, etcd.put, NOW)
    assert written[0] == "/apisix/upstreams/1" and len(written) == 6
    assert ar.drift(etcd.get) == []


def test_restore_when_in_sync_writes_nothing():
    etcd = FakeEtcd(_live())
    assert ar.restore(etcd.get, etcd.put, NOW) == [] and etcd.puts == []
