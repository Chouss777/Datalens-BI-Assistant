"""Seed an empty ERP database and optionally configure the application reader."""

import argparse
import os
import random
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import psycopg2
from faker import Faker
from psycopg2 import sql
from psycopg2.extras import execute_values

from config import db_settings, load_semantic_layer

BRANCHES = (
    ("Casablanca", "Casablanca-Settat"),
    ("Rabat", "Rabat-Salé-Kénitra"),
    ("Marrakech", "Marrakech-Safi"),
    ("Tanger", "Tanger-Tétouan-Al Hoceïma"),
    ("Fès", "Fès-Meknès"),
)
PRODUCTS = {
    "Informatique": ("Écran", "Clavier", "Souris", "Station d'accueil", "Disque SSD"),
    "Bureautique": ("Imprimante", "Toner", "Ramette A4", "Agrafeuse", "Chemise cartonnée"),
    "Mobilier": ("Bureau", "Chaise", "Armoire", "Table de réunion", "Caisson"),
    "Réseau": ("Routeur", "Switch", "Point d'accès", "Câble Ethernet", "Onduleur"),
}
SECTORS = ("Commerce", "Industrie", "Services", "BTP", "Logistique", "Hôtellerie")
READER = "bi_reader"


def insert_rows(cursor, table, columns, rows, *, return_ids=False):
    statement = sql.SQL("INSERT INTO public.{} ({}) VALUES %s").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    if return_ids:
        statement += sql.SQL(" RETURNING id")
    result = execute_values(cursor, statement, rows, fetch=return_ids)
    return [row[0] for row in result] if return_ids else None


def configure_reader(cursor, password):
    cursor.execute("SELECT current_user = %s", (READER,))
    if cursor.fetchone()[0]:
        raise ValueError("Le compte d’administration doit être distinct de bi_reader.")

    role = sql.Identifier(READER)
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READER,))
    action = sql.SQL("ALTER ROLE") if cursor.fetchone() else sql.SQL("CREATE ROLE")
    cursor.execute(
        sql.SQL("{} {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD %s").format(action, role),
        (password,),
    )
    cursor.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(role))
    cursor.execute(sql.SQL("ALTER ROLE {} SET search_path = pg_catalog").format(role))
    cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    cursor.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role))
    for table, columns in load_semantic_layer()["schema"].items():
        cursor.execute(
            sql.SQL("GRANT SELECT ({}) ON TABLE public.{} TO {}").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(table), role
            )
        )


