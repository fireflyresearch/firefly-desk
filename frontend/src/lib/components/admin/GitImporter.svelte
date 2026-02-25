<!--
  GitImporter.svelte - Multi-repo Git import wizard with cart workflow.

  A 3-step wizard (Connect -> Browse -> Cart) that supports multiple Git
  providers (GitHub, GitLab, Bitbucket). Users authenticate with a PAT,
  browse accounts/repos/branches/files, add selections to a cart from
  multiple repositories, then batch-import everything at once.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		GitBranch,
		Lock,
		Search,
		Check,
		Loader2,
		FileText,
		AlertCircle,
		CheckCircle2,
		FolderTree,
		Building,
		User,
		ShoppingCart,
		X,
		Trash2,
		Plus,
		ChevronRight,
		ExternalLink
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		onsuccess?: () => void;
	}

	let { onsuccess }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface GitProvider {
		id: string;
		provider_type: string;
		display_name: string;
		base_url: string;
		is_active: boolean;
	}

	interface Account {
		login: string;
		avatar_url: string;
		description: string;
	}

	interface Repo {
		full_name: string;
		name: string;
		owner: string;
		private: boolean;
		default_branch: string;
		description: string;
	}

	interface Branch {
		name: string;
		sha: string;
	}

	interface TreeEntry {
		path: string;
		sha: string;
		size: number;
		file_type: string;
	}

	interface CartItem {
		provider_id: string;
		provider_type: string;
		owner: string;
		repo: string;
		branch: string;
		paths: string[];
	}

	interface ImportResult {
		path: string;
		document_id: string;
		status: string;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const WIZARD_STEPS: { id: 'connect' | 'browse' | 'cart'; label: string }[] = [
		{ id: 'connect', label: 'Connect' },
		{ id: 'browse', label: 'Browse' },
		{ id: 'cart', label: 'Cart' }
	];

	const FILE_TYPE_COLORS: Record<string, string> = {
		markdown: 'bg-blue-100 text-blue-700',
		openapi: 'bg-purple-100 text-purple-700',
		data: 'bg-amber-100 text-amber-700',
		unknown: 'bg-gray-100 text-gray-600'
	};

	// -----------------------------------------------------------------------
	// State — step tracking
	// -----------------------------------------------------------------------

	let step = $state<'connect' | 'browse' | 'cart'>('connect');

	// -----------------------------------------------------------------------
	// State — provider & auth
	// -----------------------------------------------------------------------

	let providers = $state<GitProvider[]>([]);
	let selectedProviderId = $state('');
	let token = $state('');
	let connecting = $state(false);
	let connected = $state(false);
	let loadingProviders = $state(true);
	let error = $state('');

	// -----------------------------------------------------------------------
	// State — browse
	// -----------------------------------------------------------------------

	let accounts = $state<Account[]>([]);
	let selectedAccount = $state('');
	let repos = $state<Repo[]>([]);
	let repoSearch = $state('');
	let selectedRepo = $state<Repo | null>(null);
	let branches = $state<Branch[]>([]);
	let selectedBranch = $state('');
	let treeEntries = $state<TreeEntry[]>([]);
	let selectedPaths = $state<Set<string>>(new Set());
	let loadingRepos = $state(false);
	let loadingTree = $state(false);
	let loadingBranches = $state(false);

	// -----------------------------------------------------------------------
	// State — cart
	// -----------------------------------------------------------------------

	let cart = $state<CartItem[]>([]);
	let importTags = $state('');
	let importing = $state(false);
	let importResults = $state<ImportResult[] | null>(null);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let selectedProvider = $derived(providers.find((p) => p.id === selectedProviderId));

	let totalCartFiles = $derived(cart.reduce((sum, item) => sum + item.paths.length, 0));

	let selectedCount = $derived(selectedPaths.size);

	let filteredRepos = $derived.by(() => {
		if (!repoSearch.trim()) return repos;
		const term = repoSearch.toLowerCase();
		return repos.filter(
			(r) =>
				r.name.toLowerCase().includes(term) ||
				r.full_name.toLowerCase().includes(term) ||
				(r.description && r.description.toLowerCase().includes(term))
		);
	});

	// -----------------------------------------------------------------------
	// Provider loading
	// -----------------------------------------------------------------------

	async function loadProviders() {
		loadingProviders = true;
		error = '';
		try {
			providers = await apiJson<GitProvider[]>('/git/providers');
			if (providers.length === 1) {
				selectedProviderId = providers[0].id;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load Git providers';
		} finally {
			loadingProviders = false;
		}
	}

	// Initial load
	$effect(() => {
		loadProviders();
	});

	// -----------------------------------------------------------------------
	// Connect
	// -----------------------------------------------------------------------

	async function connect() {
		if (!selectedProviderId || !token.trim()) return;
		connecting = true;
		error = '';
		try {
			accounts = await apiJson<Account[]>(
				`/git/${encodeURIComponent(selectedProviderId)}/accounts?token=${encodeURIComponent(token)}`
			);
			connected = true;
			step = 'browse';
			// Auto-load personal repos
			await loadRepos();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to connect. Check your token and try again.';
		} finally {
			connecting = false;
		}
	}

	// -----------------------------------------------------------------------
	// Browse — repos
	// -----------------------------------------------------------------------

	async function loadRepos(account?: string) {
		loadingRepos = true;
		error = '';
		selectedRepo = null;
		branches = [];
		treeEntries = [];
		selectedPaths = new Set();
		try {
			const params = new URLSearchParams();
			params.set('token', token);
			if (account) params.set('account', account);
			if (repoSearch.trim()) params.set('search', repoSearch.trim());
			repos = await apiJson<Repo[]>(
				`/git/${encodeURIComponent(selectedProviderId)}/repos?${params.toString()}`
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load repositories';
		} finally {
			loadingRepos = false;
		}
	}

	async function searchRepos() {
		await loadRepos(selectedAccount || undefined);
	}

	function selectAccountAndLoad(account: string) {
		selectedAccount = account;
		repoSearch = '';
		loadRepos(account);
	}

	function loadPersonalRepos() {
		selectedAccount = '';
		repoSearch = '';
		loadRepos();
	}

	// -----------------------------------------------------------------------
	// Browse — repo selection -> branches -> tree
	// -----------------------------------------------------------------------

	async function selectRepo(repo: Repo) {
		selectedRepo = repo;
		selectedBranch = '';
		treeEntries = [];
		selectedPaths = new Set();
		loadingBranches = true;
		error = '';
		try {
			branches = await apiJson<Branch[]>(
				`/git/${encodeURIComponent(selectedProviderId)}/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}/branches?token=${encodeURIComponent(token)}`
			);
			// Auto-select default branch
			if (branches.length > 0) {
				const defaultBr = repo.default_branch ?? 'main';
				const found = branches.find((b) => b.name === defaultBr);
				selectedBranch = found ? found.name : branches[0].name;
				await loadTree(selectedBranch);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load branches';
		} finally {
			loadingBranches = false;
		}
	}

	async function loadTree(branch: string) {
		if (!selectedRepo) return;
		loadingTree = true;
		error = '';
		selectedPaths = new Set();
		try {
			treeEntries = await apiJson<TreeEntry[]>(
				`/git/${encodeURIComponent(selectedProviderId)}/repos/${encodeURIComponent(selectedRepo.owner)}/${encodeURIComponent(selectedRepo.name)}/tree/${encodeURIComponent(branch)}?token=${encodeURIComponent(token)}`
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load file tree';
		} finally {
			loadingTree = false;
		}
	}

	async function changeBranch(branch: string) {
		selectedBranch = branch;
		await loadTree(branch);
	}

	// -----------------------------------------------------------------------
	// Browse — file selection
	// -----------------------------------------------------------------------

	function togglePath(path: string) {
		const next = new Set(selectedPaths);
		if (next.has(path)) {
			next.delete(path);
		} else {
			next.add(path);
		}
		selectedPaths = next;
	}

	function selectAllFiles() {
		selectedPaths = new Set(treeEntries.map((e) => e.path));
	}

	function deselectAllFiles() {
		selectedPaths = new Set();
	}

	// -----------------------------------------------------------------------
	// Cart operations
	// -----------------------------------------------------------------------

	function addToCart() {
		if (!selectedRepo || selectedPaths.size === 0 || !selectedProvider) return;

		// Check if we already have an item for this repo+branch combo
		const existingIndex = cart.findIndex(
			(item) =>
				item.provider_id === selectedProviderId &&
				item.owner === selectedRepo!.owner &&
				item.repo === selectedRepo!.name &&
				item.branch === selectedBranch
		);

		if (existingIndex >= 0) {
			// Merge paths
			const existing = cart[existingIndex];
			const mergedPaths = new Set([...existing.paths, ...selectedPaths]);
			cart[existingIndex] = { ...existing, paths: [...mergedPaths] };
			// Trigger reactivity
			cart = [...cart];
		} else {
			cart = [
				...cart,
				{
					provider_id: selectedProviderId,
					provider_type: selectedProvider.provider_type,
					owner: selectedRepo.owner,
					repo: selectedRepo.name,
					branch: selectedBranch,
					paths: [...selectedPaths]
				}
			];
		}

		// Reset browse selection for next pick
		selectedRepo = null;
		branches = [];
		treeEntries = [];
		selectedPaths = new Set();
	}

	function removeCartItem(index: number) {
		cart = cart.filter((_, i) => i !== index);
	}

	function removeCartPath(itemIndex: number, path: string) {
		const item = cart[itemIndex];
		if (!item) return;
		const newPaths = item.paths.filter((p) => p !== path);
		if (newPaths.length === 0) {
			removeCartItem(itemIndex);
		} else {
			cart[itemIndex] = { ...item, paths: newPaths };
			cart = [...cart];
		}
	}

	// -----------------------------------------------------------------------
	// Import
	// -----------------------------------------------------------------------

	async function importAll() {
		if (cart.length === 0) return;
		importing = true;
		error = '';
		importResults = null;

		const tags = importTags
			.split(',')
			.map((t) => t.trim())
			.filter(Boolean);

		// Group cart items by provider_id
		const byProvider = new Map<string, CartItem[]>();
		for (const item of cart) {
			const group = byProvider.get(item.provider_id) ?? [];
			group.push(item);
			byProvider.set(item.provider_id, group);
		}

		const allResults: ImportResult[] = [];

		try {
			for (const [providerId, items] of byProvider) {
				const payload = {
					items: items.map((item) => ({
						owner: item.owner,
						repo: item.repo,
						branch: item.branch,
						paths: item.paths,
						tags
					}))
				};

				const result = await apiJson<{ status: string; items: ImportResult[] }>(
					`/git/${encodeURIComponent(providerId)}/import?token=${encodeURIComponent(token)}`,
					{
						method: 'POST',
						body: JSON.stringify(payload)
					}
				);

				allResults.push(...(result.items ?? []));
			}

			importResults = allResults;
			cart = [];
			onsuccess?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Import failed';
		} finally {
			importing = false;
		}
	}

	// -----------------------------------------------------------------------
	// Disconnect / reset
	// -----------------------------------------------------------------------

	function disconnect() {
		step = 'connect';
		connected = false;
		token = '';
		accounts = [];
		selectedAccount = '';
		repos = [];
		repoSearch = '';
		selectedRepo = null;
		branches = [];
		selectedBranch = '';
		treeEntries = [];
		selectedPaths = new Set();
		cart = [];
		importTags = '';
		importResults = null;
		error = '';
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<div class="flex flex-col gap-4">
	<!-- Step indicator -->
	<div class="flex items-center gap-2 text-xs">
		{#each WIZARD_STEPS as s, i}
			{#if i > 0}
				<div
					class="h-px w-6 {step === s.id || (s.id === 'browse' && step === 'cart') || (s.id === 'connect' && step !== 'connect') ? 'bg-accent' : 'bg-border'}"
				></div>
			{/if}
			<button
				type="button"
				disabled={s.id === 'connect' ? false : s.id === 'browse' ? !connected : !connected}
				onclick={() => {
					if (s.id === 'connect' || connected) {
						step = s.id;
						error = '';
					}
				}}
				class="flex items-center gap-1.5"
			>
				<div
					class="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium transition-colors
						{step === s.id
						? 'bg-accent text-white'
						: (s.id === 'connect' && step !== 'connect') || (s.id === 'browse' && step === 'cart')
							? 'bg-accent/20 text-accent'
							: 'bg-surface-secondary text-text-tertiary'}"
				>
					{#if (s.id === 'connect' && step !== 'connect') || (s.id === 'browse' && step === 'cart')}
						<Check size={10} />
					{:else}
						{i + 1}
					{/if}
				</div>
				<span
					class="{step === s.id ? 'font-medium text-text-primary' : 'text-text-tertiary'}"
				>
					{s.label}
				</span>
				{#if s.id === 'cart' && totalCartFiles > 0}
					<span
						class="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold text-white"
					>
						{totalCartFiles}
					</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Error banner -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} />
			{error}
		</div>
	{/if}

	<!-- ================================================================= -->
	<!-- Step 1: Connect                                                    -->
	<!-- ================================================================= -->
	{#if step === 'connect'}
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-2">
				<GitBranch size={20} class="text-text-primary" />
				<h3 class="text-sm font-semibold text-text-primary">Connect to Git Provider</h3>
			</div>

			{#if loadingProviders}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else if providers.length === 0}
				<div class="rounded-xl border border-border bg-surface-secondary p-5 text-center">
					<GitBranch size={24} class="mx-auto mb-2 text-text-tertiary" />
					<p class="text-sm text-text-secondary">No Git providers configured.</p>
					<a
						href="/admin/git-providers"
						class="mt-2 inline-flex items-center gap-1 text-sm text-accent hover:underline"
					>
						Configure providers
						<ExternalLink size={12} />
					</a>
				</div>
			{:else}
				<p class="text-xs text-text-secondary">
					Select a Git provider and enter a Personal Access Token to browse repositories.
				</p>

				<!-- Provider selector -->
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Provider</span>
					<select
						bind:value={selectedProviderId}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						<option value="">Select a provider...</option>
						{#each providers as provider}
							<option value={provider.id}>
								{provider.display_name} ({provider.provider_type})
							</option>
						{/each}
					</select>
				</label>

				<!-- Token input -->
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Personal Access Token</span>
					<div class="flex gap-2">
						<input
							type="password"
							bind:value={token}
							placeholder="Enter your access token..."
							class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							onkeydown={(e) => {
								if (e.key === 'Enter') {
									e.preventDefault();
									connect();
								}
							}}
						/>
						<button
							type="button"
							disabled={!selectedProviderId || !token.trim() || connecting}
							onclick={connect}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if connecting}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Lock size={14} />
							{/if}
							Connect
						</button>
					</div>
				</label>
			{/if}
		</div>

	<!-- ================================================================= -->
	<!-- Step 2: Browse                                                     -->
	<!-- ================================================================= -->
	{:else if step === 'browse'}
		<div class="flex flex-col gap-3">
			<!-- Connected provider info + disconnect -->
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<GitBranch size={14} class="text-accent" />
					<span class="text-xs font-medium text-text-primary">
						{selectedProvider?.display_name ?? 'Connected'}
					</span>
				</div>
				<button
					type="button"
					onclick={disconnect}
					class="text-xs text-text-secondary hover:text-danger"
				>
					Disconnect
				</button>
			</div>

			<!-- Account selector bar -->
			<div class="flex flex-wrap items-center gap-1.5">
				<button
					type="button"
					onclick={loadPersonalRepos}
					class="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors
						{selectedAccount === ''
						? 'bg-accent/10 font-medium text-accent'
						: 'bg-surface-secondary text-text-secondary hover:bg-surface-hover'}"
				>
					<User size={12} />
					My Repos
				</button>
				{#each accounts as account}
					<button
						type="button"
						onclick={() => selectAccountAndLoad(account.login)}
						class="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors
							{selectedAccount === account.login
							? 'bg-accent/10 font-medium text-accent'
							: 'bg-surface-secondary text-text-secondary hover:bg-surface-hover'}"
					>
						{#if account.avatar_url}
							<img
								src={account.avatar_url}
								alt={account.login}
								class="h-3.5 w-3.5 rounded-full"
							/>
						{:else}
							<Building size={12} />
						{/if}
						{account.login}
					</button>
				{/each}
			</div>

			<!-- Two-panel browse layout -->
			<div class="grid gap-3 {selectedRepo ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}">
				<!-- Left: Repo list -->
				<div class="flex flex-col gap-2">
					<!-- Repo search -->
					<div class="flex gap-1.5">
						<div class="relative flex-1">
							<Search
								size={14}
								class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
							/>
							<input
								type="text"
								bind:value={repoSearch}
								placeholder="Filter repositories..."
								class="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-xs text-text-primary outline-none focus:border-accent"
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										searchRepos();
									}
								}}
							/>
						</div>
						<button
							type="button"
							onclick={searchRepos}
							disabled={loadingRepos}
							class="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-primary transition-colors hover:bg-surface-secondary disabled:opacity-50"
						>
							{#if loadingRepos}
								<Loader2 size={12} class="animate-spin" />
							{:else}
								<Search size={12} />
							{/if}
						</button>
					</div>

					<!-- Repo list -->
					<div class="flex max-h-64 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1">
						{#if loadingRepos}
							<div class="flex items-center justify-center py-6">
								<Loader2 size={16} class="animate-spin text-accent" />
							</div>
						{:else if filteredRepos.length > 0}
							{#each filteredRepos as repo}
								<button
									type="button"
									onclick={() => selectRepo(repo)}
									class="flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs transition-colors
										{selectedRepo?.full_name === repo.full_name
										? 'bg-accent/10 text-accent'
										: 'text-text-primary hover:bg-surface-secondary'}"
								>
									<GitBranch size={12} class="shrink-0" />
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-1">
											<span class="truncate font-medium">{repo.full_name}</span>
											{#if repo.private}
												<Lock size={10} class="shrink-0 text-text-tertiary" />
											{/if}
										</div>
										{#if repo.description}
											<p class="truncate text-[11px] text-text-secondary">
												{repo.description}
											</p>
										{/if}
									</div>
									<ChevronRight size={12} class="shrink-0 text-text-tertiary" />
								</button>
							{/each}
						{:else}
							<p class="py-6 text-center text-xs text-text-secondary">
								No repositories found.
							</p>
						{/if}
					</div>
				</div>

				<!-- Right: Branch + file tree (shown when a repo is selected) -->
				{#if selectedRepo}
					<div class="flex flex-col gap-2">
						<!-- Repo header -->
						<div class="flex items-center justify-between">
							<span class="text-xs font-medium text-text-primary">
								{selectedRepo.full_name}
							</span>
							<button
								type="button"
								onclick={() => {
									selectedRepo = null;
									branches = [];
									treeEntries = [];
									selectedPaths = new Set();
								}}
								class="text-text-secondary hover:text-text-primary"
							>
								<X size={14} />
							</button>
						</div>

						<!-- Branch selector -->
						{#if loadingBranches}
							<div class="flex items-center justify-center py-4">
								<Loader2 size={14} class="animate-spin text-accent" />
							</div>
						{:else}
							<div class="flex items-center gap-2">
								<GitBranch size={12} class="shrink-0 text-text-secondary" />
								<select
									bind:value={selectedBranch}
									onchange={(e) => changeBranch((e.target as HTMLSelectElement).value)}
									class="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
								>
									{#each branches as branch}
										<option value={branch.name}>{branch.name}</option>
									{/each}
								</select>
							</div>
						{/if}

						<!-- File tree -->
						{#if loadingTree}
							<div class="flex items-center justify-center py-6">
								<Loader2 size={14} class="animate-spin text-accent" />
							</div>
						{:else if treeEntries.length > 0}
							<!-- Bulk actions -->
							<div class="flex items-center justify-between">
								<span class="text-[11px] text-text-secondary">
									{selectedCount} of {treeEntries.length} selected
								</span>
								<div class="flex gap-1.5">
									<button
										type="button"
										onclick={selectAllFiles}
										class="text-[11px] text-accent hover:underline"
									>
										Select all
									</button>
									{#if selectedCount > 0}
										<button
											type="button"
											onclick={deselectAllFiles}
											class="text-[11px] text-text-secondary hover:text-danger"
										>
											Clear
										</button>
									{/if}
								</div>
							</div>

							<div
								class="flex max-h-52 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1"
							>
								{#each treeEntries as entry}
									<label
										class="flex cursor-pointer items-center gap-1.5 rounded px-2 py-1 transition-colors hover:bg-surface-secondary"
									>
										<input
											type="checkbox"
											checked={selectedPaths.has(entry.path)}
											onchange={() => togglePath(entry.path)}
											class="h-3 w-3 rounded border-border accent-accent"
										/>
										<FileText size={11} class="shrink-0 text-text-tertiary" />
										<span class="min-w-0 flex-1 truncate text-[11px] text-text-primary">
											{entry.path}
										</span>
										<span
											class="shrink-0 rounded px-1 py-0.5 text-[9px] font-medium {FILE_TYPE_COLORS[entry.file_type] ?? FILE_TYPE_COLORS.unknown}"
										>
											{entry.file_type}
										</span>
										<span class="shrink-0 text-[9px] text-text-tertiary">
											{formatBytes(entry.size)}
										</span>
									</label>
								{/each}
							</div>

							<!-- Add to Cart button -->
							<button
								type="button"
								disabled={selectedCount === 0}
								onclick={addToCart}
								class="inline-flex items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
							>
								<Plus size={12} />
								Add {selectedCount} file{selectedCount !== 1 ? 's' : ''} to Cart
							</button>
						{:else}
							<p class="py-6 text-center text-xs text-text-secondary">
								No importable files found in this branch.
							</p>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Bottom bar: cart badge + go to cart -->
			{#if totalCartFiles > 0}
				<div class="flex items-center justify-between rounded-lg border border-accent/30 bg-accent/5 px-4 py-2">
					<div class="flex items-center gap-2">
						<ShoppingCart size={14} class="text-accent" />
						<span class="text-xs font-medium text-text-primary">
							{totalCartFiles} file{totalCartFiles !== 1 ? 's' : ''} in {cart.length} repo{cart.length !== 1 ? 's' : ''}
						</span>
					</div>
					<button
						type="button"
						onclick={() => (step = 'cart')}
						class="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
					>
						<ShoppingCart size={12} />
						Review Cart
					</button>
				</div>
			{/if}
		</div>

	<!-- ================================================================= -->
	<!-- Step 3: Cart & Import                                              -->
	<!-- ================================================================= -->
	{:else if step === 'cart'}
		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<ShoppingCart size={16} class="text-text-primary" />
					<h3 class="text-sm font-semibold text-text-primary">Import Cart</h3>
					<span class="text-xs text-text-secondary">
						{totalCartFiles} file{totalCartFiles !== 1 ? 's' : ''}
					</span>
				</div>
				<button
					type="button"
					onclick={() => (step = 'browse')}
					class="inline-flex items-center gap-1 text-xs text-accent hover:underline"
				>
					<Plus size={12} />
					Browse More
				</button>
			</div>

			{#if cart.length === 0 && !importResults}
				<div class="rounded-xl border border-border bg-surface-secondary p-6 text-center">
					<ShoppingCart size={24} class="mx-auto mb-2 text-text-tertiary" />
					<p class="text-sm text-text-secondary">Your cart is empty.</p>
					<button
						type="button"
						onclick={() => (step = 'browse')}
						class="mt-2 text-sm text-accent hover:underline"
					>
						Browse repositories to add files
					</button>
				</div>
			{:else}
				<!-- Cart items grouped by repo -->
				{#each cart as item, itemIndex}
					<div class="rounded-lg border border-border bg-surface p-3">
						<div class="mb-2 flex items-center justify-between">
							<div class="flex items-center gap-2">
								<GitBranch size={12} class="text-accent" />
								<span class="text-xs font-medium text-text-primary">
									{item.owner}/{item.repo}
								</span>
								<span class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary">
									{item.branch}
								</span>
								<span class="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">
									{item.provider_type}
								</span>
							</div>
							<button
								type="button"
								onclick={() => removeCartItem(itemIndex)}
								class="inline-flex items-center gap-1 rounded p-1 text-xs text-text-secondary hover:bg-danger/10 hover:text-danger"
								title="Remove repo"
							>
								<Trash2 size={12} />
							</button>
						</div>
						<div class="flex flex-col gap-0.5">
							{#each item.paths as path}
								<div class="flex items-center gap-1.5 rounded px-2 py-0.5">
									<FileText size={10} class="shrink-0 text-text-tertiary" />
									<span class="min-w-0 flex-1 truncate text-[11px] text-text-primary">
										{path}
									</span>
									<button
										type="button"
										onclick={() => removeCartPath(itemIndex, path)}
										class="shrink-0 rounded p-0.5 text-text-tertiary hover:text-danger"
										title="Remove file"
									>
										<X size={10} />
									</button>
								</div>
							{/each}
						</div>
					</div>
				{/each}

				<!-- Tags input -->
				{#if cart.length > 0}
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Tags (comma-separated, applied to all)</span>
						<input
							type="text"
							bind:value={importTags}
							placeholder="e.g. docs, git-import"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>

					<!-- Import button -->
					<div class="flex justify-end">
						<button
							type="button"
							disabled={importing || cart.length === 0}
							onclick={importAll}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if importing}
								<Loader2 size={14} class="animate-spin" />
								Importing...
							{:else}
								<FolderTree size={14} />
								Import All ({totalCartFiles} file{totalCartFiles !== 1 ? 's' : ''})
							{/if}
						</button>
					</div>
				{/if}

				<!-- Import results -->
				{#if importResults}
					<div class="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-secondary p-3">
						<div class="mb-1 flex items-center gap-2">
							<CheckCircle2 size={14} class="text-success" />
							<span class="text-xs font-medium text-text-primary">Import Complete</span>
						</div>
						{#each importResults as result}
							<div class="flex items-center gap-2 text-xs">
								{#if result.status === 'queued' || result.status === 'success'}
									<CheckCircle2 size={12} class="shrink-0 text-success" />
								{:else}
									<AlertCircle size={12} class="shrink-0 text-danger" />
								{/if}
								<span class="min-w-0 flex-1 truncate text-text-primary">{result.path}</span>
								<span class="shrink-0 text-text-secondary">{result.status}</span>
							</div>
						{/each}
						<button
							type="button"
							onclick={() => {
								importResults = null;
								step = 'browse';
							}}
							class="mt-2 self-start text-xs text-accent hover:underline"
						>
							Import more files
						</button>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>
