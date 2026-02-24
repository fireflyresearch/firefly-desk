<!--
  DeploymentStep.svelte -- Deployment and locale configuration step of the setup wizard.

  Collects FQDN, protocol, and locale settings (language, timezone, country).
  Auto-detects locale from the browser and defaults to localhost in dev mode.
  POSTs to both /setup/configure-fqdn and /setup/configure-locale endpoints.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowLeft, ArrowRight, Loader2, XCircle } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface DeploymentStepProps {
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { onNext, onBack }: DeploymentStepProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let fqdn = $state('');
	let protocol = $state('https');
	let language = $state('en-US');
	let timezone = $state('UTC');
	let country = $state('US');

	let submitting = $state(false);
	let errorMessage = $state('');

	// -----------------------------------------------------------------------
	// Auto-detection on mount
	// -----------------------------------------------------------------------

	onMount(() => {
		// Detect dev mode from URL
		const hostname = window.location.hostname;
		const port = window.location.port;
		if (hostname === 'localhost' || hostname === '127.0.0.1') {
			fqdn = port ? `${hostname}:${port}` : hostname;
			protocol = 'http';
		}

		// Detect locale from browser
		try {
			const navLang = navigator.language || 'en-US';
			language = navLang;

			// Derive country from language locale (e.g. "en-US" -> "US")
			const parts = navLang.split('-');
			if (parts.length > 1) {
				country = parts[parts.length - 1].toUpperCase();
			}
		} catch {
			// Fallback to defaults
		}

		// Detect timezone
		try {
			timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
		} catch {
			timezone = 'UTC';
		}
	});

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let isValid = $derived(fqdn.trim().length > 0 && language.trim().length > 0);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	async function handleSubmit() {
		if (!isValid || submitting) return;

		submitting = true;
		errorMessage = '';

		try {
			// Configure FQDN
			await apiJson<{ success: boolean }>('/setup/configure-fqdn', {
				method: 'POST',
				body: JSON.stringify({
					fqdn: fqdn.trim(),
					protocol
				})
			});

			// Configure locale
			await apiJson<{ success: boolean }>('/setup/configure-locale', {
				method: 'POST',
				body: JSON.stringify({
					language: language.trim(),
					timezone: timezone.trim(),
					country: country.trim()
				})
			});

			onNext({
				deployment: {
					fqdn: fqdn.trim(),
					protocol
				},
				locale: {
					language: language.trim(),
					timezone: timezone.trim(),
					country: country.trim()
				}
			});
		} catch (e) {
			errorMessage =
				e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">Deployment</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Configure your application's domain and locale settings.
	</p>

	<div class="mt-6 space-y-5">
		<!-- Error banner -->
		{#if errorMessage}
			<div
				class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
			>
				<XCircle size={18} class="mt-0.5 shrink-0" />
				<span>{errorMessage}</span>
			</div>
		{/if}

		<!-- FQDN + Protocol -->
		<div class="grid grid-cols-3 gap-4">
			<div class="col-span-1">
				<label for="deploy-protocol" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Protocol
				</label>
				<select
					id="deploy-protocol"
					bind:value={protocol}
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
				>
					<option value="https">https</option>
					<option value="http">http</option>
				</select>
			</div>

			<div class="col-span-2">
				<label for="deploy-fqdn" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Fully Qualified Domain Name
				</label>
				<input
					id="deploy-fqdn"
					type="text"
					bind:value={fqdn}
					placeholder="myapp.example.com"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
		</div>

		<!-- Preview -->
		{#if fqdn.trim()}
			<p class="text-xs text-text-secondary">
				Application URL: <code class="rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-text-primary">{protocol}://{fqdn.trim()}</code>
			</p>
		{/if}

		<!-- Locale section divider -->
		<div class="border-t border-border pt-5">
			<h3 class="text-sm font-semibold text-text-primary">Locale</h3>
			<p class="mt-0.5 text-xs text-text-secondary">
				Auto-detected from your browser. Adjust if needed.
			</p>
		</div>

		<!-- Language -->
		<div>
			<label for="deploy-language" class="mb-1.5 block text-xs font-medium text-text-secondary">
				Language
			</label>
			<input
				id="deploy-language"
				type="text"
				bind:value={language}
				placeholder="en-US"
				class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
			/>
		</div>

		<!-- Timezone + Country -->
		<div class="grid grid-cols-2 gap-4">
			<div>
				<label for="deploy-timezone" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Timezone
				</label>
				<input
					id="deploy-timezone"
					type="text"
					bind:value={timezone}
					placeholder="America/New_York"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>

			<div>
				<label for="deploy-country" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Country
				</label>
				<input
					id="deploy-country"
					type="text"
					bind:value={country}
					placeholder="US"
					class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
				/>
			</div>
		</div>
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
			onclick={handleSubmit}
			disabled={!isValid || submitting}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if submitting}
				<Loader2 size={16} class="animate-spin" />
				Saving...
			{:else}
				Save & Continue
				<ArrowRight size={16} />
			{/if}
		</button>
	</div>
</div>
