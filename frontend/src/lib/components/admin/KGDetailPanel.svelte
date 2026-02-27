<!--
  KGDetailPanel.svelte - Entity detail / edit slide-out panel for the Knowledge Graph Explorer.

  Shows entity name, type, properties, confidence, neighbor list.
  Supports inline editing + delete via callback props.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { Loader2, Pencil, Trash2, X, Check, Save } from 'lucide-svelte';
	import type { GraphEntity, GraphRelation } from '$lib/components/flow/flow-types.js';

	interface Props {
		entity: GraphEntity;
		neighborhood: { entities: GraphEntity[]; relations: GraphRelation[] } | null;
		loadingDetail: boolean;
		typeColors: Record<string, string>;
		onClose: () => void;
		onSave: (entityId: string, updates: { name: string; type: string; properties: string; confidence: number }) => Promise<void>;
		onDelete: (entityId: string) => Promise<void>;
		onSelectNeighbor: (entity: GraphEntity) => void;
	}

	let {
		entity,
		neighborhood,
		loadingDetail,
		typeColors,
		onClose,
		onSave,
		onDelete,
		onSelectNeighbor
	}: Props = $props();

	// Internal state
	let editingEntity = $state(false);
	let savingEntity = $state(false);
	let propertiesJsonError = $state('');
	let editForm = $state({
		name: '',
		type: '',
		properties: '',
		confidence: 1
	});

	let editFormModified = $derived(
		editingEntity && (
			editForm.name !== entity.name ||
			editForm.type !== entity.type ||
			editForm.confidence !== (entity.confidence ?? 1) ||
			editForm.properties !== JSON.stringify(entity.properties ?? {}, null, 2)
		)
	);

	function getTypeColor(type: string): string {
		return typeColors[type?.toLowerCase()] ?? typeColors.default ?? '#6b7280';
	}

	function startEdit() {
		editForm = {
			name: entity.name,
			type: entity.type,
			properties: JSON.stringify(entity.properties ?? {}, null, 2),
			confidence: entity.confidence ?? 1
		};
		propertiesJsonError = '';
		editingEntity = true;
	}

	function cancelEdit() {
		editingEntity = false;
		propertiesJsonError = '';
	}

	function validatePropertiesJson(value: string) {
		try {
			JSON.parse(value);
			propertiesJsonError = '';
		} catch {
			propertiesJsonError = 'Invalid JSON';
		}
	}

	async function handleSave() {
		if (propertiesJsonError) return;
		savingEntity = true;
		try {
			await onSave(entity.id, {
				name: editForm.name,
				type: editForm.type,
				properties: editForm.properties,
				confidence: editForm.confidence
			});
			editingEntity = false;
		} finally {
			savingEntity = false;
		}
	}

	async function handleDelete() {
		await onDelete(entity.id);
	}
</script>

<div
	class="absolute inset-y-0 right-0 z-10 flex w-72 shrink-0 flex-col border-l border-border bg-surface shadow-lg"
	transition:fly={{ x: 288, duration: 200 }}
