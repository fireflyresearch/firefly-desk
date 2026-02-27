<!--
  DocumentSourceWizard.svelte - 4-step wizard for document source configuration.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		ChevronLeft,
		ChevronRight,
		Save,
		Loader2,
		Check,
		AlertTriangle,
		Cloud,
		Globe,
		Database,
		FolderOpen,
		Code,
		Zap,
		CheckCircle,
		XCircle
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		open: boolean;
		onClose: () => void;
		onCreated: () => void;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onCreated }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Source Type', 'Connection', 'Sync Options', 'Test & Review'] as const;

	const SOURCE_TYPES = [
		{
			value: 'google_drive',
			label: 'Google Drive',
			description: 'Sync documents from Google Drive',
			icon: Cloud
		},
		{
			value: 'sharepoint',
			label: 'SharePoint/OneDrive',
			description: 'Microsoft SharePoint or OneDrive',
			icon: Globe
		},
		{
			value: 's3',
			label: 'Amazon S3',
			description: 'AWS S3 bucket',
			icon: Database
		},
		{
			value: 'local',
			label: 'Local Files',
			description: 'Local filesystem directory',
			icon: FolderOpen
		},
		{
			value: 'web_crawler',
			label: 'Web Crawler',
			description: 'Crawl web pages and sitemaps',
			icon: Globe
		},
		{
			value: 'custom',
			label: 'Custom',
			description: 'Custom integration via webhook',
			icon: Code
		}
	] as const;

	const SYNC_SCHEDULES = [
		{ value: 'manual', label: 'Manual' },
		{ value: 'hourly', label: 'Hourly' },
		{ value: 'daily', label: 'Daily' },
		{ value: 'weekly', label: 'Weekly' }
	] as const;

	const FILE_TYPES = [
		{ value: 'pdf', label: 'PDF' },
		{ value: 'docx', label: 'DOCX' },
		{ value: 'xlsx', label: 'XLSX' },
		{ value: 'pptx', label: 'PPTX' },
		{ value: 'txt', label: 'TXT' },
		{ value: 'md', label: 'MD' },
		{ value: 'html', label: 'HTML' }
	] as const;

	const SETUP_GUIDES: Record<string, { title: string; steps: string[] }> = {
		google_drive: {
			title: 'Google Drive Setup',
			steps: [
				'Enable the Google Drive API in Google Cloud Console.',
				'Create a service account and download the JSON key.',
				'Share the target folder with the service account email.',
				'Paste the JSON key contents and folder ID below.'
			]
		},
		sharepoint: {
			title: 'SharePoint / OneDrive Setup',
			steps: [
				'Register an app in Azure AD (App Registrations).',
				'Add Sites.Read.All application permission and grant admin consent.',
				'Copy the Tenant ID, Client ID, and create a Client Secret.',
				'Enter your SharePoint site URL and library name.'
			]
		},
		s3: {
			title: 'Amazon S3 Setup',
			steps: [
				'Create an IAM user with S3 read access (AmazonS3ReadOnlyAccess).',
				'Generate an Access Key ID and Secret Access Key.',
				'Enter the bucket name, region, and optional prefix.',
				'For production, prefer IAM Roles over static credentials.'
			]
		},
		local: {
			title: 'Local Files Setup',
			steps: [
				'Provide the absolute path to the directory on the server.',
				'Ensure the application has read permissions for the path.',
				'Enable "Watch for changes" for automatic re-indexing.'
			]
		},
		web_crawler: {
			title: 'Web Crawler Setup',
			steps: [
				'Enter one or more start URLs (one per line).',
				'Set the max crawl depth and page limit.',
				'Disable "Follow external links" to stay on the same domain.',
				'Pages are converted to text and indexed automatically.'
			]
		},
		custom: {
			title: 'Custom Integration Setup',
			steps: [
				'Provide the webhook URL that Firefly Desk will call.',
				'Optionally set an Authorization header value.',
				'The webhook must return documents in the expected JSON format.',
				'See the API documentation for the webhook contract.'
			]
		}
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let saving = $state(false);
	let testing = $state(false);
	let error = $state('');

	let testResult = $state<{ success: boolean; message: string } | null>(null);

	let formData = $state({
		source_type: '' as string,
		// Connection fields — Google Drive
		gd_service_account_json: '',
		gd_folder_id: '',
		gd_include_shared_drives: false,
		// Connection fields — SharePoint
		sp_tenant_id: '',
		sp_client_id: '',
		sp_client_secret: '',
		sp_site_url: '',
		sp_library_name: '',
		// Connection fields — S3
		s3_bucket_name: '',
		s3_region: '',
		s3_access_key_id: '',
		s3_secret_access_key: '',
		s3_prefix: '',
		// Connection fields — Local
		local_directory_path: '',
		local_watch: false,
		// Connection fields — Web Crawler
		wc_start_urls: '',
		wc_max_depth: 3,
		wc_max_pages: 100,
		wc_follow_external: false,
		// Connection fields — Custom
		custom_webhook_url: '',
		custom_auth_header: '',
		// Sync options
		sync_schedule: 'manual',
		file_types: ['pdf', 'docx', 'txt', 'md'] as string[],
		max_file_size_mb: 50,
		include_subdirectories: true
	});

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const sourceTypeInfo = $derived(
		SOURCE_TYPES.find((s) => s.value === formData.source_type)
	);

	const setupGuide = $derived(SETUP_GUIDES[formData.source_type]);

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const step1Valid = $derived(formData.source_type !== '');

	const step2Valid = $derived(() => {
		switch (formData.source_type) {
			case 'google_drive':
				return formData.gd_service_account_json.trim() !== '';
			case 'sharepoint':
				return (
					formData.sp_tenant_id.trim() !== '' &&
					formData.sp_client_id.trim() !== '' &&
					formData.sp_client_secret.trim() !== '' &&
					formData.sp_site_url.trim() !== ''
				);
			case 's3':
				return (
					formData.s3_bucket_name.trim() !== '' &&
					formData.s3_region.trim() !== ''
				);
			case 'local':
				return formData.local_directory_path.trim() !== '';
			case 'web_crawler':
				return formData.wc_start_urls.trim() !== '';
			case 'custom':
				return formData.custom_webhook_url.trim() !== '';
			default:
				return false;
		}
	});

	const step3Valid = $derived(
		formData.file_types.length > 0 && formData.max_file_size_mb > 0
	);

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return step1Valid;
			case 1:
				return step2Valid();
			case 2:
				return step3Valid;
			case 3:
				return step1Valid && step2Valid() && step3Valid;
			default:
				return false;
		}
	}

	function isStepComplete(step: number): boolean {
		return step < currentStep && isStepValid(step);
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function goNext() {
		if (currentStep < STEPS.length - 1 && isStepValid(currentStep)) {
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
	// Reset when modal opens/closes
	// -----------------------------------------------------------------------

	$effect(() => {
		if (open) {
			currentStep = 0;
			saving = false;
			testing = false;
			error = '';
			testResult = null;
			formData = {
				source_type: '',
				gd_service_account_json: '',
				gd_folder_id: '',
				gd_include_shared_drives: false,
				sp_tenant_id: '',
				sp_client_id: '',
				sp_client_secret: '',
				sp_site_url: '',
				sp_library_name: '',
				s3_bucket_name: '',
				s3_region: '',
				s3_access_key_id: '',
				s3_secret_access_key: '',
				s3_prefix: '',
				local_directory_path: '',
				local_watch: false,
				wc_start_urls: '',
				wc_max_depth: 3,
				wc_max_pages: 100,
				wc_follow_external: false,
				custom_webhook_url: '',
				custom_auth_header: '',
				sync_schedule: 'manual',
				file_types: ['pdf', 'docx', 'txt', 'md'],
				max_file_size_mb: 50,
				include_subdirectories: true
			};
		}
	});

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function toggleFileType(ft: string) {
		if (formData.file_types.includes(ft)) {
			formData.file_types = formData.file_types.filter((t) => t !== ft);
		} else {
			formData.file_types = [...formData.file_types, ft];
		}
	}

	function buildConnectionConfig(): Record<string, unknown> {
		switch (formData.source_type) {
			case 'google_drive':
				return {
					service_account_json: formData.gd_service_account_json,
					folder_id: formData.gd_folder_id,
					include_shared_drives: formData.gd_include_shared_drives
				};
			case 'sharepoint':
				return {
					tenant_id: formData.sp_tenant_id,
					client_id: formData.sp_client_id,
					client_secret: formData.sp_client_secret,
					site_url: formData.sp_site_url,
					library_name: formData.sp_library_name
				};
			case 's3':
				return {
					bucket_name: formData.s3_bucket_name,
					region: formData.s3_region,
					access_key_id: formData.s3_access_key_id,
					secret_access_key: formData.s3_secret_access_key,
					prefix: formData.s3_prefix
				};
			case 'local':
				return {
					directory_path: formData.local_directory_path,
					watch: formData.local_watch
				};
			case 'web_crawler':
				return {
					start_urls: formData.wc_start_urls
						.split('\n')
						.map((u) => u.trim())
						.filter(Boolean),
					max_depth: formData.wc_max_depth,
					max_pages: formData.wc_max_pages,
					follow_external: formData.wc_follow_external
				};
			case 'custom':
				return {
					webhook_url: formData.custom_webhook_url,
					auth_header: formData.custom_auth_header
				};
			default:
				return {};
		}
	}

	function buildPayload(): Record<string, unknown> {
		return {
			source_type: formData.source_type,
			connection: buildConnectionConfig(),
			sync_schedule: formData.sync_schedule,
			file_types: formData.file_types,
			max_file_size_mb: formData.max_file_size_mb,
			include_subdirectories: formData.include_subdirectories
		};
	}

	function sourceTypeLabel(value: string): string {
		return SOURCE_TYPES.find((s) => s.value === value)?.label ?? value;
	}

	function scheduleLabel(value: string): string {
		return SYNC_SCHEDULES.find((s) => s.value === value)?.label ?? value;
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			onClose();
		}
	}

	// -----------------------------------------------------------------------
	// Test Connection
	// -----------------------------------------------------------------------

	async function testConnection() {
		testing = true;
		testResult = null;
		error = '';

		try {
			const result = await apiJson<{ success: boolean; message?: string; error?: string }>(
				'/admin/document-sources/test',
				{
					method: 'POST',
					body: JSON.stringify({
						source_type: formData.source_type,
						connection: buildConnectionConfig()
					})
				}
			);
			testResult = {
				success: result.success,
				message: result.success
					? result.message ?? 'Connection successful'
					: result.error ?? 'Connection failed'
			};
		} catch (e) {
			testResult = {
				success: false,
				message: e instanceof Error ? e.message : 'Connection test failed'
			};
		} finally {
			testing = false;
		}
	}

	// -----------------------------------------------------------------------
	// Submit
	// -----------------------------------------------------------------------

	async function submit() {
		if (!isStepValid(3)) return;

		saving = true;
		error = '';

		try {
			await apiJson('/admin/document-sources', {
				method: 'POST',
				body: JSON.stringify(buildPayload())
			});
			onCreated();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create document source';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

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
				<h2 class="text-base font-semibold text-text-primary">
					New Document Source
				</h2>
				<button
					type="button"
					onclick={onClose}
					class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Step indicators -->
			<div class="flex items-center gap-2 border-b border-border px-6 py-3">
				{#each STEPS as stepLabel, i}
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
						class="flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors
							{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}
							{clickable ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default opacity-50'}"
					>
						<span
							class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
								{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
						>
							{#if complete}
								<Check size={12} />
							{:else}
								{i + 1}
							{/if}
						</span>
						<span class="hidden sm:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Error banner -->
			{#if error}
				<div class="mx-6 mt-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
					{error}
				</div>
			{/if}

			<!-- Step content -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				<!-- Step 1: Source Type -->
				{#if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Choose the type of document source you want to connect.
						</p>

						<div class="grid grid-cols-3 gap-3">
							{#each SOURCE_TYPES as source}
								{@const selected = formData.source_type === source.value}
								<button
									type="button"
									onclick={() => (formData.source_type = source.value)}
									class="flex flex-col items-center gap-2 rounded-lg border-2 px-4 py-5 text-center transition-colors
										{selected
											? 'ring-2 ring-accent bg-accent/5 border-accent'
											: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<source.icon size={28} class="{selected ? 'text-accent' : 'text-text-secondary'}" />
									<span class="text-sm font-medium {selected ? 'text-accent' : 'text-text-primary'}">
										{source.label}
									</span>
									<span class="text-xs {selected ? 'text-accent/70' : 'text-text-secondary'}">
										{source.description}
									</span>
								</button>
							{/each}
						</div>
					</div>

				<!-- Step 2: Connection Configuration -->
				{:else if currentStep === 1}
					<div class="flex gap-5">
						<!-- Form fields -->
						<div class="flex flex-1 flex-col gap-4">
							<p class="text-sm text-text-secondary">
								Configure the connection settings for {sourceTypeInfo?.label ?? 'your source'}.
							</p>

							<!-- Google Drive -->
							{#if formData.source_type === 'google_drive'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Service Account JSON <span class="text-danger">*</span></span>
									<textarea
										bind:value={formData.gd_service_account_json}
										rows={5}
										required
										placeholder={'{"type": "service_account", "project_id": "...", ...}'}
										class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-text-primary outline-none focus:border-accent"
									></textarea>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Folder ID</span>
									<input
										type="text"
										bind:value={formData.gd_folder_id}
										placeholder="e.g. 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2ktIm"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex items-center gap-2">
									<input
										type="checkbox"
										bind:checked={formData.gd_include_shared_drives}
										class="rounded border-border text-accent focus:ring-accent"
									/>
									<span class="text-sm text-text-primary">Include shared drives</span>
								</label>

							<!-- SharePoint -->
							{:else if formData.source_type === 'sharepoint'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Tenant ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.sp_tenant_id}
										required
										placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client ID <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.sp_client_id}
										required
										placeholder="Application (client) ID"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Client Secret <span class="text-danger">*</span></span>
									<input
										type="password"
										bind:value={formData.sp_client_secret}
										required
										placeholder="Enter client secret"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Site URL <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.sp_site_url}
										required
										placeholder="https://contoso.sharepoint.com/sites/docs"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Library Name</span>
									<input
										type="text"
										bind:value={formData.sp_library_name}
										placeholder="Documents"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

							<!-- Amazon S3 -->
							{:else if formData.source_type === 's3'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Bucket Name <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.s3_bucket_name}
										required
										placeholder="my-documents-bucket"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Region <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.s3_region}
										required
										placeholder="us-east-1"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Access Key ID</span>
									<input
										type="password"
										bind:value={formData.s3_access_key_id}
										placeholder="AKIA..."
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Secret Access Key</span>
									<input
										type="password"
										bind:value={formData.s3_secret_access_key}
										placeholder="Enter secret access key"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Prefix / Path</span>
									<input
										type="text"
										bind:value={formData.s3_prefix}
										placeholder="docs/"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

							<!-- Local Files -->
							{:else if formData.source_type === 'local'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Directory Path <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.local_directory_path}
										required
										placeholder="/var/data/documents"
										class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex items-center gap-2">
									<input
										type="checkbox"
										bind:checked={formData.local_watch}
										class="rounded border-border text-accent focus:ring-accent"
									/>
									<span class="text-sm text-text-primary">Watch for changes</span>
								</label>

							<!-- Web Crawler -->
							{:else if formData.source_type === 'web_crawler'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Start URLs <span class="text-danger">*</span></span>
									<textarea
										bind:value={formData.wc_start_urls}
										rows={4}
										required
										placeholder="https://docs.example.com&#10;https://help.example.com/sitemap.xml"
										class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-text-primary outline-none focus:border-accent"
									></textarea>
									<span class="text-xs text-text-secondary">One URL per line</span>
								</label>

								<div class="grid grid-cols-2 gap-3">
									<label class="flex flex-col gap-1">
										<span class="text-xs font-medium text-text-secondary">Max Depth</span>
										<input
											type="number"
											bind:value={formData.wc_max_depth}
											min={1}
											max={10}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>

									<label class="flex flex-col gap-1">
										<span class="text-xs font-medium text-text-secondary">Max Pages</span>
										<input
											type="number"
											bind:value={formData.wc_max_pages}
											min={1}
											max={10000}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>
								</div>

								<label class="flex items-center gap-2">
									<input
										type="checkbox"
										bind:checked={formData.wc_follow_external}
										class="rounded border-border text-accent focus:ring-accent"
									/>
									<span class="text-sm text-text-primary">Follow external links</span>
								</label>

							<!-- Custom -->
							{:else if formData.source_type === 'custom'}
								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Webhook URL <span class="text-danger">*</span></span>
									<input
										type="text"
										bind:value={formData.custom_webhook_url}
										required
										placeholder="https://api.example.com/documents/webhook"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>

								<label class="flex flex-col gap-1">
									<span class="text-xs font-medium text-text-secondary">Auth Header</span>
									<input
										type="password"
										bind:value={formData.custom_auth_header}
										placeholder="Bearer token or API key"
										class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
									/>
								</label>
							{/if}
						</div>

						<!-- Setup Guide panel -->
						{#if setupGuide}
							<div class="w-56 shrink-0 rounded-lg border border-accent/20 bg-accent/5 p-4">
								<h4 class="mb-2 text-xs font-semibold text-accent">{setupGuide.title}</h4>
								<ol class="list-inside list-decimal space-y-1.5 text-[11px] leading-relaxed text-text-secondary">
									{#each setupGuide.steps as step}
										<li>{step}</li>
									{/each}
								</ol>
							</div>
						{/if}
					</div>

				<!-- Step 3: Sync Options -->
				{:else if currentStep === 2}
					<div class="flex flex-col gap-5">
						<p class="text-sm text-text-secondary">
							Configure how and when documents are synced.
						</p>

						<!-- Sync Schedule -->
						<div class="flex flex-col gap-2">
							<span class="text-xs font-medium text-text-secondary">Sync Schedule</span>
							<div class="flex gap-2">
								{#each SYNC_SCHEDULES as schedule}
									{@const selected = formData.sync_schedule === schedule.value}
									<button
										type="button"
										onclick={() => (formData.sync_schedule = schedule.value)}
										class="flex-1 rounded-md border-2 px-3 py-2 text-sm font-medium transition-colors
											{selected
												? 'border-accent bg-accent/5 text-accent'
												: 'border-border bg-surface text-text-secondary hover:border-accent/50 hover:bg-surface-hover'}"
									>
										{schedule.label}
									</button>
								{/each}
							</div>
						</div>

						<!-- File type filters -->
						<div class="flex flex-col gap-2">
							<span class="text-xs font-medium text-text-secondary">File Type Filters</span>
							<div class="flex flex-wrap gap-2">
								{#each FILE_TYPES as ft}
									{@const checked = formData.file_types.includes(ft.value)}
									<label
										class="flex cursor-pointer items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors
											{checked
												? 'border-accent bg-accent/5 text-accent'
												: 'border-border bg-surface text-text-secondary hover:bg-surface-hover'}"
									>
										<input
											type="checkbox"
											checked={checked}
											onchange={() => toggleFileType(ft.value)}
											class="rounded border-border text-accent focus:ring-accent"
										/>
										{ft.label}
									</label>
								{/each}
							</div>
						</div>

						<!-- Max file size -->
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Max File Size (MB)</span>
							<input
								type="number"
								bind:value={formData.max_file_size_mb}
								min={1}
								max={500}
								class="w-32 rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<!-- Include subdirectories -->
						<label class="flex items-center gap-2">
							<input
								type="checkbox"
								bind:checked={formData.include_subdirectories}
								class="rounded border-border text-accent focus:ring-accent"
							/>
							<span class="text-sm text-text-primary">Include subdirectories</span>
						</label>
					</div>

				<!-- Step 4: Test & Review -->
				{:else if currentStep === 3}
					<div class="flex flex-col gap-5">
						<p class="text-sm text-text-secondary">
							Test the connection and review your configuration before creating.
						</p>

						<!-- Test Connection -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<div class="flex items-center justify-between">
								<h4 class="text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Connection Test
								</h4>
								<button
									type="button"
									onclick={testConnection}
									disabled={testing}
									class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
								>
									{#if testing}
										<Loader2 size={14} class="animate-spin" />
										Testing...
									{:else}
										<Zap size={14} />
										Test Connection
									{/if}
								</button>
							</div>

							{#if testResult}
								<div class="mt-3 flex items-start gap-2 rounded-md border px-3 py-2
									{testResult.success
										? 'border-success/30 bg-success/5'
										: 'border-danger/30 bg-danger/5'}"
								>
									{#if testResult.success}
										<CheckCircle size={16} class="mt-0.5 shrink-0 text-success" />
										<span class="text-sm text-success">{testResult.message}</span>
									{:else}
										<XCircle size={16} class="mt-0.5 shrink-0 text-danger" />
										<span class="text-sm text-danger">{testResult.message}</span>
									{/if}
								</div>
							{/if}
						</div>

						<!-- Summary -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<div class="flex flex-col gap-3">
								<!-- Source Type -->
								<div>
									<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
										Source Type
									</h4>
									<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
										<span class="text-text-secondary">Type:</span>
										<span class="font-medium text-text-primary">{sourceTypeLabel(formData.source_type)}</span>
									</div>
								</div>

								<hr class="border-border" />

								<!-- Connection -->
								<div>
									<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
										Connection
									</h4>
									<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
										{#if formData.source_type === 'google_drive'}
											<span class="text-text-secondary">Service Account:</span>
											<span class="text-text-primary">{formData.gd_service_account_json ? 'Provided' : 'Not set'}</span>
											<span class="text-text-secondary">Folder ID:</span>
											<span class="font-mono text-xs text-text-primary">{formData.gd_folder_id || 'Root'}</span>
											<span class="text-text-secondary">Shared Drives:</span>
											<span class="text-text-primary">{formData.gd_include_shared_drives ? 'Yes' : 'No'}</span>
										{:else if formData.source_type === 'sharepoint'}
											<span class="text-text-secondary">Tenant ID:</span>
											<span class="font-mono text-xs text-text-primary">{formData.sp_tenant_id}</span>
											<span class="text-text-secondary">Client ID:</span>
											<span class="font-mono text-xs text-text-primary">{formData.sp_client_id}</span>
											<span class="text-text-secondary">Site URL:</span>
											<span class="text-xs text-text-primary">{formData.sp_site_url}</span>
											{#if formData.sp_library_name}
												<span class="text-text-secondary">Library:</span>
												<span class="text-text-primary">{formData.sp_library_name}</span>
											{/if}
										{:else if formData.source_type === 's3'}
											<span class="text-text-secondary">Bucket:</span>
											<span class="font-mono text-xs text-text-primary">{formData.s3_bucket_name}</span>
											<span class="text-text-secondary">Region:</span>
											<span class="text-text-primary">{formData.s3_region}</span>
											<span class="text-text-secondary">Credentials:</span>
											<span class="text-text-primary">{formData.s3_access_key_id ? 'Provided' : 'IAM Role'}</span>
											{#if formData.s3_prefix}
												<span class="text-text-secondary">Prefix:</span>
												<span class="font-mono text-xs text-text-primary">{formData.s3_prefix}</span>
											{/if}
										{:else if formData.source_type === 'local'}
											<span class="text-text-secondary">Path:</span>
											<span class="font-mono text-xs text-text-primary">{formData.local_directory_path}</span>
											<span class="text-text-secondary">Watch:</span>
											<span class="text-text-primary">{formData.local_watch ? 'Yes' : 'No'}</span>
										{:else if formData.source_type === 'web_crawler'}
											<span class="text-text-secondary">Start URLs:</span>
											<span class="text-text-primary">{formData.wc_start_urls.split('\n').filter(Boolean).length} URL(s)</span>
											<span class="text-text-secondary">Max Depth:</span>
											<span class="text-text-primary">{formData.wc_max_depth}</span>
											<span class="text-text-secondary">Max Pages:</span>
											<span class="text-text-primary">{formData.wc_max_pages}</span>
											<span class="text-text-secondary">External Links:</span>
											<span class="text-text-primary">{formData.wc_follow_external ? 'Yes' : 'No'}</span>
										{:else if formData.source_type === 'custom'}
											<span class="text-text-secondary">Webhook URL:</span>
											<span class="text-xs text-text-primary">{formData.custom_webhook_url}</span>
											<span class="text-text-secondary">Auth Header:</span>
											<span class="text-text-primary">{formData.custom_auth_header ? 'Provided' : 'None'}</span>
										{/if}
									</div>
								</div>

								<hr class="border-border" />

								<!-- Sync Options -->
								<div>
									<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
										Sync Options
									</h4>
									<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
										<span class="text-text-secondary">Schedule:</span>
										<span class="text-text-primary">{scheduleLabel(formData.sync_schedule)}</span>
										<span class="text-text-secondary">File Types:</span>
										<span class="text-text-primary">
											{formData.file_types.map((t) => t.toUpperCase()).join(', ')}
										</span>
										<span class="text-text-secondary">Max File Size:</span>
										<span class="text-text-primary">{formData.max_file_size_mb} MB</span>
										<span class="text-text-secondary">Subdirectories:</span>
										<span class="text-text-primary">{formData.include_subdirectories ? 'Yes' : 'No'}</span>
									</div>
								</div>
							</div>
						</div>

						{#if !isStepValid(3)}
							<div class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3">
								<AlertTriangle size={16} class="mt-0.5 shrink-0 text-warning" />
								<p class="text-sm text-warning">
									Please complete all required fields before creating.
								</p>
							</div>
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
						onclick={onClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>

					{#if currentStep < STEPS.length - 1}
						<button
							type="button"
							onclick={goNext}
							disabled={!isStepValid(currentStep)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ChevronRight size={14} />
						</button>
					{:else}
						<button
							type="button"
							onclick={submit}
							disabled={saving || !isStepValid(3)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							Create Source
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
