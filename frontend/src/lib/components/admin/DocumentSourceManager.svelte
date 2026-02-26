<!--
  DocumentSourceManager.svelte - CRUD interface for cloud document source configuration.

  Lists document sources in a table with inline forms for adding / editing.
  Supports testing connectivity, triggering sync, and toggling active state.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Pencil,
		Trash2,
		X,
		Save,
		Loader2,
		Zap,
		CheckCircle,
		XCircle,
		ToggleLeft,
		ToggleRight,
		RefreshCw,
		Database,
		Cloud,
		HardDrive,
		Lock,
		Clock,
		BookOpen,
		ArrowRight,
		Info
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		embedded?: boolean;
	}

	let { embedded = false }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface DocumentSource {
		id: string;
		name: string;
		source_type: string;
		category: string;
		auth_method: string;
		config: Record<string, unknown>;
		sync_enabled: boolean;
		sync_cron: string | null;
		is_active: boolean;
		last_sync_at: string | null;
		last_sync_status: string | null;
		created_at: string | null;
		updated_at: string | null;
	}

	interface TestResult {
		success: boolean;
		error: string | null;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const SOURCE_TYPES = [
		{ value: 's3', label: 'Amazon S3', category: 'blob_storage', icon: HardDrive },
		{ value: 'azure_blob', label: 'Azure Blob', category: 'blob_storage', icon: HardDrive },
		{ value: 'gcs', label: 'Google Cloud Storage', category: 'blob_storage', icon: HardDrive },
		{ value: 'onedrive', label: 'OneDrive', category: 'drive', icon: Cloud },
		{ value: 'sharepoint', label: 'SharePoint', category: 'drive', icon: Cloud },
		{ value: 'google_drive', label: 'Google Drive', category: 'drive', icon: Cloud }
	];

	const AUTH_METHODS: Record<string, { value: string; label: string }[]> = {
		s3: [
			{ value: 'credentials', label: 'Credentials' },
			{ value: 'iam_role', label: 'IAM Role' }
		],
		azure_blob: [
			{ value: 'credentials', label: 'Connection String' }
		],
		gcs: [
			{ value: 'service_account', label: 'Service Account' }
		],
		onedrive: [
			{ value: 'credentials', label: 'Client Credentials' },
			{ value: 'oauth', label: 'OAuth' }
		],
		sharepoint: [
			{ value: 'credentials', label: 'Client Credentials' },
			{ value: 'oauth', label: 'OAuth' }
		],
		google_drive: [
			{ value: 'service_account', label: 'Service Account' },
			{ value: 'oauth', label: 'OAuth' }
		]
	};

	interface ConfigField {
		key: string;
		label: string;
		type: 'text' | 'password' | 'textarea';
		placeholder: string;
		required?: boolean;
	}

	const CONFIG_FIELDS: Record<string, ConfigField[]> = {
		s3: [
			{ key: 'bucket', label: 'Bucket', type: 'text', placeholder: 'my-bucket', required: true },
			{ key: 'region', label: 'Region', type: 'text', placeholder: 'us-east-1', required: true },
			{ key: 'prefix', label: 'Prefix', type: 'text', placeholder: 'docs/' },
			{ key: 'access_key_id', label: 'Access Key ID', type: 'password', placeholder: 'AKIA...' },
			{ key: 'secret_access_key', label: 'Secret Access Key', type: 'password', placeholder: 'Enter secret key' },
			{ key: 'endpoint_url', label: 'Endpoint URL (optional)', type: 'text', placeholder: 'https://s3-compatible.example.com' }
		],
		azure_blob: [
			{ key: 'account_name', label: 'Account Name', type: 'text', placeholder: 'mystorageaccount', required: true },
			{ key: 'container', label: 'Container', type: 'text', placeholder: 'documents', required: true },
			{ key: 'prefix', label: 'Prefix', type: 'text', placeholder: 'docs/' },
			{ key: 'connection_string', label: 'Connection String', type: 'password', placeholder: 'DefaultEndpointsProtocol=https;AccountName=...' }
		],
		gcs: [
			{ key: 'project_id', label: 'Project ID', type: 'text', placeholder: 'my-gcp-project', required: true },
			{ key: 'bucket', label: 'Bucket', type: 'text', placeholder: 'my-bucket', required: true },
			{ key: 'prefix', label: 'Prefix', type: 'text', placeholder: 'docs/' },
			{ key: 'service_account_json', label: 'Service Account JSON', type: 'textarea', placeholder: '{"type": "service_account", ...}' }
		],
		onedrive: [
			{ key: 'tenant_id', label: 'Tenant ID', type: 'text', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', required: true },
			{ key: 'client_id', label: 'Client ID', type: 'text', placeholder: 'Application (client) ID', required: true },
			{ key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Enter client secret' },
			{ key: 'drive_id', label: 'Drive ID', type: 'text', placeholder: 'Drive ID (optional)' },
			{ key: 'folder_path', label: 'Folder Path', type: 'text', placeholder: '/Documents' }
		],
		sharepoint: [
			{ key: 'tenant_id', label: 'Tenant ID', type: 'text', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', required: true },
			{ key: 'client_id', label: 'Client ID', type: 'text', placeholder: 'Application (client) ID', required: true },
			{ key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Enter client secret' },
			{ key: 'site_url', label: 'Site URL', type: 'text', placeholder: 'https://contoso.sharepoint.com/sites/docs', required: true },
			{ key: 'library_name', label: 'Library Name', type: 'text', placeholder: 'Documents' }
		],
		google_drive: [
			{ key: 'folder_id', label: 'Folder ID', type: 'text', placeholder: 'Google Drive folder ID' },
			{ key: 'service_account_json', label: 'Service Account JSON', type: 'textarea', placeholder: '{"type": "service_account", ...}' }
		]
	};

	const SYNC_PRESETS = [
		{ value: '', label: 'Never' },
		{ value: '0 */6 * * *', label: 'Every 6 hours' },
		{ value: '0 */12 * * *', label: 'Every 12 hours' },
		{ value: '0 0 * * *', label: 'Daily (midnight)' }
	];

	const SOURCE_GUIDES: Record<string, { title: string; steps: string[]; tip: string }> = {
		s3: {
			title: 'Amazon S3 Setup',
			steps: [
				'Create an IAM user with S3 read access (AmazonS3ReadOnlyAccess policy)',
				'Generate an Access Key ID and Secret Access Key for that user',
				'Enter the bucket name, region, and optional prefix below',
				'Use "Test Connection" to verify access before saving'
			],
			tip: 'For production, use IAM Roles instead of access keys. Attach the role to your EC2 or ECS instance.'
		},
		azure_blob: {
			title: 'Azure Blob Storage Setup',
			steps: [
				'In Azure Portal, go to your Storage Account > Access Keys',
				'Copy the full Connection String (starts with DefaultEndpointsProtocol=...)',
				'Enter the account name, container name, and paste the connection string below',
				'Use "Test Connection" to verify access'
			],
			tip: 'For better security, use Shared Access Signatures (SAS) with read-only permissions scoped to the container.'
		},
		gcs: {
			title: 'Google Cloud Storage Setup',
			steps: [
				'In Google Cloud Console, go to IAM & Admin > Service Accounts',
				'Create a service account with Storage Object Viewer role',
				'Generate a JSON key and paste its contents below',
				'Enter your GCP project ID and bucket name'
			],
			tip: 'Store the service account key securely. Consider using Workload Identity for GKE deployments.'
		},
		onedrive: {
			title: 'OneDrive Setup',
			steps: [
				'In Azure Portal > App Registrations, create a new app',
				'Under API Permissions, add Microsoft Graph > Files.Read.All (Application)',
				'Grant admin consent for the permissions',
				'Copy the Tenant ID, Client ID, and create a Client Secret'
			],
			tip: 'Use a dedicated App Registration for Firefly Desk. Set the client secret to expire in 12+ months.'
		},
		sharepoint: {
			title: 'SharePoint Setup',
			steps: [
				'In Azure Portal > App Registrations, create a new app',
				'Under API Permissions, add SharePoint > Sites.Read.All (Application)',
				'Grant admin consent for the permissions',
				'Get your SharePoint site URL (e.g. https://contoso.sharepoint.com/sites/docs)'
			],
			tip: 'Use Sites.Selected permission for least-privilege access to specific SharePoint sites.'
		},
		google_drive: {
			title: 'Google Drive Setup',
			steps: [
				'In Google Cloud Console, enable the Google Drive API',
				'Create a service account and download the JSON key',
				'Share the target folder with the service account email',
				'Copy the folder ID from the Google Drive URL and enter it below'
			],
			tip: 'The folder ID is the last segment of the folder URL: drive.google.com/drive/folders/<folder-id>'
		}
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let sources = $state<DocumentSource[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let formData = $state({
		name: '',
		source_type: 's3',
		auth_method: 'credentials',
		config: {} as Record<string, string>,
		sync_enabled: false,
		sync_cron: ''
	});
	let saving = $state(false);

	// Test connection state
	let testingId = $state<string | null>(null);
	let testResults = $state<Record<string, TestResult>>({});

	// Sync state
	let syncingId = $state<string | null>(null);

	// Delete confirmation
	let confirmDeleteId = $state<string | null>(null);

	// -----------------------------------------------------------------------
	// Update auth method when source type changes (only for new sources)
	// -----------------------------------------------------------------------

	$effect(() => {
		if (!editingId) {
			const methods = AUTH_METHODS[formData.source_type];
			if (methods && methods.length > 0) {
				formData.auth_method = methods[0].value;
			}
			formData.config = {};
		}
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadSources() {
		loading = true;
		error = '';
		try {
			sources = await apiJson<DocumentSource[]>('/admin/document-sources');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document sources';
		} finally {
			loading = false;
		}
	}

	// Initial load
	$effect(() => {
		loadSources();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openAddForm() {
		editingId = null;
		formData = {
			name: '',
			source_type: 's3',
			auth_method: 'credentials',
			config: {},
			sync_enabled: false,
			sync_cron: ''
		};
		showForm = true;
	}

	function openEditForm(source: DocumentSource) {
		editingId = source.id;
		formData = {
			name: source.name,
			source_type: source.source_type,
			auth_method: source.auth_method || 'credentials',
			config: { ...source.config } as Record<string, string>,
			sync_enabled: source.sync_enabled,
			sync_cron: source.sync_cron || ''
		};
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editingId = null;
	}

	async function submitForm() {
		saving = true;
		error = '';

		const payload: Record<string, unknown> = {
			name: formData.name,
			source_type: formData.source_type,
			auth_method: formData.auth_method,
			config: formData.config,
			sync_enabled: formData.sync_enabled,
			sync_cron: formData.sync_enabled && formData.sync_cron ? formData.sync_cron : null,
			is_active: true
		};

		try {
			if (editingId) {
				await apiJson(`/admin/document-sources/${editingId}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson('/admin/document-sources', {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			showForm = false;
			editingId = null;
			await loadSources();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save document source';
		} finally {
			saving = false;
		}
	}

	async function deleteSource(id: string) {
		error = '';
		try {
			await apiFetch(`/admin/document-sources/${id}`, { method: 'DELETE' });
			confirmDeleteId = null;
			await loadSources();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete document source';
		}
	}

	async function toggleActive(source: DocumentSource) {
		error = '';
		try {
			await apiJson(`/admin/document-sources/${source.id}`, {
				method: 'PUT',
				body: JSON.stringify({
					name: source.name,
					source_type: source.source_type,
					auth_method: source.auth_method,
					config: source.config,
					sync_enabled: source.sync_enabled,
					sync_cron: source.sync_cron,
					is_active: !source.is_active
				})
			});
			await loadSources();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to toggle source';
		}
	}

	async function testConnection(source: DocumentSource) {
		testingId = source.id;
		try {
			const result = await apiJson<TestResult>(
				`/admin/document-sources/${source.id}/test`,
				{ method: 'POST' }
			);
			testResults = { ...testResults, [source.id]: result };
		} catch (e) {
			testResults = {
				...testResults,
				[source.id]: {
					success: false,
					error: e instanceof Error ? e.message : 'Test failed'
				}
			};
		} finally {
			testingId = null;
		}
	}

	async function triggerSync(source: DocumentSource) {
		syncingId = source.id;
		error = '';
		try {
			await apiJson(`/admin/document-sources/${source.id}/sync`, { method: 'POST' });
			await loadSources();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to trigger sync';
		} finally {
			syncingId = null;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function sourceTypeLabel(type: string): string {
		return SOURCE_TYPES.find((t) => t.value === type)?.label ?? type;
	}

	function sourceTypeIcon(type: string) {
		return SOURCE_TYPES.find((t) => t.value === type)?.icon ?? Database;
	}

	function categoryLabel(cat: string): string {
		if (cat === 'blob_storage') return 'Blob Storage';
		if (cat === 'drive') return 'Drive';
		return cat;
	}

	function formatSyncCron(cron: string | null): string {
		if (!cron) return 'Manual';
		const preset = SYNC_PRESETS.find((p) => p.value === cron);
		return preset ? preset.label : cron;
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		const d = new Date(dateStr);
		return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	function currentConfigFields(): ConfigField[] {
		return CONFIG_FIELDS[formData.source_type] ?? [];
	}

	function currentAuthMethods(): { value: string; label: string }[] {
		return AUTH_METHODS[formData.source_type] ?? [];
	}

	function startGuidedSetup(sourceType: string) {
		editingId = null;
		formData = {
			name: '',
			source_type: sourceType,
			auth_method: AUTH_METHODS[sourceType]?.[0]?.value ?? 'credentials',
			config: {},
			sync_enabled: false,
			sync_cron: ''
		};
		showForm = true;
	}
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Document Sources</h1>
				<p class="text-sm text-text-secondary">
					Manage cloud storage and drive connections for document import and sync
				</p>
			</div>
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add Source
			</button>
		</div>
	{:else}
		<div class="flex justify-end">
			<button
				type="button"
				onclick={openAddForm}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
			>
				<Plus size={16} />
				Add Source
			</button>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Inline form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">
					{editingId ? 'Edit Document Source' : 'New Document Source'}
				</h3>
				<button
					type="button"
					onclick={cancelForm}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<!-- Setup guide -->
			{#if !editingId && SOURCE_GUIDES[formData.source_type]}
				{@const guide = SOURCE_GUIDES[formData.source_type]}
				<div class="mb-4 rounded-lg border border-accent/20 bg-accent/5 p-4">
					<div class="mb-2 flex items-center gap-2">
						<BookOpen size={14} class="text-accent" />
						<span class="text-xs font-semibold text-accent">{guide.title}</span>
					</div>
					<ol class="mb-2 list-inside list-decimal space-y-1 text-xs text-text-secondary">
						{#each guide.steps as step}
							<li>{step}</li>
						{/each}
					</ol>
					<div class="flex items-start gap-1.5 rounded-md bg-accent/5 px-2.5 py-1.5">
						<Info size={12} class="mt-0.5 shrink-0 text-accent/70" />
						<p class="text-[11px] text-accent/80">{guide.tip}</p>
					</div>
				</div>
			{/if}

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitForm();
				}}
				class="flex flex-col gap-3"
			>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Source Type</span>
						<select
							bind:value={formData.source_type}
							disabled={!!editingId}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent disabled:opacity-50"
						>
							<optgroup label="Blob Storage">
								{#each SOURCE_TYPES.filter((t) => t.category === 'blob_storage') as st}
									<option value={st.value}>{st.label}</option>
								{/each}
							</optgroup>
							<optgroup label="Drive">
								{#each SOURCE_TYPES.filter((t) => t.category === 'drive') as st}
									<option value={st.value}>{st.label}</option>
								{/each}
							</optgroup>
						</select>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Display Name</span>
						<input
							type="text"
							bind:value={formData.name}
							required
							placeholder="e.g. Production S3 Bucket"
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

				<!-- Auth Method Toggle -->
				{#if currentAuthMethods().length > 1}
					<div class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Authentication Method</span>
						<div class="flex gap-2">
							{#each currentAuthMethods() as method}
								<button
									type="button"
									onclick={() => (formData.auth_method = method.value)}
									class="flex-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors {formData.auth_method === method.value
										? 'border-accent bg-accent/10 text-accent'
										: 'border-border text-text-secondary hover:bg-surface-hover'}"
								>
									<Lock size={14} class="mb-0.5 mr-1 inline-block" />
									{method.label}
								</button>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Dynamic config fields -->
				<div class="grid grid-cols-2 gap-3">
					{#each currentConfigFields() as field}
						{#if field.type === 'textarea'}
							<label class="col-span-2 flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">
									{field.label}
									{#if editingId && (field.key.includes('secret') || field.key.includes('password') || field.key.includes('json') || field.key.includes('connection'))}
										<span class="text-text-secondary/60">(leave blank to keep existing)</span>
									{/if}
								</span>
								<textarea
									rows={4}
									bind:value={formData.config[field.key]}
									placeholder={field.placeholder}
									class="rounded-md border border-border bg-surface px-3 py-1.5 font-mono text-xs text-text-primary outline-none focus:border-accent"
								></textarea>
							</label>
						{:else}
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">
									{field.label}
									{#if editingId && field.type === 'password'}
										<span class="text-text-secondary/60">(leave blank to keep existing)</span>
									{/if}
								</span>
								<input
									type={field.type}
									bind:value={formData.config[field.key]}
									placeholder={editingId && field.type === 'password' ? '********' : field.placeholder}
									required={field.required && !editingId}
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						{/if}
					{/each}
				</div>

				<!-- Sync settings -->
				<div class="flex flex-col gap-2 rounded-lg border border-border bg-surface-secondary/50 p-3">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<RefreshCw size={14} class="text-text-secondary" />
							<span class="text-xs font-medium text-text-secondary">Automatic Sync</span>
						</div>
						<button
							type="button"
							onclick={() => (formData.sync_enabled = !formData.sync_enabled)}
							class="rounded p-0.5 text-text-secondary transition-colors hover:text-text-primary"
						>
							{#if formData.sync_enabled}
								<ToggleRight size={20} class="text-success" />
							{:else}
								<ToggleLeft size={20} />
							{/if}
						</button>
					</div>

					{#if formData.sync_enabled}
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Schedule</span>
							<select
								bind:value={formData.sync_cron}
								class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
							>
								{#each SYNC_PRESETS.filter((p) => p.value !== '') as preset}
									<option value={preset.value}>{preset.label}</option>
								{/each}
							</select>
						</label>
					{/if}
				</div>

				<div class="flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={cancelForm}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						{editingId ? 'Update' : 'Create'}
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Name</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Type</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Category</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Auth</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Sync</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Active</th>
							<th class="w-52 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each sources as source, i}
							<tr
								class="border-b border-border last:border-b-0 {i % 2 === 1
									? 'bg-surface-secondary/50'
									: ''}"
							>
								<td class="px-4 py-2">
									<div class="font-medium text-text-primary">
										{source.name}
									</div>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										<svelte:component this={sourceTypeIcon(source.source_type)} size={12} />
										{sourceTypeLabel(source.source_type)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {source.category === 'blob_storage'
											? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
											: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'}"
									>
										{categoryLabel(source.category)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span
										class="inline-block rounded-full px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
									>
										{source.auth_method}
									</span>
								</td>
								<td class="px-4 py-2">
									{#if source.sync_enabled}
										<div class="flex flex-col gap-0.5">
											<span
												class="inline-flex items-center gap-1 text-xs text-success"
											>
												<Clock size={10} />
												{formatSyncCron(source.sync_cron)}
											</span>
											{#if source.last_sync_at}
												<span class="text-[10px] text-text-secondary">
													Last: {formatDate(source.last_sync_at)}
													{#if source.last_sync_status}
														<span class="ml-1 {source.last_sync_status === 'completed' ? 'text-success' : source.last_sync_status === 'failed' ? 'text-danger' : 'text-text-secondary'}">
															({source.last_sync_status})
														</span>
													{/if}
												</span>
											{/if}
										</div>
									{:else}
										<span class="text-xs text-text-secondary">Disabled</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									{#if source.is_active}
										<span
											class="inline-block rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
										>
											Active
										</span>
									{:else}
										<span
											class="inline-block rounded-full bg-text-secondary/10 px-2 py-0.5 text-xs font-medium text-text-secondary"
										>
											Inactive
										</span>
									{/if}
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() => openEditForm(source)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
										</button>
										<button
											type="button"
											onclick={() => testConnection(source)}
											disabled={testingId === source.id}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent disabled:opacity-50"
											title="Test Connection"
										>
											{#if testingId === source.id}
												<Loader2 size={14} class="animate-spin" />
											{:else}
												<Zap size={14} />
											{/if}
										</button>
										{#if source.sync_enabled}
											<button
												type="button"
												onclick={() => triggerSync(source)}
												disabled={syncingId === source.id}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent disabled:opacity-50"
												title="Sync Now"
											>
												{#if syncingId === source.id}
													<Loader2 size={14} class="animate-spin" />
												{:else}
													<RefreshCw size={14} />
												{/if}
											</button>
										{/if}
										<button
											type="button"
											onclick={() => toggleActive(source)}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title={source.is_active ? 'Deactivate' : 'Activate'}
										>
											{#if source.is_active}
												<ToggleRight size={14} class="text-success" />
											{:else}
												<ToggleLeft size={14} />
											{/if}
										</button>
										{#if confirmDeleteId === source.id}
											<span class="ml-1 flex items-center gap-1 text-xs">
												<button
													type="button"
													onclick={() => deleteSource(source.id)}
													class="rounded bg-danger px-1.5 py-0.5 text-white hover:bg-danger/80"
												>
													Confirm
												</button>
												<button
													type="button"
													onclick={() => (confirmDeleteId = null)}
													class="rounded border border-border px-1.5 py-0.5 text-text-secondary hover:bg-surface-hover"
												>
													Cancel
												</button>
											</span>
										{:else}
											<button
												type="button"
												onclick={() => (confirmDeleteId = source.id)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										{/if}
									</div>

									<!-- Inline test result -->
									{#if testResults[source.id]}
										{@const result = testResults[source.id]}
										<div class="mt-1 text-xs">
											{#if result.success}
												<span
													class="inline-flex items-center gap-1 text-success"
												>
													<CheckCircle size={12} />
													Connection OK
												</span>
											{:else}
												<span
													class="inline-flex items-center gap-1 text-danger"
												>
													<XCircle size={12} />
													{result.error || 'Connection failed'}
												</span>
											{/if}
										</div>
									{/if}
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="7" class="px-4 py-6">
									<div class="mx-auto max-w-2xl text-center">
										<Cloud size={32} class="mx-auto mb-2 text-text-secondary/40" />
										<h3 class="text-sm font-semibold text-text-primary">
											Connect your first document source
										</h3>
										<p class="mb-4 text-xs text-text-secondary">
											Import documents from cloud storage or drive services to build your knowledge base.
										</p>
										<div class="grid grid-cols-3 gap-2">
											{#each SOURCE_TYPES as st}
												<button
													type="button"
													onclick={() => startGuidedSetup(st.value)}
													class="flex flex-col items-center gap-1.5 rounded-lg border border-border p-3 text-text-secondary transition-all hover:border-accent/40 hover:bg-accent/5 hover:text-accent"
												>
													<svelte:component this={st.icon} size={20} />
													<span class="text-xs font-medium">{st.label}</span>
												</button>
											{/each}
										</div>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
