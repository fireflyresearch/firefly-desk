<!--
  TunnelSetupWizard.svelte — Step-by-step modal wizard for tunnel setup.

  Walks administrators through: backend selection, auth token (ngrok),
  dependency installation (pyngrok), and tunnel connection with live
  webhook URL generation.

  Follows the EmailSetupWizard modal/step-indicator patterns exactly.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		ChevronLeft,
		ChevronRight,
		Loader2,
		Check,
		CheckCircle,
		Copy,
		Key,
		Download,
		Play,
		Square,
		ExternalLink,
		Mail,
		Eye,
		EyeOff,
		AlertTriangle,
		Cloud,
		Zap,
		Radio,
		Globe,
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		open: boolean;
		onClose: () => void;
		onConnected?: () => void;
	}

	interface TunnelStatus {
		active: boolean;
		url: string | null;
		available: boolean;
		error: string | null;
		backend?: string;
	}

	interface PyngrokStatus {
		installed: boolean;
		version: string | null;
	}

	interface TunnelBackendInfo {
		id: string;
		label: string;
		available: boolean;
		requires_auth: boolean;
	}

	interface Integration {
		type: string;
		provider: string;
		enabled: boolean;
		webhook_path: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onConnected }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const NGROK_STEPS = ['Backend', 'Auth Token', 'Dependencies', 'Connect'] as const;
	const CLOUDFLARED_STEPS = ['Backend', 'Connect'] as const;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);

	// Backend selection
	let tunnelBackends = $state<TunnelBackendInfo[]>([]);
	let selectedBackend = $state<string | null>(null);

	// Auth token (ngrok)
	let authToken = $state('');
	let showAuthToken = $state(false);
	let authTokenSaved = $state(false);
	let authTokenSaving = $state(false);

	// pyngrok (ngrok)
	let pyngrokStatus = $state<PyngrokStatus>({ installed: false, version: null });
	let pyngrokInstalling = $state(false);

	// Tunnel
	let tunnelStatus = $state<TunnelStatus>({ active: false, url: null, available: false, error: null });
	let tunnelLoading = $state(false);

	// Integrations (for webhook URL display)
	let integrations = $state<Integration[]>([]);

	// Clipboard
	let copiedField = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let steps = $derived(selectedBackend === 'cloudflared' ? CLOUDFLARED_STEPS : NGROK_STEPS);
	let lastStepIdx = $derived(steps.length - 1);
	let cfAvailable = $derived(tunnelBackends.find(b => b.id === 'cloudflared')?.available ?? false);

	let tunnelReady = $derived(
		selectedBackend === 'cloudflared'
			? tunnelBackends.some(b => b.id === 'cloudflared' && b.available)
			: authTokenSaved && pyngrokStatus.installed
	);

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	function isStepValid(step: number): boolean {
		if (selectedBackend === 'cloudflared') {
			switch (step) {
				case 0: return selectedBackend !== null;
				case 1: return true; // connect step is always "valid" to reach
				default: return false;
			}
		}
		// ngrok
		switch (step) {
			case 0: return selectedBackend !== null;
			case 1: return authTokenSaved;
			case 2: return pyngrokStatus.installed;
			case 3: return true;
			default: return false;
		}
	}

	function isStepComplete(step: number): boolean {
		if (selectedBackend === 'cloudflared') {
			if (step === 0) return selectedBackend !== null;
			if (step === 1) return tunnelStatus.active;
			return false;
		}
		if (step === 0) return selectedBackend !== null;
		if (step === 1) return authTokenSaved;
		if (step === 2) return pyngrokStatus.installed;
		if (step === 3) return tunnelStatus.active;
		return false;
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function goNext() {
		if (currentStep < lastStepIdx && isStepValid(currentStep)) {
			currentStep += 1;
		}
	}

	function goPrev() {
		if (currentStep > 0) {
			currentStep -= 1;
		}
	}

	function goToStep(step: number) {
		if (step <= currentStep || (step === currentStep + 1 && isStepValid(currentStep))) {
			currentStep = step;
		}
	}

	// -----------------------------------------------------------------------
	// Clipboard
	// -----------------------------------------------------------------------

	async function copyToClipboard(text: string, field: string) {
		try {
			await navigator.clipboard.writeText(text);
			copiedField = field;
			setTimeout(() => (copiedField = null), 2000);
		} catch { /* ignore */ }
	}

	// -----------------------------------------------------------------------
	// Init — load data when opened
	// -----------------------------------------------------------------------

	$effect(() => {
		if (open) {
			loadTunnelBackends();
			loadTunnelStatus();
			loadPyngrokStatus();
			loadAuthToken();
			loadIntegrations();
		}
	});

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	async function loadTunnelBackends() {
		try {
			const res = await apiJson<{ backends: TunnelBackendInfo[] }>('/dev-tools/tunnel/backends');
			tunnelBackends = res.backends || [];
		} catch { /* ignore */ }
	}

	async function loadTunnelStatus() {
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/status');
		} catch { /* ignore */ }
	}

	async function loadPyngrokStatus() {
		try {
			pyngrokStatus = await apiJson<PyngrokStatus>('/dev-tools/tunnel/pyngrok-status');
		} catch { /* ignore */ }
	}

	async function loadAuthToken() {
		try {
			const res = await apiJson<{ ngrok_auth_token?: string; tunnel_backend?: string }>('/settings/email');
			if (res.ngrok_auth_token) {
				authToken = res.ngrok_auth_token;
				authTokenSaved = true;
			}
			if (res.tunnel_backend) {
				selectedBackend = res.tunnel_backend;
			}
		} catch { /* ignore */ }
	}

	async function loadIntegrations() {
		try {
			const res = await apiJson<{ integrations: Integration[] }>('/dev-tools/integrations');
			integrations = res.integrations || [];
		} catch { /* ignore */ }
	}

	async function selectBackend(backend: string) {
		selectedBackend = backend;
		try {
			await apiJson('/dev-tools/tunnel/backend', {
				method: 'PUT',
				body: JSON.stringify({ backend }),
			});
		} catch { /* ignore */ }
	}

	async function saveAuthToken() {
		if (!authToken.trim()) return;
		authTokenSaving = true;
		try {
			await apiJson('/dev-tools/tunnel/auth-token', {
				method: 'PUT',
				body: JSON.stringify({ auth_token: authToken.trim() }),
			});
			authTokenSaved = true;
		} catch { /* ignore */ }
		finally { authTokenSaving = false; }
	}

	async function installPyngrok() {
		pyngrokInstalling = true;
		try {
			const res = await apiJson<{ success: boolean; error?: string }>('/dev-tools/tunnel/install-pyngrok', {
				method: 'POST',
			});
			if (res.success) {
				await loadPyngrokStatus();
			}
		} catch { /* ignore */ }
		finally { pyngrokInstalling = false; }
	}

	async function startTunnel() {
		tunnelLoading = true;
		tunnelStatus = { ...tunnelStatus, error: null };
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/start', { method: 'POST' });
			if (tunnelStatus.active) {
				onConnected?.();
			}
		} catch (e) {
			tunnelStatus = { ...tunnelStatus, error: e instanceof Error ? e.message : 'Failed to start tunnel' };
		} finally {
			tunnelLoading = false;
		}
	}

	async function stopTunnel() {
		tunnelLoading = true;
		try {
			tunnelStatus = await apiJson<TunnelStatus>('/dev-tools/tunnel/stop', { method: 'POST' });
		} catch (e) {
			tunnelStatus = { ...tunnelStatus, error: e instanceof Error ? e.message : 'Failed to stop tunnel' };
		} finally {
			tunnelLoading = false;
		}
	}

	function handleClose() {
		onClose();
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) handleClose();
	}
