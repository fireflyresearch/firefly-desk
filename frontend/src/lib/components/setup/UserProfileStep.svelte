<!--
  UserProfileStep.svelte -- Dev-mode only step for setting the dev user profile.

  Collects a display name and role for the auto-injected development user.
  These mirror the FLYDESK_DEV_USER_* environment variables.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { ArrowLeft, ArrowRight } from 'lucide-svelte';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface UserProfileStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: UserProfileStepProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let displayName = $state('Dev Admin');
	let role = $state('admin');

	const roles = [
		{ value: 'admin', label: 'Admin', desc: 'Full access to all features and settings.' },
		{
			value: 'operator',
			label: 'Operator',
			desc: 'Manage conversations and catalog, no system config.'
		},
		{ value: 'viewer', label: 'Viewer', desc: 'Read-only access to conversations.' }
	];

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleContinue() {
		onNext({ dev_user: { display_name: displayName, role } });
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">User Profile</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Configure the development user identity. This only applies in dev mode.
	</p>

	<div class="mt-6 space-y-5">
		<!-- Display name -->
		<div>
			<label for="display-name" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Display Name
			</label>
			<input
				id="display-name"
				type="text"
				bind:value={displayName}
				placeholder="Dev Admin"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Role selector -->
		<div>
			<span class="mb-2 block text-xs font-medium text-text-secondary">Role</span>
			<div class="space-y-2">
				{#each roles as r}
					<label
						class="flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition-all
							{role === r.value
							? 'border-ember bg-ember/5'
							: 'border-border hover:border-text-secondary/40'}"
					>
						<input
							type="radio"
							name="role"
							value={r.value}
							bind:group={role}
							class="mt-0.5 accent-amber-500"
						/>
						<div>
							<span class="text-sm font-medium text-text-primary">{r.label}</span>
							<p class="mt-0.5 text-xs text-text-secondary">{r.desc}</p>
						</div>
					</label>
				{/each}
			</div>
		</div>

		<!-- Env var note -->
		<p class="rounded-lg bg-surface-secondary px-4 py-3 text-xs text-text-secondary">
			These values map to the
			<code class="font-mono text-text-primary">FLYDESK_DEV_USER_NAME</code>
			and
			<code class="font-mono text-text-primary">FLYDESK_DEV_USER_ROLE</code>
			environment variables.
		</p>
	</div>

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Navigation -->
	<div class="mt-8 flex items-center justify-between border-t border-border pt-4">
		<button
			type="button"
			onclick={onBack}
			class="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<ArrowLeft size={16} />
			Back
		</button>
		<button
			type="button"
			onclick={handleContinue}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm"
		>
			Continue
			<ArrowRight size={16} />
		</button>
	</div>
</div>