>
	<!-- Panel header -->
	<div class="flex items-center justify-between border-b border-border px-3 py-2">
		<div class="flex items-center gap-1.5">
			<h4 class="text-xs font-semibold text-text-primary">
				{editingEntity ? 'Edit Entity' : 'Entity Detail'}
			</h4>
			{#if editingEntity && editFormModified}
				<span class="inline-flex items-center gap-0.5 rounded-full bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-warning">
					<Pencil size={8} />
					modified
				</span>
			{:else if !editingEntity}
				<span class="inline-flex items-center gap-0.5 rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
					<Check size={8} />
					verified
				</span>
			{/if}
		</div>
		<div class="flex items-center gap-0.5">
			{#if !editingEntity}
				<button
					type="button"
					onclick={startEdit}
					class="rounded p-1 text-text-secondary hover:bg-accent/10 hover:text-accent"
					title="Edit"
				>
					<Pencil size={11} />
				</button>
				<button
					type="button"
					onclick={handleDelete}
					class="rounded p-1 text-text-secondary hover:bg-danger/10 hover:text-danger"
					title="Delete"
				>
					<Trash2 size={11} />
				</button>
			{/if}
			<button
				type="button"
				onclick={editingEntity ? cancelEdit : onClose}
				class="rounded p-1 text-text-secondary hover:text-text-primary"
				title="Close"
			>
				<X size={13} />
			</button>
		</div>
	</div>

	<!-- Panel body -->
	<div class="flex-1 overflow-y-auto p-3">
		{#if loadingDetail}
			<div class="flex items-center justify-center py-8">
				<Loader2 size={14} class="animate-spin text-text-secondary" />
			</div>
		{:else if editingEntity}
			<!-- Edit Mode -->
			<div class="flex flex-col gap-2.5">
				<div>
					<label for="edit-name" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Name</label>
					<input id="edit-name" type="text" bind:value={editForm.name} class="w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-accent" />
				</div>
				<div>
					<label for="edit-type" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Type</label>
					<input id="edit-type" type="text" bind:value={editForm.type} class="w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-accent" />
				</div>
				<div>
					<label for="edit-confidence" class="mb-0.5 flex justify-between text-[10px] font-medium text-text-secondary">
						<span>Confidence</span>
						<span class="tabular-nums">{editForm.confidence.toFixed(2)}</span>
					</label>
					<input id="edit-confidence" type="range" min="0" max="1" step="0.01" bind:value={editForm.confidence} class="w-full accent-accent" />
				</div>
				<div>
					<label for="edit-properties" class="mb-0.5 block text-[10px] font-medium text-text-secondary">Properties (JSON)</label>
					<textarea
						id="edit-properties"
						bind:value={editForm.properties}
						oninput={() => validatePropertiesJson(editForm.properties)}
						rows={5}
						class="w-full resize-y rounded border bg-surface px-2 py-1 font-mono text-[10px] text-text-primary outline-none
							{propertiesJsonError ? 'border-danger' : 'border-border focus:border-accent'}"
						spellcheck="false"
					></textarea>
					{#if propertiesJsonError}
						<p class="mt-0.5 text-[10px] text-danger">{propertiesJsonError}</p>
					{/if}
				</div>
			</div>
		{:else}
			<!-- View Mode -->
			<div class="flex flex-col gap-2.5">
				<div>
					<h5 class="text-xs font-semibold text-text-primary">{entity.name}</h5>
					<span
						class="mt-0.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize"
						style="background-color: {getTypeColor(entity.type)}20; color: {getTypeColor(entity.type)}"
					>
						<span class="inline-block h-1.5 w-1.5 rounded-full" style="background-color: {getTypeColor(entity.type)}"></span>
						{entity.type}
					</span>
				</div>

				{#if entity.confidence != null}
					<div>
						<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Confidence</h6>
						<div class="flex items-center gap-2">
							<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-secondary">
								<div class="h-full rounded-full bg-accent" style="width: {(entity.confidence ?? 1) * 100}%"></div>
							</div>
							<span class="text-[10px] tabular-nums text-text-secondary">{Math.round((entity.confidence ?? 1) * 100)}%</span>
						</div>
					</div>
				{/if}

				{#if entity.properties && Object.keys(entity.properties).length > 0}
					<div>
						<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Properties</h6>
						<div class="rounded border border-border bg-surface-secondary p-1.5">
							{#each Object.entries(entity.properties) as [key, value]}
								<div class="flex items-start gap-1.5 py-0.5 text-[10px]">
									<span class="font-medium text-text-secondary">{key}:</span>
									<span class="text-text-primary">{String(value)}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				{#if neighborhood?.entities}
					{@const neighbors = neighborhood.entities.filter((e) => e.id !== entity?.id)}
					{#if neighbors.length > 0}
						<div>
							<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Related Entities ({neighbors.length})</h6>
							<div class="flex flex-col gap-0.5">
								{#each neighbors.slice(0, 15) as neighbor}
									<button
										type="button"
										onclick={() => onSelectNeighbor(neighbor)}
										class="flex items-center gap-1.5 rounded px-1.5 py-1 text-left text-[10px] transition-colors hover:bg-surface-secondary"
									>
										<span class="inline-block h-2 w-2 rounded-full" style="background-color: {getTypeColor(neighbor.type ?? '')}"></span>
										<span class="min-w-0 flex-1 truncate font-medium text-text-primary">{neighbor.name ?? 'Unnamed'}</span>
										<span class="shrink-0 capitalize text-text-secondary">{neighbor.type ?? 'unknown'}</span>
									</button>
								{/each}
								{#if neighbors.length > 15}
									<span class="px-1.5 text-[10px] text-text-secondary">+{neighbors.length - 15} more</span>
								{/if}
							</div>
						</div>
					{/if}
				{/if}

				{#if neighborhood?.relations && neighborhood.relations.length > 0}
					<div>
						<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Relations ({neighborhood.relations.length})</h6>
						<div class="flex flex-col gap-0.5">
							{#each neighborhood.relations.slice(0, 15) as rel}
								<div class="rounded border border-border bg-surface-secondary px-1.5 py-1 text-[10px]">
									<span class="font-medium text-accent">{rel.label}</span>
								</div>
							{/each}
							{#if neighborhood.relations.length > 15}
								<span class="px-1.5 text-[10px] text-text-secondary">+{neighborhood.relations.length - 15} more</span>
							{/if}
						</div>
					</div>
				{/if}

				{#if entity.source_documents && entity.source_documents.length > 0}
					<div>
						<h6 class="mb-0.5 text-[10px] font-medium text-text-secondary">Source Documents ({entity.source_documents.length})</h6>
						<div class="flex flex-col gap-0.5">
							{#each entity.source_documents.slice(0, 5) as docId}
								<div class="rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">{docId}</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Panel footer: Save / Cancel (edit mode only) -->
	{#if editingEntity}
		<div class="flex items-center gap-2 border-t border-border px-3 py-2">
			<button
				type="button"
				onclick={handleSave}
				disabled={savingEntity || !!propertiesJsonError}
				class="inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-accent px-2.5 py-1.5 text-[10px] font-medium text-white hover:bg-accent/90 disabled:opacity-50"
			>
				{#if savingEntity}
					<Loader2 size={10} class="animate-spin" />
					Saving...
				{:else}
					<Save size={10} />
					Save
				{/if}
			</button>
			<button
				type="button"
				onclick={cancelEdit}
				class="inline-flex flex-1 items-center justify-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-[10px] font-medium text-text-secondary hover:bg-surface-hover"
			>
				Cancel
			</button>
		</div>
	{/if}
</div>
