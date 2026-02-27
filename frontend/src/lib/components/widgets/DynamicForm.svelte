<!--
  DynamicForm.svelte - Sectioned form widget combining read-only info,
  editable fields, and action buttons.

  Sections are rendered in order:
  - "info"    → key-value pairs or severity-styled alert messages
  - "fields"  → editable form fields in a responsive 2-column grid
  - "actions" → submit / cancel / custom action buttons

  After submission the form becomes read-only and the clicked action is
  sent as a chat message so the agent can continue the conversation.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Check, X, Info, TriangleAlert, CircleX, CircleCheckBig } from 'lucide-svelte';
	import type { Component } from 'svelte';
	import { sendMessage } from '$lib/services/chat.js';
	import { activeConversationId } from '$lib/stores/chat.js';
	import { get } from 'svelte/store';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	type FieldType =
		| 'text'
		| 'number'
		| 'select'
		| 'date'
		| 'textarea'
		| 'checkbox'
		| 'email'
		| 'phone'
		| 'url'
		| 'currency'
		| 'password'
		| 'radio'
		| 'toggle';

	interface FormField {
		key: string;
		label: string;
		type: FieldType;
		placeholder?: string;
		description?: string;
		required?: boolean;
		default?: string | number | boolean;
		options?: string[];
		currency_code?: string;
		validation?: string;
	}

	interface InfoItem {
		label: string;
		value: string;
	}

	interface ActionButton {
		label: string;
		action: string;
		style?: 'primary' | 'danger' | 'ghost' | 'default';
	}

	interface InfoSection {
		kind: 'info';
		title?: string;
		items?: InfoItem[];
		message?: string;
		severity?: 'info' | 'warning' | 'error' | 'success';
	}

	interface FieldsSection {
		kind: 'fields';
		title?: string;
		fields: FormField[];
	}

	interface ActionsSection {
		kind: 'actions';
		buttons: ActionButton[];
	}

	type Section = InfoSection | FieldsSection | ActionsSection;

	interface DynamicFormProps {
		widget_id?: string;
		title?: string;
		sections: Section[];
		save_endpoint?: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { widget_id, title, sections, save_endpoint }: DynamicFormProps = $props();

	// -----------------------------------------------------------------------
	// Severity styling (for info sections with a message)
	// -----------------------------------------------------------------------

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const severityIcons: Record<string, Component<any>> = {
		info: Info as unknown as Component<any>,
		warning: TriangleAlert as unknown as Component<any>,
		error: CircleX as unknown as Component<any>,
		success: CircleCheckBig as unknown as Component<any>
	};

	const severityBorder: Record<string, string> = {
		info: 'border-l-accent',
		warning: 'border-l-ember',
		error: 'border-l-danger',
		success: 'border-l-success'
	};

	const severityBg: Record<string, string> = {
		info: 'bg-accent/5',
		warning: 'bg-ember/5',
		error: 'bg-danger/5',
		success: 'bg-success/5'
	};

	const severityIconColor: Record<string, string> = {
		info: 'text-accent',
		warning: 'text-ember',
		error: 'text-danger',
		success: 'text-success'
	};

	// -----------------------------------------------------------------------
	// Form state
	// -----------------------------------------------------------------------

	function buildDefaults(): Record<string, string | number | boolean> {
		const defaults: Record<string, string | number | boolean> = {};
		for (const section of sections) {
			if (section.kind !== 'fields') continue;
			for (const field of section.fields) {
				if (field.default != null) {
					if (field.type === 'date' && field.default === 'today') {
						defaults[field.key] = new Date().toISOString().slice(0, 10);
					} else {
						defaults[field.key] = field.default;
					}
				} else if (field.type === 'checkbox' || field.type === 'toggle') {
					defaults[field.key] = false;
				} else if (field.type === 'number' || field.type === 'currency') {
					defaults[field.key] = '';
				} else {
					defaults[field.key] = '';
				}
			}
		}
		return defaults;
	}

	let formValues: Record<string, string | number | boolean> = $state(buildDefaults());
	let errors: Record<string, string> = $state({});
	let submitted = $state(false);
	let submittedAction = $state('');
	let submitting = $state(false);

	// -----------------------------------------------------------------------
	// Decline/cancel actions bypass validation
	// -----------------------------------------------------------------------

	const declineActions = new Set(['decline', 'reject', 'cancel', 'deny', 'dismiss']);

	function isDeclineAction(action: string): boolean {
		return declineActions.has(action.toLowerCase());
	}

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	function allFields(): FormField[] {
		const result: FormField[] = [];
		for (const section of sections) {
			if (section.kind === 'fields') {
				result.push(...section.fields);
			}
		}
		return result;
	}

	function validate(): boolean {
		const newErrors: Record<string, string> = {};
		for (const field of allFields()) {
			const value = formValues[field.key];

			// Required check
			if (field.required) {
				if (value == null || value === '') {
					newErrors[field.key] = `${field.label} is required`;
					continue;
				}
			}

			// Skip further validation if empty and not required
			if (value == null || value === '') continue;

			// Regex pattern validation
			if (field.validation && typeof value === 'string') {
				try {
					const re = new RegExp(field.validation);
					if (!re.test(value)) {
						newErrors[field.key] = `${field.label} format is invalid`;
					}
				} catch {
					// Invalid regex — skip
				}
			}
		}
		errors = newErrors;
		return Object.keys(newErrors).length === 0;
	}

	// -----------------------------------------------------------------------
	// Submission
	// -----------------------------------------------------------------------

	async function handleAction(action: string) {
		if (submitted || submitting) return;

		const isDecline = isDeclineAction(action);

		// Validate unless it's a decline action
		if (!isDecline && !validate()) return;

		submitting = true;

		const data: Record<string, string | number | boolean> = {};
		for (const field of allFields()) {
			data[field.key] = formValues[field.key];
		}

		try {
			// POST to save_endpoint if provided and not a decline action
			if (save_endpoint && !isDecline) {
				const resp = await fetch(save_endpoint, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ action, data })
				});
				if (!resp.ok) {
					throw new Error(`Save failed: ${resp.statusText}`);
				}
			}

			// Send chat message
			const conversationId = get(activeConversationId);
			if (conversationId) {
				const wid = widget_id ?? 'unknown';
				const payload = JSON.stringify(data);
				await sendMessage(conversationId, `__form_submit__:${wid}:${action}\n${payload}`);
			}

			submitted = true;
			submittedAction = action;
		} catch {
			errors = { _form: 'Submission failed. Please try again.' };
		} finally {
			submitting = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	/** Whether a field type should span the full width of the form grid. */
	function isFullWidth(type: FieldType): boolean {
		return type === 'textarea' || type === 'radio';
	}

	/** Map an HTML input type from our FieldType. */
	function inputType(type: FieldType): string {
		switch (type) {
			case 'email':
				return 'email';
			case 'phone':
				return 'tel';
			case 'url':
				return 'url';
			case 'password':
				return 'password';
			case 'number':
			case 'currency':
				return 'number';
			case 'date':
				return 'date';
			default:
				return 'text';
		}
	}

	/** Format a value for read-only display after submission. */
	function displayValue(field: FormField): string {
		const val = formValues[field.key];
		if (val == null || val === '') return '--';
		if (field.type === 'checkbox' || field.type === 'toggle') {
			return val ? 'Yes' : 'No';
		}
		if (field.type === 'currency' && field.currency_code) {
			return `${field.currency_code} ${val}`;
		}
		return String(val);
	}

	// -----------------------------------------------------------------------
	// Button styling
	// -----------------------------------------------------------------------

	const buttonStyles: Record<string, string> = {
		primary:
			'bg-accent text-white hover:bg-accent/90',
		danger:
			'bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20',
		ghost:
			'text-text-secondary hover:bg-surface-secondary',
		default:
			'bg-surface-secondary border border-border text-text-primary hover:bg-surface-hover'
	};

	function getButtonStyle(style?: string): string {
		return buttonStyles[style ?? 'default'] ?? buttonStyles['default'];
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm">
	<!-- Title bar -->
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<!-- Sections -->
	<div class="divide-y divide-border/50">
		{#each sections as section}
			<!-- Info Section -->
			{#if section.kind === 'info'}
				<div class="px-4 py-3">
					{#if section.title}
						<h4 class="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
							{section.title}
						</h4>
					{/if}

					<!-- Alert-style message -->
					{#if section.message}
						{@const sev = section.severity ?? 'info'}
						{@const SevIcon = severityIcons[sev]}
						<div
							class="rounded-lg border border-border border-l-4 {severityBorder[sev]} {severityBg[sev]} p-3"
						>
							<div class="flex items-start gap-2.5">
								{#if SevIcon}
									<span class="mt-0.5 shrink-0 {severityIconColor[sev]}">
										<SevIcon size={16} />
									</span>
								{/if}
								<p class="text-sm text-text-primary">{section.message}</p>
							</div>
						</div>
					{/if}

					<!-- Key-value items -->
					{#if section.items && section.items.length > 0}
						<dl class="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
							{#each section.items as item}
								<div class="flex items-baseline justify-between gap-2">
									<dt class="shrink-0 text-xs font-medium text-text-secondary">{item.label}</dt>
									<dd class="truncate text-sm text-text-primary">{item.value}</dd>
								</div>
							{/each}
						</dl>
					{/if}
				</div>

			<!-- Fields Section -->
			{:else if section.kind === 'fields'}
				<div class="px-4 py-3">
					{#if section.title}
						<h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">
							{section.title}
						</h4>
					{/if}

					<div class="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
						{#each section.fields as field}
							<div class={isFullWidth(field.type) ? 'sm:col-span-2' : ''}>
								<!-- Label -->
								{#if field.type !== 'checkbox' && field.type !== 'toggle'}
									<label
										for="form-{field.key}"
										class="mb-1 block text-xs font-medium text-text-secondary"
									>
										{field.label}
										{#if field.required}
											<span class="text-danger">*</span>
										{/if}
									</label>
								{/if}

								<!-- Submitted: read-only display -->
								{#if submitted}
									<p class="py-1.5 text-sm text-text-primary">{displayValue(field)}</p>

								<!-- Textarea -->
								{:else if field.type === 'textarea'}
									<textarea
										id="form-{field.key}"
										class="w-full rounded-md border px-3 py-1.5 text-sm text-text-primary outline-none transition-colors
											{errors[field.key]
												? 'border-danger/50 focus:border-danger focus:ring-1 focus:ring-danger/30'
												: 'border-border bg-surface focus:border-accent focus:ring-1 focus:ring-accent/30'}"
										rows={3}
										placeholder={field.placeholder ?? ''}
										bind:value={formValues[field.key]}
									></textarea>

								<!-- Select -->
								{:else if field.type === 'select'}
									<select
										id="form-{field.key}"
										class="w-full rounded-md border px-3 py-1.5 text-sm text-text-primary outline-none transition-colors
											{errors[field.key]
												? 'border-danger/50 focus:border-danger focus:ring-1 focus:ring-danger/30'
												: 'border-border bg-surface focus:border-accent focus:ring-1 focus:ring-accent/30'}"
										bind:value={formValues[field.key]}
									>
										<option value="">{field.placeholder ?? 'Select...'}</option>
										{#if field.options}
											{#each field.options as opt}
												<option value={opt}>{opt}</option>
											{/each}
										{/if}
									</select>

								<!-- Radio -->
								{:else if field.type === 'radio'}
									<div class="flex flex-wrap gap-3 py-1">
										{#if field.options}
											{#each field.options as opt}
												<label class="inline-flex items-center gap-1.5 text-sm text-text-primary cursor-pointer">
													<input
														type="radio"
														name="form-{field.key}"
														value={opt}
														checked={formValues[field.key] === opt}
														onchange={() => { formValues[field.key] = opt; }}
														class="accent-accent"
													/>
													{opt}
												</label>
											{/each}
										{/if}
									</div>

								<!-- Checkbox -->
								{:else if field.type === 'checkbox'}
									<label class="inline-flex items-center gap-2 cursor-pointer py-1">
										<input
											type="checkbox"
											id="form-{field.key}"
											checked={!!formValues[field.key]}
											onchange={() => { formValues[field.key] = !formValues[field.key]; }}
											class="accent-accent"
										/>
										<span class="text-sm text-text-primary">
											{field.label}
											{#if field.required}
												<span class="text-danger">*</span>
											{/if}
										</span>
									</label>

								<!-- Toggle -->
								{:else if field.type === 'toggle'}
									<label class="inline-flex items-center gap-2 cursor-pointer py-1">
										<button
											type="button"
											role="switch"
											aria-checked={!!formValues[field.key]}
											onclick={() => { formValues[field.key] = !formValues[field.key]; }}
											class="relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors
												{formValues[field.key] ? 'bg-accent' : 'bg-surface-secondary'}"
										>
											<span
												class="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform
													{formValues[field.key] ? 'translate-x-4' : 'translate-x-0'}"
											></span>
										</button>
										<span class="text-sm text-text-primary">
											{field.label}
											{#if field.required}
												<span class="text-danger">*</span>
											{/if}
										</span>
									</label>

								<!-- Currency (number with prefix) -->
								{:else if field.type === 'currency'}
									<div class="flex items-center gap-1">
										{#if field.currency_code}
											<span class="shrink-0 text-xs font-medium text-text-secondary">
												{field.currency_code}
											</span>
										{/if}
										<input
											id="form-{field.key}"
											type="number"
											step="0.01"
											class="w-full rounded-md border px-3 py-1.5 text-sm text-text-primary outline-none transition-colors
												{errors[field.key]
													? 'border-danger/50 focus:border-danger focus:ring-1 focus:ring-danger/30'
													: 'border-border bg-surface focus:border-accent focus:ring-1 focus:ring-accent/30'}"
											placeholder={field.placeholder ?? '0.00'}
											bind:value={formValues[field.key]}
										/>
									</div>

								<!-- Default input (text, number, email, phone, url, password, date) -->
								{:else}
									<input
										id="form-{field.key}"
										type={inputType(field.type)}
										class="w-full rounded-md border px-3 py-1.5 text-sm text-text-primary outline-none transition-colors
											{errors[field.key]
												? 'border-danger/50 focus:border-danger focus:ring-1 focus:ring-danger/30'
												: 'border-border bg-surface focus:border-accent focus:ring-1 focus:ring-accent/30'}"
										placeholder={field.placeholder ?? ''}
										bind:value={formValues[field.key]}
									/>
								{/if}

								<!-- Description -->
								{#if field.description && !submitted}
									<p class="mt-0.5 text-xs text-text-secondary">{field.description}</p>
								{/if}

								<!-- Field error -->
								{#if errors[field.key]}
									<p class="mt-0.5 text-xs text-danger">{errors[field.key]}</p>
								{/if}
							</div>
						{/each}
					</div>
				</div>

			<!-- Actions Section -->
			{:else if section.kind === 'actions'}
				<div class="px-4 py-3">
					{#if submitted}
						<!-- Submitted status badge -->
						<div class="flex items-center gap-2">
							{#if isDeclineAction(submittedAction)}
								<span class="inline-flex items-center gap-1.5 rounded-full border border-danger/30 bg-danger/10 px-3 py-1 text-xs font-medium text-danger">
									<X size={14} />
									{submittedAction.charAt(0).toUpperCase() + submittedAction.slice(1)}ed
								</span>
							{:else}
								<span class="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-3 py-1 text-xs font-medium text-success">
									<Check size={14} />
									{#each section.buttons.filter((b) => b.action === submittedAction) as btn}
										{btn.label}
									{:else}
										Submitted
									{/each}
								</span>
							{/if}
						</div>
					{:else}
						<!-- Form-level error -->
						{#if errors['_form']}
							<p class="mb-2 text-xs text-danger">{errors['_form']}</p>
						{/if}

						<!-- Buttons -->
						<div class="flex flex-wrap items-center gap-2">
							{#each section.buttons as btn}
								<button
									type="button"
									class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed {getButtonStyle(btn.style)}"
									disabled={submitting}
									onclick={() => handleAction(btn.action)}
								>
									{btn.label}
								</button>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		{/each}
	</div>
</div>
