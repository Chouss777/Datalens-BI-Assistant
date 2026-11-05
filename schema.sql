BEGIN;

CREATE TABLE public.filiales (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom text NOT NULL,
    ville text NOT NULL,
    region text NOT NULL,
    date_creation date NOT NULL,
    actif boolean NOT NULL DEFAULT true
);

CREATE TABLE public.employes (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom text NOT NULL,
    prenom text NOT NULL,
    poste text NOT NULL,
    filiale_id integer NOT NULL REFERENCES public.filiales(id),
    date_embauche date NOT NULL,
    salaire numeric(12, 2) NOT NULL CHECK (salaire >= 0),
    email text NOT NULL UNIQUE,
    actif boolean NOT NULL DEFAULT true,
    UNIQUE (id, filiale_id)
);

CREATE TABLE public.clients (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raison_sociale text NOT NULL,
    ice text NOT NULL UNIQUE CHECK (ice ~ '^[0-9]{15}$'),
    if_fiscal text NOT NULL UNIQUE CHECK (if_fiscal ~ '^[0-9]{8}$'),
    ville text NOT NULL,
    secteur text NOT NULL,
    date_creation date NOT NULL,
    actif boolean NOT NULL DEFAULT true
);

CREATE TABLE public.produits (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference text NOT NULL UNIQUE,
    designation text NOT NULL,
    categorie text NOT NULL,
    prix_unitaire_ht numeric(12, 2) NOT NULL CHECK (prix_unitaire_ht >= 0),
    tva_taux numeric(5, 2) NOT NULL CHECK (tva_taux BETWEEN 0 AND 100),
    actif boolean NOT NULL DEFAULT true
);

CREATE TABLE public.stocks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    produit_id integer NOT NULL REFERENCES public.produits(id),
    filiale_id integer NOT NULL REFERENCES public.filiales(id),
    quantite integer NOT NULL CHECK (quantite >= 0),
    seuil_alerte integer NOT NULL CHECK (seuil_alerte >= 0),
    date_maj timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (produit_id, filiale_id)
);

CREATE TABLE public.factures (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_facture text NOT NULL UNIQUE,
    client_id integer NOT NULL REFERENCES public.clients(id),
    filiale_id integer NOT NULL REFERENCES public.filiales(id),
    employe_id integer NOT NULL REFERENCES public.employes(id),
    date_facture date NOT NULL,
    montant_ht numeric(14, 2) NOT NULL CHECK (montant_ht >= 0),
    tva numeric(14, 2) NOT NULL CHECK (tva >= 0),
    montant_ttc numeric(14, 2) NOT NULL CHECK (montant_ttc = montant_ht + tva),
    statut text NOT NULL CHECK (statut IN ('payee', 'en_attente', 'annulee')),
    date_paiement date,
    FOREIGN KEY (employe_id, filiale_id) REFERENCES public.employes(id, filiale_id),
    CHECK ((statut = 'payee') = (date_paiement IS NOT NULL)),
    CHECK (date_paiement >= date_facture)
);

CREATE TABLE public.lignes_facture (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facture_id integer NOT NULL REFERENCES public.factures(id),
    produit_id integer NOT NULL REFERENCES public.produits(id),
    quantite integer NOT NULL CHECK (quantite > 0),
    prix_unitaire numeric(12, 2) NOT NULL CHECK (prix_unitaire >= 0),
    montant_ligne numeric(14, 2) GENERATED ALWAYS AS (quantite * prix_unitaire) STORED
);

CREATE INDEX factures_date_facture_idx ON public.factures (date_facture);
CREATE INDEX factures_filiale_id_idx ON public.factures (filiale_id);
CREATE INDEX factures_client_id_idx ON public.factures (client_id);
CREATE INDEX lignes_facture_facture_id_idx ON public.lignes_facture (facture_id);

CREATE VIEW public.employes_public AS
SELECT id, nom, prenom, poste, filiale_id, date_embauche, actif
FROM public.employes;

COMMIT;
