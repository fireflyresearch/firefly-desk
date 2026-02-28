<!--
  ProcessExplorer.svelte - Process discovery management and visualization.

  Toolbar + sidebar layout: a top toolbar with search, status filters,
  auto-analyze toggle, discovery settings dropdown, and re-discover action;
  a slim sidebar listing discovered processes with pagination; and a main
  content area with a SvelteFlow canvas + step edit panel. Allows admins to
  browse discovered business processes, visualize step graphs, edit steps,
  verify processes, trigger re-discovery jobs, and toggle auto-analysis.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Search,
		Loader2,
		X,
		Save,
		CheckCircle2,
		RefreshCw,
		GitBranch,
		Cog,
		Monitor,
		FileText,
		Tag,
		ChevronRight,
		AlertCircle,
		ToggleLeft,
		ToggleRight,
		Sparkles,
		Clock,
		ArrowRight,
		Filter,
		Brain,
		Database,
		Merge,
		CircleCheck,
		CircleX,
		Settings,
		Trash2,
		Archive,
		Pencil,
		Plus,
		ChevronUp,
		ChevronDown,
		Zap,
		Split,
		Timer,
		Bell,
		ShieldCheck,
		Shuffle,
		Link2,
		Server,
		ArrowDownRight,
		LogIn,
		LogOut,
		GripVertical
	} from 'lucide-svelte';
	import { apiJson, apiFetch } from '$lib/services/api.js';
	import RichEditor from '$lib/components/shared/RichEditor.svelte';
	import { parseSSEStream } from '$lib/services/sse.js';
	import FlowCanvas from '$lib/components/flow/FlowCanvas.svelte';
	import {
		toProcessFlowNodes,
		toProcessFlowEdges,
		layoutDagre
	} from '$lib/components/flow/flow-utils.js';
	import type {
		FlowNode as FlowNodeType,
		FlowEdge as FlowEdgeType,
		ProcessStep,
		ProcessDependency
	} from '$lib/components/flow/flow-types.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface BusinessProcess {
		id: string;
		name: string;
		description: string;
		category: string;
		steps: ProcessStep[];
		dependencies: ProcessDependency[];
		source: string;
		confidence: number;
		status: string;
		tags: string[];
		created_at: string;
		updated_at: string;
	}

	interface AnalysisSettings {
		auto_analyze: boolean;
	}

	interface ProcessDiscoverySettings {
		workspace_ids: string[];
		document_types: string[];
		focus_hint: string;
	}

	interface WorkspaceInfo {
		id: string;
		name: string;
	}

	interface DiscoverResponse {
		job_id: string;
		status: string;
		progress_pct: number;
	}

	type ProcessStatus = 'discovered' | 'verified' | 'modified' | 'archived';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let processes = $state<BusinessProcess[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Sidebar filters
	let searchQuery = $state('');
	let statusFilter = $state<ProcessStatus | 'all'>('all');

	// Pagination
	let currentPage = $state(1);
	let pageSize = $state(20);

	// Selected process
	let selectedProcess = $state<BusinessProcess | null>(null);
	let loadingDetail = $state(false);

	// Flow graph
	let flowNodes = $state<FlowNodeType[]>([]);
	let flowEdges = $state<FlowEdgeType[]>([]);

	// Step edit panel
	let editingStep = $state<ProcessStep | null>(null);
	let stepForm = $state({
		name: '',
		description: '',
		step_type: '',
		system_id: '',
		inputs: [] as string[],
		outputs: [] as string[],
		newInput: '',
		newOutput: ''
	});
	let savingStep = $state(false);

	// Verify / re-discover
	let verifying = $state(false);

	// Process actions (delete, archive, edit metadata)
	let confirmingDelete = $state(false);
	let deletingProcess = $state(false);
	let archivingProcess = $state(false);
	let editingMetadata = $state(false);
	let metadataForm = $state({
		name: '',
		description: '',
		category: '',
		tags: [] as string[],
		newTag: ''
	});
	let savingMetadata = $state(false);

	// Step creation
	let creatingStep = $state(false);

	// Discovery job
	let discoveryJobId = $state<string | null>(null);
	let discoveryJobStatus = $state<string | null>(null);
	let discoveryJobProgress = $state(0);
	let discoveryProgressMessage = $state('');

	// Discovery conversation log
	interface DiscoveryLogEntry {
		message: string;
		pct: number;
		timestamp: Date;
		type: 'scan' | 'context' | 'llm' | 'result' | 'merge' | 'done' | 'error' | 'info';
	}
	let discoveryLog = $state<DiscoveryLogEntry[]>([]);
	let discoveryLogEl: HTMLDivElement | null = $state(null);

	// Auto-analyze toggle
	let autoAnalyze = $state(false);
	let loadingAutoAnalyze = $state(true);
	let togglingAutoAnalyze = $state(false);

	// Discovery settings panel (dropdown in toolbar)
	let showDiscoverySettings = $state(false);
	let discoverySettingsRef: HTMLDivElement | null = $state(null);
	let workspaces = $state<WorkspaceInfo[]>([]);
	let discoverySettings = $state<ProcessDiscoverySettings>({
		workspace_ids: [],
		document_types: [],
		focus_hint: ''
	});
	let savingDiscoverySettings = $state(false);
	let loadingDiscoverySettings = $state(true);

	const DOCUMENT_TYPES = [
		{ value: 'manual', label: 'Manual' },
		{ value: 'tutorial', label: 'Tutorial' },
		{ value: 'api_spec', label: 'API Spec' },
		{ value: 'faq', label: 'FAQ' },
		{ value: 'policy', label: 'Policy' },
		{ value: 'reference', label: 'Reference' }
	];

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let filteredProcesses = $derived.by(() => {
		let result = processes;

		if (statusFilter !== 'all') {
			result = result.filter((p) => p.status === statusFilter);
		}

		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(
				(p) =>
					p.name.toLowerCase().includes(q) ||
					p.description.toLowerCase().includes(q) ||
					p.category.toLowerCase().includes(q) ||
					p.tags.some((t) => t.toLowerCase().includes(q))
			);
		}

		return result;
	});

	let totalPages = $derived(Math.ceil(filteredProcesses.length / pageSize));
	let paginatedProcesses = $derived(
		filteredProcesses.slice((currentPage - 1) * pageSize, currentPage * pageSize)
	);

	let isDiscovering = $derived(
		discoveryJobStatus === 'pending' || discoveryJobStatus === 'running'
	);

	let editingStepIcon = $derived(editingStep ? stepTypeIcon(editingStep.step_type) : Cog);

	let processStats = $derived.by(() => {
		if (!selectedProcess) return null;
		const stepsByType: Record<string, number> = {};
		for (const s of selectedProcess.steps) {
			const t = s.step_type || 'general';
			stepsByType[t] = (stepsByType[t] || 0) + 1;
		}
		const systemIds = new Set(
			selectedProcess.steps.map((s) => s.system_id).filter(Boolean)
		);
		const conditionalDeps = selectedProcess.dependencies.filter(
			(d) => d.condition
		).length;
		return { stepsByType, linkedSystemCount: systemIds.size, conditionalDeps };
	});

	let incomingDeps = $derived.by(() => {
		if (!selectedProcess || !editingStep || !editingStep.id) return [];
		return selectedProcess.dependencies.filter((d) => d.target_step_id === editingStep!.id);
	});

	let availableDepSources = $derived.by(() => {
		if (!selectedProcess || !editingStep || !editingStep.id) return [];
		const existingSources = new Set(incomingDeps.map((d) => d.source_step_id));
		return selectedProcess.steps.filter(
			(s) => s.id !== editingStep!.id && !existingSources.has(s.id)
		);
	});

	// -----------------------------------------------------------------------
	// Build flow graph when selected process changes
	// -----------------------------------------------------------------------

	$effect(() => {
		if (!selectedProcess || selectedProcess.steps.length === 0) {
			flowNodes = [];
			flowEdges = [];
			return;
		}

		const rawNodes = toProcessFlowNodes(selectedProcess.steps, selectedProcess.dependencies);
		const rawEdges = toProcessFlowEdges(selectedProcess.dependencies, selectedProcess.steps);

		flowNodes = layoutDagre(rawNodes, rawEdges, {
			nodeWidth: 200,
			nodeHeight: 60,
			horizontalGap: 60,
			verticalGap: 80,
			direction: 'TB'
		});

		flowEdges = rawEdges.map((edge) => ({
			...edge,
			markerEnd: 'arrowclosed'
		}));
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadProcesses(preserveError = false) {
		loading = true;
		if (!preserveError) error = '';
		try {
			processes = await apiJson<BusinessProcess[]>('/processes');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load processes';
		} finally {
			loading = false;
		}
	}

	async function loadProcessDetail(id: string, preserveError = false) {
		loadingDetail = true;
		if (!preserveError) error = '';
		editingStep = null;
		try {
			selectedProcess = await apiJson<BusinessProcess>(`/processes/${id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load process detail';
		} finally {
			loadingDetail = false;
		}
	}

	async function loadAnalysisSettings() {
		loadingAutoAnalyze = true;
		try {
			const settings = await apiJson<AnalysisSettings>('/settings/analysis');
			autoAnalyze = settings.auto_analyze;
		} catch {
			// Non-critical -- toggle simply remains off
		} finally {
			loadingAutoAnalyze = false;
		}
	}

	async function loadWorkspaces() {
		try {
			const result = await apiJson<WorkspaceInfo[]>('/workspaces');
			workspaces = result.map((w) => ({ id: w.id, name: w.name }));
		} catch {
			// Non-critical
		}
	}

	async function loadDiscoverySettings() {
		loadingDiscoverySettings = true;
		try {
			discoverySettings = await apiJson<ProcessDiscoverySettings>('/settings/process-discovery');
		} catch {
			// Use defaults
		} finally {
			loadingDiscoverySettings = false;
		}
	}

	async function saveDiscoverySettings() {
		savingDiscoverySettings = true;
		error = '';
		try {
			await apiJson('/settings/process-discovery', {
				method: 'PUT',
				body: JSON.stringify(discoverySettings)
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save discovery settings';
		} finally {
			savingDiscoverySettings = false;
		}
	}

	function toggleWorkspace(id: string) {
		const idx = discoverySettings.workspace_ids.indexOf(id);
		if (idx >= 0) {
			discoverySettings.workspace_ids = discoverySettings.workspace_ids.filter((w) => w !== id);
		} else {
			discoverySettings.workspace_ids = [...discoverySettings.workspace_ids, id];
		}
	}

	function toggleDocType(type: string) {
		const idx = discoverySettings.document_types.indexOf(type);
		if (idx >= 0) {
			discoverySettings.document_types = discoverySettings.document_types.filter((t) => t !== type);
		} else {
			discoverySettings.document_types = [...discoverySettings.document_types, type];
		}
	}

	$effect(() => {
		loadProcesses();
		loadAnalysisSettings();
		loadWorkspaces();
		loadDiscoverySettings();
	});

	$effect(() => {
		void searchQuery;
		void statusFilter;
		currentPage = 1;
	});

	// -----------------------------------------------------------------------
	// Process selection
	// -----------------------------------------------------------------------

	function selectProcess(process: BusinessProcess) {
		if (selectedProcess?.id === process.id) return;
		loadProcessDetail(process.id);
	}

	function clearSelection() {
		selectedProcess = null;
		editingStep = null;
		editingMetadata = false;
		confirmingDelete = false;
		creatingStep = false;
		flowNodes = [];
		flowEdges = [];
	}

	// -----------------------------------------------------------------------
	// Node click -> step edit
	// -----------------------------------------------------------------------

	function handleNodeClick(node: FlowNodeType) {
		if (!selectedProcess) return;
		const step = selectedProcess.steps.find((s) => s.id === node.id);
		if (step) {
			openStepEditor(step);
		}
	}

	function handlePaneClick() {
		editingStep = null;
	}

	function openStepEditor(step: ProcessStep) {
		editingStep = step;
		creatingStep = false;
		stepForm = {
			name: step.name,
			description: step.description ?? '',
			step_type: step.step_type ?? '',
			system_id: step.system_id ?? '',
			inputs: [...(step.inputs ?? [])],
			outputs: [...(step.outputs ?? [])],
			newInput: '',
			newOutput: ''
		};
	}

	function closeStepEditor() {
		editingStep = null;
		creatingStep = false;
		confirmingStepDelete = false;
		addingDependency = false;
	}

	function buildStepPayload(order?: number) {
		return {
			name: stepForm.name,
			description: stepForm.description || '',
			step_type: stepForm.step_type || '',
			system_id: stepForm.system_id || null,
			order: order ?? editingStep?.order ?? 0,
			inputs: stepForm.inputs.filter(Boolean),
			outputs: stepForm.outputs.filter(Boolean)
		};
	}

	async function saveStep() {
		if (!selectedProcess || !editingStep) return;
		if (creatingStep) {
			await createStep();
			return;
		}
		if (!stepForm.name.trim()) {
			error = 'Step name is required.';
			return;
		}
		savingStep = true;
		error = '';
		try {
			await apiJson(`/processes/${selectedProcess.id}/steps/${editingStep.id}`, {
				method: 'PUT',
				body: JSON.stringify(buildStepPayload())
			});
			editingStep = null;
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save step';
		} finally {
			savingStep = false;
		}
	}

	async function changeStepOrder(delta: number) {
		if (!selectedProcess || !editingStep) return;
		const newOrder = editingStep.order + delta;
		if (newOrder < 0) return;
		editingStep = { ...editingStep, order: newOrder };
		savingStep = true;
		error = '';
		try {
			await apiJson(`/processes/${selectedProcess.id}/steps/${editingStep.id}`, {
				method: 'PUT',
				body: JSON.stringify(buildStepPayload(newOrder))
			});
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to reorder step';
		} finally {
			savingStep = false;
		}
	}

	function addInput() {
		const val = stepForm.newInput.trim();
		if (val && !stepForm.inputs.includes(val)) {
			stepForm.inputs = [...stepForm.inputs, val];
		}
		stepForm.newInput = '';
	}

	function removeInput(val: string) {
		stepForm.inputs = stepForm.inputs.filter((v) => v !== val);
	}

	function addOutput() {
		const val = stepForm.newOutput.trim();
		if (val && !stepForm.outputs.includes(val)) {
			stepForm.outputs = [...stepForm.outputs, val];
		}
		stepForm.newOutput = '';
	}

	function removeOutput(val: string) {
		stepForm.outputs = stepForm.outputs.filter((v) => v !== val);
	}

	// -----------------------------------------------------------------------
	// Verify process
	// -----------------------------------------------------------------------

	async function verifyProcess() {
		if (!selectedProcess) return;
		verifying = true;
		error = '';
		try {
			await apiFetch(`/processes/${selectedProcess.id}/verify`, { method: 'POST' });
			await loadProcessDetail(selectedProcess.id);
			await loadProcesses();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to verify process';
		} finally {
			verifying = false;
		}
	}

	// -----------------------------------------------------------------------
	// Delete process
	// -----------------------------------------------------------------------

	async function deleteProcess() {
		if (!selectedProcess) return;
		deletingProcess = true;
		error = '';
		try {
			await apiFetch(`/processes/${selectedProcess.id}`, { method: 'DELETE' });
			processes = processes.filter((p) => p.id !== selectedProcess!.id);
			clearSelection();
			confirmingDelete = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete process';
		} finally {
			deletingProcess = false;
		}
	}

	// -----------------------------------------------------------------------
	// Archive process
	// -----------------------------------------------------------------------

	async function archiveProcess() {
		if (!selectedProcess) return;
		archivingProcess = true;
		error = '';
		try {
			const updated = { ...selectedProcess, status: 'archived' };
			await apiJson(`/processes/${selectedProcess.id}`, {
				method: 'PUT',
				body: JSON.stringify(updated)
			});
			await loadProcessDetail(selectedProcess.id);
			await loadProcesses();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to archive process';
		} finally {
			archivingProcess = false;
		}
	}

	// -----------------------------------------------------------------------
	// Edit metadata
	// -----------------------------------------------------------------------

	function startEditingMetadata() {
		if (!selectedProcess) return;
		metadataForm = {
			name: selectedProcess.name,
			description: selectedProcess.description,
			category: selectedProcess.category,
			tags: [...selectedProcess.tags],
			newTag: ''
		};
		editingMetadata = true;
	}

	function cancelEditingMetadata() {
		editingMetadata = false;
	}

	function addMetadataTag() {
		const tag = metadataForm.newTag.trim();
		if (tag && !metadataForm.tags.includes(tag)) {
			metadataForm.tags = [...metadataForm.tags, tag];
		}
		metadataForm.newTag = '';
	}

	function removeMetadataTag(tag: string) {
		metadataForm.tags = metadataForm.tags.filter((t) => t !== tag);
	}

	async function saveMetadata() {
		if (!selectedProcess) return;
		if (!metadataForm.name.trim()) {
			error = 'Process name is required.';
			return;
		}
		savingMetadata = true;
		error = '';
		try {
			const updated = {
				...selectedProcess,
				name: metadataForm.name,
				description: metadataForm.description,
				category: metadataForm.category,
				tags: metadataForm.tags
			};
			await apiJson(`/processes/${selectedProcess.id}`, {
				method: 'PUT',
				body: JSON.stringify(updated)
			});
			editingMetadata = false;
			await loadProcessDetail(selectedProcess.id);
			await loadProcesses();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save metadata';
		} finally {
			savingMetadata = false;
		}
	}

	// -----------------------------------------------------------------------
	// Step CRUD
	// -----------------------------------------------------------------------

	function openNewStepEditor() {
		const maxOrder = selectedProcess
			? Math.max(0, ...selectedProcess.steps.map((s) => s.order))
			: 0;
		editingStep = {
			id: '',
			name: '',
			description: '',
			step_type: 'action',
			system_id: null,
			endpoint_id: null,
			order: maxOrder + 1,
			inputs: [],
			outputs: []
		} as ProcessStep;
		stepForm = {
			name: '',
			description: '',
			step_type: 'action',
			system_id: '',
			inputs: [],
			outputs: [],
			newInput: '',
			newOutput: ''
		};
		creatingStep = true;
	}

	async function createStep() {
		if (!selectedProcess) return;
		if (!stepForm.name.trim()) {
			error = 'Step name is required.';
			return;
		}
		savingStep = true;
		error = '';
		try {
			await apiJson(`/processes/${selectedProcess.id}/steps`, {
				method: 'POST',
				body: JSON.stringify(buildStepPayload())
			});
			editingStep = null;
			creatingStep = false;
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create step';
		} finally {
			savingStep = false;
		}
	}

	let confirmingStepDelete = $state(false);

	async function deleteStep() {
		if (!selectedProcess || !editingStep || !editingStep.id) return;
		savingStep = true;
		error = '';
		try {
			await apiFetch(`/processes/${selectedProcess.id}/steps/${editingStep.id}`, {
				method: 'DELETE'
			});
			editingStep = null;
			confirmingStepDelete = false;
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete step';
		} finally {
			savingStep = false;
		}
	}

	// -----------------------------------------------------------------------
	// Dependency management
	// -----------------------------------------------------------------------

	let addingDependency = $state(false);
	let newDepSourceId = $state('');
	let newDepCondition = $state('');

	async function addDependency() {
		if (!selectedProcess || !editingStep || !newDepSourceId) return;
		error = '';
		try {
			await apiJson(`/processes/${selectedProcess.id}/dependencies`, {
				method: 'POST',
				body: JSON.stringify({
					source_step_id: newDepSourceId,
					target_step_id: editingStep.id,
					condition: newDepCondition || null
				})
			});
			addingDependency = false;
			newDepSourceId = '';
			newDepCondition = '';
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to add dependency';
		}
	}

	async function removeDependency(sourceStepId: string, targetStepId: string) {
		if (!selectedProcess) return;
		error = '';
		try {
			await apiFetch(
				`/processes/${selectedProcess.id}/dependencies?source_step_id=${encodeURIComponent(sourceStepId)}&target_step_id=${encodeURIComponent(targetStepId)}`,
				{ method: 'DELETE' }
			);
			await loadProcessDetail(selectedProcess.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove dependency';
		}
	}

	// -----------------------------------------------------------------------
	// Re-discover
	// -----------------------------------------------------------------------

	function classifyLogEntry(message: string): DiscoveryLogEntry['type'] {
		const lower = message.toLowerCase();
		// Scanning / gathering phases
		if (lower.includes('scanning system:') || lower.includes('scanning catalog')) return 'scan';
		if (lower.includes('scanning') || lower.includes('gathering')) return 'scan';
		if (lower.includes('querying knowledge graph')) return 'scan';
		if (lower.includes('processing document:')) return 'scan';
		// Context summary
		if (lower.includes('found') && (lower.includes('systems') || lower.includes('entities') || lower.includes('documents'))) return 'context';
		if (lower.includes('loaded') && lower.includes('documents')) return 'context';
		if (lower.includes('context gathered') || lower.includes('no context available')) return 'context';
		// LLM interaction
		if (lower.includes('sending') && lower.includes('llm')) return 'llm';
		if (lower.includes('calling llm') || lower.includes('waiting for llm')) return 'llm';
		if (lower.includes('llm responded') || lower.includes('parsing')) return 'llm';
		if (lower.includes('truncated') || lower.includes('token limit')) return 'llm';
		if (lower.includes('repair') && lower.includes('successful')) return 'result';
		if (lower.includes('repair') || lower.includes('parse issue')) return 'llm';
		// Results
		if (lower.includes('identified') || lower.includes('analysis complete')) return 'result';
		// Merge
		if (lower.includes('merging') || lower.includes('merge complete')) return 'merge';
		// Done
		if (lower.includes('discovery complete')) return 'done';
		// Errors
		if (lower.includes('failed') || lower.includes('error') || lower.includes('also failed')) return 'error';
		if (lower.includes('skipped') || lower.includes('no llm')) return 'error';
		// Completion
		if (lower.includes('complete')) return 'done';
		return 'info';
	}

	async function triggerRediscover() {
		error = '';
		discoveryProgressMessage = '';
		discoveryLog = [];
		try {
			const resp = await apiJson<DiscoverResponse>('/processes/discover', { method: 'POST' });
			discoveryJobId = resp.job_id;
			discoveryJobStatus = resp.status;
			discoveryJobProgress = resp.progress_pct ?? 0;

			const response = await apiFetch(`/jobs/${resp.job_id}/stream`);
			await parseSSEStream(
				response,
				(msg) => {
					if (msg.event === 'job_progress') {
						discoveryJobStatus = (msg.data.status as string) ?? discoveryJobStatus;
						discoveryJobProgress = (msg.data.progress_pct as number) ?? discoveryJobProgress;
						if (msg.data.progress_message) {
							const message = msg.data.progress_message as string;
							discoveryProgressMessage = message;
							// Accumulate into conversation log (skip duplicates)
							if (!discoveryLog.some((e) => e.message === message)) {
								discoveryLog = [
									...discoveryLog,
									{
										message,
										pct: msg.data.progress_pct as number,
										timestamp: new Date(),
										type: classifyLogEntry(message)
									}
								];
								// Auto-scroll to bottom
								requestAnimationFrame(() => {
									discoveryLogEl?.scrollTo({
										top: discoveryLogEl.scrollHeight,
										behavior: 'smooth'
									});
								});
							}
						}
					} else if (msg.event === 'done') {
						discoveryJobStatus = msg.data.status as string;
						if (msg.data.error) {
							const errMsg = `Discovery failed: ${msg.data.error as string}`;
							error = errMsg;
							discoveryLog = [
								...discoveryLog,
								{
									message: errMsg,
									pct: 100,
									timestamp: new Date(),
									type: 'error'
								}
							];
						}
					}
				},
				(err) => {
					error = `Stream error: ${err.message}`;
				},
				async () => {
					// Stream ended -- update final state
					if (discoveryJobStatus !== 'failed' && discoveryJobStatus !== 'cancelled') {
						discoveryJobStatus = 'completed';
						discoveryProgressMessage = '';
					}
					await loadProcesses(true);
					if (selectedProcess) {
						await loadProcessDetail(selectedProcess.id, true);
					}
				}
			);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to start discovery';
		}
	}

	// -----------------------------------------------------------------------
	// Auto-analyze toggle
	// -----------------------------------------------------------------------

	async function toggleAutoAnalyze() {
		togglingAutoAnalyze = true;
		const next = !autoAnalyze;
		try {
			await apiJson('/settings/analysis', {
				method: 'PUT',
				body: JSON.stringify({ auto_analyze: next })
			});
			autoAnalyze = next;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update setting';
		} finally {
			togglingAutoAnalyze = false;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function confidenceColor(confidence: number): string {
		if (confidence >= 0.8) return 'bg-success/10 text-success';
		if (confidence >= 0.5) return 'bg-warning/10 text-warning';
		return 'bg-danger/10 text-danger';
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'verified':
				return 'bg-success/10 text-success';
			case 'discovered':
				return 'bg-accent/10 text-accent';
			case 'modified':
				return 'bg-warning/10 text-warning';
			case 'archived':
				return 'bg-text-secondary/10 text-text-secondary';
			default:
				return 'bg-text-secondary/10 text-text-secondary';
		}
	}

	function sourceLabel(source: string): string {
		switch (source) {
			case 'auto_discovered':
				return 'Auto-discovered';
			case 'manual':
				return 'Manual';
			case 'imported':
				return 'Imported';
			default:
				return source;
		}
	}

	function formatDate(dateStr: string): string {
		if (!dateStr) return '--';
		const d = new Date(dateStr);
		return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	function relativeTime(dateStr: string): string {
		if (!dateStr) return '--';
		const now = Date.now();
		const then = new Date(dateStr).getTime();
		const diffMs = now - then;
		const diffSec = Math.floor(diffMs / 1000);
		if (diffSec < 60) return 'just now';
		const diffMin = Math.floor(diffSec / 60);
		if (diffMin < 60) return `${diffMin}m ago`;
		const diffHr = Math.floor(diffMin / 60);
		if (diffHr < 24) return `${diffHr}h ago`;
		const diffDay = Math.floor(diffHr / 24);
		if (diffDay < 30) return `${diffDay}d ago`;
		const diffMonth = Math.floor(diffDay / 30);
		if (diffMonth < 12) return `${diffMonth}mo ago`;
		return `${Math.floor(diffMonth / 12)}y ago`;
	}

	const STEP_TYPE_CONFIG: Record<string, { icon: typeof Cog; color: string; bg: string; label: string }> = {
		action: { icon: Zap, color: 'text-accent', bg: 'bg-accent/10 border-accent/20', label: 'Action' },
		decision: { icon: Split, color: 'text-warning', bg: 'bg-warning/10 border-warning/20', label: 'Decision' },
		wait: { icon: Timer, color: 'text-text-secondary', bg: 'bg-text-secondary/10 border-text-secondary/20', label: 'Wait' },
		notification: { icon: Bell, color: 'text-[#8b5cf6]', bg: 'bg-[#8b5cf6]/10 border-[#8b5cf6]/20', label: 'Notification' },
		validation: { icon: ShieldCheck, color: 'text-success', bg: 'bg-success/10 border-success/20', label: 'Validation' },
		transformation: { icon: Shuffle, color: 'text-[#ec4899]', bg: 'bg-[#ec4899]/10 border-[#ec4899]/20', label: 'Transform' }
	};
	const STEP_TYPES = Object.keys(STEP_TYPE_CONFIG);

	const statusOptions: { value: ProcessStatus | 'all'; label: string }[] = [
		{ value: 'all', label: 'All' },
		{ value: 'discovered', label: 'Discovered' },
		{ value: 'verified', label: 'Verified' },
		{ value: 'modified', label: 'Modified' },
		{ value: 'archived', label: 'Archived' }
	];

	function stepTypeIcon(stepType?: string): typeof Cog {
		if (!stepType) return Cog;
		return STEP_TYPE_CONFIG[stepType.toLowerCase()]?.icon ?? Cog;
	}

	function getStepTypeConfig(stepType?: string) {
		if (!stepType) return { icon: Cog, color: 'text-text-secondary', bg: 'bg-surface-secondary border-border', label: stepType || 'General' };
		return STEP_TYPE_CONFIG[stepType.toLowerCase()] ?? { icon: Cog, color: 'text-text-secondary', bg: 'bg-surface-secondary border-border', label: stepType };
	}

	function logEntryIcon(type: DiscoveryLogEntry['type']): typeof Cog {
		switch (type) {
			case 'scan':
				return Search;
			case 'context':
				return Database;
			case 'llm':
				return Brain;
			case 'result':
				return Sparkles;
			case 'merge':
				return Merge;
			case 'done':
				return CircleCheck;
			case 'error':
				return CircleX;
			default:
				return Cog;
		}
	}

	function logEntryColor(type: DiscoveryLogEntry['type']): string {
		switch (type) {
			case 'scan':
				return 'text-accent';
			case 'context':
				return 'text-accent';
			case 'llm':
				return 'text-warning';
			case 'result':
				return 'text-success';
			case 'merge':
				return 'text-accent';
			case 'done':
				return 'text-success';
			case 'error':
				return 'text-danger';
			default:
				return 'text-text-secondary';
		}
	}

	function formatTime(date: Date): string {
		return date.toLocaleTimeString('en-US', {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	}

	// Click-outside handler for discovery settings dropdown
	function handleClickOutside(event: MouseEvent) {
		if (
			showDiscoverySettings &&
			discoverySettingsRef &&
			!discoverySettingsRef.contains(event.target as Node)
		) {
			showDiscoverySettings = false;
		}
	}

	$effect(() => {
		if (showDiscoverySettings) {
			document.addEventListener('mousedown', handleClickOutside);
			return () => {
				document.removeEventListener('mousedown', handleClickOutside);
			};
		}
	});
</script>

<div class="flex h-full flex-col">
	<!-- ================================================================= -->
	<!-- Top toolbar                                                        -->
	<!-- ================================================================= -->
	<div class="flex h-12 shrink-0 items-center gap-3 border-b border-border/40 bg-surface px-4">
		<!-- Search (aligned with sidebar width) -->
		<div class="relative w-60">
			<Search
				size={13}
				class="absolute top-1/2 left-2.5 -translate-y-1/2 text-text-secondary"
			/>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search processes..."
				class="h-8 w-full rounded-lg border border-border bg-surface py-1.5 pr-3 pl-8 text-sm text-text-primary outline-none focus:border-accent"
			/>
		</div>

		<!-- Status filter pills (compact, inline) -->
		<div class="flex items-center gap-1">
			{#each statusOptions as option}
				<button
					type="button"
					onclick={() => (statusFilter = option.value)}
					class="flex-shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors
						{statusFilter === option.value
						? 'border-accent/30 bg-accent/10 text-accent'
						: 'border-border text-text-secondary hover:bg-surface-hover'}"
				>
					{option.label}
				</button>
			{/each}
		</div>

		<!-- Spacer -->
		<div class="flex-1"></div>

		<!-- Auto-analyze toggle (small) -->
		<div class="flex items-center gap-1.5">
			<span class="text-xs text-text-secondary">Auto-analyze</span>
			<button
				type="button"
				onclick={toggleAutoAnalyze}
				disabled={loadingAutoAnalyze || togglingAutoAnalyze}
				class="text-text-secondary transition-colors hover:text-text-primary disabled:opacity-50"
				title={autoAnalyze ? 'Auto-analyze is on' : 'Auto-analyze is off'}
			>
				{#if loadingAutoAnalyze || togglingAutoAnalyze}
					<Loader2 size={16} class="animate-spin" />
				{:else if autoAnalyze}
					<ToggleRight size={20} class="text-accent" />
				{:else}
					<ToggleLeft size={20} />
				{/if}
			</button>
		</div>

		<!-- Discovery Settings button + dropdown -->
		<div class="relative" bind:this={discoverySettingsRef}>
			<button
				type="button"
				onclick={() => (showDiscoverySettings = !showDiscoverySettings)}
				class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary {showDiscoverySettings ? 'bg-surface-hover text-text-primary' : ''}"
				title="Discovery Settings"
			>
				<Settings size={16} />
			</button>

			{#if showDiscoverySettings}
				<div class="absolute top-full right-0 z-20 mt-1 w-80 rounded-lg border border-border bg-surface-elevated p-4 shadow-lg">
					{#if loadingDiscoverySettings}
						<div class="flex justify-center py-2">
							<Loader2 size={14} class="animate-spin text-text-secondary" />
						</div>
					{:else}
						<div class="flex flex-col gap-3">
							<!-- Workspaces -->
							<div>
								<span class="text-[10px] font-medium uppercase tracking-wide text-text-secondary">
									Workspaces
								</span>
								<p class="mb-1.5 text-[10px] text-text-secondary/60">
									Empty = scan all
								</p>
								<div class="flex flex-col gap-1">
									{#each workspaces as ws}
										<label class="flex items-center gap-2 text-xs text-text-primary">
											<input
												type="checkbox"
												checked={discoverySettings.workspace_ids.includes(ws.id)}
												onchange={() => toggleWorkspace(ws.id)}
												class="accent-accent"
											/>
											{ws.name}
										</label>
									{/each}
									{#if workspaces.length === 0}
										<p class="text-[10px] text-text-secondary/60">No workspaces available</p>
									{/if}
								</div>
							</div>

							<!-- Document Types -->
							<div>
								<span class="text-[10px] font-medium uppercase tracking-wide text-text-secondary">
									Document Types
								</span>
								<p class="mb-1.5 text-[10px] text-text-secondary/60">
									Empty = all types
								</p>
								<div class="grid grid-cols-2 gap-1">
									{#each DOCUMENT_TYPES as dt}
										<label class="flex items-center gap-1.5 text-xs text-text-primary">
											<input
												type="checkbox"
												checked={discoverySettings.document_types.includes(dt.value)}
												onchange={() => toggleDocType(dt.value)}
												class="accent-accent"
											/>
											{dt.label}
										</label>
									{/each}
								</div>
							</div>

							<!-- Focus Hint -->
							<div>
								<span class="text-[10px] font-medium uppercase tracking-wide text-text-secondary">
									Focus Areas
								</span>
								<input
									type="text"
									bind:value={discoverySettings.focus_hint}
									placeholder="e.g. onboarding workflows"
									class="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
								/>
							</div>

							<!-- Save -->
							<button
								type="button"
								onclick={saveDiscoverySettings}
								disabled={savingDiscoverySettings}
								class="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-accent/40 bg-accent/5 px-2.5 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
							>
								{#if savingDiscoverySettings}
									<Loader2 size={12} class="animate-spin" />
								{:else}
									<Save size={12} />
								{/if}
								Save Settings
							</button>
						</div>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Re-discover button (compact) + progress indicator -->
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={triggerRediscover}
				disabled={isDiscovering}
				class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
			>
				{#if isDiscovering}
					<Loader2 size={14} class="animate-spin" />
					Discovering...
				{:else}
					<RefreshCw size={14} />
					Re-discover
				{/if}
			</button>

			</div>
	</div>

	<!-- ================================================================= -->
	<!-- Body: sidebar + main content                                       -->
	<!-- ================================================================= -->
	<div class="flex min-h-0 flex-1">
		<!-- Process list sidebar (slim) -->
		<div class="flex w-64 shrink-0 flex-col border-r border-border bg-surface-secondary">
			<!-- Process list -->
			<div class="min-h-0 flex-1 overflow-y-auto">
				{#if loading}
					<div class="flex items-center justify-center py-12">
						<Loader2 size={20} class="animate-spin text-text-secondary" />
					</div>
				{:else if filteredProcesses.length === 0}
					<div class="px-4 py-8 text-center text-xs text-text-secondary">
						{searchQuery || statusFilter !== 'all'
							? 'No processes match your filters.'
							: 'No processes discovered yet.'}
					</div>
				{:else}
					<ul class="flex flex-col gap-0.5 p-2">
						{#each paginatedProcesses as process}
							{@const isSelected = selectedProcess?.id === process.id}
							<li>
								<button
									type="button"
									onclick={() => selectProcess(process)}
									class="flex w-full flex-col gap-1 rounded-md px-3 py-2.5 text-left transition-colors
										{isSelected
										? 'bg-accent/10 ring-1 ring-accent/30'
										: 'hover:bg-surface-hover'}"
								>
									<div class="flex items-center gap-2">
										<GitBranch
											size={14}
											class={isSelected ? 'text-accent' : 'text-text-secondary'}
										/>
										<span
											class="flex-1 truncate text-xs font-medium {isSelected
												? 'text-accent'
												: 'text-text-primary'}"
										>
											{process.name}
										</span>
									</div>
									<div class="flex items-center gap-1.5 pl-5">
										<span
											class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {statusBadge(
												process.status
											)}"
										>
											{process.status}
										</span>
										<span
											class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {confidenceColor(
												process.confidence
											)}"
										>
											{Math.round(process.confidence * 100)}%
										</span>
										{#if process.category}
											<span class="truncate text-[10px] text-text-secondary">
												{process.category}
											</span>
										{/if}
									</div>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			<!-- Pagination -->
			{#if filteredProcesses.length > pageSize}
				<div class="flex shrink-0 items-center justify-between border-t border-border/50 px-3 py-1.5">
					<span class="text-[10px] text-text-secondary">
						{(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredProcesses.length)} of {filteredProcesses.length}
					</span>
					<div class="flex items-center gap-1">
						<button
							type="button"
							disabled={currentPage <= 1}
							onclick={() => currentPage--}
							class="rounded px-1.5 py-0.5 text-[10px] text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
						>Prev</button>
						<span class="text-[10px] text-text-secondary">{currentPage}/{totalPages}</span>
						<button
							type="button"
							disabled={currentPage >= totalPages}
							onclick={() => currentPage++}
							class="rounded px-1.5 py-0.5 text-[10px] text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-40"
						>Next</button>
					</div>
				</div>
			{/if}
		</div>

		<!-- ================================================================= -->
		<!-- Main content area                                                  -->
		<!-- ================================================================= -->
		<div class="flex min-w-0 flex-1 flex-col overflow-hidden">
		<!-- Error banner -->
		{#if error}
			<div
				class="shrink-0 mx-4 mt-3 flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
			>
				<AlertCircle size={16} />
				<span class="flex-1">{error}</span>
				<button
					type="button"
					onclick={() => (error = '')}
					class="text-danger/60 hover:text-danger"
				>
					<X size={14} />
				</button>
			</div>
		{/if}

		{#if !selectedProcess && discoveryLog.length > 0}
			<!-- Discovery conversation timeline -->
			<div class="flex flex-1 flex-col overflow-hidden">
				<div class="border-b border-border px-5 py-3">
					<div class="flex items-center gap-2">
						<Brain size={18} class="text-accent" />
						<h2 class="text-base font-semibold text-text-primary">Process Discovery</h2>
						{#if isDiscovering}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
							>
								<Loader2 size={12} class="animate-spin" />
								Running
							</span>
						{:else if discoveryJobStatus === 'completed'}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success"
							>
								<CircleCheck size={12} />
								Complete
							</span>
						{:else if discoveryJobStatus === 'failed'}
							<span
								class="ml-2 inline-flex items-center gap-1 rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger"
							>
								<CircleX size={12} />
								Failed
							</span>
						{/if}
					</div>
				</div>

				<!-- Scrollable log -->
				<div
					bind:this={discoveryLogEl}
					class="flex-1 overflow-y-auto px-5 py-4"
				>
					<div class="mx-auto max-w-2xl space-y-1">
						{#each discoveryLog as entry, i}
							{@const Icon = logEntryIcon(entry.type)}
							{@const color = logEntryColor(entry.type)}
							<div
								class="group flex gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-hover/50"
							>
								<!-- Icon column -->
								<div class="flex flex-col items-center pt-0.5">
									<div
										class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-secondary {color}"
									>
										<Icon size={14} />
									</div>
									{#if i < discoveryLog.length - 1}
										<div class="mt-1 w-px flex-1 bg-border/50"></div>
									{/if}
								</div>

								<!-- Content -->
								<div class="min-w-0 flex-1 pb-2">
									<p class="text-sm leading-relaxed text-text-primary">
										{entry.message}
									</p>
									<p class="mt-0.5 text-[10px] text-text-secondary/60">
										{formatTime(entry.timestamp)} · {entry.pct}%
									</p>
								</div>
							</div>
						{/each}

						{#if isDiscovering}
							<!-- Typing indicator -->
							<div class="flex gap-3 px-3 py-2.5">
								<div
									class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-secondary text-accent"
								>
									<Loader2 size={14} class="animate-spin" />
								</div>
								<div class="flex items-center pt-1">
									<span class="text-xs text-text-secondary/60">Processing...</span>
								</div>
							</div>
						{/if}
					</div>
				</div>

				<!-- Progress bar at bottom -->
				{#if isDiscovering || discoveryJobStatus === 'completed'}
					<div class="border-t border-border px-5 py-3">
						<div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-secondary">
							<div
								class="h-full rounded-full transition-all duration-500 {discoveryJobStatus === 'completed'
									? 'bg-success'
									: discoveryJobStatus === 'failed'
										? 'bg-danger'
										: 'bg-accent'}"
								style="width: {discoveryJobProgress}%"
							></div>
						</div>
						<div class="mt-1 flex items-center justify-between text-[10px] text-text-secondary/60">
							<span>{discoveryProgressMessage || (discoveryJobStatus === 'completed' ? 'Discovery complete' : '')}</span>
							<span>{discoveryJobProgress}%</span>
						</div>
					</div>
				{/if}
			</div>
		{:else if !selectedProcess}
			<!-- Empty state -->
			<div class="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary">
				<GitBranch size={48} strokeWidth={1} class="opacity-30" />
				<p class="text-sm">Select a process to view its steps and dependencies</p>
				<p class="text-xs">Or trigger a new discovery job from the toolbar</p>
			</div>
		{:else if loadingDetail}
			<div class="flex flex-1 items-center justify-center">
				<Loader2 size={24} class="animate-spin text-text-secondary" />
			</div>
		{:else}
			<!-- Process detail header -->
			<div class="shrink-0 border-b border-border px-5 py-3">
				<!-- Delete confirmation bar -->
				{#if confirmingDelete}
					<div class="mb-3 flex items-center gap-3 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2">
						<span class="text-xs text-danger">Are you sure? This cannot be undone.</span>
						<div class="flex-1"></div>
						<button
							type="button"
							onclick={() => (confirmingDelete = false)}
							class="rounded-md border border-border px-3 py-1 text-xs text-text-secondary hover:bg-surface-hover"
						>Cancel</button>
						<button
							type="button"
							onclick={deleteProcess}
							disabled={deletingProcess}
							class="inline-flex items-center gap-1 rounded-md bg-danger px-3 py-1 text-xs font-medium text-white hover:bg-danger/90 disabled:opacity-50"
						>
							{#if deletingProcess}<Loader2 size={12} class="animate-spin" />{/if}
							Delete
						</button>
					</div>
				{/if}

				<div class="flex items-start justify-between gap-4">
					<div class="min-w-0 flex-1">
						{#if editingMetadata}
							<!-- Editable metadata form -->
							<div class="flex flex-col gap-2">
								<input
									type="text"
									bind:value={metadataForm.name}
									placeholder="Process name"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-base font-semibold text-text-primary outline-none focus:border-accent"
								/>
								<textarea
									bind:value={metadataForm.description}
									placeholder="Description"
									rows="2"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
								></textarea>
								<input
									type="text"
									bind:value={metadataForm.category}
									placeholder="Category (e.g. customer-service)"
									class="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
								/>
								<!-- Tags editor -->
								<div class="flex flex-wrap items-center gap-1.5">
									{#each metadataForm.tags as tag}
										<span class="inline-flex items-center gap-1 rounded-full bg-surface-secondary px-2 py-0.5 text-[10px] text-text-secondary">
											{tag}
											<button
												type="button"
												onclick={() => removeMetadataTag(tag)}
												class="text-text-secondary hover:text-danger"
											><X size={10} /></button>
										</span>
									{/each}
									<input
										type="text"
										bind:value={metadataForm.newTag}
										placeholder="Add tag..."
										class="w-24 rounded border border-border bg-surface px-2 py-0.5 text-[10px] text-text-primary outline-none focus:border-accent"
										onkeydown={(e) => {
											if (e.key === 'Enter') {
												e.preventDefault();
												addMetadataTag();
											}
										}}
									/>
								</div>
								<div class="flex gap-2 pt-1">
									<button
										type="button"
										onclick={cancelEditingMetadata}
										class="rounded-md border border-border px-3 py-1 text-xs text-text-secondary hover:bg-surface-hover"
									>Cancel</button>
									<button
										type="button"
										onclick={saveMetadata}
										disabled={savingMetadata}
										class="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
									>
										{#if savingMetadata}<Loader2 size={12} class="animate-spin" />{/if}
										<Save size={12} />
										Save
									</button>
								</div>
							</div>
						{:else}
							<!-- Read-only metadata display -->
							<div class="flex items-center gap-2">
								<h2 class="truncate text-base font-semibold text-text-primary">
									{selectedProcess.name}
								</h2>
								<span
									class="flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {statusBadge(
										selectedProcess.status
									)}"
								>
									{selectedProcess.status}
								</span>
								<span
									class="flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {confidenceColor(
										selectedProcess.confidence
									)}"
								>
									{Math.round(selectedProcess.confidence * 100)}% confidence
								</span>
							</div>
							{#if selectedProcess.description}
								<p class="mt-1 text-xs leading-relaxed text-text-secondary">
									{selectedProcess.description}
								</p>
							{/if}
							<div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
								{#if selectedProcess.category}
									<span class="flex items-center gap-1">
										<Cog size={12} />
										{selectedProcess.category}
									</span>
								{/if}
								<span class="flex items-center gap-1">
									<Sparkles size={12} />
									{sourceLabel(selectedProcess.source)}
								</span>
								{#if selectedProcess.tags.length > 0}
									<span class="flex items-center gap-1">
										<Tag size={12} />
										{#each selectedProcess.tags as tag}
											<span
												class="rounded bg-surface-secondary px-1.5 py-0.5 text-[10px] text-text-secondary"
											>
												{tag}
											</span>
										{/each}
									</span>
								{/if}
							</div>
						{/if}
					</div>

					<!-- Actions -->
					<div class="flex items-center gap-1.5">
						<button
							type="button"
							onclick={startEditingMetadata}
							class="rounded p-1.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							title="Edit metadata"
						>
							<Pencil size={14} />
						</button>
						{#if selectedProcess.status !== 'archived'}
							<button
								type="button"
								onclick={archiveProcess}
								disabled={archivingProcess}
								class="rounded p-1.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
								title="Archive process"
							>
								{#if archivingProcess}
									<Loader2 size={14} class="animate-spin" />
								{:else}
									<Archive size={14} />
								{/if}
							</button>
						{/if}
						<button
							type="button"
							onclick={() => (confirmingDelete = true)}
							class="rounded p-1.5 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
							title="Delete process"
						>
							<Trash2 size={14} />
						</button>
						<div class="mx-1 h-5 w-px bg-border/50"></div>
						{#if selectedProcess.status !== 'verified'}
							<button
								type="button"
								onclick={verifyProcess}
								disabled={verifying}
								class="inline-flex items-center gap-1.5 rounded-md border border-success/40 bg-success/5 px-3 py-1.5 text-xs font-medium text-success transition-colors hover:bg-success/10 disabled:opacity-50"
							>
								{#if verifying}
									<Loader2 size={14} class="animate-spin" />
								{:else}
									<CheckCircle2 size={14} />
								{/if}
								Verify
							</button>
						{:else}
							<span class="inline-flex items-center gap-1 text-xs font-medium text-success">
								<CheckCircle2 size={14} />
								Verified
							</span>
						{/if}
						<button
							type="button"
							onclick={() => clearSelection()}
							class="rounded p-1.5 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
							title="Close"
						>
							<X size={16} />
						</button>
					</div>
				</div>
			</div>

			<!-- Rich detail stats row -->
			{#if processStats}
				<div class="shrink-0 border-b border-border/50 bg-surface-secondary/30 px-5 py-2.5">
					<div class="flex flex-wrap items-center gap-3">
						<!-- Steps breakdown -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs">
							<GitBranch size={12} class="text-accent" />
							<span class="font-medium text-text-primary">{selectedProcess.steps.length}</span>
							<span class="text-text-secondary">steps</span>
							{#if Object.keys(processStats.stepsByType).length > 0}
								<span class="text-text-secondary/30 mx-0.5">|</span>
								{#each Object.entries(processStats.stepsByType) as [t, c]}
									{@const conf = STEP_TYPE_CONFIG[t]}
									{#if conf}
										{@const Icon = conf.icon}
										<span class="inline-flex items-center gap-0.5 {conf.color}" title="{c} {t}">
											<Icon size={10} />
											<span class="text-[10px] font-medium">{c}</span>
										</span>
									{:else}
										<span class="text-[10px] text-text-secondary">{c} {t}</span>
									{/if}
								{/each}
							{/if}
						</div>

						<!-- Dependencies -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs">
							<ArrowRight size={12} class="text-accent" />
							<span class="font-medium text-text-primary">{selectedProcess.dependencies.length}</span>
							<span class="text-text-secondary">deps</span>
							{#if processStats.conditionalDeps > 0}
								<span class="text-text-secondary/50">·</span>
								<span class="text-[10px] text-text-secondary">{processStats.conditionalDeps} conditional</span>
							{/if}
						</div>

						<!-- Linked Systems -->
						{#if processStats.linkedSystemCount > 0}
							<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs">
								<Monitor size={12} class="text-accent" />
								<span class="font-medium text-text-primary">{processStats.linkedSystemCount}</span>
								<span class="text-text-secondary">systems</span>
							</div>
						{/if}

						<!-- Source -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs">
							<Sparkles size={12} class="text-text-secondary" />
							<span class="text-text-secondary">{sourceLabel(selectedProcess.source)}</span>
						</div>

						<!-- Confidence gauge -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs">
							<div class="h-1.5 w-16 overflow-hidden rounded-full bg-surface-secondary">
								<div
									class="h-full rounded-full {selectedProcess.confidence >= 0.8 ? 'bg-success' : selectedProcess.confidence >= 0.5 ? 'bg-warning' : 'bg-danger'}"
									style="width: {Math.round(selectedProcess.confidence * 100)}%"
								></div>
							</div>
							<span class="text-text-secondary">{Math.round(selectedProcess.confidence * 100)}%</span>
						</div>

						<!-- Created -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs" title={formatDate(selectedProcess.created_at)}>
							<Clock size={12} class="text-text-secondary" />
							<span class="text-text-secondary">Created {relativeTime(selectedProcess.created_at)}</span>
						</div>

						<!-- Updated -->
						<div class="flex items-center gap-1.5 rounded-md border border-border/50 bg-surface px-2.5 py-1.5 text-xs" title={formatDate(selectedProcess.updated_at)}>
							<Clock size={12} class="text-text-secondary" />
							<span class="text-text-secondary">Updated {relativeTime(selectedProcess.updated_at)}</span>
						</div>
					</div>
				</div>
			{/if}

			<!-- Canvas and step editor area -->
			<div class="flex min-h-0 flex-1 overflow-hidden">
				<!-- SvelteFlow canvas -->
				<div class="relative flex-1 overflow-hidden">
					{#if selectedProcess.steps.length === 0}
						<div
							class="flex h-full flex-col items-center justify-center gap-2 text-text-secondary"
						>
							<GitBranch size={36} strokeWidth={1} class="opacity-30" />
							<p class="text-sm">No steps in this process</p>
							<button
								type="button"
								onclick={openNewStepEditor}
								class="mt-2 inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/5 px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
							>
								<Plus size={14} />
								Add First Step
							</button>
						</div>
					{:else}
						<FlowCanvas
							nodes={flowNodes}
							edges={flowEdges}
							fitView={true}
							interactive={true}
							options={{
								minimap: true,
								controls: true,
								background: 'dots',
								minZoom: 0.1,
								maxZoom: 5
							}}
							onNodeClick={handleNodeClick}
							onPaneClick={handlePaneClick}
						/>

						<!-- Add step overlay button -->
						<div class="pointer-events-none absolute top-3 left-3">
							<button
								type="button"
								onclick={openNewStepEditor}
								class="pointer-events-auto inline-flex items-center gap-1.5 rounded-md border border-border bg-surface/90 px-3 py-1.5 text-xs font-medium text-text-primary shadow-sm backdrop-blur-sm transition-colors hover:bg-surface-hover"
							>
								<Plus size={14} />
								Add Step
							</button>
						</div>

						<!-- Click hint -->
						{#if !editingStep}
							<div
								class="pointer-events-none absolute bottom-3 left-3 rounded-md border border-border bg-surface/90 px-3 py-1.5 text-xs text-text-secondary backdrop-blur-sm"
							>
								Click a step node to edit
							</div>
						{/if}
					{/if}
				</div>

				<!-- Step edit panel (slide-out) -->
				{#if editingStep}
					{@const typeConf = getStepTypeConfig(stepForm.step_type || editingStep.step_type)}
					<div
						class="flex w-[340px] shrink-0 flex-col border-l border-border bg-surface"
					>
						<!-- Panel header — rich with type badge + order controls -->
						<div class="border-b border-border">
							<div class="flex items-center justify-between px-4 pt-3 pb-2">
								<div class="flex items-center gap-2.5">
									{#if typeConf}
										{@const TypeIcon = typeConf.icon}
										<div class="flex h-8 w-8 items-center justify-center rounded-lg border {typeConf.bg}">
											<TypeIcon size={16} class={typeConf.color} />
										</div>
									{/if}
									<div>
										<h4 class="text-sm font-semibold text-text-primary leading-tight">
											{creatingStep ? 'New Step' : 'Edit Step'}
										</h4>
										{#if !creatingStep}
											<div class="flex items-center gap-1.5 mt-0.5">
												<span class="text-[10px] text-text-secondary/60">#{editingStep.order}</span>
												<div class="flex">
													<button
														type="button"
														onclick={() => changeStepOrder(-1)}
														disabled={savingStep || editingStep.order <= 0}
														class="rounded p-0.5 text-text-secondary/50 hover:text-text-primary disabled:opacity-20 transition-colors"
														title="Move up"
													><ChevronUp size={12} /></button>
													<button
														type="button"
														onclick={() => changeStepOrder(1)}
														disabled={savingStep}
														class="rounded p-0.5 text-text-secondary/50 hover:text-text-primary disabled:opacity-20 transition-colors"
														title="Move down"
													><ChevronDown size={12} /></button>
												</div>
											</div>
										{/if}
									</div>
								</div>
								<button
									type="button"
									onclick={closeStepEditor}
									class="rounded-lg p-1.5 text-text-secondary/50 transition-colors hover:bg-surface-hover hover:text-text-primary"
									title="Close"
								>
									<X size={14} />
								</button>
							</div>
						</div>

						<!-- Panel body -->
						<div class="flex-1 overflow-y-auto">
							<form
								onsubmit={(e) => {
									e.preventDefault();
									saveStep();
								}}
								class="flex flex-col"
							>
								<!-- Section: Identity -->
								<div class="px-4 pt-4 pb-3 flex flex-col gap-3">
									<input
										type="text"
										bind:value={stepForm.name}
										required
										placeholder="Step name..."
										class="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-text-primary outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/20"
									/>
									<RichEditor
										value={stepForm.description}
										placeholder="Describe what this step does..."
										mode="compact"
										minHeight="64px"
										onchange={(md) => (stepForm.description = md)}
									/>
								</div>

								<!-- Section: Type selector (visual pills) -->
								<div class="border-t border-border/50 px-4 py-3">
									<span class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary/50 mb-2 block">Type</span>
									<div class="grid grid-cols-3 gap-1.5">
										{#each STEP_TYPES as t}
											{@const conf = STEP_TYPE_CONFIG[t]}
											{@const Icon = conf.icon}
											{@const isActive = stepForm.step_type === t}
											<button
												type="button"
												onclick={() => (stepForm.step_type = t)}
												class="flex flex-col items-center gap-1 rounded-lg border px-2 py-2 text-[10px] font-medium transition-all
													{isActive
													? conf.bg + ' ' + conf.color + ' ring-1 ring-current/20 shadow-sm'
													: 'border-border/50 text-text-secondary/60 hover:border-border hover:bg-surface-hover hover:text-text-secondary'}"
											>
												<Icon size={14} />
												{conf.label}
											</button>
										{/each}
									</div>
								</div>

								<!-- Section: System integration -->
								<div class="border-t border-border/50 px-4 py-3">
									<span class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary/50 mb-2 block">Integration</span>
									{#if stepForm.system_id}
										<div class="flex items-center gap-2 rounded-lg border border-border bg-surface-secondary/50 p-2.5">
											<div class="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10">
												<Server size={13} class="text-accent" />
											</div>
											<div class="flex-1 min-w-0">
												<div class="text-xs font-medium text-text-primary truncate">{stepForm.system_id}</div>
												<div class="text-[10px] text-text-secondary/50">System link</div>
											</div>
											<button
												type="button"
												onclick={() => (stepForm.system_id = '')}
												class="rounded p-1 text-text-secondary/40 hover:text-danger transition-colors"
											><X size={12} /></button>
										</div>
									{:else}
										<div class="relative">
											<Link2 size={13} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary/40" />
											<input
												type="text"
												bind:value={stepForm.system_id}
												placeholder="Link a system..."
												class="w-full rounded-lg border border-dashed border-border/60 bg-transparent pl-8 pr-3 py-2 text-xs text-text-primary outline-none transition-colors focus:border-accent focus:border-solid"
											/>
										</div>
									{/if}
									{#if editingStep.endpoint_id}
										<div class="mt-2 flex items-center gap-1.5 rounded-md bg-surface-secondary/50 px-2.5 py-1.5 text-[10px] text-text-secondary">
											<ArrowRight size={10} class="text-text-secondary/40" />
											<span class="font-mono truncate">{editingStep.endpoint_id}</span>
										</div>
									{/if}
								</div>

								<!-- Section: Data flow — Inputs & Outputs as chips -->
								<div class="border-t border-border/50 px-4 py-3">
									<span class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary/50 mb-2.5 block">Data Flow</span>

									<!-- Inputs -->
									<div class="mb-3">
										<div class="flex items-center gap-1.5 mb-1.5">
											<LogIn size={11} class="text-accent/60" />
											<span class="text-[10px] font-medium text-text-secondary">Inputs</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each stepForm.inputs as val}
												<span class="group inline-flex items-center gap-1 rounded-md border border-accent/15 bg-accent/5 px-2 py-0.5 text-[11px] font-mono text-accent transition-colors">
													{val}
													<button
														type="button"
														onclick={() => removeInput(val)}
														class="opacity-0 group-hover:opacity-100 text-accent/40 hover:text-danger transition-all"
													><X size={10} /></button>
												</span>
											{/each}
											<div class="inline-flex">
												<input
													type="text"
													bind:value={stepForm.newInput}
													placeholder={stepForm.inputs.length === 0 ? 'Add input...' : '+'}
													class="w-20 rounded-md border border-dashed border-border/40 bg-transparent px-2 py-0.5 text-[11px] font-mono text-text-primary outline-none transition-all focus:w-32 focus:border-accent/40"
													onkeydown={(e) => {
														if (e.key === 'Enter') { e.preventDefault(); addInput(); }
													}}
												/>
											</div>
										</div>
									</div>

									<!-- Outputs -->
									<div>
										<div class="flex items-center gap-1.5 mb-1.5">
											<LogOut size={11} class="text-success/60" />
											<span class="text-[10px] font-medium text-text-secondary">Outputs</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each stepForm.outputs as val}
												<span class="group inline-flex items-center gap-1 rounded-md border border-success/15 bg-success/5 px-2 py-0.5 text-[11px] font-mono text-success transition-colors">
													{val}
													<button
														type="button"
														onclick={() => removeOutput(val)}
														class="opacity-0 group-hover:opacity-100 text-success/40 hover:text-danger transition-all"
													><X size={10} /></button>
												</span>
											{/each}
											<div class="inline-flex">
												<input
													type="text"
													bind:value={stepForm.newOutput}
													placeholder={stepForm.outputs.length === 0 ? 'Add output...' : '+'}
													class="w-20 rounded-md border border-dashed border-border/40 bg-transparent px-2 py-0.5 text-[11px] font-mono text-text-primary outline-none transition-all focus:w-32 focus:border-success/40"
													onkeydown={(e) => {
														if (e.key === 'Enter') { e.preventDefault(); addOutput(); }
													}}
												/>
											</div>
										</div>
									</div>
								</div>

								<!-- Section: Dependencies (existing steps only) -->
								{#if !creatingStep && editingStep.id}
									<div class="border-t border-border/50 px-4 py-3">
										<span class="text-[10px] font-semibold uppercase tracking-wider text-text-secondary/50 mb-2 block">Dependencies</span>
										{#if incomingDeps.length > 0}
											<div class="flex flex-col gap-1.5">
												{#each incomingDeps as dep}
													{@const sourceStep = selectedProcess.steps.find((s) => s.id === dep.source_step_id)}
													{@const srcConf = getStepTypeConfig(sourceStep?.step_type)}
													{@const SrcIcon = srcConf.icon}
													<div class="group flex items-center gap-2 rounded-lg border border-border/50 bg-surface-secondary/30 px-2.5 py-2 transition-colors hover:bg-surface-secondary/60">
														<div class="flex h-6 w-6 items-center justify-center rounded-md {srcConf.bg}">
															<SrcIcon size={11} class={srcConf.color} />
														</div>
														<div class="flex-1 min-w-0">
															<div class="text-[11px] font-medium text-text-primary truncate">{sourceStep?.name ?? dep.source_step_id}</div>
															{#if dep.condition}
																<div class="text-[10px] text-text-secondary/50 truncate">when: {dep.condition}</div>
															{/if}
														</div>
														<button
															type="button"
															onclick={() => removeDependency(dep.source_step_id, dep.target_step_id)}
															class="rounded p-1 opacity-0 group-hover:opacity-100 text-text-secondary/40 hover:text-danger transition-all"
															title="Remove"
														><X size={12} /></button>
													</div>
												{/each}
											</div>
										{:else}
											<div class="flex items-center gap-2 rounded-lg border border-dashed border-border/40 px-3 py-2.5 text-[10px] text-text-secondary/40">
												<ArrowDownRight size={12} />
												No incoming dependencies
											</div>
										{/if}

										{#if addingDependency}
											<div class="mt-2 flex flex-col gap-2 rounded-lg border border-accent/20 bg-accent/5 p-3">
												<select
													bind:value={newDepSourceId}
													class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
												>
													<option value="">Select step...</option>
													{#each availableDepSources as step}
														{@const sConf = getStepTypeConfig(step.step_type)}
														<option value={step.id}>{sConf.label}: {step.name}</option>
													{/each}
												</select>
												<input
													type="text"
													bind:value={newDepCondition}
													placeholder="Condition (optional)"
													class="rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent"
												/>
												<div class="flex gap-2">
													<button
														type="button"
														onclick={() => { addingDependency = false; newDepSourceId = ''; newDepCondition = ''; }}
														class="flex-1 rounded-md border border-border px-2 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-hover"
													>Cancel</button>
													<button
														type="button"
														onclick={addDependency}
														disabled={!newDepSourceId}
														class="flex-1 rounded-md bg-accent px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
													>Add</button>
												</div>
											</div>
										{:else if availableDepSources.length > 0}
											<button
												type="button"
												onclick={() => (addingDependency = true)}
												class="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border/60 px-3 py-2 text-[11px] text-text-secondary/50 transition-colors hover:border-border hover:bg-surface-hover hover:text-text-secondary"
											>
												<Plus size={12} />
												Add dependency
											</button>
										{/if}
									</div>
								{/if}

								<!-- Action footer — sticky at bottom -->
								<div class="sticky bottom-0 border-t border-border bg-surface px-4 py-3">
									<div class="flex gap-2">
										<button
											type="button"
											onclick={closeStepEditor}
											class="flex-1 rounded-lg border border-border px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover"
										>Cancel</button>
										<button
											type="submit"
											disabled={savingStep}
											class="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
										>
											{#if savingStep}
												<Loader2 size={13} class="animate-spin" />
											{:else}
												<Save size={13} />
											{/if}
											{creatingStep ? 'Create' : 'Save'}
										</button>
									</div>
									{#if !creatingStep && editingStep.id}
										{#if confirmingStepDelete}
											<div class="mt-2 flex items-center gap-2 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2">
												<span class="flex-1 text-[11px] text-danger">Delete this step?</span>
												<button
													type="button"
													onclick={() => (confirmingStepDelete = false)}
													class="rounded px-2 py-0.5 text-[10px] text-text-secondary hover:bg-surface-hover"
												>No</button>
												<button
													type="button"
													onclick={deleteStep}
													disabled={savingStep}
													class="inline-flex items-center gap-1 rounded bg-danger px-2 py-0.5 text-[10px] font-medium text-white hover:bg-danger/90 disabled:opacity-50"
												>
													{#if savingStep}<Loader2 size={10} class="animate-spin" />{/if}
													Yes, delete
												</button>
											</div>
										{:else}
											<button
												type="button"
												onclick={() => (confirmingStepDelete = true)}
												class="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-danger/15 py-1.5 text-[11px] text-danger/50 transition-colors hover:border-danger/30 hover:bg-danger/5 hover:text-danger"
											>
												<Trash2 size={12} />
												Delete step
											</button>
										{/if}
									{/if}
								</div>
							</form>
						</div>
					</div>
				{/if}
			</div>
		{/if}
		</div>
	</div>
</div>