def seed(cursor, random_seed):
    rng = random.Random(random_seed)
    fake = Faker("fr_FR")
    fake.seed_instance(random_seed)
    cursor.execute("SELECT CURRENT_DATE")
    today = cursor.fetchone()[0]
    first_invoice_date = date(today.year - 1, 1, 1)

    branch_ids = insert_rows(cursor, "filiales", ("nom", "ville", "region", "date_creation"), [
        (f"Agence {city}", city, region, date(2014 + index, 1, 15))
        for index, (city, region) in enumerate(BRANCHES)
    ], return_ids=True)

    branch_employees = {}
    for branch_id in branch_ids:
        employees = [
            (fake.last_name(), fake.first_name(), job, branch_id,
             date(today.year - 4, 1, 1) + timedelta(days=rng.randrange(730)),
             rng.randrange(5000, 22000), f"e{branch_id}-{index}@example.test", True)
            for index, job in enumerate(("Responsable d’agence", "Commercial", "Comptable"), 1)
        ]
        branch_employees[branch_id] = insert_rows(
            cursor, "employes",
            ("nom", "prenom", "poste", "filiale_id", "date_embauche", "salaire", "email", "actif"),
            employees, return_ids=True,
        )

    client_ids = insert_rows(
        cursor, "clients", ("raison_sociale", "ice", "if_fiscal", "ville", "secteur", "date_creation", "actif"),
        [(f"{fake.company()} Maroc {index:02d}", f"{index:015d}", f"{index:08d}",
          rng.choice(BRANCHES)[0], rng.choice(SECTORS),
          first_invoice_date - timedelta(days=rng.randrange(365, 1461)), index % 11 != 0)
         for index in range(1, 31)],
        return_ids=True,
    )

    products = [
        (f"PRD-{category_index:02d}-{item_index:02d}", item, category,
         Decimal(rng.randrange(2_500, 750_001)).scaleb(-2), rng.choice((10, 20)), True)
        for category_index, (category, items) in enumerate(PRODUCTS.items(), 1)
        for item_index, item in enumerate(items, 1)
    ]
    product_ids = insert_rows(
        cursor, "produits", ("reference", "designation", "categorie", "prix_unitaire_ht", "tva_taux", "actif"),
        products, return_ids=True,
    )
    catalog = [(product_id, row[3], row[4]) for product_id, row in zip(product_ids, products)]
    insert_rows(cursor, "stocks", ("produit_id", "filiale_id", "quantite", "seuil_alerte"), [
        (product_id, branch_id, rng.randrange(151), rng.randrange(8, 26))
        for branch_id in branch_ids for product_id in product_ids
    ])

    invoices, invoice_lines = [], []
    for index in range(1, 201):
        invoice_date = first_invoice_date + timedelta(
            days=rng.randrange((today - first_invoice_date).days + 1)
        )
        branch_id = rng.choice(branch_ids)
        status = rng.choices(("payee", "en_attente", "annulee"), weights=(72, 22, 6))[0]
        payment_date = min(today, invoice_date + timedelta(days=rng.randrange(1, 61))) if status == "payee" else None
        net = tax = Decimal("0.00")
        lines = []
        for product_id, price, tax_rate in rng.sample(catalog, 2):
            quantity = rng.randint(1, 12)
            line_net = price * quantity
            net += line_net
            tax += (line_net * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append((product_id, quantity, price))
        invoices.append((
            f"DEMO-{invoice_date.year}-{index:04d}", rng.choice(client_ids), branch_id,
            rng.choice(branch_employees[branch_id]), invoice_date, net, tax, net + tax, status, payment_date,
        ))
        invoice_lines.append(lines)

    invoice_ids = insert_rows(
        cursor, "factures",
        ("numero_facture", "client_id", "filiale_id", "employe_id", "date_facture",
         "montant_ht", "tva", "montant_ttc", "statut", "date_paiement"),
        invoices, return_ids=True,
    )
    insert_rows(cursor, "lignes_facture", ("facture_id", "produit_id", "quantite", "prix_unitaire"), [
        (invoice_id, *line) for invoice_id, lines in zip(invoice_ids, invoice_lines) for line in lines
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--provision-reader", action="store_true",
                        help="Configure bi_reader using BI_READER_PASSWORD.")
    parser.add_argument("--enable-vector", action="store_true",
                        help="Enable the vector extension on a pgvector PostgreSQL server.")
    args = parser.parse_args()
    password = os.getenv("BI_READER_PASSWORD")
    if args.provision_reader and not password:
        parser.error("BI_READER_PASSWORD doit être défini avec --provision-reader.")

    settings = db_settings()
    with closing(psycopg2.connect(**settings)) as connection, connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(769205147)")
        if args.enable_vector:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if args.provision_reader:
            configure_reader(cursor, password)
        for table in ("filiales", "employes", "clients", "produits", "stocks", "factures", "lignes_facture"):
            cursor.execute(sql.SQL("SELECT 1 FROM public.{} LIMIT 1").format(sql.Identifier(table)))
            if cursor.fetchone():
                print("Base déjà peuplée. Aucun jeu de démonstration ajouté.")
                break
        else:
            seed(cursor, args.seed)
            print("Données ajoutées (5 filiales, 15 employés, 30 clients, 20 produits, "
                  "100 stocks, 200 factures, 400 lignes).")


if __name__ == "__main__":
    main()
