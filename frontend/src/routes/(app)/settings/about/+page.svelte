<!--
  Settings about page - Application version and info.

  Shows app name, version, tech stack, and licensing information.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Info, Code, Cpu, Globe } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import EmberAvatar from '$lib/components/chat/EmberAvatar.svelte';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let appInfo = $state({
		appTitle: 'Firefly Desk',
		appVersion: '0.0.0',
		agentName: 'Ember'
	});

	// -----------------------------------------------------------------------
	// Lifecycle
	// -----------------------------------------------------------------------

	$effect(() => {
		fetchAppInfo();
	});

	async function fetchAppInfo() {
		try {
			const status = await apiJson<Record<string, unknown>>('/setup/status');
			appInfo = {
				appTitle: (status.app_title as string) ?? 'Firefly Desk',
				appVersion: (status.app_version as string) ?? '0.0.0',
				agentName: (status.agent_name as string) ?? 'Ember'
			};
		} catch {
			// Keep defaults
		}
	}

	// -----------------------------------------------------------------------
	// Tech stack data
	// -----------------------------------------------------------------------

	const techStack = [
		{ label: 'Frontend', value: 'SvelteKit + Svelte 5', icon: Globe },
		{ label: 'Backend', value: 'Python + FastAPI', icon: Cpu },
		{ label: 'AI Framework', value: 'Pydantic AI + Firefly GenAI', icon: Code },
		{ label: 'Styling', value: 'Tailwind CSS 4', icon: Code }
	];
</script>

<div class="mx-auto flex h-full max-w-2xl flex-col gap-6 overflow-y-auto p-6">
	<!-- Header -->
	<div>
		<h1 class="text-lg font-semibold text-text-primary">About</h1>
		<p class="text-sm text-text-secondary">Application information and credits</p>
	</div>

	<!-- App Info -->
	<div
		class="rounded-lg border border-border border-t-2 border-t-ember bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Info size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Application</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					Version and agent information.
				</p>
			</div>
		</div>

		<div class="flex items-start gap-4">
			<EmberAvatar size={32} />
			<div class="flex-1 space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-text-secondary">Application</span>
					<span class="font-medium text-text-primary">{appInfo.appTitle}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-text-secondary">Version</span>
					<span class="font-mono text-text-primary">{appInfo.appVersion}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-text-secondary">Agent</span>
					<span class="font-medium text-text-primary">{appInfo.agentName}</span>
				</div>
			</div>
		</div>
	</div>

	<!-- Tech Stack -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="mb-5 flex items-start gap-3">
			<div
				class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember"
			>
				<Code size={16} />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Technology Stack</h2>
				<p class="mt-0.5 text-xs text-text-secondary">
					The technologies powering Firefly Desk.
				</p>
			</div>
		</div>

		<div class="space-y-3">
			{#each techStack as item}
				<div class="flex items-center gap-3 rounded-md border border-border/50 bg-surface px-4 py-3">
					<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-secondary text-text-secondary">
						<item.icon size={14} />
					</div>
					<div class="flex-1">
						<p class="text-sm font-medium text-text-primary">{item.label}</p>
						<p class="text-xs text-text-secondary">{item.value}</p>
					</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- License -->
	<div
		class="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm transition-shadow hover:shadow-md"
	>
		<div class="space-y-2 text-center">
			<p class="text-sm font-medium text-text-primary">Firefly Desk</p>
			<p class="text-xs text-text-secondary">
				Apache License 2.0 &mdash; Firefly Software Solutions Inc.
			</p>
			<p class="text-xs text-text-secondary/60">
				Copyright 2026. All rights reserved.
			</p>
		</div>
	</div>

	<!-- Bottom spacer -->
	<div class="h-4"></div>
</div>
