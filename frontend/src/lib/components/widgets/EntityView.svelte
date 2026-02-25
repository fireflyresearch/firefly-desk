<!--
  EntityView.svelte - 360-degree entity view with tabbed sections.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { TrendingUp, TrendingDown, Minus } from 'lucide-svelte';

	interface HeaderData {
		title: string;
		subtitle?: string;
		avatar_url?: string;
		status?: string;
		status_color?: 'success' | 'warning' | 'danger' | 'default';
	}

	interface DetailsItem {
		label: string;
		value: string;
	}

	interface MetricItem {
		label: string;
		value: string;
		trend?: 'up' | 'down' | 'stable';
		change?: string;
	}

	interface TimelineEvent {
		date: string;
		title: string;
		description?: string;
	}

	interface RelatedItem {
		name: string;
		type?: string;
		description?: string;
	}

	interface Section {
		type: 'details' | 'metrics' | 'timeline' | 'related' | 'table';
		title: string;
		// Items are typed per-section-type; the template narrows by `section.type`.
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		items?: any[];
		columns?: { key: string; label: string }[];
		rows?: Record<string, unknown>[];
		events?: TimelineEvent[];
	}

	interface EntityViewProps {
		header: HeaderData;
		sections: Section[];
	}

	let { header, sections }: EntityViewProps = $props();

	let activeTab = $state(0);

	const statusColorMap: Record<string, string> = {
		success: 'bg-success text-white',
		warning: 'bg-warning text-white',
		danger: 'bg-danger text-white',
		default: 'bg-surface-secondary text-text-secondary'
	};
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	<!-- Header -->
	<div class="border-b border-border bg-surface-secondary/50 px-5 py-4">
		<div class="flex items-center gap-4">
			{#if header.avatar_url}
				<img
					src={header.avatar_url}
					alt={header.title}
					class="h-12 w-12 rounded-full border border-border object-cover"
				/>
			{:else}
				<div
					class="flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-lg font-bold text-accent"
				>
					{header.title.charAt(0).toUpperCase()}
				</div>
			{/if}
			<div class="min-w-0 flex-1">
				<h3 class="truncate text-base font-semibold text-text-primary">{header.title}</h3>
				{#if header.subtitle}
					<p class="text-sm text-text-secondary">{header.subtitle}</p>
				{/if}
			</div>
			{#if header.status}
				<span
					class="rounded-full px-2.5 py-0.5 text-xs font-medium {statusColorMap[
						header.status_color ?? 'default'
					]}"
				>
					{header.status}
				</span>
			{/if}
		</div>
	</div>

	<!-- Section tabs -->
	{#if sections.length > 1}
		<div class="flex overflow-x-auto border-b border-border">
			{#each sections as section, i}
				<button
					type="button"
					class="shrink-0 px-4 py-2 text-xs font-medium transition-colors {activeTab === i
						? 'border-b-2 border-accent text-accent'
						: 'text-text-secondary hover:text-text-primary'}"
					onclick={() => (activeTab = i)}
				>
					{section.title}
				</button>
			{/each}
		</div>
	{/if}

	<!-- Active section content -->
	{#if sections[activeTab]}
		{@const section = sections[activeTab]}
		<div class="p-4">
			{#if sections.length === 1}
				<h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">
					{section.title}
				</h4>
			{/if}

			{#if section.type === 'details' && section.items}
				<div class="grid grid-cols-2 gap-3">
					{#each section.items as item}
						<div class="flex flex-col">
							<span class="text-xs text-text-secondary">{item.label}</span>
							<span class="text-sm font-medium text-text-primary">{item.value}</span>
						</div>
					{/each}
				</div>
			{:else if section.type === 'metrics' && section.items}
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#each section.items as item}
						<div class="rounded-lg border border-border bg-surface-secondary/50 p-3">
							<span class="text-xs text-text-secondary">{item.label}</span>
							<div class="mt-1 flex items-baseline gap-2">
								<span class="text-lg font-bold text-text-primary">{item.value}</span>
								{#if item.trend === 'up'}
									<span class="flex items-center gap-0.5 text-xs text-success">
										<TrendingUp size={12} />{item.change ?? ''}
									</span>
								{:else if item.trend === 'down'}
									<span class="flex items-center gap-0.5 text-xs text-danger">
										<TrendingDown size={12} />{item.change ?? ''}
									</span>
								{:else if item.trend === 'stable'}
									<span
										class="flex items-center gap-0.5 text-xs text-text-secondary"
									>
										<Minus size={12} />{item.change ?? ''}
									</span>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'timeline' && (section.events || section.items)}
				{@const events = section.events || section.items || []}
				<div class="space-y-3">
					{#each events as event}
						<div class="flex gap-3">
							<div class="flex flex-col items-center">
								<div class="mt-1.5 h-2 w-2 rounded-full bg-accent"></div>
								<div class="w-px flex-1 bg-border"></div>
							</div>
							<div class="pb-3">
								<div class="flex items-baseline gap-2">
									<span class="text-sm font-medium text-text-primary"
										>{event.title}</span
									>
									<span class="text-xs text-text-secondary">{event.date}</span>
								</div>
								{#if event.description}
									<p class="mt-0.5 text-xs text-text-secondary">
										{event.description}
									</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'related' && section.items}
				<div class="space-y-2">
					{#each section.items as item}
						<div
							class="flex items-center gap-3 rounded-lg border border-border p-2.5"
						>
							<div
								class="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 text-xs font-bold text-accent"
							>
								{item.name.charAt(0).toUpperCase()}
							</div>
							<div class="min-w-0 flex-1">
								<span class="text-sm font-medium text-text-primary"
									>{item.name}</span
								>
								{#if item.type}
									<span class="ml-1.5 text-xs text-text-secondary"
										>&middot; {item.type}</span
									>
								{/if}
								{#if item.description}
									<p class="truncate text-xs text-text-secondary">
										{item.description}
									</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'table' && section.columns && section.rows}
				<div class="overflow-auto">
					<table class="w-full text-left text-xs">
						<thead>
							<tr class="border-b border-border">
								{#each section.columns as col}
									<th class="px-3 py-2 font-semibold text-text-secondary"
										>{col.label}</th
									>
								{/each}
							</tr>
						</thead>
						<tbody>
							{#each section.rows as row, i}
								<tr
									class="border-b border-border/50 {i % 2 === 0
										? ''
										: 'bg-surface-secondary/50'}"
								>
									{#each section.columns as col}
										<td class="px-3 py-1.5 text-text-primary"
											>{row[col.key] ?? ''}</td
										>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}
</div>
