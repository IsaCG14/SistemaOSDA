#!/usr/bin/env python3
"""Respaldar y retirar de Neo4j documentos ausentes o eliminados en PostgreSQL.

Sin argumentos solo informa. Para modificar la réplica usar --apply.
PostgreSQL es la fuente autoritativa; el respaldo JSON se crea antes de borrar.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase


def plain(value):
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", default="/backups")
    args = parser.parse_args()

    with psycopg.connect(
        host=os.getenv("SUPABASE_DB_HOST", "supabase-db"),
        dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
        user=os.getenv("SUPABASE_DB_USER", "postgres"),
        password=os.environ["SUPABASE_DB_PASSWORD"],
        port=5432,
        connect_timeout=10,
    ) as conn:
        active_ids = {
            str(row[0])
            for row in conn.execute(
                "SELECT id FROM public.documentos WHERE eliminado_en IS NULL"
            ).fetchall()
        }

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "graphify_password")),
    )
    try:
        records = driver.execute_query(
            "MATCH (d:Documento) RETURN d.id AS id, properties(d) AS props"
        ).records
        graph_docs = {record["id"]: plain(record["props"]) for record in records}
        orphan_ids = sorted(set(graph_docs) - active_ids)
        missing_ids = sorted(active_ids - set(graph_docs))
        print(f"PostgreSQL activos: {len(active_ids)}")
        print(f"Neo4j antes: {len(graph_docs)}")
        print(f"Huérfanos a retirar: {len(orphan_ids)}")
        print(f"Activos ausentes en Neo4j: {len(missing_ids)}")
        print("Correlativos huérfanos:")
        for doc_id in orphan_ids:
            print(f"- {graph_docs[doc_id].get('correlativo', doc_id)}")

        if not args.apply:
            print("Modo diagnóstico: no se modificó Neo4j.")
            return
        if not orphan_ids:
            print("Nada que retirar.")
            return

        relationships = driver.execute_query(
            """
            MATCH (d:Documento)-[r]-(other)
            WHERE d.id IN $ids
            RETURN d.id AS documento_id, type(r) AS tipo,
                   startNode(r).id AS inicio_id, endNode(r).id AS fin_id,
                   labels(other) AS etiquetas, properties(other) AS otro_nodo,
                   properties(r) AS propiedades
            """,
            ids=orphan_ids,
        ).records
        backup = {
            "creado_en": datetime.now(timezone.utc).isoformat(),
            "documentos": [graph_docs[doc_id] for doc_id in orphan_ids],
            "relaciones": [plain(dict(record)) for record in relationships],
        }
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"graphify_huerfanos_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Respaldo creado: {backup_path}")

        driver.execute_query(
            "UNWIND $ids AS id MATCH (d:Documento {id: id}) DETACH DELETE d",
            ids=orphan_ids,
        )
        remaining = driver.execute_query("MATCH (d:Documento) RETURN count(d) AS n").records[0]["n"]
        leftovers = driver.execute_query(
            "MATCH (d:Documento) WHERE d.id IN $ids RETURN count(d) AS n", ids=orphan_ids
        ).records[0]["n"]
        if leftovers:
            raise RuntimeError(f"Quedaron {leftovers} documentos huérfanos")
        print(f"Neo4j después: {remaining}")
        print("Reconciliación verificada.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
