#!/usr/bin/env python3
"""Load the FlyWire v630 graph into the Neo4j database in .env."""

import json
import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent


def main():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    src = ROOT / "flywire-network-analysis" / "v630_data"
    neurons = pd.read_csv(src / "neurons.csv.gz")
    neurons = neurons.merge(pd.read_csv(src / "classification.csv.gz"), on="root_id")
    neurons = neurons.merge(pd.read_csv(src / "cell_stats.csv.gz"), on="root_id")
    links = pd.read_csv(src / "connections.csv.gz")
    nodes = json.loads(neurons.to_json(orient="records"))
    edges = json.loads(links.to_json(orient="records"))

    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
        session.run("MATCH (n:Neuron) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 20000 ROWS")
        session.run("CREATE CONSTRAINT neuron_root_id IF NOT EXISTS FOR (n:Neuron) REQUIRE n.root_id IS UNIQUE")
        for start in range(0, len(nodes), 5000):
            session.run("UNWIND $rows AS row CREATE (n:Neuron) SET n = row", rows=nodes[start:start + 5000])
        for start in range(0, len(edges), 5000):
            session.run(
                "UNWIND $rows AS row MATCH (a:Neuron {root_id: row.pre_root_id}) MATCH (b:Neuron {root_id: row.post_root_id}) "
                "CREATE (a)-[:SYNAPSES_IN {neuropil: row.neuropil, syn_count: row.syn_count, nt_type: row.nt_type}]->(b)",
                rows=edges[start:start + 5000],
            )
    driver.close()
    print(len(nodes), len(edges))


if __name__ == "__main__":
    main()
