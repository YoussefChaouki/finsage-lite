# FinSage-Lite — Sprint 5 : Document de Cadrage
## Frontend React (Vite + Tailwind + shadcn/ui)

**Sprint** : 5 / 6  
**Durée estimée** : 2 semaines  
**Objectif** : Remplacer le Streamlit placeholder par une interface professionnelle,
moderne et impressionnante qui met en valeur le pipeline RAG pour les recruteurs.

---

## Contexte et décision architecturale

### Ce qu'on abandonne
Le `streamlit_app/` existant est un placeholder minimal (`app.py` de 30 lignes). Il
est supprimé en totalité. Streamlit impose un plafond de qualité UX incompatible
avec les objectifs portfolio du projet.

### Ce qu'on construit
Une **Single Page Application React** servie par nginx en production, qui communique
exclusivement avec le FastAPI existant via HTTP. Le backend n'est **pas modifié** —
zéro changement dans `src/`, `tests/`, ni les schemas Pydantic.

### Stack retenue

| Couche | Technologie | Justification |
|---|---|---|
| Framework | Vite + React 18 | Dev server ultra-rapide, build statique, pas de SSR inutile |
| Styling | Tailwind CSS v3 | Utility-first, dark mode natif, cohérence totale |
| Composants | shadcn/ui | Composants accessibles, non-opinionated, copiés dans le repo |
| État | Zustand | Léger, pas de boilerplate Redux, parfait pour cette taille |
| HTTP | Axios + React Query | Cache automatique, loading states, retry |
| Types | TypeScript strict | Calqués sur les schemas Pydantic du backend |
| Icons | Lucide React | Déjà dans la stack shadcn |
| Animations | Framer Motion | Micro-animations fluides, typewriter effect |

---

## Direction artistique

### Thème : Dark Professional Financial Terminal

L'aesthetic cible est à mi-chemin entre **Linear** (épuré, moderne) et un
**terminal Bloomberg** (dense, crédible, professionnel). L'utilisateur doit
sentir qu'il utilise un vrai produit, pas un prototype académique.

### Palette de couleurs

```
Background principal  : slate-950  (#020617)
Surfaces / cards      : slate-900  (#0f172a)
Borders               : slate-800  (#1e293b)
Texte principal       : slate-100  (#f1f5f9)
Texte secondaire      : slate-400  (#94a3b8)
Accent primaire       : emerald-500 (#10b981)  — scores, succès, CTA
Accent warning        : amber-500  (#f59e0b)   — citations, tables
Accent info           : sky-500    (#0ea5e9)   — liens, mode info
```

### Codes couleur des sections (constants dans toute l'app)

```
ITEM_1   → sky-500/20 border sky-500    (Business — neutre/info)
ITEM_1A  → red-500/20 border red-500    (Risk Factors — danger)
ITEM_7   → emerald-500/20 border emerald-500  (MD&A — performance)
ITEM_7A  → orange-500/20 border orange-500    (Market Risk — attention)
ITEM_8   → violet-500/20 border violet-500    (Financial Statements — data)
OTHER    → slate-700/20 border slate-600      (fallback)
```

### Typographie

- **Font principale** : Inter (Google Fonts) — lisible, neutre, professionnelle
- **Font mono** : JetBrains Mono — pour les valeurs financières et chunks bruts
- **Hiérarchie** : titres en `font-semibold`, labels en `text-xs uppercase tracking-wider`

---

## Architecture des écrans

### Navigation globale

Sidebar fixe gauche (240px) avec :
- Logo FinSage-Lite + badge version
- 3 items de navigation avec icônes Lucide
- En bas : statut API (dot vert/rouge animé), statut Ollama

### Écran 1 — Search (route `/`)

**C'est l'écran portfolio principal. Il doit épater.**

```
┌─────────────────────────────────────────────────────┐
│  [Sidebar]  │  SEARCH                               │
│             │                                       │
│  🔍 Search  │  ┌─────────────────────────────────┐  │
│  📁 Browse  │  │  Ask anything about SEC 10-K... │  │
│  📄 Docs    │  └─────────────────────────────────┘  │
│             │  [AAPL ▾] [2024 ▾] [Hybrid ▾] [HyDE] │
│             │                                       │
│             │  ─── Answer ──────────────────────── │
│             │  Apple reported total revenue of      │
│             │  $391B [¹] driven by iPhone sales...  │
│             │  [²] Services segment grew 16%...     │
│             │                                       │
│             │  ─── Sources (5) ─────────────────── │
│             │  [ITEM_7] ████████░░ 0.94  ▾          │
│             │  [ITEM_8] ██████░░░░ 0.87  ▾          │
│             │  ...                                  │
└─────────────────────────────────────────────────────┘
```

**Comportements clés :**
- Typewriter effect sur la réponse LLM (char par char, 20ms de délai)
- Citation chips `[¹]` dans le texte → hover highlight la source card en bas
- Source cards : badge section coloré, barre de score, extrait tronqué,
  expand/collapse animé (Framer Motion)
- TABLE chunks affichent une vraie `<table>` stylisée avec valeurs financières
- Si Ollama offline : banner amber "LLM offline — showing raw retrieval results"
- Keyboard : `Cmd/Ctrl+K` focus search, `Esc` clear, `Enter` submit

