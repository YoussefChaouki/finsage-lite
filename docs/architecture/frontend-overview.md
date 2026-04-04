# Frontend Architecture Overview

React 19 + Vite SPA served on port 5173. Dark-theme, single-page application
with three top-level routes managed by React Router v7.

---

## Pages

| Route | Component | Responsibility |
|-------|-----------|---------------|
| `/` | `SearchPage` | Full-text hybrid search over ingested chunks; displays answer panel + source cards |
| `/browse` | `BrowsePage` | Navigate filings by company/year, read section content inline |
| `/documents` | `DocumentsPage` | Ingest new filings, monitor progress, view filing grid with stats |

`NotFoundPage` handles unmatched routes.

---

## Component tree

```
App
└── MainLayout (Sidebar + <Outlet>)
    ├── SearchPage
    │   ├── SearchBar
    │   ├── SearchControls        (mode selector: dense/sparse/hybrid, HyDE toggle)
    │   ├── SearchEmptyState
    │   ├── AnswerPanel           (LLM cited answer, collapsed when null)
    │   ├── SourceCard[]          (one per retrieved chunk)
    │   │   ├── CitationChip      (section badge + score bar)
    │   │   └── TableChunkView    (rendered when chunk type = table)
    │   └── SkeletonCard[]        (loading state)
    │
    ├── BrowsePage
    │   ├── FilingSelector        (company + fiscal year dropdowns)
    │   ├── SectionNav            (vertical list of 10-K sections)
    │   └── SectionContent        (rendered Markdown / plain text)
    │
    └── DocumentsPage
        ├── StatsStrip            (4 stat tiles: filings, chunks, companies, ready)
        ├── IngestForm            (ticker + fiscal year input)
        ├── IngestProgress        (step indicator: fetch → parse → embed → done)
        ├── FilingCard[]          (one per document)
        └── RebuildIndexButton    (POST /api/v1/search/rebuild-index)
```

Shared UI primitives (`badge`, `button`, `card`, `input`, `select`, `progress`,
`scroll-area`, `separator`, `sheet`, `switch`, `tabs`, `tooltip`) come from
**shadcn/ui** and are vendored into `src/components/ui/`.

Custom domain primitives: `ScoreBar`, `SectionBadge`, `SkeletonCard`, `StatusDot`.

---

## State management

### Zustand — `src/store/appStore.ts`

Global UI state shared between Search and Browse:

```
selectedCompany : string | null   — active company filter
selectedYear    : number | null   — active fiscal year filter
selectedMode    : SearchMode      — "dense" | "sparse" | "hybrid"
hydeEnabled     : boolean         — HyDE query expansion toggle
```

Mutations are synchronous setters (`setCompany`, `setYear`, `setMode`, `toggleHyde`).
No persistence — state resets on page refresh by design (filters are ephemeral).

### TanStack Query — server state

All API calls go through `src/lib/api.ts` (axios-based client).
Each page/feature has a dedicated hook:

| Hook | Query key | What it fetches |
|------|-----------|-----------------|
| `useDocuments` | `["documents"]` | `GET /api/v1/documents` — full filing list |
| `useSearch` | `["search", query, filters]` | `POST /api/v1/search` — chunk results + answer |
| `useBrowse` | `["browse", docId, section]` | `GET /api/v1/documents/:id/chunks` |
| `useIngest` | mutation | `POST /api/v1/documents/ingest` |

`useDocuments` and `useBrowse` use `staleTime: 30_000` (30 s) to avoid
re-fetching on every navigation. Search results are not cached (each query
is unique).

---

## Data fetching patterns

### Optimistic UI — ingestion progress

`useIngest` drives a four-step progress indicator without polling:

```
step 0 → idle
step 1 → fetching from EDGAR (mutation fired)
step 2 → parsing & chunking  (simulated transition after ~1 s)
step 3 → done / error
```

The backend processes synchronously; the step transitions are client-side
timers giving visual feedback while awaiting the response.

### Error boundary

Network errors surface as typed `AxiosError` values returned from hooks;
components render inline error states rather than throwing to a React error
boundary.

---

## Routing

React Router v7 (`createBrowserRouter`). Routes are defined in `App.tsx`:

```
/           → SearchPage   (default)
/browse     → BrowsePage
/documents  → DocumentsPage
*           → NotFoundPage
```

The `Sidebar` component renders `<NavLink>` for each route; active state is
styled via Tailwind classes applied by React Router's `isActive` flag.

---

## Styling conventions

- **Tailwind CSS** utility classes only — no CSS modules or styled-components.
- Dark theme: `slate-*` colour scale for backgrounds/text, `emerald` for
  primary accent, `sky` for secondary, `violet` for tertiary.
- Spacing scale: `gap-4` / `gap-6` between sections, `px-8 py-8` page padding.
- Animations: **Framer Motion** `motion.div` with `variants` for stagger-in
  grid entrances; CSS `animate-pulse` for skeleton loading states.
- Font: `font-display` (mapped to Inter via Tailwind config) for headings;
  system `font-mono` for code/ticker values.

---

## Key design decisions

**No global loading spinner** — each section manages its own skeleton state,
so the layout never flashes blank.

**Sidebar always visible** — navigation is always accessible; no hamburger
menu required given the narrow three-item nav.

**HyDE toggle on search page** — exposed as a switch in `SearchControls`
rather than a settings page, keeping the feature discoverable without
cluttering the UI.

**`content_raw` displayed in source cards** — the embedding field
(`content_context`) includes a section prefix that would be noisy to show
to users; source cards render `content_raw` for readability.
