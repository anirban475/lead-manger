# Telecaller Cockpit — Agent Guide (CLAUDE.md)

Refer to the main system architecture and sync document:
[Main CLAUDE.md](file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Jd%20Lead%20Scrapping/JD%20Lead%20Scrapping/CLAUDE.md)

---

## ⚡ Agent Triggers / Commands
- **`do handoff`**: Write a **Hot Handoff** summary directly to the main [CLAUDE.md](file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Jd%20Lead%20Scrapping/JD%20Lead%20Scrapping/CLAUDE.md) file and stop.
- **`handup`**: Read the main [CLAUDE.md](file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Jd%20Lead%20Scrapping/JD%20Lead%20Scrapping/CLAUDE.md) file, summarize previous changes/state, and prepare to execute the next tasks.

---

## 🛠️ Common Commands
- **Start Dev Server**: `npm run dev`
- **Build Project**: `npm run build`
- **Start Production**: `npm start`
- **Run Linter**: `npm run lint`

## 📋 Next Actions (For the Next Agent)
1. Review delta edits under `/Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Jd Lead Scrapping/JD Lead Scrapping/Interface plan.md`.
2. Implement grouped dispositions in `lib/dispositions.ts`.
3. Add comments actions & forms in `actions/addComment.ts` and `components/CommentForm.tsx`.
4. Apply the `deploy/schema.sql` changes to PostgreSQL database.