</script>

{#if open}
	<!-- Modal backdrop -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		role="presentation"
		onclick={handleBackdropClick}
	>
		<!-- Modal content -->
		<div class="mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-surface shadow-2xl">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="flex items-center gap-2 text-base font-semibold text-text-primary">
					<Radio size={18} class="text-accent" />
					Tunnel Setup
				</h2>
				<button
					type="button"
					onclick={handleClose}
					class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Step indicators -->
			<div class="flex items-center gap-1 border-b border-border px-6 py-3">
				{#each steps as stepLabel, i}
					{@const active = i === currentStep}
					{@const complete = isStepComplete(i)}
					{@const clickable = i <= currentStep || (i === currentStep + 1 && isStepValid(currentStep))}

					{#if i > 0}
						<div class="h-px flex-1 {i <= currentStep ? 'bg-accent' : 'bg-border'}"></div>
					{/if}

					<button
						type="button"
						onclick={() => goToStep(i)}
						disabled={!clickable}
						class="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-medium transition-colors
							{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}
							{clickable ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default opacity-50'}"
					>
						<span
							class="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold
								{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
						>
							{#if complete}
								<Check size={10} />
							{:else}
								{i + 1}
							{/if}
						</span>
						<span class="hidden lg:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Step content -->
			<div class="flex-1 overflow-y-auto px-6 py-5">

				<!-- ============================================ -->
				<!-- Step 0: Choose Backend                        -->
				<!-- ============================================ -->
				{#if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Choose the tunnel provider that will forward webhook traffic from the internet to your local development server.
						</p>

						{#if tunnelBackends.length === 0}
							<div class="flex justify-center py-8">
								<Loader2 size={20} class="animate-spin text-text-secondary" />
							</div>
						{:else}
							<div class="grid grid-cols-2 gap-4">
								<!-- ngrok -->
								<button
									type="button"
									onclick={() => selectBackend('ngrok')}
									class="flex flex-col items-start gap-3 rounded-lg border-2 p-5 text-left transition-all
										{selectedBackend === 'ngrok'
										? 'border-accent ring-2 ring-accent/30 bg-accent/5'
										: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<div class="flex w-full items-center justify-between">
										<span class="text-sm font-semibold {selectedBackend === 'ngrok' ? 'text-accent' : 'text-text-primary'}">
											ngrok
										</span>
										<Zap size={20} class={selectedBackend === 'ngrok' ? 'text-accent' : 'text-text-secondary'} />
									</div>
									<span class="text-xs text-text-secondary">
										Popular tunneling service with built-in dashboard and request inspection.
									</span>
									<ul class="flex flex-col gap-1 text-[11px] text-text-secondary">
										<li class="flex items-center gap-1.5">
											<Check size={10} class="shrink-0 text-success" /> Stable public URLs
										</li>
										<li class="flex items-center gap-1.5">
											<Check size={10} class="shrink-0 text-success" /> Request inspection UI
										</li>
										<li class="flex items-center gap-1.5">
											<Check size={10} class="shrink-0 text-success" /> Free tier available
										</li>
									</ul>
								</button>

								<!-- Cloudflare Tunnel -->
								<button
									type="button"
									onclick={() => selectBackend('cloudflared')}
									disabled={!cfAvailable}
									class="flex flex-col items-start gap-3 rounded-lg border-2 p-5 text-left transition-all
										{selectedBackend === 'cloudflared'
										? 'border-accent ring-2 ring-accent/30 bg-accent/5'
										: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}
										{!cfAvailable ? 'opacity-60 cursor-not-allowed' : ''}"
								>
									<div class="flex w-full items-center justify-between">
										<span class="text-sm font-semibold {selectedBackend === 'cloudflared' ? 'text-accent' : 'text-text-primary'}">
											Cloudflare Tunnel
										</span>
										<Cloud size={20} class={selectedBackend === 'cloudflared' ? 'text-accent' : 'text-text-secondary'} />
									</div>
									<span class="text-xs text-text-secondary">
										Zero-config tunnel by Cloudflare. No account or auth token needed.
									</span>
									<ul class="flex flex-col gap-1 text-[11px] text-text-secondary">
										<li class="flex items-center gap-1.5">
											<Check size={10} class="shrink-0 text-success" /> No authentication required
										</li>
										<li class="flex items-center gap-1.5">
											<Check size={10} class="shrink-0 text-success" /> Single binary, no setup
										</li>
										<li class="flex items-center gap-1.5">
											{#if cfAvailable}
												<Check size={10} class="shrink-0 text-success" /> Installed
											{:else}
												<AlertTriangle size={10} class="shrink-0 text-warning" /> Not installed — run <code class="rounded bg-surface-secondary px-1">brew install cloudflared</code>
											{/if}
										</li>
									</ul>
								</button>
							</div>
						{/if}
					</div>

				<!-- ============================================ -->
				<!-- Step 1 (ngrok): Auth Token                    -->
				<!-- ============================================ -->
				{:else if selectedBackend === 'ngrok' && currentStep === 1}
					<div class="flex flex-col gap-5">
						<p class="text-sm text-text-secondary">
							Enter your ngrok authentication token. This is required to create tunnels through the ngrok service.
						</p>

						<label class="flex flex-col gap-1.5">
							<span class="text-xs font-medium text-text-secondary">
								Auth Token <span class="text-danger">*</span>
							</span>
							<div class="flex items-center gap-2">
								<div class="relative flex-1">
									<input
										type={showAuthToken ? 'text' : 'password'}
										bind:value={authToken}
										placeholder="Paste your ngrok auth token"
										oninput={() => { if (authTokenSaved) authTokenSaved = false; }}
										class="w-full rounded-md border border-border bg-surface px-3 py-2 pr-9 font-mono text-sm text-text-primary outline-none transition-colors focus:border-accent"
									/>
									<button
										type="button"
										onclick={() => (showAuthToken = !showAuthToken)}
										class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover"
										title={showAuthToken ? 'Hide' : 'Show'}
									>
										{#if showAuthToken}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
									</button>
								</div>
								<button
									type="button"
									onclick={saveAuthToken}
									disabled={authTokenSaving || !authToken.trim()}
									class="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-all disabled:opacity-50
										{authTokenSaved ? 'border border-success/30 bg-success/10 text-success' : 'bg-accent text-white hover:bg-accent-hover'}"
								>
									{#if authTokenSaving}
										<Loader2 size={14} class="animate-spin" />
									{:else if authTokenSaved}
										<CheckCircle size={14} />
										Saved
									{:else}
										Save
									{/if}
								</button>
							</div>
						</label>

						<!-- Help box -->
						<div class="rounded-lg border border-border/50 bg-surface-secondary/30 p-4">
							<h3 class="mb-1 text-xs font-semibold text-text-primary">Where to find your token</h3>
							<ol class="flex flex-col gap-1 text-xs text-text-secondary">
								<li>1. Sign up or log in at <a href="https://dashboard.ngrok.com" target="_blank" rel="noopener noreferrer" class="font-medium text-accent underline decoration-accent/30 hover:decoration-accent">dashboard.ngrok.com <ExternalLink size={10} class="mb-0.5 inline" /></a></li>
								<li>2. Navigate to <strong>Your Authtoken</strong> in the sidebar</li>
								<li>3. Copy the token and paste it above</li>
							</ol>
						</div>

						{#if authTokenSaved}
							<div class="flex items-center gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3">
								<CheckCircle size={16} class="text-success" />
								<span class="text-sm text-success">Auth token saved successfully. Click Next to continue.</span>
							</div>
						{/if}
					</div>

				<!-- ============================================ -->
				<!-- Step 2 (ngrok): Dependencies                  -->
				<!-- ============================================ -->
				{:else if selectedBackend === 'ngrok' && currentStep === 2}
					<div class="flex flex-col gap-5">
						<p class="text-sm text-text-secondary">
							The <strong>pyngrok</strong> Python package is required to manage ngrok tunnels from the server.
						</p>

						<div class="rounded-lg border border-border bg-surface p-5">
							<div class="flex items-center gap-3">
								<div class="flex h-10 w-10 items-center justify-center rounded-lg {pyngrokStatus.installed ? 'bg-success/10' : 'bg-surface-secondary'}">
									{#if pyngrokStatus.installed}
										<CheckCircle size={20} class="text-success" />
									{:else}
										<Download size={20} class="text-text-secondary" />
									{/if}
								</div>
								<div class="flex-1">
									<h3 class="text-sm font-semibold text-text-primary">pyngrok</h3>
									<p class="text-xs text-text-secondary">Python wrapper for the ngrok CLI</p>
								</div>
								{#if pyngrokStatus.installed}
									<span class="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
										<CheckCircle size={12} />
										v{pyngrokStatus.version}
									</span>
								{:else}
									<button
										type="button"
										onclick={installPyngrok}
										disabled={pyngrokInstalling}
										class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
									>
										{#if pyngrokInstalling}
											<Loader2 size={14} class="animate-spin" />
											Installing...
										{:else}
											<Download size={14} />
											Install
										{/if}
									</button>
								{/if}
							</div>

							{#if !pyngrokStatus.installed}
								<p class="mt-3 text-xs text-text-secondary">
									This will run <code class="rounded bg-surface-secondary px-1.5 py-0.5 text-[11px]">pip install pyngrok</code> in the server's Python environment.
								</p>
							{/if}
						</div>

						{#if pyngrokStatus.installed}
							<div class="flex items-center gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3">
								<CheckCircle size={16} class="text-success" />
								<span class="text-sm text-success">All dependencies installed. Click Next to connect your tunnel.</span>
							</div>
						{/if}
					</div>

				<!-- ============================================ -->
				<!-- Last Step: Connect                             -->
				<!-- ============================================ -->
				{:else if currentStep === lastStepIdx}
					<div class="flex flex-col gap-5">
						{#if tunnelStatus.active}
							<div class="flex items-center gap-3 rounded-lg border border-success/30 bg-success/5 px-4 py-3">
								<span class="relative flex h-3 w-3">
									<span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75"></span>
									<span class="relative inline-flex h-3 w-3 rounded-full bg-success"></span>
								</span>
								<div class="flex-1">
									<p class="text-sm font-medium text-success">Tunnel connected</p>
									<p class="text-xs text-success/70">Forwarding internet traffic to your local server</p>
								</div>
								<button
									type="button"
									onclick={stopTunnel}
									disabled={tunnelLoading}
									class="inline-flex items-center gap-1.5 rounded-md border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
								>
									{#if tunnelLoading}<Loader2 size={12} class="animate-spin" />{:else}<Square size={12} />{/if}
									Disconnect
								</button>
							</div>
						{:else}
							<p class="text-sm text-text-secondary">
								{#if selectedBackend === 'cloudflared'}
									Start a Cloudflare Tunnel to expose your local server to the internet.
								{:else}
									Start an ngrok tunnel to expose your local server to the internet. Your webhook endpoints will be accessible at the generated public URL.
								{/if}
							</p>

							<div class="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface-secondary/20 p-8">
								<div class="flex h-14 w-14 items-center justify-center rounded-full bg-accent/10">
									<Globe size={28} class="text-accent" />
								</div>
								<div class="text-center">
									<p class="text-sm font-medium text-text-primary">Ready to connect</p>
									<p class="text-xs text-text-secondary">
										Using <strong>{selectedBackend === 'cloudflared' ? 'Cloudflare Tunnel' : 'ngrok'}</strong> to forward to <code class="rounded bg-surface-secondary px-1">localhost:8000</code>
									</p>
								</div>
								<button
									type="button"
									onclick={startTunnel}
									disabled={tunnelLoading || !tunnelReady}
									class="inline-flex items-center gap-2 rounded-md bg-accent px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
								>
									{#if tunnelLoading}
										<Loader2 size={16} class="animate-spin" />
										Connecting...
									{:else}
										<Play size={16} />
										Start Tunnel
									{/if}
								</button>
								{#if !tunnelReady}
									<div class="flex items-center gap-1.5 text-xs text-warning">
										<AlertTriangle size={12} />
										{#if selectedBackend === 'cloudflared'}
											cloudflared is not installed
										{:else if !authTokenSaved}
											Save your auth token first
										{:else}
											Install pyngrok first
										{/if}
									</div>
								{/if}
							</div>
						{/if}

						<!-- Error -->
						{#if tunnelStatus.error}
							<div class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3">
								<AlertTriangle size={14} class="mt-0.5 shrink-0 text-danger" />
								<p class="text-sm text-danger">{tunnelStatus.error}</p>
							</div>
						{/if}

						<!-- Active tunnel details -->
						{#if tunnelStatus.active && tunnelStatus.url}
							<!-- Public URL -->
							<div>
								<label class="mb-1.5 block text-xs font-medium text-text-secondary">Public URL</label>
								<div class="flex items-center gap-2">
									<code class="flex-1 rounded-lg border border-success/30 bg-success/5 px-4 py-2.5 text-sm font-medium text-success">
										{tunnelStatus.url}
									</code>
									<button
										type="button"
										onclick={() => copyToClipboard(tunnelStatus.url!, 'tunnel-url')}
										class="inline-flex h-[38px] items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
									>
										{#if copiedField === 'tunnel-url'}
											<CheckCircle size={12} class="text-success" /> Copied
										{:else}
											<Copy size={12} /> Copy
										{/if}
									</button>
								</div>
							</div>

							<!-- Webhook Endpoints -->
							{#if integrations.length > 0}
								<div>
									<label class="mb-1.5 block text-xs font-medium text-text-secondary">Webhook Endpoints</label>
									<div class="flex flex-col gap-2">
										{#each integrations as integration}
											{@const fullUrl = `${tunnelStatus.url}${integration.webhook_path}`}
											<div class="flex items-center gap-2 rounded-lg border border-border/50 bg-surface-secondary/20 p-3">
												<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent/10">
													<Mail size={14} class="text-accent" />
												</div>
												<div class="flex-1 overflow-hidden">
													<p class="text-xs font-medium capitalize text-text-primary">{integration.provider}</p>
													<code class="block truncate text-[11px] text-text-secondary">{fullUrl}</code>
												</div>
												<button
													type="button"
													onclick={() => copyToClipboard(fullUrl, `webhook-${integration.provider}`)}
													class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
												>
													{#if copiedField === `webhook-${integration.provider}`}
														<CheckCircle size={10} class="text-success" />
													{:else}
														<Copy size={10} />
													{/if}
												</button>
											</div>
										{/each}
									</div>
									<p class="mt-2 text-xs text-text-secondary">
										Paste this URL into your email provider's webhook configuration.
									</p>
								</div>
							{:else}
								<div class="rounded-lg border border-border/50 bg-surface-secondary/20 p-4 text-center">
									<p class="text-sm text-text-secondary">No integrations configured.</p>
									<p class="mt-1 text-xs text-text-secondary">
										Set up email in <a href="/admin/email" class="font-medium text-accent hover:underline">Email Settings</a> to see webhook URLs here.
									</p>
								</div>
							{/if}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Footer navigation -->
			<div class="flex items-center justify-between border-t border-border px-6 py-4">
				<div>
					{#if currentStep > 0}
						<button
							type="button"
							onclick={goPrev}
							class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							<ChevronLeft size={14} />
							Back
						</button>
					{/if}
				</div>

				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={handleClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						{tunnelStatus.active ? 'Done' : 'Cancel'}
					</button>

					{#if currentStep < lastStepIdx}
						<button
							type="button"
							onclick={goNext}
							disabled={!isStepValid(currentStep)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ChevronRight size={14} />
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
