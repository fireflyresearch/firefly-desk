<!--
  EndpointWizard.svelte - Multi-step wizard for creating/editing service endpoints.

  4-step wizard: Basics, Protocol, Parameters & Body, Advanced & Review.
  Displays as a modal overlay with step indicators, validation, and
  dynamic protocol-specific fields based on selected protocol type.

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
		Zap,
		Globe,
		Code,
		FileText
	} from 'lucide-svelte';
	import { untrack } from 'svelte';
	import { apiJson } from '$lib/services/api.js';
	import RichEditor from '$lib/components/shared/RichEditor.svelte';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		systemId: string;
		editingEndpoint?: any | null;
		onClose: () => void;
		onSaved: () => void;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let {
		systemId,
		editingEndpoint = null,
		onClose,
		onSaved
	}: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Basics', 'Protocol', 'Parameters & Body', 'Advanced & Review'] as const;

	const PROTOCOL_TYPES = [
		{ value: 'rest', label: 'REST', icon: Globe },
		{ value: 'graphql', label: 'GraphQL', icon: Zap },
		{ value: 'soap', label: 'SOAP', icon: FileText },
		{ value: 'grpc', label: 'gRPC', icon: Code }
	] as const;

	const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const;

	const RISK_LEVELS = [
		{ value: 'read', label: 'Read', desc: 'Read-only operations' },
		{ value: 'low_write', label: 'Low Write', desc: 'Low-impact write operations' },
		{ value: 'high_write', label: 'High Write', desc: 'High-impact write operations' },
		{ value: 'destructive', label: 'Destructive', desc: 'Destructive / irreversible operations' }
	] as const;

	// -----------------------------------------------------------------------
	// Initial values (captured once at mount)
	// -----------------------------------------------------------------------

	const _init = untrack(() => editingEndpoint);
	const isEditMode = _init !== null;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let saving = $state(false);
	let error = $state('');

	let formData = $state({
		id: _init?.id ?? '',
		name: _init?.name ?? '',
		description: _init?.description ?? '',
		when_to_use: _init?.when_to_use ?? '',
		risk_level: _init?.risk_level ?? 'read',
		required_permissions: _init?.required_permissions?.join(', ') ?? '',
		protocol_type: _init?.protocol_type ?? 'rest',
		method: _init?.method ?? 'GET',
		path: _init?.path ?? '',
		graphql_query: _init?.graphql_query ?? '',
		graphql_operation_name: _init?.graphql_operation_name ?? '',
		soap_action: _init?.soap_action ?? '',
		soap_body_template: _init?.soap_body_template ?? '',
		grpc_service: _init?.grpc_service ?? '',
		grpc_method_name: _init?.grpc_method_name ?? '',
		path_params_json: _init?.path_params ? JSON.stringify(_init.path_params, null, 2) : '{}',
		query_params_json: _init?.query_params ? JSON.stringify(_init.query_params, null, 2) : '{}',
		request_body_json: _init?.request_body ? JSON.stringify(_init.request_body, null, 2) : '{}',
		response_schema_json: _init?.response_schema ? JSON.stringify(_init.response_schema, null, 2) : '{}',
		timeout_seconds: _init?.timeout_seconds ?? 30,
		rate_limit_max: _init?.rate_limit?.max_requests?.toString() ?? '',
		rate_limit_window: _init?.rate_limit?.window_seconds?.toString() ?? '',
		retry_max: _init?.retry_policy?.max_retries?.toString() ?? '',
		retry_backoff: _init?.retry_policy?.backoff_multiplier?.toString() ?? '',
		tags: _init?.tags?.join(', ') ?? '',
		examples: _init?.examples?.join('\n') ?? ''
	});

	// -----------------------------------------------------------------------
	// JSON validation state
	// -----------------------------------------------------------------------

	let jsonErrors = $state<Record<string, string>>({});

	function validateJson(field: string, value: string): boolean {
		try {
			JSON.parse(value);
			delete jsonErrors[field];
			jsonErrors = { ...jsonErrors };
			return true;
		} catch (e) {
			jsonErrors = { ...jsonErrors, [field]: e instanceof Error ? e.message : 'Invalid JSON' };
			return false;
		}
	}

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const endpointId = $derived(
		isEditMode
			? _init!.id
			: formData.id || formData.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
	);

	const detectedPathParams = $derived(
		(formData.path.match(/\{(\w+)\}/g) ?? []).map((p: string) => p.slice(1, -1))
	);

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const step1Valid = $derived(
		formData.name.trim() !== '' && formData.description.trim() !== ''
	);

	const step2Valid = $derived(() => {
		switch (formData.protocol_type) {
			case 'rest':
				return formData.method !== '' && formData.path.trim() !== '';
			case 'graphql':
				return formData.graphql_query.trim() !== '';
			case 'soap':
				return formData.soap_action.trim() !== '';
			case 'grpc':
				return formData.grpc_service.trim() !== '' && formData.grpc_method_name.trim() !== '';
			default:
				return false;
		}
	});

	const step3Valid = $derived(() => {
		const fields = ['path_params_json', 'query_params_json', 'request_body_json', 'response_schema_json'] as const;
		for (const f of fields) {
			try {
				JSON.parse(formData[f]);
			} catch {
				return false;
			}
		}
		return true;
	});

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return step1Valid;
			case 1:
				return step2Valid();
			case 2:
				return step3Valid();
			case 3:
				return step1Valid && step2Valid() && step3Valid();
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
	// Helpers
	// -----------------------------------------------------------------------

	function safeJsonParse(value: string): any {
		try {
			return JSON.parse(value);
		} catch {
			return {};
		}
	}

	function riskLevelLabel(value: string): string {
		return RISK_LEVELS.find((r) => r.value === value)?.label ?? value;
	}

	function protocolLabel(value: string): string {
		return PROTOCOL_TYPES.find((p) => p.value === value)?.label ?? value;
	}

	function riskLevelVariant(level: string): string {
		switch (level) {
			case 'read':
				return 'bg-success/10 text-success';
			case 'low_write':
				return 'bg-accent/10 text-accent';
			case 'high_write':
				return 'bg-warning/10 text-warning';
			case 'destructive':
				return 'bg-danger/10 text-danger';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}

	function methodVariant(method: string): string {
		switch (method.toUpperCase()) {
			case 'GET':
				return 'bg-success/10 text-success';
			case 'POST':
				return 'bg-accent/10 text-accent';
			case 'PUT':
			case 'PATCH':
				return 'bg-warning/10 text-warning';
			case 'DELETE':
				return 'bg-danger/10 text-danger';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}

	// -----------------------------------------------------------------------
	// Submit
	// -----------------------------------------------------------------------

	function buildPayload(): Record<string, unknown> {
		return {
			id: endpointId,
			system_id: systemId,
			name: formData.name.trim(),
			description: formData.description.trim(),
			when_to_use: formData.when_to_use.trim() || null,
			risk_level: formData.risk_level,
			required_permissions: formData.required_permissions
				.split(',')
				.map((s: string) => s.trim())
				.filter(Boolean),
			protocol_type: formData.protocol_type,
			method: formData.protocol_type === 'rest' ? formData.method : 'POST',
			path: formData.path.trim(),
			graphql_query: formData.protocol_type === 'graphql' ? formData.graphql_query.trim() : null,
			graphql_operation_name: formData.protocol_type === 'graphql' ? formData.graphql_operation_name.trim() || null : null,
			soap_action: formData.protocol_type === 'soap' ? formData.soap_action.trim() : null,
			soap_body_template: formData.protocol_type === 'soap' ? formData.soap_body_template.trim() || null : null,
			grpc_service: formData.protocol_type === 'grpc' ? formData.grpc_service.trim() : null,
			grpc_method_name: formData.protocol_type === 'grpc' ? formData.grpc_method_name.trim() : null,
			path_params: safeJsonParse(formData.path_params_json),
			query_params: safeJsonParse(formData.query_params_json),
			request_body: safeJsonParse(formData.request_body_json),
			response_schema: safeJsonParse(formData.response_schema_json),
			timeout_seconds: formData.timeout_seconds,
			rate_limit: formData.rate_limit_max
				? {
						max_requests: Number(formData.rate_limit_max),
						window_seconds: Number(formData.rate_limit_window) || 60
					}
				: null,
			retry_policy: formData.retry_max
				? {
						max_retries: Number(formData.retry_max),
						backoff_multiplier: Number(formData.retry_backoff) || 2
					}
				: null,
			tags: formData.tags
				.split(',')
				.map((t: string) => t.trim())
				.filter(Boolean),
			examples: formData.examples.split('\n').filter(Boolean)
		};
	}

	async function submit() {
		if (!isStepValid(3)) return;

		saving = true;
		error = '';

		const payload = buildPayload();

		try {
			if (isEditMode) {
				await apiJson(`/catalog/endpoints/${_init!.id}`, {
					method: 'PUT',
					body: JSON.stringify(payload)
				});
			} else {
				await apiJson(`/catalog/systems/${systemId}/endpoints`, {
					method: 'POST',
					body: JSON.stringify(payload)
				});
			}
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save endpoint';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Modal backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
	role="presentation"
	onclick={handleBackdropClick}
>
	<!-- Modal content -->
	<div class="mx-4 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl bg-surface shadow-2xl">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-6 py-4">
			<h2 class="text-base font-semibold text-text-primary">
				{isEditMode ? 'Edit Endpoint' : 'New Endpoint'}
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
			<!-- Step 1: Basics -->
			{#if currentStep === 0}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Define the basic information about this endpoint.
					</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Name <span class="text-danger">*</span></span>
						<input
							type="text"
							bind:value={formData.name}
							required
							placeholder="e.g. Get Customer Details"
							class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
						/>
						{#if formData.name && endpointId}
							<span class="text-xs text-text-secondary">
								Endpoint ID: <code class="rounded bg-surface-secondary px-1 py-0.5 font-mono">{endpointId}</code>
							</span>
						{/if}
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Description <span class="text-danger">*</span></span>
						<RichEditor
							value={formData.description}
							placeholder="Endpoint description..."
							mode="compact"
							minHeight="80px"
							onchange={(md) => (formData.description = md)}
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">When to Use (Agent Guidance)</span>
						<RichEditor
							value={formData.when_to_use}
							placeholder="When to use this endpoint..."
							mode="compact"
							minHeight="60px"
							onchange={(md) => (formData.when_to_use = md)}
						/>
						<span class="text-xs text-text-secondary">
							Natural language guidance for the AI agent on when to use this endpoint.
						</span>
					</label>

					<div class="grid grid-cols-2 gap-4">
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Risk Level</span>
							<select
								bind:value={formData.risk_level}
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							>
								{#each RISK_LEVELS as level}
									<option value={level.value}>{level.label} -- {level.desc}</option>
								{/each}
							</select>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Required Permissions</span>
							<input
								type="text"
								bind:value={formData.required_permissions}
								placeholder="e.g. read:customers, write:orders"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
							<span class="text-xs text-text-secondary">Comma-separated permission strings.</span>
						</label>
					</div>
				</div>

			<!-- Step 2: Protocol Configuration -->
			{:else if currentStep === 1}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Select the protocol and configure protocol-specific settings.
					</p>

					<!-- Protocol type selector -->
					<div class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Protocol Type</span>
						<div class="grid grid-cols-4 gap-2">
							{#each PROTOCOL_TYPES as proto}
								{@const selected = formData.protocol_type === proto.value}
								<button
									type="button"
									onclick={() => (formData.protocol_type = proto.value)}
									class="flex flex-col items-center gap-1.5 rounded-lg border-2 px-3 py-3 text-sm font-medium transition-colors
										{selected
											? 'border-accent bg-accent/5 text-accent'
											: 'border-border bg-surface text-text-secondary hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<proto.icon size={20} />
									{proto.label}
								</button>
							{/each}
						</div>
					</div>

					<!-- REST fields -->
					{#if formData.protocol_type === 'rest'}
						<div class="grid grid-cols-[140px_1fr] gap-4">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Method <span class="text-danger">*</span></span>
								<select
									bind:value={formData.method}
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono font-medium text-text-primary outline-none focus:border-accent"
								>
									{#each HTTP_METHODS as m}
										<option value={m}>{m}</option>
									{/each}
								</select>
							</label>

							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Path <span class="text-danger">*</span></span>
								<input
									type="text"
									bind:value={formData.path}
									required
									placeholder={'/customers/{customer_id}/orders'}
									class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						</div>

						{#if detectedPathParams.length > 0}
							<div class="flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2">
								<Zap size={14} class="shrink-0 text-accent" />
								<span class="text-xs text-text-secondary">
									Detected path parameters:
									{#each detectedPathParams as param, i}
										<code class="rounded bg-accent/10 px-1 py-0.5 font-mono text-accent">{param}</code>{i < detectedPathParams.length - 1 ? ', ' : ''}
									{/each}
								</span>
							</div>
						{/if}

					<!-- GraphQL fields -->
					{:else if formData.protocol_type === 'graphql'}
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">GraphQL Query <span class="text-danger">*</span></span>
							<textarea
								bind:value={formData.graphql_query}
								rows={6}
								required
								placeholder={'query GetCustomer($id: ID!) {\n  customer(id: $id) {\n    id\n    name\n    email\n  }\n}'}
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							></textarea>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Operation Name</span>
							<input
								type="text"
								bind:value={formData.graphql_operation_name}
								placeholder="e.g. GetCustomer"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

					<!-- SOAP fields -->
					{:else if formData.protocol_type === 'soap'}
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">SOAP Action <span class="text-danger">*</span></span>
							<input
								type="text"
								bind:value={formData.soap_action}
								required
								placeholder="e.g. http://example.com/GetCustomer"
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Body Template</span>
							<textarea
								bind:value={formData.soap_body_template}
								rows={6}
								placeholder={'<soapenv:Envelope>\n  <soapenv:Body>\n    ...\n  </soapenv:Body>\n</soapenv:Envelope>'}
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							></textarea>
						</label>

					<!-- gRPC fields -->
					{:else if formData.protocol_type === 'grpc'}
						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Service Name <span class="text-danger">*</span></span>
							<input
								type="text"
								bind:value={formData.grpc_service}
								required
								placeholder="e.g. customer.CustomerService"
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Method Name <span class="text-danger">*</span></span>
							<input
								type="text"
								bind:value={formData.grpc_method_name}
								required
								placeholder="e.g. GetCustomer"
								class="rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>
					{/if}
				</div>

			<!-- Step 3: Parameters & Body -->
			{:else if currentStep === 2}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Define parameters, request body, and response schema as JSON.
					</p>

					{#if formData.protocol_type === 'rest' && detectedPathParams.length > 0}
						<div class="flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2">
							<Zap size={14} class="shrink-0 text-accent" />
							<span class="text-xs text-text-secondary">
								Detected path parameters from <code class="font-mono">{formData.path}</code>:
								{#each detectedPathParams as param, i}
									<code class="rounded bg-accent/10 px-1 py-0.5 font-mono text-accent">{param}</code>{i < detectedPathParams.length - 1 ? ', ' : ''}
								{/each}
							</span>
						</div>
					{/if}

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Path Parameters (JSON)</span>
						<textarea
							bind:value={formData.path_params_json}
							rows={3}
							placeholder={'{\n  "customer_id": "string"\n}'}
							oninput={() => validateJson('path_params_json', formData.path_params_json)}
							class="rounded-md border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent
								{jsonErrors['path_params_json'] ? 'border-danger' : 'border-border'}"
						></textarea>
						{#if jsonErrors['path_params_json']}
							<span class="text-xs text-danger">{jsonErrors['path_params_json']}</span>
						{/if}
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Query Parameters (JSON)</span>
						<textarea
							bind:value={formData.query_params_json}
							rows={3}
							placeholder={'{\n  "limit": "integer",\n  "offset": "integer"\n}'}
							oninput={() => validateJson('query_params_json', formData.query_params_json)}
							class="rounded-md border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent
								{jsonErrors['query_params_json'] ? 'border-danger' : 'border-border'}"
						></textarea>
						{#if jsonErrors['query_params_json']}
							<span class="text-xs text-danger">{jsonErrors['query_params_json']}</span>
						{/if}
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Request Body (JSON)</span>
						<textarea
							bind:value={formData.request_body_json}
							rows={4}
							placeholder={'{\n  "name": "string",\n  "email": "string"\n}'}
							oninput={() => validateJson('request_body_json', formData.request_body_json)}
							class="rounded-md border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent
								{jsonErrors['request_body_json'] ? 'border-danger' : 'border-border'}"
						></textarea>
						{#if jsonErrors['request_body_json']}
							<span class="text-xs text-danger">{jsonErrors['request_body_json']}</span>
						{/if}
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Response Schema (JSON)</span>
						<textarea
							bind:value={formData.response_schema_json}
							rows={4}
							placeholder={'{\n  "id": "string",\n  "name": "string",\n  "created_at": "datetime"\n}'}
							oninput={() => validateJson('response_schema_json', formData.response_schema_json)}
							class="rounded-md border bg-surface px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-accent
								{jsonErrors['response_schema_json'] ? 'border-danger' : 'border-border'}"
						></textarea>
						{#if jsonErrors['response_schema_json']}
							<span class="text-xs text-danger">{jsonErrors['response_schema_json']}</span>
						{/if}
					</label>
				</div>

			<!-- Step 4: Advanced & Review -->
			{:else if currentStep === 3}
				<div class="flex flex-col gap-4">
					<p class="text-sm text-text-secondary">
						Configure advanced settings and review before {isEditMode ? 'updating' : 'creating'}.
					</p>

					<!-- Advanced settings -->
					<div class="flex flex-col gap-4 rounded-lg border border-border bg-surface-secondary/30 p-4">
						<h4 class="text-xs font-semibold uppercase tracking-wide text-text-secondary">
							Advanced Settings
						</h4>

						<div class="grid grid-cols-3 gap-4">
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">Timeout (seconds)</span>
								<input
									type="number"
									bind:value={formData.timeout_seconds}
									min={1}
									max={300}
									class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
								/>
							</label>
						</div>

						<div class="grid grid-cols-2 gap-4">
							<div class="flex flex-col gap-2">
								<span class="text-xs font-medium text-text-secondary">Rate Limit</span>
								<div class="grid grid-cols-2 gap-2">
									<label class="flex flex-col gap-1">
										<span class="text-[10px] text-text-secondary">Max Requests</span>
										<input
											type="number"
											bind:value={formData.rate_limit_max}
											placeholder="--"
											min={1}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>
									<label class="flex flex-col gap-1">
										<span class="text-[10px] text-text-secondary">Window (sec)</span>
										<input
											type="number"
											bind:value={formData.rate_limit_window}
											placeholder="60"
											min={1}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>
								</div>
							</div>

							<div class="flex flex-col gap-2">
								<span class="text-xs font-medium text-text-secondary">Retry Policy</span>
								<div class="grid grid-cols-2 gap-2">
									<label class="flex flex-col gap-1">
										<span class="text-[10px] text-text-secondary">Max Retries</span>
										<input
											type="number"
											bind:value={formData.retry_max}
											placeholder="--"
											min={0}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>
									<label class="flex flex-col gap-1">
										<span class="text-[10px] text-text-secondary">Backoff Mult.</span>
										<input
											type="number"
											bind:value={formData.retry_backoff}
											placeholder="2"
											min={1}
											step={0.5}
											class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
										/>
									</label>
								</div>
							</div>
						</div>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
							<input
								type="text"
								bind:value={formData.tags}
								placeholder="e.g. customer, read, v2"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							/>
						</label>

						<label class="flex flex-col gap-1">
							<span class="text-xs font-medium text-text-secondary">Examples (one per line)</span>
							<textarea
								bind:value={formData.examples}
								rows={3}
								placeholder="Get customer by ID 12345&#10;Fetch the details of customer john-doe"
								class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
							></textarea>
							<span class="text-xs text-text-secondary">
								Example natural language invocations for the agent.
							</span>
						</label>
					</div>

					<!-- Summary card -->
					<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
						<div class="flex flex-col gap-3">
							<!-- Basics -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Basics
								</h4>
								<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
									<span class="text-text-secondary">Name:</span>
									<span class="font-medium text-text-primary">{formData.name}</span>
									<span class="text-text-secondary">ID:</span>
									<span class="font-mono text-xs text-text-primary">{endpointId}</span>
									<span class="text-text-secondary">Description:</span>
									<span class="text-text-primary">{formData.description}</span>
									{#if formData.when_to_use.trim()}
										<span class="text-text-secondary">When to Use:</span>
										<span class="text-text-primary">{formData.when_to_use}</span>
									{/if}
									<span class="text-text-secondary">Risk Level:</span>
									<span>
										<span class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {riskLevelVariant(formData.risk_level)}">
											{riskLevelLabel(formData.risk_level)}
										</span>
									</span>
									{#if formData.required_permissions.trim()}
										<span class="text-text-secondary">Permissions:</span>
										<span class="text-text-primary">
											{formData.required_permissions.split(',').map((s: string) => s.trim()).filter(Boolean).join(', ')}
										</span>
									{/if}
								</div>
							</div>

							<hr class="border-border" />

							<!-- Protocol -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Protocol
								</h4>
								<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
									<span class="text-text-secondary">Type:</span>
									<span class="font-medium text-text-primary">{protocolLabel(formData.protocol_type)}</span>

									{#if formData.protocol_type === 'rest'}
										<span class="text-text-secondary">Method:</span>
										<span>
											<span class="rounded px-1.5 py-0.5 font-mono text-xs font-medium {methodVariant(formData.method)}">
												{formData.method}
											</span>
										</span>
										<span class="text-text-secondary">Path:</span>
										<span class="font-mono text-xs text-text-primary">{formData.path}</span>
									{:else if formData.protocol_type === 'graphql'}
										<span class="text-text-secondary">Query:</span>
										<span class="font-mono text-xs text-text-primary line-clamp-2">{formData.graphql_query}</span>
										{#if formData.graphql_operation_name.trim()}
											<span class="text-text-secondary">Operation:</span>
											<span class="font-mono text-xs text-text-primary">{formData.graphql_operation_name}</span>
										{/if}
									{:else if formData.protocol_type === 'soap'}
										<span class="text-text-secondary">Action:</span>
										<span class="font-mono text-xs text-text-primary">{formData.soap_action}</span>
										{#if formData.soap_body_template.trim()}
											<span class="text-text-secondary">Body Template:</span>
											<span class="font-mono text-xs text-text-primary line-clamp-2">{formData.soap_body_template}</span>
										{/if}
									{:else if formData.protocol_type === 'grpc'}
										<span class="text-text-secondary">Service:</span>
										<span class="font-mono text-xs text-text-primary">{formData.grpc_service}</span>
										<span class="text-text-secondary">Method:</span>
										<span class="font-mono text-xs text-text-primary">{formData.grpc_method_name}</span>
									{/if}
								</div>
							</div>

							<hr class="border-border" />

							<!-- Advanced -->
							<div>
								<h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
									Advanced
								</h4>
								<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
									<span class="text-text-secondary">Timeout:</span>
									<span class="text-text-primary">{formData.timeout_seconds}s</span>
									{#if formData.rate_limit_max}
										<span class="text-text-secondary">Rate Limit:</span>
										<span class="text-text-primary">
											{formData.rate_limit_max} req / {formData.rate_limit_window || 60}s
										</span>
									{/if}
									{#if formData.retry_max}
										<span class="text-text-secondary">Retry:</span>
										<span class="text-text-primary">
											{formData.retry_max} retries, {formData.retry_backoff || 2}x backoff
										</span>
									{/if}
									{#if formData.tags.trim()}
										<span class="text-text-secondary">Tags:</span>
										<span class="text-text-primary">
											{formData.tags.split(',').map((t: string) => t.trim()).filter(Boolean).join(', ')}
										</span>
									{/if}
									{#if formData.examples.trim()}
										<span class="text-text-secondary">Examples:</span>
										<span class="text-text-primary">
											{formData.examples.split('\n').filter(Boolean).length} example(s)
										</span>
									{/if}
								</div>
							</div>
						</div>
					</div>

					{#if !isStepValid(3)}
						<div class="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 px-4 py-3">
							<AlertTriangle size={16} class="mt-0.5 shrink-0 text-warning" />
							<p class="text-sm text-warning">
								Please complete all required fields before saving.
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
						{isEditMode ? 'Update Endpoint' : 'Create Endpoint'}
					</button>
				{/if}
			</div>
		</div>
	</div>
</div>
