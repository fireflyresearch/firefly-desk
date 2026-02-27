/**
 * Widget registry -- maps widget type strings to Svelte components.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import type { Component } from 'svelte';

import StatusBadge from '$lib/components/widgets/StatusBadge.svelte';
import EntityCard from '$lib/components/widgets/EntityCard.svelte';
import DataTable from '$lib/components/widgets/DataTable.svelte';
import ConfirmationCard from '$lib/components/widgets/ConfirmationCard.svelte';
import KeyValueList from '$lib/components/widgets/KeyValueList.svelte';
import AlertBanner from '$lib/components/widgets/AlertBanner.svelte';
import DiffViewer from '$lib/components/widgets/DiffViewer.svelte';
import Timeline from '$lib/components/widgets/Timeline.svelte';
import ExportCard from '$lib/components/widgets/ExportCard.svelte';
import SafetyPlanCard from '$lib/components/widgets/SafetyPlanCard.svelte';
import ImageCard from '$lib/components/widgets/ImageCard.svelte';
import ChartWidget from '$lib/components/widgets/ChartWidget.svelte';
import MermaidDiagram from '$lib/components/widgets/MermaidDiagram.svelte';
import CitationCard from '$lib/components/widgets/CitationCard.svelte';
import ProgressBar from '$lib/components/widgets/ProgressBar.svelte';
import AccordionWidget from '$lib/components/widgets/AccordionWidget.svelte';
import MetricCard from '$lib/components/widgets/MetricCard.svelte';
import CodeBlock from '$lib/components/widgets/CodeBlock.svelte';
import ActionButtons from '$lib/components/widgets/ActionButtons.svelte';
import FlowDiagram from '$lib/components/widgets/FlowDiagram.svelte';
import FileViewer from '$lib/components/widgets/FileViewer.svelte';
import EditableDataTable from '$lib/components/widgets/EditableDataTable.svelte';
import PaginatedTable from '$lib/components/widgets/PaginatedTable.svelte';
import DynamicFilter from '$lib/components/widgets/DynamicFilter.svelte';
import EntityView from '$lib/components/widgets/EntityView.svelte';
import TracesTimeline from '$lib/components/widgets/TracesTimeline.svelte';
import MetricsChart from '$lib/components/widgets/MetricsChart.svelte';
import ServiceMap from '$lib/components/widgets/ServiceMap.svelte';
import LogViewer from '$lib/components/widgets/LogViewer.svelte';
import SpanDetail from '$lib/components/widgets/SpanDetail.svelte';
import DynamicForm from '$lib/components/widgets/DynamicForm.svelte';

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const widgetRegistry: Record<string, Component<any>> = {
	'status-badge': StatusBadge,
	'entity-card': EntityCard,
	'data-table': DataTable,
	'confirmation': ConfirmationCard,
	'key-value': KeyValueList,
	'alert': AlertBanner,
	'diff-viewer': DiffViewer,
	'timeline': Timeline,
	'export': ExportCard,
	'safety-plan': SafetyPlanCard,
	'image': ImageCard,
	'chart': ChartWidget,
	'mermaid-diagram': MermaidDiagram,
	'citation-card': CitationCard,
	'progress-bar': ProgressBar,
	'accordion': AccordionWidget,
	'metric-card': MetricCard,
	'code-block': CodeBlock,
	'action-buttons': ActionButtons,
	'flow-diagram': FlowDiagram,
	'file_viewer': FileViewer,
	'editable-table': EditableDataTable,
	'paginated-table': PaginatedTable,
	'dynamic-filter': DynamicFilter,
	'entity-view': EntityView,
	'traces-timeline': TracesTimeline,
	'metrics-chart': MetricsChart,
	'service-map': ServiceMap,
	'log-viewer': LogViewer,
	'span-detail': SpanDetail,
	'dynamic-form': DynamicForm
};

// ---------------------------------------------------------------------------
// Lookup
// ---------------------------------------------------------------------------

/** Resolve a widget type string to its Svelte component, or undefined. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getWidget(type: string): Component<any> | undefined {
	return widgetRegistry[type];
}
