# Guided tutorial — 2026-10-19

Second stage only: the tutorial follows the completed currency change. Unified local/online assistant behavior remains pending until the user asks to continue.

A seven-step walkthrough opens after the first successful workspace load in this browser/account. Header > Quick tutorial reopens it. Steps explain the overview, currency controls, real record entry, cash-flow scenarios, lazy corner assistant, independent payment approval and audit/export. English and Bangla are available. No records, proposals, currencies or external AI requests are submitted by the tour.

A native modal dialog provides focus containment and an inert background. Next/Back navigate pages and highlight relevant controls with SVG presentation attributes, preserving the existing CSP without inline styles or new dependencies. Escape, Close and Skip dismiss; completion/dismissal is versioned and remembered per account in browser storage. It returns to the starting page and scroll position and focuses the launcher. When storage is unavailable, dismissal still works for the session. No account secrets or financial amounts are persisted by this feature.

The welcome step does not navigate away from the current page and advises saving unfinished inputs before proceeding. The tour does not load the assistant. Highlights recompute on resize/scroll, mobile layout uses a compact modal, and reduced-motion preferences disable the entrance animation. Cross-device completion is not synchronized.

Build validation: TypeScript and Vite production build pass. Existing currency parsing and exact-conversion checks pass. Live browser verification follows deployment; do not infer full mobile or assistive-technology certification from these checks.
