<!--
  EditableDataTable.svelte - Inline-editable table with dirty tracking and save-back.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { untrack } from 'svelte';

	interface Column {
		key: string;
		label: string;
		editable?: boolean;
		type?: 'text' | 'number' | 'select' | 'date';
		options?: string[];
	}

	interface EditableDataTableProps {
		columns: Column[];
		rows: Record<string, unknown>[];
		title?: string;
		save_endpoint?: string;
		save_method?: string;
	}

	let {
		columns,
		rows: initialRows,
		title,
		save_endpoint,
		save_method = 'PATCH'
	}: EditableDataTableProps = $props();

	let rows = $state(untrack(() => structuredClone(initialRows)));
	let editingCell: { row: number; col: string } | null = $state(null);
	let editValue = $state('');
	let dirty = $state(new Set<number>());
	let saving = $state(false);
	let saveError = $state('');

	let isDirty = $derived(dirty.size > 0);

	function startEdit(rowIdx: number, col: Column) {
		if (!col.editable) return;
		editingCell = { row: rowIdx, col: col.key };
		editValue = String(rows[rowIdx][col.key] ?? '');
	}

	function commitEdit() {
		if (!editingCell) return;
		const { row, col } = editingCell;
		const colDef = columns.find((c) => c.key === col);
		let finalValue: unknown = editValue;
		if (colDef?.type === 'number') finalValue = Number(editValue);
		if (rows[row][col] !== finalValue) {
			rows[row] = { ...rows[row], [col]: finalValue };
			dirty = new Set([...dirty, row]);
		}
		editingCell = null;
	}

	function cancelEdit() {
		editingCell = null;
	}

	function cancelAll() {
		rows = structuredClone(initialRows);
		dirty = new Set();
		editingCell = null;
	}

	async function saveChanges() {
		if (!save_endpoint || !isDirty) return;
		saving = true;
		saveError = '';
		try {
			const modifiedRows = [...dirty].map((i) => rows[i]);
			const resp = await fetch(save_endpoint, {
				method: save_method,
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ rows: modifiedRows })
			});
			if (!resp.ok) throw new Error(`Save failed: ${resp.statusText}`);
			dirty = new Set();
		} catch (e: unknown) {
			saveError = e instanceof Error ? e.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') cancelEdit();
	}
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	{#if title || isDirty}
		<div class="flex items-center justify-between border-b border-border px-4 py-2">
			{#if title}
				<h4 class="text-sm font-semibold text-text-primary">{title}</h4>
			{:else}
				<div></div>
			{/if}
			{#if isDirty}
				<div class="flex items-center gap-2">
					{#if saveError}
						<span class="text-xs text-danger">{saveError}</span>
					{/if}
					<button
						type="button"
						class="rounded px-2.5 py-1 text-xs text-text-secondary hover:bg-surface-secondary"
						onclick={cancelAll}
					>
						Cancel
					</button>
					{#if save_endpoint}
						<button
							type="button"
							class="rounded bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
							onclick={saveChanges}
							disabled={saving}
						>
							{saving ? 'Saving...' : `Save ${dirty.size} change${dirty.size === 1 ? '' : 's'}`}
						</button>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<div class="overflow-auto">
		<table class="w-full text-left text-xs">
			<thead>
				<tr class="border-b border-border bg-surface-secondary">
					{#each columns as col}
						<th
							class="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-secondary"
						>
							{col.label}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each rows as row, rowIdx}
					<tr
						class="border-b border-border/50 {dirty.has(rowIdx)
							? 'bg-accent/5'
							: rowIdx % 2 === 0
								? ''
								: 'bg-surface-secondary/50'}"
					>
						{#each columns as col}
							<td
								class="px-3 py-1.5 {col.editable ? 'cursor-pointer hover:bg-accent/10' : ''}"
								onclick={() => startEdit(rowIdx, col)}
								onkeydown={() => {}}
								role={col.editable ? 'button' : undefined}
								tabindex={col.editable ? 0 : undefined}
							>
								{#if editingCell?.row === rowIdx && editingCell?.col === col.key}
									{#if col.type === 'select' && col.options}
										<select
											class="w-full rounded border border-accent bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none"
											bind:value={editValue}
											onblur={commitEdit}
											onkeydown={handleKeydown}
										>
											{#each col.options as opt}
												<option value={opt}>{opt}</option>
											{/each}
										</select>
									{:else}
										<input
											type={col.type === 'number'
												? 'number'
												: col.type === 'date'
													? 'date'
													: 'text'}
											class="w-full rounded border border-accent bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none"
											bind:value={editValue}
											onblur={commitEdit}
											onkeydown={handleKeydown}
										/>
									{/if}
								{:else}
									<span class="text-text-primary">{row[col.key] ?? ''}</span>
								{/if}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