### Écran 2 — Browse Filing (route `/browse`)

```
┌─────────────────────────────────────────────────────┐
│  [Sidebar]  │  BROWSE FILING                        │
│             │  [AAPL FY2024 ▾]                      │
│             │                                       │
│  🔍 Search  │  ┌──────────┐  ┌─────────────────┐   │
│  📁 Browse  │  │ ITEM_1   │  │ Business        │   │
│  📄 Docs    │  │ ITEM_1A  │  │                 │   │
│             │  │ ITEM_7 ← │  │ Apple designs   │   │
│             │  │ ITEM_7A  │  │ and develops... │   │
│             │  │ ITEM_8   │  │                 │   │
│             │  └──────────┘  │ [TABLE]         │   │
│             │                │ Revenue | 2024  │   │
│             │  ◀ prev  next ▶│ iPhone  | 201B  │   │
│             │                └─────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Comportements clés :**
- Dropdown filing selector en haut (liste les documents ingérés)
- Section nav liste avec badge count chunks et badge couleur section
- Navigation prev/next entre sections avec transition slide
- Chunks text rendus séquentiellement avec séparateur
- Chunks TABLE rendus comme tables HTML formatées

### Écran 3 — Documents (route `/documents`)

```
┌─────────────────────────────────────────────────────┐
│  [Sidebar]  │  DOCUMENTS                            │
│             │  ┌──────────────────────┐ [+ Ingest] │
│             │  │ AAPL  FY2024  ✓     │             │
│             │  │ Apple Inc.           │             │
│             │  │ 390 chunks · 5 sec  │             │
│             │  │ ITEM1 ITEM1A ITEM7  │             │
│             │  └──────────────────────┘             │
│             │                                       │
│             │  ── Ingest New Filing ──────────────  │
│             │  Ticker: [MSFT    ]  Year: [2023 ▾]  │
│             │  [████████░░░░ Embedding... 67%    ]  │
└─────────────────────────────────────────────────────┘
```

**Comportements clés :**
- Cards filing avec initiales company stylisées (avatar coloré généré)
- Stats : nb chunks, sections disponibles (badges), date ingestion
- Progress ingestion : 4 étapes animées (Fetching → Parsing → Chunking → Embedding)
- Status indicators : `●` vert ready, `◌` animé processing, `✕` rouge error
- Polling automatique toutes les 2s pendant ingestion
- Empty state : illustration SVG + CTA "Ingest your first 10-K"

---

## Intégration Docker

### Modifications `docker-compose.yml`

Le service `streamlit-ui` est **remplacé** par un service `frontend` :

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    target: ${BUILD_TARGET:-development}
  container_name: finsage-frontend
  ports:
    - "5173:5173"   # dev (Vite)
    - "3000:80"     # prod (nginx)
  environment:
    - VITE_API_URL=http://localhost:8000
  volumes:
    - ./frontend/src:/app/src   # hot-reload dev uniquement
  depends_on:
    - api
  restart: unless-stopped
```

### Dockerfile multi-stage

```dockerfile
# Stage dev : Vite dev server avec hot-reload
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# Stage build
FROM development AS builder
RUN npm run build

# Stage prod : nginx statique
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

---

## Contrat API — endpoints consommés

Le frontend appelle **uniquement** ces endpoints existants. Aucune modification backend.

| Méthode | Endpoint | Usage |
|---|---|---|
| `GET` | `/health` | Statut API + Ollama dans la sidebar |
| `GET` | `/api/v1/documents` | Liste des filings pour les dropdowns |
| `GET` | `/api/v1/documents/{id}` | Détail filing (sections, stats) |
| `POST` | `/api/v1/documents/ingest` | Déclencher une ingestion |
| `POST` | `/api/v1/search` | Recherche (dense/sparse/hybrid + HyDE) |
| `GET` | `/api/v1/search/health` | Statut BM25 + Ollama pour le UI |
| `POST` | `/api/v1/search/rebuild-index` | Bouton rebuild dans Documents |

---

## Ce que ce sprint démontre au recruteur

1. **Fullstack capability** — FastAPI backend + React frontend, Docker orchestré
2. **Qualité produit** — UX soignée, micro-animations, empty states, error handling
3. **Domain knowledge** — Section badges, citation highlighting, table rendering financier
4. **Engineering discipline** — TypeScript strict, composants découplés, API contract respecté

---

## Critères d'acceptance du sprint

- [ ] `make docker-up` lance backend + frontend, les deux accessibles
- [ ] Search retourne des résultats avec sources sur AAPL FY2024
- [ ] Typewriter effect visible sur la réponse LLM
- [ ] Citation chips cliquables qui highlightent les sources
- [ ] Section badges colorés cohérents partout
- [ ] TABLE chunks affichés comme tables formatées
- [ ] Graceful degradation si Ollama offline
- [ ] Browse Filing affiche le contenu de chaque section
- [ ] Ingest form avec progress steps animés fonctionne
- [ ] `Cmd+K` focus le search input
- [ ] Aucun test backend cassé (`make check` green)
- [ ] README mis à jour avec screenshot et `make docker-up`
