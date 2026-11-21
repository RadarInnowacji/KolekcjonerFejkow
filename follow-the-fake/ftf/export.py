"""Eksport wyników: graf do Neo4j (Cypher), JSON, CSV."""
import csv
import io
import json


def _q(s):
    return json.dumps(str(s), ensure_ascii=False)


def cypher(eng, camps):
    """Skrypt Cypher: węzły Material/Campaign/Domain/Person/Tracker/IP + krawędzie SIMILAR z uzasadnieniem.
    Import: wklej w Neo4j Browser albo `cypher-shell -f graph.cypher`."""
    L = ["// Follow the Fake – eksport grafu powiązań", "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Material) REQUIRE m.id IS UNIQUE;"]
    for c in camps:
        L.append(f"MERGE (c:Campaign {{code:{_q(c['code'])}}}) SET c.name={_q(c['name'])}, c.size={c['size']}, c.cohesion={c['cohesion']};")
    for k, it in enumerate(eng.items):
        mid = eng.ids[k]
        code = f"K-{int(eng.labels[k]) + 1:03d}"
        L.append(f"MERGE (m:Material {{id:{mid}}}) SET m.title={_q(it['title'][:150])}, m.date={_q(it.get('date', ''))}, m.label={_q(it.get('label') or '')};")
        L.append(f"MATCH (m:Material {{id:{mid}}}), (c:Campaign {{code:{_q(code)}}}) MERGE (m)-[:IN_CAMPAIGN]->(c);")
        for d in it["infra"]["domains"]:
            L.append(f"MERGE (d:Domain {{name:{_q(d)}}}) WITH d MATCH (m:Material {{id:{mid}}}) MERGE (m)-[:USES_DOMAIN]->(d);")
        for p in it["entities"]["persons"]:
            L.append(f"MERGE (p:Person {{name:{_q(p)}}}) WITH p MATCH (m:Material {{id:{mid}}}) MERGE (m)-[:SHOWS_PERSON]->(p);")
        for t in it["infra"]["trackers"]:
            L.append(f"MERGE (t:Tracker {{id:{_q(t)}}}) WITH t MATCH (m:Material {{id:{mid}}}) MERGE (m)-[:HAS_TRACKER]->(t);")
        for ip in it["infra"]["ips"]:
            L.append(f"MERGE (i:IP {{addr:{_q(ip)}}}) WITH i MATCH (m:Material {{id:{mid}}}) MERGE (m)-[:HOSTED_ON]->(i);")
        for ns in it["infra"]["nameservers"]:
            L.append(f"MERGE (n:NameServer {{name:{_q(ns)}}}) WITH n MATCH (m:Material {{id:{mid}}}) MERGE (m)-[:DNS]->(n);")
    for (i, j), e in eng.edges.items():
        why = "; ".join(x["text"] for x in e["evidence"][:4])
        L.append(f"MATCH (a:Material {{id:{eng.ids[i]}}}), (b:Material {{id:{eng.ids[j]}}}) MERGE (a)-[r:SIMILAR]-(b) "
                 f"SET r.score={e['score']}, r.relation={_q(e['relation'])}, r.why={_q(why)};")
    return "\n".join(L) + "\n"


def csv_items(eng):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "kampania", "etykieta", "tytul", "data", "osoby", "tematy", "domeny", "trackery", "ip", "ns", "kompletnosc"])
    for k, it in enumerate(eng.items):
        w.writerow([eng.ids[k], f"K-{int(eng.labels[k]) + 1:03d}", it.get("label") or "", it["title"][:120], it.get("date", ""),
                    ", ".join(it["entities"]["persons"]), ", ".join(it["narrative"]["topics"]), ", ".join(it["infra"]["domains"]),
                    ", ".join(it["infra"]["trackers"]), ", ".join(it["infra"]["ips"]), ", ".join(it["infra"]["nameservers"]),
                    it["quality"]["completeness"]])
    return "﻿" + buf.getvalue()


def csv_edges(eng):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["a", "b", "wynik", "relacja", "twarde_dowody", "przeslanki"])
    for (i, j), e in sorted(eng.edges.items(), key=lambda x: -x[1]["score"]):
        w.writerow([eng.ids[i], eng.ids[j], e["score"], e["relation"], ", ".join(e["hard"]), " | ".join(x["text"] for x in e["evidence"])])
    return "﻿" + buf.getvalue()
