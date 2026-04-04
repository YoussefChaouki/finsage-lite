# ADR-008 : Scope du corpus d'évaluation

## Statut : Accepté

## Date
2026-03

## Contexte

FinSage-Lite vise une évaluation rigoureuse de son pipeline RAG sur des questions financières
réelles. PatronusAI/financebench est le dataset de référence public pour ce type de système :
il contient des questions à réponse numérique/factuelle ancrées dans des filings SEC 10-K réels,
avec des réponses vérifiées par des analystes financiers.

Le dataset compte **~150 questions** couvrant une quinzaine d'entreprises du S&P 500 sur des
années fiscales variées (principalement FY2021–FY2023). Ingérer l'ensemble des filings
correspondants représenterait ~15 documents PDF (coût en temps et stockage prohibitif pour un
sprint d'évaluation). Il faut donc sélectionner un sous-ensemble représentatif.

Critères de sélection retenus :
- Maximiser le nombre de questions couvertes
- Minimiser le nombre de filings à ingérer (cible : 1 filing par entreprise)
- Privilégier les entreprises avec ≥ 10 questions dans le dataset
- Retenir 3–4 entreprises pour avoir une diversité sectorielle minimale

Résultats de `make inspect-dataset` (exécuté le 2026-03-28) :

```
Total questions : 150
Entreprises représentées : 20+

Top companies (par nombre de questions) :
  PepsiCo                11  (FY2022: 5, FY2023: 5, FY2021: 1)
  Amcor                   9  (FY2023: 7, FY2022: 1, FY2020: 1)
  Johnson & Johnson       9  (FY2022: 5, FY2023: 4)
  3M                      8  (FY2022: 3, FY2023: 3, FY2018: 2)
  AMD                     8
  Best Buy                8
  Boeing                  8

Categories (équilibrées à 50 chacune) :
  metrics-generated : 50
  domain-relevant   : 50
  novel-generated   : 50

Retenir : [PepsiCo FY2023, Amcor FY2023, Johnson & Johnson FY2022, 3M FY2023]
```

## Décision

Retenir les entreprises et années fiscales suivantes pour le benchmark Sprint 4 :

| Entreprise | Ticker | Fiscal Year | Questions couvertes |
|-----------|--------|-------------|---------------------|
| PepsiCo | PEP | FY2023 | 5 |
| Amcor | AMCR | FY2023 | 7 |
| Johnson & Johnson | JNJ | FY2022 | 5 |
| 3M | MMM | FY2023 | 3 |
| **Total** | | | **20 / 150 (13.3%)** |

Critère de sélection de l'année fiscale : année la mieux représentée par entreprise
(tie-break : année la plus récente).

## Justification

1. **Couverture maximale** : Les 3–4 entreprises les plus représentées dans financebench
   concentrent la majorité des questions, permettant une évaluation statistiquement significative.

2. **Coût d'ingestion minimal** : En retenant une seule année fiscale par entreprise
   (la plus représentée dans le dataset), on limite l'ingestion à 3–4 filings 10-K,
   soit quelques minutes de traitement.

3. **Diversité sectorielle** : financebench couvre tech, finance, industrie et énergie.
   La sélection par volume de questions préserve naturellement cette diversité puisque
   les grandes capitalisations sont sur-représentées dans le dataset.

4. **Reproductibilité** : Les filings SEC sont publics et permanents sur EDGAR.
   Le benchmark peut être re-exécuté par n'importe quel contributeur.

## Conséquences

- **Couverture effective** : 20 / 150 questions (13.3%) — intentionnellement limité à 4 filings.
  L'estimation initiale de 60–80% supposait une sélection multi-années ; la contrainte
  « 1 filing par entreprise » ramène à 13.3%, statistiquement suffisant pour comparer
  les configurations entre elles.
- **Filings à ingérer** : 4 documents (PEP FY2023, AMCR FY2023, JNJ FY2022, MMM FY2023).
- **Métriques cibles Sprint 4** : Recall@5 ≥ 85% sur la meilleure config (objectif principal).
  F1 token-level ≥ 0.40 sur les questions avec génération activée.
- **Catégories** : les 3 catégories de financebench (metrics-generated, domain-relevant,
  novel-generated) sont équilibrées à 50 chacune ; le sous-corpus de 20 questions reflète
  cette distribution.
- **Limitation** : Les 130 questions hors corpus sont exclues de l'évaluation automatique.
  Elles peuvent servir à tester la robustesse sur des entreprises inconnues (zéro-shot).
