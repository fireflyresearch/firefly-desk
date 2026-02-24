# Admin Overhaul Tier 3: Skill Wizard Enhancement

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the plain textarea skill editor with a structured editing component that guides users through creating well-formed skills with steps, guidelines, endpoint references, and document references, plus a live markdown preview.

**Architecture:** The skill backend model stays unchanged (`content` is a string). The new `SkillEditor.svelte` component presents a structured editing UI that parses existing markdown content into sections and generates markdown on save. Referenced endpoints and documents are loaded from the catalog and knowledge base APIs for multi-select pickers.

**Tech Stack:** Svelte 5 (runes), TailwindCSS, lucide-svelte, existing catalog/knowledge API endpoints

**Design doc:** `docs/plans/2026-02-24-admin-overhaul-design.md` (section 6)

---

## Task 1: Create SkillEditor.svelte Component

Create the structured skill editing component. This is a modal with two panels: a structured editor on the left and a live markdown preview on the right.

**Files:**
- Create: `frontend/src/lib/components/admin/SkillEditor.svelte`

**Steps:**

1. Read `frontend/src/lib/components/admin/SystemWizard.svelte` for modal and form patterns.

2. Create `frontend/src/lib/components/admin/SkillEditor.svelte` with:

   **Props:**
   ```typescript
   interface Props {
       editingSkill?: SkillRecord | null;
       onClose: () => void;
       onSaved: () => void;
   }

   interface SkillRecord {
       id: string;
       name: string;
       description: string;
       content: string;
       tags: string[];
       active: boolean;
   }
   ```

   **Structured form data:**
   ```typescript
   interface StepEntry {
       description: string;
       endpointId: string;  // references a catalog endpoint
   }

   let name = $state('');
   let description = $state('');
   let tags = $state('');
   let active = $state(true);

   // Structured content sections
   let steps = $state<StepEntry[]>([{ description: '', endpointId: '' }]);
   let guidelines = $state<string[]>(['']);
   let referencedEndpoints = $state<string[]>([]);  // endpoint IDs
   let referencedDocuments = $state<string[]>([]);   // document IDs

   // Raw content fallback (for skills that don't parse into structured format)
   let rawContent = $state('');
   let useStructuredMode = $state(true);

   // Preview
   let showPreview = $state(true);
   ```

   **Content parsing (on mount, for edit mode):**
   Parse existing `content` string into structured sections. Use simple heuristic:
   - Look for `## Steps` section → parse numbered list into `steps`
   - Look for `## Guidelines` section → parse bullet list into `guidelines`
   - Look for `## Referenced Endpoints` section → parse endpoint IDs
   - Look for `## Referenced Documents` section → parse document IDs
   - If parsing fails or content doesn't match expected format, fall back to raw textarea mode (`useStructuredMode = false`)

   ```typescript
   function parseContent(content: string): boolean {
       // Try to parse structured sections
       const stepsMatch = content.match(/## Steps\n([\s\S]*?)(?=\n## |$)/);
       const guidelinesMatch = content.match(/## Guidelines\n([\s\S]*?)(?=\n## |$)/);
       const endpointsMatch = content.match(/## Referenced Endpoints\n([\s\S]*?)(?=\n## |$)/);
       const docsMatch = content.match(/## Referenced Documents\n([\s\S]*?)(?=\n## |$)/);

       if (!stepsMatch && !guidelinesMatch) return false;  // Not structured

       if (stepsMatch) {
           const lines = stepsMatch[1].trim().split('\n').filter(l => l.match(/^\d+\./));
           steps = lines.map(l => {
               const text = l.replace(/^\d+\.\s*/, '').trim();
               const epMatch = text.match(/\[endpoint:([^\]]+)\]/);
               return {
                   description: text.replace(/\s*\[endpoint:[^\]]+\]/, '').trim(),
                   endpointId: epMatch?.[1] || ''
               };
           });
           if (steps.length === 0) steps = [{ description: '', endpointId: '' }];
       }

       if (guidelinesMatch) {
           guidelines = guidelinesMatch[1].trim().split('\n')
               .filter(l => l.startsWith('- '))
               .map(l => l.replace(/^- /, '').trim());
           if (guidelines.length === 0) guidelines = [''];
       }

       if (endpointsMatch) {
           referencedEndpoints = endpointsMatch[1].trim().split('\n')
               .filter(l => l.startsWith('- '))
               .map(l => l.replace(/^- /, '').trim());
       }

       if (docsMatch) {
           referencedDocuments = docsMatch[1].trim().split('\n')
               .filter(l => l.startsWith('- '))
               .map(l => l.replace(/^- /, '').trim());
       }

       return true;
   }
   ```

   **Content generation (on save):**
   ```typescript
   function generateContent(): string {
       if (!useStructuredMode) return rawContent;

       let content = '';

       // Steps
       const validSteps = steps.filter(s => s.description.trim());
       if (validSteps.length > 0) {
           content += '## Steps\n';
           validSteps.forEach((s, i) => {
               content += `${i + 1}. ${s.description}`;
               if (s.endpointId) content += ` [endpoint:${s.endpointId}]`;
               content += '\n';
           });
           content += '\n';
       }

       // Guidelines
       const validGuidelines = guidelines.filter(g => g.trim());
       if (validGuidelines.length > 0) {
           content += '## Guidelines\n';
           validGuidelines.forEach(g => { content += `- ${g}\n`; });
           content += '\n';
       }

       // Referenced Endpoints
       if (referencedEndpoints.length > 0) {
           content += '## Referenced Endpoints\n';
           referencedEndpoints.forEach(id => { content += `- ${id}\n`; });
           content += '\n';
       }

       // Referenced Documents
       if (referencedDocuments.length > 0) {
           content += '## Referenced Documents\n';
           referencedDocuments.forEach(id => { content += `- ${id}\n`; });
           content += '\n';
       }

       return content.trim();
   }
   ```

   **Layout (modal, 2-column):**
   - Modal overlay same pattern as SystemWizard
   - Left panel (~60%): structured editor sections
   - Right panel (~40%): live markdown preview (read-only pre-formatted display)
   - Toggle button at top: "Structured" / "Raw" mode switch

   **Structured editor sections:**

   a) **Basic fields** at top: name, description, tags, active toggle (same fields as current form)

   b) **Steps section:** Ordered list editor
   - Each step: text input for description + dropdown for endpoint (optional)
   - "Add step" button below the list
   - Drag-handle or up/down buttons for reordering (simple: use move up/move down buttons)
   - Remove button per step (only if > 1 step)

   c) **Guidelines section:** Bulleted list editor
   - Each guideline: text input
   - "Add guideline" button
   - Remove button per guideline (only if > 1)

   d) **Referenced Endpoints section:** Multi-select picker
   - Load endpoints from `/catalog/systems` then expand each → or simpler: use a searchable dropdown
   - Show selected endpoints as chips with remove button
   - Dropdown populated from a flat list of all endpoints (load via iterating systems)

   e) **Referenced Documents section:** Multi-select picker
   - Load documents from `/knowledge/documents`
   - Show selected as chips with remove button

   **Submit:** Build payload with `content: generateContent()` and call POST/PUT API.

3. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

4. Commit:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && git add frontend/src/lib/components/admin/SkillEditor.svelte
   git commit -m "feat(frontend): add structured SkillEditor component"
   ```

---

## Task 2: Integrate SkillEditor into SkillManager

Replace the inline form in `SkillManager.svelte` with the new `SkillEditor` modal component.

**Files:**
- Modify: `frontend/src/lib/components/admin/SkillManager.svelte`

**Steps:**

1. Read the current `SkillManager.svelte` (full file).

2. Import SkillEditor:
   ```typescript
   import SkillEditor from './SkillEditor.svelte';
   ```

3. Remove the inline form state variables (`formData`) and inline form actions (`openCreateForm`, `openEditForm`, `cancelForm`, `submitForm`). Replace with simpler wizard state:
   ```typescript
   let showEditor = $state(false);
   let editingSkill = $state<SkillRecord | null>(null);

   function openCreate() {
       editingSkill = null;
       showEditor = true;
   }

   function openEdit(skill: SkillRecord) {
       editingSkill = skill;
       showEditor = true;
   }

   function closeEditor() {
       showEditor = false;
       editingSkill = null;
   }

   async function onEditorSaved() {
       showEditor = false;
       editingSkill = null;
       await loadSkills();
   }
   ```

4. Replace the inline form HTML block (`{#if showForm}...{/if}`) with:
   ```svelte
   {#if showEditor}
       <SkillEditor
           editingSkill={editingSkill}
           onClose={closeEditor}
           onSaved={onEditorSaved}
       />
   {/if}
   ```

5. Update button handlers: `openAddForm` → `openCreate`, `openEditForm(skill)` → `openEdit(skill)`.

6. Remove unused imports (X, Save from lucide-svelte) that were only used by the inline form.

7. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

8. Commit:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && git add frontend/src/lib/components/admin/SkillManager.svelte
   git commit -m "feat(frontend): replace inline skill form with SkillEditor modal"
   ```

---

## Task 3: Add Endpoint Validation Warnings

Add warnings in the SkillEditor when referenced endpoints don't exist or aren't agent-enabled.

**Files:**
- Modify: `frontend/src/lib/components/admin/SkillEditor.svelte`

**Steps:**

1. Read the current `SkillEditor.svelte`.

2. The component should already load available endpoints and systems. Add validation by cross-referencing:

   ```typescript
   interface SystemInfo {
       id: string;
       name: string;
       agent_enabled: boolean;
   }

   let systems = $state<SystemInfo[]>([]);

   async function loadSystems() {
       try {
           systems = await apiJson<SystemInfo[]>('/catalog/systems');
       } catch { /* non-fatal */ }
   }
   ```

3. Add a derived warning list:
   ```typescript
   let endpointWarnings = $derived.by(() => {
       const warnings: string[] = [];
       const allEndpointIds = new Set(availableEndpoints.map(e => e.id));
       const disabledSystemIds = new Set(systems.filter(s => !s.agent_enabled).map(s => s.id));

       // Check referenced endpoints
       for (const epId of referencedEndpoints) {
           if (!allEndpointIds.has(epId)) {
               warnings.push(`Endpoint "${epId}" not found in catalog`);
           } else {
               const ep = availableEndpoints.find(e => e.id === epId);
               if (ep && disabledSystemIds.has(ep.system_id)) {
                   const sys = systems.find(s => s.id === ep.system_id);
                   warnings.push(`Endpoint "${epId}" belongs to system "${sys?.name || ep.system_id}" which has agent access disabled`);
               }
           }
       }

       // Check step endpoints
       for (const step of steps) {
           if (step.endpointId && !allEndpointIds.has(step.endpointId)) {
               warnings.push(`Step endpoint "${step.endpointId}" not found in catalog`);
           }
       }

       return warnings;
   });
   ```

4. Display warnings in the editor, above the preview panel or below the referenced endpoints section:
   ```svelte
   {#if endpointWarnings.length > 0}
       <div class="rounded-md border border-warning/30 bg-warning/5 px-3 py-2">
           <p class="mb-1 text-xs font-medium text-warning">Endpoint Warnings</p>
           {#each endpointWarnings as warning}
               <p class="text-xs text-warning/80">• {warning}</p>
           {/each}
       </div>
   {/if}
   ```

5. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

6. Commit:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && git add frontend/src/lib/components/admin/SkillEditor.svelte
   git commit -m "feat(frontend): add endpoint validation warnings to SkillEditor"
   ```

---

## Task 4: Verification

1. Run backend tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py
   ```

2. Run frontend checks:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

---

## Dependency Graph

```
Task 1 (SkillEditor.svelte)           — No deps
Task 2 (SkillManager integration)     — Depends on Task 1
Task 3 (Endpoint validation warnings) — Depends on Task 1
Task 4 (Verification)                 — ALL previous tasks
```

**Execution order:**
1. Task 1 (foundation)
2. Tasks 2, 3 (parallel — both modify different aspects, Task 2 modifies SkillManager, Task 3 modifies SkillEditor)
3. Task 4 (final)

---

## Summary Table

| # | Task | Key Files | Impact |
|---|------|-----------|--------|
| 1 | SkillEditor.svelte | New component | **Critical** — structured editor + preview |
| 2 | SkillManager integration | `SkillManager.svelte` | **Critical** — replace inline form |
| 3 | Endpoint validation | `SkillEditor.svelte` | **UX** — safety warnings |
| 4 | Verification | — | Quality gate |
