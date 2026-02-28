/**
 * Jobs API client.
 *
 * Wraps the background-jobs REST endpoints for listing and fetching
 * individual job records.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

import { apiJson } from './api.js';

export interface Job {
	id: string;
	job_type: string;
	status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
	progress_pct: number;
	progress_message: string;
	result: any;
	error: string | null;
	created_at: string | null;
	started_at: string | null;
	completed_at: string | null;
}

export interface JobFilters {
	job_type?: string;
	status?: string;
	limit?: number;
	offset?: number;
}

export async function fetchJobs(filters?: JobFilters): Promise<Job[]> {
	const params = new URLSearchParams();
	if (filters?.job_type) params.set('job_type', filters.job_type);
	if (filters?.status) params.set('status', filters.status);
	if (filters?.limit) params.set('limit', String(filters.limit));
	if (filters?.offset) params.set('offset', String(filters.offset));
	const qs = params.toString();
	return apiJson<Job[]>(`/jobs${qs ? '?' + qs : ''}`);
}

export async function fetchJob(id: string): Promise<Job> {
	return apiJson<Job>(`/jobs/${id}`);
}
