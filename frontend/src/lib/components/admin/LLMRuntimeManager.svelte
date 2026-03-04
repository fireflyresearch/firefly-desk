<!--
  LLMRuntimeManager.svelte - LLM runtime tuning constants.

  Admin-configurable retry limits, timeouts, context truncation budgets,
  and max tokens. Dual-mode UI: enhanced settings page + guided wizard.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Save,
		Loader2,
		RotateCcw,
		CheckCircle,
		ChevronDown,
		ChevronRight,
		Timer,
		Scissors,
		FileText,
		Cpu,
		Search,
		Shield,
		Sliders,
		Zap,
		Wand2,
		ArrowLeft,
		ArrowRight,
		X,
		Info
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface LLMRuntimeSettings {
		llm_max_retries: number;
		llm_retry_base_delay: number;
		llm_retry_max_delay: number;
		llm_fallback_retries: number;
		llm_stream_timeout: number;
		llm_followup_timeout: number;
		followup_max_retries: number;
		followup_retry_base_delay: number;
		followup_retry_max_delay: number;
		followup_max_content_chars: number;
		followup_max_total_chars: number;
		file_context_max_per_file: number;
		file_context_max_total: number;
		multimodal_max_context_chars: number;
		default_max_tokens: number;
		knowledge_analyzer_max_chars: number;
		document_read_max_chars: number;
		context_entity_limit: number;
		context_retrieval_top_k: number;
	}

	interface FieldDef {
		key: keyof LLMRuntimeSettings;
		label: string;
		help: string;
		unit?: string;
		min?: number;
		max?: number;
		step?: number;
	}

	interface SectionDef {
		key: string;
		label: string;
		icon: typeof Timer;
		description: string;
		infoText: string;
		impact: 'high' | 'tuning';
		fields: FieldDef[];
	}

	interface PresetStyle {
		bg: string;
		border: string;
		icon: string;
		ring: string;
		badge: string;
	}

	interface PresetProfile {
		name: string;
		key: string;
		description: string;
		icon: typeof Shield;
		stats: string[];
		style: PresetStyle;
		values: LLMRuntimeSettings;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const DEFAULTS: LLMRuntimeSettings = {
		llm_max_retries: 3,
		llm_retry_base_delay: 3.0,
		llm_retry_max_delay: 15.0,
		llm_fallback_retries: 2,
		llm_stream_timeout: 300,
		llm_followup_timeout: 240,
		followup_max_retries: 3,
		followup_retry_base_delay: 15.0,
		followup_retry_max_delay: 60.0,
		followup_max_content_chars: 8000,
		followup_max_total_chars: 60000,
		file_context_max_per_file: 12000,
		file_context_max_total: 40000,
		multimodal_max_context_chars: 12000,
		default_max_tokens: 4096,
		knowledge_analyzer_max_chars: 8000,
		document_read_max_chars: 30000,
		context_entity_limit: 5,
		context_retrieval_top_k: 5
	};

	const PRESETS: PresetProfile[] = [
		{
			name: 'Conservative',
			key: 'conservative',
			description:
				'Maximizes reliability with more retries, longer timeouts, and smaller context windows. Best for rate-limited APIs.',
			icon: Shield,
			get stats() { return presetStats(this.values); },
			style: {
				bg: 'bg-success/5',
				border: 'border-success/20',
				icon: 'text-success',
				ring: 'ring-success/50',
				badge: 'bg-success/10 text-success'
			},
			values: {
				llm_max_retries: 4,
				llm_retry_base_delay: 5.0,
				llm_retry_max_delay: 25.0,
				llm_fallback_retries: 3,
				llm_stream_timeout: 420,
				llm_followup_timeout: 300,
				followup_max_retries: 4,
				followup_retry_base_delay: 20.0,
				followup_retry_max_delay: 90.0,
				followup_max_content_chars: 4000,
				followup_max_total_chars: 40000,
				file_context_max_per_file: 6000,
				file_context_max_total: 20000,
				multimodal_max_context_chars: 6000,
				default_max_tokens: 2048,
				knowledge_analyzer_max_chars: 6000,
				document_read_max_chars: 20000,
				context_entity_limit: 3,
				context_retrieval_top_k: 3
			}
		},
		{
			name: 'Balanced',
			key: 'balanced',
			description:
				'The default configuration. Good balance of reliability and performance for most deployments.',
			icon: Sliders,
			get stats() { return presetStats(this.values); },
			style: {
				bg: 'bg-accent/5',
				border: 'border-accent/20',
				icon: 'text-accent',
				ring: 'ring-accent/50',
				badge: 'bg-accent/10 text-accent'
			},
			values: { ...DEFAULTS }
		},
		{
			name: 'Performance',
			key: 'performance',
			description:
				'Faster responses and larger context windows. Best for high-throughput APIs with generous rate limits.',
			icon: Zap,
			get stats() { return presetStats(this.values); },
			style: {
				bg: 'bg-warning/5',
				border: 'border-warning/20',
				icon: 'text-warning',
				ring: 'ring-warning/50',
				badge: 'bg-warning/10 text-warning'
			},
			values: {
				llm_max_retries: 2,
				llm_retry_base_delay: 1.5,
				llm_retry_max_delay: 10.0,
				llm_fallback_retries: 1,
				llm_stream_timeout: 240,
				llm_followup_timeout: 180,
				followup_max_retries: 2,
				followup_retry_base_delay: 8.0,
				followup_retry_max_delay: 30.0,
				followup_max_content_chars: 16000,
				followup_max_total_chars: 100000,
				file_context_max_per_file: 20000,
				file_context_max_total: 80000,
				multimodal_max_context_chars: 20000,
				default_max_tokens: 8192,
				knowledge_analyzer_max_chars: 12000,
				document_read_max_chars: 60000,
				context_entity_limit: 8,
				context_retrieval_top_k: 8
			}
		}
	];

	// -----------------------------------------------------------------------
	// Section definitions with enhanced descriptions
	// -----------------------------------------------------------------------

	const sections: SectionDef[] = [
		{
			key: 'retry',
			label: 'Retry & Timeout',
			icon: Timer,
			description: 'Control how the agent retries failed LLM calls and how long it waits.',
			infoText:
				'When the LLM returns a transient error, the agent retries with exponential backoff. If the primary model is exhausted, it falls back to lighter models. Longer timeouts and more retries improve reliability but delay error reporting.',
			impact: 'high',
			fields: [
				{
					key: 'llm_max_retries',
					label: 'Max Retries',
					help: 'How many times to retry the primary LLM when it returns a transient error (rate limit, 529, 503). Higher values improve reliability but delay error reporting. Recommended: 2\u20135.',
					min: 1,
					max: 10,
					step: 1
				},
				{
					key: 'llm_retry_base_delay',
					label: 'Retry Base Delay',
					help: 'Initial delay between retries, which doubles each attempt (exponential backoff). Lower values retry faster; higher values give the provider more recovery time. Recommended: 2\u201310s.',
					unit: 'seconds',
					min: 0.5,
					max: 30,
					step: 0.5
				},
				{
					key: 'llm_retry_max_delay',
					label: 'Retry Max Delay',
					help: 'Maximum delay cap for exponential backoff. Prevents excessively long waits between retries. Recommended: 10\u201330s.',
					unit: 'seconds',
					min: 5,
					max: 120,
					step: 1
				},
				{
					key: 'llm_fallback_retries',
					label: 'Fallback Model Retries',
					help: 'When the primary model is exhausted, the agent tries lighter fallback models. This sets how many attempts per fallback model. Recommended: 1\u20133.',
					min: 0,
					max: 10,
					step: 1
				},
				{
					key: 'llm_stream_timeout',
					label: 'Stream Timeout',
					help: 'Maximum seconds to wait for a complete streaming response. Increase this if you see timeout errors with complex queries or slow providers. Recommended: 120\u2013600s.',
					unit: 'seconds',
					min: 30,
					max: 900,
					step: 30
				},
				{
					key: 'llm_followup_timeout',
					label: 'Follow-up Timeout',
					help: 'Maximum seconds for the follow-up LLM call after tool execution. This is typically faster than the initial call. Recommended: 120\u2013360s.',
					unit: 'seconds',
					min: 30,
					max: 600,
					step: 30
				},
				{
					key: 'followup_max_retries',
					label: 'Follow-up Max Retries',
					help: 'Retry attempts for the follow-up call after tools run. Follow-ups are more prone to rate limits because they happen in quick succession. Recommended: 2\u20135.',
					min: 1,
					max: 10,
					step: 1
				},
				{
					key: 'followup_retry_base_delay',
					label: 'Follow-up Retry Base Delay',
					help: 'Initial backoff delay for follow-up retries. Set higher than primary retries to allow rate-limit recovery. Recommended: 10\u201330s.',
					unit: 'seconds',
					min: 1,
					max: 60,
					step: 1
				},
				{
					key: 'followup_retry_max_delay',
					label: 'Follow-up Retry Max Delay',
					help: 'Maximum delay cap for follow-up retry backoff. Recommended: 30\u2013120s.',
					unit: 'seconds',
					min: 10,
					max: 300,
					step: 5
				}
			]
		},
		{
			key: 'truncation',
			label: 'Context Truncation',
			icon: Scissors,
			description: 'Limits applied to tool results before sending them to the LLM.',
			infoText:
				"Tool results and document content are truncated to fit within the LLM's context window. Smaller budgets prevent rate limits; larger ones give the LLM more information to work with.",
			impact: 'high',
			fields: [
				{
					key: 'followup_max_content_chars',
					label: 'Max Chars per Tool Result',
					help: "When a tool returns a large result (e.g., document text), it's truncated to this limit before being sent to the LLM. Too low \u2192 the LLM misses information. Too high \u2192 you hit token limits. Recommended: 4K\u201320K.",
					unit: 'chars',
					min: 1000,
					max: 50000,
					step: 1000
				},
				{
					key: 'followup_max_total_chars',
					label: 'Total Context Budget',
					help: 'Total character budget across all tool results and message history in a single turn. This is the main lever for controlling prompt size. Recommended: 40K\u2013120K.',
					unit: 'chars',
					min: 10000,
					max: 200000,
					step: 5000
				}
			]
		},
		{
			key: 'file',
			label: 'File Context',
			icon: FileText,
			description: 'Budgets for file content injected into the LLM prompt.',
			infoText:
				'Uploaded files are extracted to text and injected into the LLM prompt. These limits prevent oversized prompts from exhausting your token budget.',
			impact: 'tuning',
			fields: [
				{
					key: 'file_context_max_per_file',
					label: 'Max Chars per File',
					help: "Character limit for each uploaded file's extracted text. Larger files are truncated to fit. Recommended: 8K\u201320K.",
					unit: 'chars',
					min: 1000,
					max: 100000,
					step: 1000
				},
				{
					key: 'file_context_max_total',
					label: 'Total File Context Budget',
					help: 'Total character budget across all uploaded files in a single turn. Limits the combined file context injected into the prompt. Recommended: 30K\u201380K.',
					unit: 'chars',
					min: 5000,
					max: 200000,
					step: 5000
				},
				{
					key: 'multimodal_max_context_chars',
					label: 'Multimodal Text Limit',
					help: 'Character limit for text extracted from files in multimodal (image+text) content parts. Recommended: 8K\u201320K.',
					unit: 'chars',
					min: 1000,
					max: 100000,
					step: 1000
				},
				{
					key: 'knowledge_analyzer_max_chars',
					label: 'Analyzer Content Limit',
					help: 'Maximum characters sent to the LLM when analysing a document during knowledge import (classification, tagging, entity extraction). Recommended: 6K\u201312K.',
					unit: 'chars',
					min: 2000,
					max: 50000,
					step: 1000
				},
				{
					key: 'document_read_max_chars',
					label: 'Document Read Default Limit',
					help: 'Default max characters returned by the document_read tool when the LLM does not specify a limit. Higher values give more context but consume more tokens. Recommended: 20K\u201360K.',
					unit: 'chars',
					min: 5000,
					max: 200000,
					step: 5000
				}
			]
		},
		{
			key: 'output',
			label: 'LLM Output',
			icon: Cpu,
			description: 'Controls for the LLM response generation.',
			infoText:
				'Controls the maximum length of LLM-generated responses. Higher values allow longer answers but increase cost and latency.',
			impact: 'tuning',
			fields: [
				{
					key: 'default_max_tokens',
					label: 'Default Max Tokens',
					help: "Maximum number of tokens the LLM can generate in a single response. Higher values allow longer answers but increase cost and latency. The model's own capability limit takes precedence when known. Recommended: 2048\u20138192.",
					unit: 'tokens',
					min: 256,
					max: 32768,
					step: 256
				}
			]
		},
		{
			key: 'enricher',
			label: 'Context Enricher',
			icon: Search,
			description: 'Tuning for the knowledge graph and RAG retrieval that runs before each LLM call.',
			infoText:
				'Before each LLM call, the system retrieves relevant knowledge snippets. More results mean better-informed answers but more tokens consumed.',
			impact: 'tuning',
			fields: [
				{
					key: 'context_entity_limit',
					label: 'Entity Limit',
					help: 'Maximum knowledge graph entities to include in context. Entities are structured facts extracted from your knowledge base. Recommended: 3\u20138.',
					min: 1,
					max: 20,
					step: 1
				},
				{
					key: 'context_retrieval_top_k',
					label: 'Retrieval Top-K',
					help: "How many knowledge base snippets to retrieve and inject into the LLM's context for each user message. More snippets = better-informed answers but more tokens consumed. Recommended: 2\u20135.",
					min: 1,
					max: 20,
					step: 1
				}
			]
		}
	];

	// -----------------------------------------------------------------------
	// Helpers & derived constants
	// -----------------------------------------------------------------------

	const CUSTOM_PROFILE = 'Custom';
	const DEFAULT_PRESET_KEY = 'balanced';

	const fieldLabelMap = new Map<string, string>();
	for (const s of sections) for (const f of s.fields) fieldLabelMap.set(f.key, f.label);

	/** Lookup sections by key instead of fragile array index. */
	const sectionByKey = new Map(sections.map((s) => [s.key, s]));

	const WIZARD_STEPS = ['Choose Profile', 'Resilience', 'Context', 'Review'];
	const LAST_WIZARD_STEP = WIZARD_STEPS.length - 1;

	/** Maps each wizard field-step index to the section keys it covers. */
	const WIZARD_FIELD_SECTIONS: string[][] = [
		[], // Step 0: Choose Profile (no fields)
		['retry'], // Step 1: Resilience
		['truncation', 'file', 'output', 'enricher'], // Step 2: Context
		[] // Step 3: Review (no fields)
	];

	function detectProfile(values: LLMRuntimeSettings): string {
		for (const preset of PRESETS) {
			const allMatch = (Object.keys(DEFAULTS) as Array<keyof LLMRuntimeSettings>).every(
				(k) => values[k] === preset.values[k]
			);
			if (allMatch) return preset.name;
		}
		return CUSTOM_PROFILE;
	}

	function formatNumber(value: number): string {
		return value.toLocaleString();
	}

	/** Derive human-readable stats from preset values so they stay in sync. */
	function presetStats(v: LLMRuntimeSettings): string[] {
		return [
			`${v.llm_max_retries} retries`,
			`${Math.round(v.llm_stream_timeout / 60)}min timeout`,
			`${Math.round(v.followup_max_content_chars / 1000)}K context`
		];
	}

	function defaultPresetName(): string {
		const dp = PRESETS.find((p) => p.key === DEFAULT_PRESET_KEY);
		return dp ? dp.name : 'Balanced';
	}

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let form = $state<LLMRuntimeSettings>({ ...DEFAULTS });
	let savedForm = $state<LLMRuntimeSettings>({ ...DEFAULTS });
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');
	let collapsedSections = $state<Set<string>>(new Set());
	let lastSavedTime = $state('');

	// Wizard state
	let showWizard = $state(false);
	let wizardStep = $state(0);
	let wizardForm = $state<LLMRuntimeSettings>({ ...DEFAULTS });
	let wizardPreset = $state('');

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let dirty = $derived(JSON.stringify(form) !== JSON.stringify(savedForm));
	let activeProfile = $derived(detectProfile(form));
	let activePreset = $derived(PRESETS.find((p) => p.name === activeProfile) || null);
	let modifiedCount = $derived(
		(Object.keys(DEFAULTS) as Array<keyof LLMRuntimeSettings>).filter(
			(k) => form[k] !== DEFAULTS[k]
		).length
	);
	let wizardDetectedProfile = $derived(detectProfile(wizardForm));
	let wizardChanges = $derived(
		(Object.keys(DEFAULTS) as Array<keyof LLMRuntimeSettings>)
			.filter((k) => wizardForm[k] !== DEFAULTS[k])
			.map((k) => ({
				key: k,
				label: fieldLabelMap.get(k) || k,
				defaultValue: DEFAULTS[k],
				newValue: wizardForm[k]
			}))
	);

	// -----------------------------------------------------------------------
	// Data loading & actions
	// -----------------------------------------------------------------------

	async function loadSettings() {
		loading = true;
		error = '';
		try {
			const data = await apiJson<LLMRuntimeSettings>('/settings/llm-runtime');
			form = { ...DEFAULTS, ...data };
			savedForm = { ...form };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load LLM runtime settings';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadSettings();
	});

	async function saveSettings() {
		saving = true;
		error = '';
		successMsg = '';
		try {
			const data = await apiJson<LLMRuntimeSettings>('/settings/llm-runtime', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(form)
			});
			form = { ...DEFAULTS, ...data };
			savedForm = { ...form };
			successMsg = 'Settings saved successfully';
			lastSavedTime = new Date().toLocaleTimeString();
			setTimeout(() => (successMsg = ''), 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save settings';
		} finally {
			saving = false;
		}
	}

	function resetToDefaults() {
		form = { ...DEFAULTS };
	}

	function toggleSection(key: string) {
		const next = new Set(collapsedSections);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		collapsedSections = next;
	}

	function applyPreset(preset: PresetProfile) {
		form = { ...preset.values };
	}

	// -----------------------------------------------------------------------
	// Wizard
	// -----------------------------------------------------------------------

	function openWizard() {
		wizardForm = { ...form };
		wizardPreset = '';
		wizardStep = 0;
		showWizard = true;
	}

	function closeWizard() {
		showWizard = false;
	}

	async function applyWizard() {
		form = { ...wizardForm };
		showWizard = false;
		await saveSettings();
	}

	function loadPresetInWizard(presetKey: string) {
		const preset = PRESETS.find((p) => p.key === presetKey);
		if (preset) {
			wizardForm = { ...preset.values };
			wizardPreset = presetKey;
		}
	}
</script>

<!-- ===================================================================== -->
<!-- Wizard Modal                                                          -->
<!-- ===================================================================== -->

{#if showWizard}
	<div
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		aria-label="LLM Runtime Configuration Wizard"
		class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm"
		onkeydown={(e) => {
			if (e.key === 'Escape') closeWizard();
		}}
	>
		<div
			class="my-8 w-full max-w-3xl rounded-xl border border-border bg-surface-elevated shadow-xl"
		>
			<!-- Wizard header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="text-base font-semibold text-text-primary">Configure LLM Runtime</h2>
				<button
					type="button"
					onclick={closeWizard}
					class="rounded-md p-1 text-text-secondary/60 transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Step indicator -->
			<div class="flex items-center justify-center gap-2 border-b border-border/50 px-6 py-3">
				{#each WIZARD_STEPS as stepLabel, i}
					{#if i > 0}
						<div class="h-px w-6 {i <= wizardStep ? 'bg-accent' : 'bg-border'}"></div>
					{/if}
					<button
						type="button"
						onclick={() => {
							if (i <= wizardStep) wizardStep = i;
						}}
						disabled={i > wizardStep}
						class="flex items-center gap-1.5 text-xs {i <= wizardStep
							? 'cursor-pointer'
							: 'cursor-default'} {i === wizardStep
							? 'font-semibold text-accent'
							: i < wizardStep
								? 'text-text-secondary'
								: 'text-text-secondary/40'}"
					>
						<span
							class="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold {i ===
							wizardStep
								? 'bg-accent text-white'
								: i < wizardStep
									? 'bg-accent/10 text-accent'
									: 'bg-surface-hover text-text-secondary/40'}"
						>
							{i + 1}
						</span>
						<span class="hidden sm:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Step content -->
			<div class="p-6">
				<!-- Step 1: Choose Profile -->
				{#if wizardStep === 0}
					<div class="mb-4">
						<h3 class="text-sm font-semibold text-text-primary">Choose a Profile</h3>
						<p class="mt-1 text-xs text-text-secondary">
							Select a preset that matches your deployment. You can fine-tune individual
							values in the next steps.
						</p>
					</div>
					<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
						{#each PRESETS as preset}
							{@const isSelected = wizardPreset === preset.key}
							<button
								type="button"
								onclick={() => loadPresetInWizard(preset.key)}
								class="rounded-xl border-2 p-5 text-left transition-all hover:shadow-md {isSelected
									? `${preset.style.border} ${preset.style.bg} ring-2 ${preset.style.ring}`
									: 'border-border bg-surface hover:border-border/80'}"
							>
								<div
									class="mb-3 flex h-10 w-10 items-center justify-center rounded-lg {preset
										.style.bg}"
								>
									<preset.icon size={20} class={preset.style.icon} />
								</div>
								<h4 class="text-sm font-semibold text-text-primary">{preset.name}</h4>
								<p class="mt-1 text-xs text-text-secondary">{preset.description}</p>
								<div class="mt-3 flex flex-wrap gap-1.5">
									{#each preset.stats as stat}
										<span
											class="rounded-full bg-surface-secondary px-2 py-0.5 text-[10px] font-medium text-text-secondary"
										>
											{stat}
										</span>
									{/each}
								</div>
							</button>
						{/each}
					</div>
					<div class="mt-4 text-center">
						<button
							type="button"
							onclick={() => {
								wizardPreset = '';
								wizardStep = 1;
							}}
							class="text-xs text-text-secondary/60 underline hover:text-text-secondary"
						>
							Start from scratch
						</button>
					</div>

					<!-- Step 2: Resilience & Timeouts -->
				{:else if wizardStep === 1}
					<div class="mb-4">
						<h3 class="text-sm font-semibold text-text-primary">Resilience & Timeouts</h3>
						<p class="mt-1 text-xs text-text-secondary">
							Configure retry behavior and timeout limits for LLM calls.
						</p>
					</div>
					<!-- Info card -->
					<div
						class="mb-5 flex items-start gap-3 rounded-lg border border-accent/15 bg-accent/5 p-3"
					>
						<Info size={16} class="mt-0.5 shrink-0 text-accent" />
						<p class="text-xs leading-relaxed text-text-secondary">
							When the LLM provider returns an error (rate limit, overload), the agent
							retries with exponential backoff. If the primary model is exhausted, it falls
							back to lighter models.
						</p>
					</div>
					<!-- Flow diagram -->
					<div
						class="mb-5 flex flex-wrap items-center justify-center gap-2 rounded-lg bg-surface-secondary/50 px-4 py-3 text-[11px]"
					>
						<span
							class="rounded-md border border-border bg-surface px-2.5 py-1 font-medium text-text-primary"
							>User Query</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-accent/30 bg-accent/5 px-2.5 py-1 font-medium text-accent"
							>Primary Model</span
						>
						<span class="text-text-secondary/40">&circlearrowright;</span>
						<span
							class="rounded-md border border-warning/30 bg-warning/5 px-2.5 py-1 font-medium text-warning"
							>Retry Loop</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-border bg-surface px-2.5 py-1 font-medium text-text-primary"
							>Fallback Models</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-success/30 bg-success/5 px-2.5 py-1 font-medium text-success"
							>Response</span
						>
					</div>
					<!-- Fields -->
					<div class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
						{#each sectionByKey.get('retry')?.fields ?? [] as field}
							<label class="flex flex-col gap-1.5">
								<div class="flex items-baseline justify-between">
									<span class="text-xs font-medium text-text-secondary"
										>{field.label}</span
									>
									{#if wizardForm[field.key] !== DEFAULTS[field.key]}
										<span
											class="rounded-full bg-accent/10 px-1.5 py-px text-[10px] font-medium text-accent"
											>modified</span
										>
									{/if}
								</div>
								<div class="flex items-center gap-2">
									<input
										type="number"
										bind:value={wizardForm[field.key]}
										min={field.min}
										max={field.max}
										step={field.step}
										class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm tabular-nums text-text-primary outline-none transition-colors focus:border-accent"
									/>
									{#if field.unit}
										<span class="shrink-0 text-xs text-text-secondary/60"
											>{field.unit}</span
										>
									{/if}
								</div>
								<span class="text-[11px] leading-tight text-text-secondary/60">
									{field.help}
								</span>
							</label>
						{/each}
					</div>

					<!-- Step 3: Context & Token Budgets -->
				{:else if wizardStep === 2}
					<div class="mb-4">
						<h3 class="text-sm font-semibold text-text-primary">
							Context & Token Budgets
						</h3>
						<p class="mt-1 text-xs text-text-secondary">
							Control how much content is sent to the LLM in each request.
						</p>
					</div>
					<!-- Info card -->
					<div
						class="mb-5 flex items-start gap-3 rounded-lg border border-accent/15 bg-accent/5 p-3"
					>
						<Info size={16} class="mt-0.5 shrink-0 text-accent" />
						<p class="text-xs leading-relaxed text-text-secondary">
							Before each LLM call, the agent assembles context from tool results, uploaded
							files, and knowledge retrieval. These budgets prevent oversized prompts that
							trigger rate limits or degrade quality.
						</p>
					</div>
					<!-- Flow diagram -->
					<div
						class="mb-5 flex flex-wrap items-center justify-center gap-2 rounded-lg bg-surface-secondary/50 px-4 py-3 text-[11px]"
					>
						<span
							class="rounded-md border border-border bg-surface px-2.5 py-1 font-medium text-text-primary"
							>Files & Tools</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-warning/30 bg-warning/5 px-2.5 py-1 font-medium text-warning"
							>Truncation</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-accent/30 bg-accent/5 px-2.5 py-1 font-medium text-accent"
							>LLM Prompt</span
						>
						<span class="text-text-secondary/40">&rarr;</span>
						<span
							class="rounded-md border border-success/30 bg-success/5 px-2.5 py-1 font-medium text-success"
							>Response</span
						>
					</div>
					<!-- Sub-sections -->
					{#each WIZARD_FIELD_SECTIONS[2].map((k) => sectionByKey.get(k)).filter((s): s is SectionDef => !!s) as section}
						<div class="mb-5 last:mb-0">
							<h4
								class="mb-2 flex items-center gap-2 text-xs font-semibold text-text-primary"
							>
								<section.icon size={14} class="text-accent" />
								{section.label}
							</h4>
							<div class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
								{#each section.fields as field}
									<label class="flex flex-col gap-1.5">
										<div class="flex items-baseline justify-between">
											<span class="text-xs font-medium text-text-secondary"
												>{field.label}</span
											>
											{#if wizardForm[field.key] !== DEFAULTS[field.key]}
												<span
													class="rounded-full bg-accent/10 px-1.5 py-px text-[10px] font-medium text-accent"
													>modified</span
												>
											{/if}
										</div>
										<div class="flex items-center gap-2">
											<input
												type="number"
												bind:value={wizardForm[field.key]}
												min={field.min}
												max={field.max}
												step={field.step}
												class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm tabular-nums text-text-primary outline-none transition-colors focus:border-accent"
											/>
											{#if field.unit}
												<span class="shrink-0 text-xs text-text-secondary/60"
													>{field.unit}</span
												>
											{/if}
										</div>
										<span class="text-[11px] leading-tight text-text-secondary/60">
											{field.help}
										</span>
									</label>
								{/each}
							</div>
						</div>
					{/each}

					<!-- Step 4: Review & Apply -->
				{:else if wizardStep === LAST_WIZARD_STEP}
					<div class="mb-4">
						<h3 class="text-sm font-semibold text-text-primary">Review & Apply</h3>
						<p class="mt-1 text-xs text-text-secondary">
							Review your configuration before applying it.
						</p>
					</div>
					<!-- Profile badge -->
					{#each [PRESETS.find((p) => p.name === wizardDetectedProfile)] as wp}
						<div class="mb-4 flex items-center gap-2">
							<span class="text-xs text-text-secondary">Detected profile:</span>
							<span
								class="rounded-full px-2.5 py-0.5 text-xs font-medium {wp
									? wp.style.badge
									: 'bg-surface-secondary text-text-secondary'}"
							>
								{wizardDetectedProfile}
							</span>
						</div>
					{/each}
					<!-- Changes table -->
					{#if wizardChanges.length === 0}
						<div
							class="rounded-lg border border-border bg-surface-secondary/30 px-4 py-8 text-center text-sm text-text-secondary"
						>
							All values match defaults &mdash; no changes from the {defaultPresetName()} profile.
						</div>
					{:else}
						<div class="overflow-hidden rounded-lg border border-border">
							<table class="w-full text-left text-[13px]">
								<thead>
									<tr class="border-b border-border bg-surface-secondary/40">
										<th
											class="px-4 py-2 text-[11px] font-medium text-text-secondary"
											>Setting</th
										>
										<th
											class="px-4 py-2 text-[11px] font-medium text-text-secondary"
											>Default</th
										>
										<th
											class="px-4 py-2 text-[11px] font-medium text-text-secondary"
											>New Value</th
										>
									</tr>
								</thead>
								<tbody>
									{#each wizardChanges as change}
										<tr class="border-b border-border/50 last:border-b-0">
											<td class="px-4 py-2 font-medium text-text-primary"
												>{change.label}</td
											>
											<td
												class="px-4 py-2 tabular-nums text-text-secondary/60"
												>{formatNumber(change.defaultValue)}</td
											>
											<td class="px-4 py-2 tabular-nums font-medium text-accent"
												>{formatNumber(change.newValue)}</td
											>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
						<p class="mt-2 text-[11px] text-text-secondary/50">
							{wizardChanges.length} field{wizardChanges.length > 1 ? 's' : ''} differ from
							defaults
						</p>
					{/if}
				{/if}
			</div>

			<!-- Wizard footer nav -->
			<div class="flex items-center justify-between border-t border-border px-6 py-4">
				<div>
					{#if wizardStep > 0}
						<button
							type="button"
							onclick={() => (wizardStep -= 1)}
							class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							<ArrowLeft size={14} />
							Back
						</button>
					{/if}
				</div>
				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={closeWizard}
						class="rounded-md px-3 py-1.5 text-sm text-text-secondary/60 transition-colors hover:text-text-secondary"
					>
						Cancel
					</button>
					{#if wizardStep < LAST_WIZARD_STEP}
						<button
							type="button"
							onclick={() => (wizardStep += 1)}
							disabled={wizardStep === 0 && !wizardPreset}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ArrowRight size={14} />
						</button>
					{:else}
						<button
							type="button"
							onclick={applyWizard}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
						>
							<Save size={14} />
							Apply Settings
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- ===================================================================== -->
<!-- Main Settings Page                                                    -->
<!-- ===================================================================== -->

<div class="flex h-full flex-col gap-4 overflow-y-auto p-6">
	<!-- Hero Header -->
	<div class="rounded-xl border border-border bg-surface p-5">
		<div class="flex flex-wrap items-center justify-between gap-4">
			<div class="flex items-center gap-4">
				<div
					class="flex h-12 w-12 items-center justify-center rounded-xl {activePreset
						? activePreset.style.bg
						: 'bg-surface-secondary'}"
				>
					{#if activePreset}
						<activePreset.icon size={24} class={activePreset.style.icon} />
					{:else}
						<Sliders size={24} class="text-text-secondary" />
					{/if}
				</div>
				<div>
					<div class="flex items-center gap-2">
						<h1 class="text-lg font-semibold text-text-primary">LLM Runtime</h1>
						<span
							class="rounded-full px-2 py-0.5 text-[11px] font-medium {activePreset
								? activePreset.style.badge
								: 'bg-surface-secondary text-text-secondary'}"
						>
							{activeProfile}
						</span>
					</div>
					<p class="text-sm text-text-secondary">
						{#if modifiedCount > 0}
							{modifiedCount} field{modifiedCount > 1 ? 's' : ''} modified from defaults
						{:else}
							All values at defaults
						{/if}
						{#if lastSavedTime}
							&middot; Last saved {lastSavedTime}
						{/if}
					</p>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={openWizard}
					disabled={loading}
					class="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/5 px-3 py-1.5 text-sm font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
				>
					<Wand2 size={14} />
					Configure Wizard
				</button>
				<button
					type="button"
					onclick={resetToDefaults}
					disabled={saving}
					class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
				>
					<RotateCcw size={14} />
					Reset to Defaults
				</button>
				<button
					type="button"
					onclick={saveSettings}
					disabled={saving || !dirty}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
						Saving...
					{:else}
						<Save size={14} />
						Save Changes
					{/if}
				</button>
			</div>
		</div>
	</div>

	<!-- Messages -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}
	{#if successMsg}
		<div
			class="flex items-center gap-2 rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success"
		>
			<CheckCircle size={16} />
			{successMsg}
		</div>
	{/if}

	<!-- Loading -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<!-- Quick-apply preset bar -->
		<div class="flex items-center gap-2">
			<span class="text-xs font-medium text-text-secondary">Quick apply:</span>
			{#each PRESETS as preset}
				<button
					type="button"
					onclick={() => applyPreset(preset)}
					class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors {activeProfile ===
					preset.name
						? preset.style.badge
						: 'bg-surface-secondary text-text-secondary hover:bg-surface-hover'}"
				>
					<preset.icon size={12} />
					{preset.name}
				</button>
			{/each}
		</div>

		<!-- Settings sections -->
		<div class="flex flex-col gap-3">
			{#each sections as section}
				{@const collapsed = collapsedSections.has(section.key)}
				<div class="rounded-lg border border-border bg-surface">
					<!-- Section header -->
					<button
						type="button"
						onclick={() => toggleSection(section.key)}
						class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-hover/50"
					>
						<span class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
							<section.icon size={16} class="text-accent" />
						</span>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<h3 class="text-sm font-semibold text-text-primary">
									{section.label}
								</h3>
								<span
									class="rounded-full px-1.5 py-px text-[10px] font-medium {section.impact ===
									'high'
										? 'bg-warning/10 text-warning'
										: 'bg-surface-secondary text-text-secondary/60'}"
								>
									{section.impact === 'high' ? 'High Impact' : 'Tuning'}
								</span>
							</div>
							<p class="text-xs text-text-secondary">{section.description}</p>
						</div>
						<span class="text-text-secondary/50">
							{#if collapsed}
								<ChevronRight size={16} />
							{:else}
								<ChevronDown size={16} />
							{/if}
						</span>
					</button>

					<!-- Section fields -->
					{#if !collapsed}
						<div class="border-t border-border px-4 pb-4 pt-3">
							<!-- Why this matters info card -->
							<div
								class="mb-4 flex items-start gap-2.5 rounded-lg border border-accent/10 bg-accent/[0.03] px-3 py-2.5"
							>
								<Info size={14} class="mt-0.5 shrink-0 text-accent/60" />
								<p class="text-[11px] leading-relaxed text-text-secondary">
									{section.infoText}
								</p>
							</div>
							<div
								class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3"
							>
								{#each section.fields as field}
									<label class="flex flex-col gap-1.5">
										<div class="flex items-baseline justify-between">
											<span class="text-xs font-medium text-text-secondary"
												>{field.label}</span
											>
											{#if form[field.key] !== DEFAULTS[field.key]}
												<span
													class="rounded-full bg-accent/10 px-1.5 py-px text-[10px] font-medium text-accent"
												>
													modified
												</span>
											{/if}
										</div>
										<div class="flex items-center gap-2">
											<input
												type="number"
												bind:value={form[field.key]}
												min={field.min}
												max={field.max}
												step={field.step}
												class="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm tabular-nums text-text-primary outline-none transition-colors focus:border-accent"
											/>
											{#if field.unit}
												<span class="shrink-0 text-xs text-text-secondary/60"
													>{field.unit}</span
												>
											{/if}
										</div>
										<span class="text-[11px] leading-tight text-text-secondary/60">
											{field.help}
											{#if form[field.key] !== DEFAULTS[field.key]}
												<span class="text-text-secondary/40">
													(default: {formatNumber(DEFAULTS[field.key])})
												</span>
											{/if}
										</span>
									</label>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Sticky save bar when dirty -->
		{#if dirty}
			<div
				class="sticky bottom-0 -mx-6 -mb-6 flex items-center justify-between border-t border-border bg-surface-secondary/95 px-6 py-3 backdrop-blur-sm"
			>
				<p class="text-xs text-text-secondary">You have unsaved changes</p>
				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={() => {
							form = { ...savedForm };
						}}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Discard
					</button>
					<button
						type="button"
						onclick={saveSettings}
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						Save Changes
					</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
