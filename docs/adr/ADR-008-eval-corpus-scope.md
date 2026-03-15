# ADR-008 : Scope du corpus d'évaluation

## Statut : Accepté

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

Résultats de `make inspect-dataset` (à compléter après première exécution) :

```
# Résumé à coller ici après avoir lancé le script
# Retenir : [COMPANY_A FY20XX, COMPANY_B FY20XX, ...]
```

## Décision

Retenir les entreprises et années fiscales suivantes pour le benchmark Sprint 4 :

| Entreprise | Ticker | Fiscal Year | Questions couvertes |
|-----------|--------|-------------|---------------------|
| À compléter après `make inspect-dataset` | | | |

> **Note** : Mettre à jour ce tableau après avoir exécuté `make inspect-dataset` et
> copier le résumé "Retenir : [...]" produit par le script.

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

- **Couverture estimée** : ~60–80% des questions de financebench couvertes par le corpus retenu
  (à confirmer après inspection).
- **Filings à ingérer** : 3–4 documents (vs ~15 pour couverture complète).
- **Métriques cibles Sprint 4** : Exact-match accuracy ≥ 40%, ROUGE-L ≥ 0.35 sur le
  sous-ensemble retenu.
- **Limitation** : Les questions portant sur des entreprises hors corpus seront exclues
  de l'évaluation automatique ; elles pourront servir de test de robustesse manuel.
- **Action** : Mettre à jour ce document après `make inspect-dataset` avec les vrais chiffres.
