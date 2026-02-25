<!--
  KnowledgeGitHubImporter.svelte - 7-step GitHub import wizard.

  Guides users through authenticating with GitHub, selecting an account
  (personal or organization), repository, branch, and files, previewing
  content, and importing into the knowledge base.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Github,
		Lock,
		Unlock,
		Search,
		ChevronRight,
		ChevronLeft,
		Check,
		Loader2,
		FileText,
		Code2,
		AlertCircle,
		FolderTree,
		GitBranch,
		Building,
		User
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

	interface Repo {
		full_name: string;
		name: string;
		owner: string;
		private: boolean;
		default_branch: string;
		description: string;
		html_url: string;
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

	interface PreviewFile {
		path: string;
		file_type: string;
		size: number;
		content_preview: string;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = [
		'Authenticate',
		'Account',
		'Repository',
		'Branch',
		'Select Files',
		'Preview',
		'Import'
	] as const;

	const FILE_TYPE_COLORS: Record<string, string> = {
		markdown: 'bg-blue-100 text-blue-700',
		openapi: 'bg-purple-100 text-purple-700',
		data: 'bg-amber-100 text-amber-700',
		unknown: 'bg-gray-100 text-gray-600'
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let loading = $state(false);
	let error = $state('');

	// Step 1: Auth
	let authToken = $state('');
	let authMethod = $state<'none' | 'pat' | 'oauth'>('none');

	// Step 2: Account selection
	let organizations = $state<Array<{ login: string; avatar_url: string; description: string }>>([]);
	let selectedAccount = $state<string | null>(null); // null = personal, org login = org

	// Step 3: Repository
	let repos = $state<Repo[]>([]);
	let repoSearch = $state('');
	let selectedRepo = $state<Repo | null>(null);
	let manualOwner = $state('');
	let manualRepo = $state('');

	// Step 4: Branch
	let branches = $state<Branch[]>([]);
	let selectedBranch = $state('');

	// Step 5: File selection
	let treeEntries = $state<TreeEntry[]>([]);
	let selectedPaths = $state<Set<string>>(new Set());

	// Step 6: Preview
	let previewFiles = $state<PreviewFile[]>([]);

	// Step 7: Import
	let importStatus = $state<'idle' | 'importing' | 'done' | 'error'>('idle');
	let importedCount = $state(0);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let isAuthenticated = $derived(authToken.length > 0);
	let repoOwner = $derived(selectedRepo?.owner ?? manualOwner);
	let repoName = $derived(selectedRepo?.name ?? manualRepo);
	let selectedCount = $derived(selectedPaths.size);

	let filteredEntries = $derived.by(() => {
		return treeEntries;
	});

	let markdownEntries = $derived(treeEntries.filter((e) => e.file_type === 'markdown'));
	let openapiEntries = $derived(treeEntries.filter((e) => e.file_type === 'openapi'));

	// -----------------------------------------------------------------------
	// Step 1: Authentication
	// -----------------------------------------------------------------------

	async function startOAuth() {
		loading = true;
		error = '';
		try {
			const result = await apiJson<{ url: string }>('/github/auth/url');
			window.open(result.url, '_blank', 'width=600,height=700');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to get OAuth URL';
		} finally {
			loading = false;
		}
	}

	function continueWithPat() {
		if (authToken.trim()) {
			authMethod = 'pat';
			goNext();
		}
	}

	function continueWithoutAuth() {
		authMethod = 'none';
		authToken = '';
		goNext();
	}

	// -----------------------------------------------------------------------
	// Step 2: Account selection
	// -----------------------------------------------------------------------

	async function fetchOrganizations() {
		if (!authToken) return;
		loading = true;
		error = '';
		try {
			organizations = await apiJson<typeof organizations>(
				`/github/orgs?token=${encodeURIComponent(authToken)}`
			);
		} catch {
			organizations = [];
		} finally {
			loading = false;
		}
	}

	function selectAccount(account: string | null) {
		selectedAccount = account;
		// Reset repo selection when switching accounts
		repos = [];
		selectedRepo = null;
		repoSearch = '';
		goNext();
	}

	// -----------------------------------------------------------------------
	// Step 3: Repository selection
	// -----------------------------------------------------------------------

	async function fetchRepos() {
		loading = true;
		error = '';
		try {
			const params = new URLSearchParams();
			if (authToken) params.set('token', authToken);
			if (repoSearch) params.set('search', repoSearch);
			const qs = params.toString();
			const endpoint = selectedAccount
				? `/github/orgs/${encodeURIComponent(selectedAccount)}/repos${qs ? `?${qs}` : ''}`
				: `/github/repos${qs ? `?${qs}` : ''}`;
			repos = await apiJson<Repo[]>(endpoint);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to fetch repositories';
		} finally {
			loading = false;
		}
	}

	function selectRepo(repo: Repo) {
		selectedRepo = repo;
		manualOwner = '';
		manualRepo = '';
	}

	// -----------------------------------------------------------------------
	// Step 4: Branch selection
	// -----------------------------------------------------------------------

	async function fetchBranches() {
		loading = true;
		error = '';
		try {
			const params = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
			branches = await apiJson<Branch[]>(
				`/github/repos/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/branches${params}`
			);
			// Auto-select default branch
			if (branches.length > 0 && !selectedBranch) {
				const defaultBr = selectedRepo?.default_branch ?? 'main';
				const found = branches.find((b) => b.name === defaultBr);
				selectedBranch = found ? found.name : branches[0].name;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to fetch branches';
		} finally {
			loading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Step 5: File tree
	// -----------------------------------------------------------------------

	async function fetchTree() {
		loading = true;
		error = '';
		try {
			const params = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
			treeEntries = await apiJson<TreeEntry[]>(
				`/github/repos/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/tree/${encodeURIComponent(selectedBranch)}${params}`
			);
			selectedPaths = new Set();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to fetch file tree';
		} finally {
			loading = false;
		}
	}

	function togglePath(path: string) {
		const next = new Set(selectedPaths);
		if (next.has(path)) {
			next.delete(path);
		} else {
			next.add(path);
		}
		selectedPaths = next;
	}

	function selectAllOfType(fileType: string) {
		const next = new Set(selectedPaths);
		for (const entry of treeEntries) {
			if (entry.file_type === fileType) {
				next.add(entry.path);
			}
		}
		selectedPaths = next;
	}

	function clearSelection() {
		selectedPaths = new Set();
	}

	// -----------------------------------------------------------------------
	// Step 6: Preview
	// -----------------------------------------------------------------------

	async function fetchPreview() {
		loading = true;
		error = '';
		try {
			const params = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
			previewFiles = await apiJson<PreviewFile[]>(
				`/github/repos/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/preview${params}`,
				{
					method: 'POST',
					body: JSON.stringify({
						paths: [...selectedPaths],
						branch: selectedBranch
					})
				}
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to preview files';
		} finally {
			loading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Step 7: Import
	// -----------------------------------------------------------------------

	async function runImport() {
		importStatus = 'importing';
		error = '';
		try {
			const params = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
			const result = await apiJson<{ status: string; files: number }>(
				`/github/repos/${encodeURIComponent(repoOwner)}/${encodeURIComponent(repoName)}/import${params}`,
				{
					method: 'POST',
					body: JSON.stringify({
						paths: [...selectedPaths],
						branch: selectedBranch,
						tags: ['github-import']
					})
				}
			);
			importedCount = result.files;
			importStatus = 'done';
			onsuccess?.();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Import failed';
			importStatus = 'error';
		}
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	async function goNext() {
		error = '';
		const nextStep = currentStep + 1;

		// Load data for the next step
		if (nextStep === 1) {
			// Moving to account selection step
			if (isAuthenticated) {
				await fetchOrganizations();
			} else {
				// Skip account selection for unauthenticated users
				currentStep = 2;
				return;
			}
		} else if (nextStep === 2) {
			// Moving to repository step
			if (isAuthenticated) {
				await fetchRepos();
			}
		} else if (nextStep === 3) {
			// Moving to branch step
			if (!repoOwner || !repoName) {
				error = 'Please select or enter a repository.';
				return;
			}
			await fetchBranches();
		} else if (nextStep === 4) {
			// Moving to file selection step
			if (!selectedBranch) {
				error = 'Please select a branch.';
				return;
			}
			await fetchTree();
		} else if (nextStep === 5) {
			// Moving to preview step
			if (selectedPaths.size === 0) {
				error = 'Please select at least one file.';
				return;
			}
			await fetchPreview();
		} else if (nextStep === 6) {
			// Moving to import step
			await runImport();
		}

		if (!error) {
			currentStep = nextStep;
		}
	}

	function goBack() {
		error = '';
		if (currentStep > 0) {
			// Skip account step for unauthenticated users going back
			if (currentStep === 2 && !isAuthenticated) {
				currentStep = 0;
			} else {
				currentStep -= 1;
			}
		}
	}

	function resetWizard() {
		currentStep = 0;
		loading = false;
		error = '';
		authToken = '';
		authMethod = 'none';
		organizations = [];
		selectedAccount = null;
		repos = [];
		repoSearch = '';
		selectedRepo = null;
		manualOwner = '';
		manualRepo = '';
		branches = [];
		selectedBranch = '';
		treeEntries = [];
		selectedPaths = new Set();
		previewFiles = [];
		importStatus = 'idle';
		importedCount = 0;
	}

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<div class="flex flex-col gap-4">
	<!-- Step indicator -->
	<div class="flex items-center gap-1">
		{#each STEPS as stepLabel, i}
			<div class="flex items-center gap-1">
				<div
					class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium transition-colors
						{i < currentStep
						? 'bg-accent text-white'
						: i === currentStep
							? 'bg-accent text-white'
							: 'bg-surface-secondary text-text-tertiary'}"
				>
					{#if i < currentStep}
						<Check size={12} />
					{:else}
						{i + 1}
					{/if}
				</div>
				<span
					class="hidden text-xs sm:inline
						{i === currentStep ? 'font-medium text-text-primary' : 'text-text-tertiary'}"
				>
					{stepLabel}
				</span>
				{#if i < STEPS.length - 1}
					<div
						class="mx-1 h-px w-4 sm:w-6
							{i < currentStep ? 'bg-accent' : 'bg-border'}"
					></div>
				{/if}
			</div>
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
	<!-- Step 1: Authenticate                                               -->
	<!-- ================================================================= -->
	{#if currentStep === 0}
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-2">
				<Github size={20} class="text-text-primary" />
				<h3 class="text-sm font-semibold text-text-primary">Connect to GitHub</h3>
			</div>

			<p class="text-xs text-text-secondary">
				Authenticate to access private repositories, or continue without authentication to
				browse public repositories only.
			</p>

			<!-- PAT input -->
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-text-secondary">Personal Access Token</span>
				<div class="flex gap-2">
					<input
						type="password"
						bind:value={authToken}
						placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
						class="flex-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					/>
					<button
						type="button"
						disabled={!authToken.trim()}
						onclick={continueWithPat}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						<Lock size={14} />
						Continue with PAT
					</button>
				</div>
			</label>

			<div class="flex items-center gap-3">
				<div class="h-px flex-1 bg-border"></div>
				<span class="text-xs text-text-tertiary">or</span>
				<div class="h-px flex-1 bg-border"></div>
			</div>

			<!-- OAuth button -->
			<button
				type="button"
				onclick={startOAuth}
				disabled={loading}
				class="inline-flex items-center justify-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-secondary"
			>
				{#if loading}
					<Loader2 size={16} class="animate-spin" />
				{:else}
					<Github size={16} />
				{/if}
				Sign in with GitHub OAuth
			</button>

			<!-- Continue without auth -->
			<button
				type="button"
				onclick={continueWithoutAuth}
				class="inline-flex items-center justify-center gap-1.5 text-xs text-text-secondary transition-colors hover:text-text-primary"
			>
				<Unlock size={12} />
				Continue without authentication (public repos only)
			</button>
		</div>

	<!-- ================================================================= -->
	<!-- Step 2: Select Account                                             -->
	<!-- ================================================================= -->
	{:else if currentStep === 1}
		<div class="flex flex-col gap-3">
			<h3 class="text-sm font-semibold text-text-primary">Select Account</h3>
			<p class="text-xs text-text-secondary">
				Choose which account to browse repositories from.
			</p>

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else}
				<div class="flex flex-col gap-1 rounded-md border border-border p-1">
					<!-- Personal account -->
					<button
						type="button"
						onclick={() => selectAccount(null)}
						class="flex items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-secondary"
					>
						<div
							class="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10"
						>
							<User size={16} class="text-accent" />
						</div>
						<div class="min-w-0 flex-1">
							<span class="font-medium text-text-primary">Personal Repositories</span>
							<p class="text-xs text-text-secondary">
								Your own repositories and forks
							</p>
						</div>
						<ChevronRight size={14} class="text-text-tertiary" />
					</button>

					<!-- Organizations -->
					{#each organizations as org}
						<button
							type="button"
							onclick={() => selectAccount(org.login)}
							class="flex items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-secondary"
						>
							<div class="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-surface-secondary">
								{#if org.avatar_url}
									<img
										src={org.avatar_url}
										alt={org.login}
										class="h-8 w-8 rounded-full object-cover"
									/>
								{:else}
									<Building size={16} class="text-text-secondary" />
								{/if}
							</div>
							<div class="min-w-0 flex-1">
								<span class="font-medium text-text-primary">{org.login}</span>
								{#if org.description}
									<p class="truncate text-xs text-text-secondary">
										{org.description}
									</p>
								{/if}
							</div>
							<ChevronRight size={14} class="text-text-tertiary" />
						</button>
					{/each}

					{#if organizations.length === 0}
						<p class="py-2 text-center text-xs text-text-tertiary">
							No organizations found.
						</p>
					{/if}
				</div>
			{/if}

			<!-- Navigation -->
			<div class="flex justify-between pt-2">
				<button
					type="button"
					onclick={goBack}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					<ChevronLeft size={14} />
					Back
				</button>
			</div>
		</div>

	<!-- ================================================================= -->
	<!-- Step 3: Select Repository                                          -->
	<!-- ================================================================= -->
	{:else if currentStep === 2}
		<div class="flex flex-col gap-3">
			<h3 class="text-sm font-semibold text-text-primary">Select Repository</h3>

			{#if isAuthenticated}
				<!-- Search bar for authenticated users -->
				<div class="flex gap-2">
					<div class="relative flex-1">
						<Search
							size={14}
							class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
						/>
						<input
							type="text"
							bind:value={repoSearch}
							placeholder="Search repositories..."
							class="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</div>
					<button
						type="button"
						onclick={fetchRepos}
						disabled={loading}
						class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-surface-secondary disabled:opacity-50"
					>
						{#if loading}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Search size={14} />
						{/if}
						Search
					</button>
				</div>

				<!-- Repo list -->
				{#if repos.length > 0}
					<div
						class="flex max-h-60 flex-col gap-1 overflow-y-auto rounded-md border border-border p-1"
					>
						{#each repos as repo}
							<button
								type="button"
								onclick={() => selectRepo(repo)}
								class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors
									{selectedRepo?.full_name === repo.full_name
									? 'bg-accent/10 text-accent'
									: 'text-text-primary hover:bg-surface-secondary'}"
							>
								<Github size={14} class="shrink-0" />
								<div class="min-w-0 flex-1">
									<div class="flex items-center gap-1.5">
										<span class="font-medium">{repo.full_name}</span>
										{#if repo.private}
											<Lock size={10} class="text-text-tertiary" />
										{/if}
									</div>
									{#if repo.description}
										<p class="truncate text-xs text-text-secondary">
											{repo.description}
										</p>
									{/if}
								</div>
							</button>
						{/each}
					</div>
				{:else if !loading}
					<p class="py-4 text-center text-xs text-text-secondary">
						{repoSearch ? 'No repositories found.' : 'Search or browse your repositories.'}
					</p>
				{/if}
			{:else}
				<!-- Manual input for unauthenticated users -->
				<p class="text-xs text-text-secondary">
					Enter the owner and repository name of a public GitHub repository.
				</p>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Owner</span>
						<input
							type="text"
							bind:value={manualOwner}
							placeholder="e.g. octocat"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Repository</span>
						<input
							type="text"
							bind:value={manualRepo}
							placeholder="e.g. hello-world"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>
			{/if}

			<!-- Navigation -->
			<div class="flex justify-between pt-2">
				<button
					type="button"
					onclick={goBack}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					<ChevronLeft size={14} />
					Back
				</button>
				<button
					type="button"
					disabled={loading || (!selectedRepo && (!manualOwner || !manualRepo))}
					onclick={goNext}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					Continue
					<ChevronRight size={14} />
				</button>
			</div>
		</div>

	<!-- ================================================================= -->
	<!-- Step 4: Select Branch                                              -->
	<!-- ================================================================= -->
	{:else if currentStep === 3}
		<div class="flex flex-col gap-3">
			<div class="flex items-center gap-2">
				<GitBranch size={16} class="text-text-primary" />
				<h3 class="text-sm font-semibold text-text-primary">Select Branch</h3>
			</div>

			<p class="text-xs text-text-secondary">
				Choose the branch to import files from
				<span class="font-medium text-text-primary">{repoOwner}/{repoName}</span>.
			</p>

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else}
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium text-text-secondary">Branch</span>
					<select
						bind:value={selectedBranch}
						class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
					>
						{#each branches as branch}
							<option value={branch.name}>{branch.name}</option>
						{/each}
					</select>
				</label>
			{/if}

			<div class="flex justify-between pt-2">
				<button
					type="button"
					onclick={goBack}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					<ChevronLeft size={14} />
					Back
				</button>
				<button
					type="button"
					disabled={loading || !selectedBranch}
					onclick={goNext}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					Continue
					<ChevronRight size={14} />
				</button>
			</div>
		</div>

	<!-- ================================================================= -->
	<!-- Step 5: Select Files                                               -->
	<!-- ================================================================= -->
	{:else if currentStep === 4}
		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<FolderTree size={16} class="text-text-primary" />
					<h3 class="text-sm font-semibold text-text-primary">Select Files</h3>
				</div>
				<span class="text-xs text-text-secondary">
					{selectedCount} file{selectedCount !== 1 ? 's' : ''} selected
				</span>
			</div>

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else}
				<!-- Quick select buttons -->
				<div class="flex flex-wrap gap-2">
					{#if markdownEntries.length > 0}
						<button
							type="button"
							onclick={() => selectAllOfType('markdown')}
							class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-secondary"
						>
							<FileText size={12} />
							Select all Markdown ({markdownEntries.length})
						</button>
					{/if}
					{#if openapiEntries.length > 0}
						<button
							type="button"
							onclick={() => selectAllOfType('openapi')}
							class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-secondary"
						>
							<Code2 size={12} />
							Select all OpenAPI ({openapiEntries.length})
						</button>
					{/if}
					{#if selectedCount > 0}
						<button
							type="button"
							onclick={clearSelection}
							class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-danger/5 hover:text-danger"
						>
							Clear selection
						</button>
					{/if}
				</div>

				<!-- File tree list -->
				<div
					class="flex max-h-72 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1"
				>
					{#each filteredEntries as entry}
						<label
							class="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 transition-colors hover:bg-surface-secondary"
						>
							<input
								type="checkbox"
								checked={selectedPaths.has(entry.path)}
								onchange={() => togglePath(entry.path)}
								class="h-3.5 w-3.5 rounded border-border text-accent focus:ring-accent"
							/>
							<FileText size={12} class="shrink-0 text-text-tertiary" />
							<span class="min-w-0 flex-1 truncate text-xs text-text-primary">
								{entry.path}
							</span>
							<span
								class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium {FILE_TYPE_COLORS[
									entry.file_type
								] ?? FILE_TYPE_COLORS.unknown}"
							>
								{entry.file_type}
							</span>
							<span class="shrink-0 text-[10px] text-text-tertiary">
								{formatBytes(entry.size)}
							</span>
						</label>
					{/each}
					{#if filteredEntries.length === 0}
						<p class="py-6 text-center text-xs text-text-secondary">
							No importable files found in this branch.
						</p>
					{/if}
				</div>
			{/if}

			<div class="flex justify-between pt-2">
				<button
					type="button"
					onclick={goBack}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					<ChevronLeft size={14} />
					Back
				</button>
				<button
					type="button"
					disabled={loading || selectedCount === 0}
					onclick={goNext}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					Preview {selectedCount} file{selectedCount !== 1 ? 's' : ''}
					<ChevronRight size={14} />
				</button>
			</div>
		</div>

	<!-- ================================================================= -->
	<!-- Step 6: Analysis Preview                                           -->
	<!-- ================================================================= -->
	{:else if currentStep === 5}
		<div class="flex flex-col gap-3">
			<h3 class="text-sm font-semibold text-text-primary">Analysis Preview</h3>
			<p class="text-xs text-text-secondary">
				Review the files that will be imported into the knowledge base.
			</p>

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<Loader2 size={20} class="animate-spin text-accent" />
				</div>
			{:else}
				<div class="flex max-h-80 flex-col gap-2 overflow-y-auto">
					{#each previewFiles as file}
						<div class="rounded-md border border-border p-3">
							<div class="mb-2 flex items-center gap-2">
								<FileText size={14} class="shrink-0 text-text-secondary" />
								<span class="min-w-0 flex-1 truncate text-xs font-medium text-text-primary">
									{file.path}
								</span>
								<span
									class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium {FILE_TYPE_COLORS[
										file.file_type
									] ?? FILE_TYPE_COLORS.unknown}"
								>
									{file.file_type}
								</span>
								<span class="shrink-0 text-[10px] text-text-tertiary">
									{formatBytes(file.size)}
								</span>
							</div>
							{#if file.content_preview}
								<pre
									class="max-h-32 overflow-auto rounded bg-surface-secondary p-2 text-[11px] leading-relaxed text-text-secondary">{file.content_preview}</pre>
							{/if}
						</div>
					{/each}
					{#if previewFiles.length === 0}
						<p class="py-6 text-center text-xs text-text-secondary">
							No preview data available.
						</p>
					{/if}
				</div>
			{/if}

			<div class="flex justify-between pt-2">
				<button
					type="button"
					onclick={goBack}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					<ChevronLeft size={14} />
					Back
				</button>
				<button
					type="button"
					disabled={loading}
					onclick={goNext}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					Import {previewFiles.length} file{previewFiles.length !== 1 ? 's' : ''}
					<ChevronRight size={14} />
				</button>
			</div>
		</div>

	<!-- ================================================================= -->
	<!-- Step 7: Import Progress                                            -->
	<!-- ================================================================= -->
	{:else if currentStep === 6}
		<div class="flex flex-col items-center gap-4 py-6">
			{#if importStatus === 'importing'}
				<Loader2 size={32} class="animate-spin text-accent" />
				<p class="text-sm font-medium text-text-primary">Importing files...</p>
				<p class="text-xs text-text-secondary">
					This may take a moment depending on file sizes.
				</p>
			{:else if importStatus === 'done'}
				<div
					class="flex h-12 w-12 items-center justify-center rounded-full bg-success/10"
				>
					<Check size={24} class="text-success" />
				</div>
				<p class="text-sm font-medium text-text-primary">Import Complete</p>
				<p class="text-xs text-text-secondary">
					Successfully imported {importedCount} file{importedCount !== 1 ? 's' : ''} from
					<span class="font-medium">{repoOwner}/{repoName}</span>.
				</p>
				<button
					type="button"
					onclick={resetWizard}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
				>
					Import more files
				</button>
			{:else if importStatus === 'error'}
				<div
					class="flex h-12 w-12 items-center justify-center rounded-full bg-danger/10"
				>
					<AlertCircle size={24} class="text-danger" />
				</div>
				<p class="text-sm font-medium text-text-primary">Import Failed</p>
				<div class="flex gap-2">
					<button
						type="button"
						onclick={goBack}
						class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-secondary"
					>
						<ChevronLeft size={14} />
						Back
					</button>
					<button
						type="button"
						onclick={runImport}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
					>
						Retry
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>
