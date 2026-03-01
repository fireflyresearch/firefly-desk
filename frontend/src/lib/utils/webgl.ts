/*
 * WebGL capability detection.
 *
 * Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0.
 */

/** Returns `true` when the browser can create a WebGL (1 or 2) rendering context. */
export function isWebGLAvailable(): boolean {
	try {
		const canvas = document.createElement('canvas');
		const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
		return gl instanceof WebGL2RenderingContext || gl instanceof WebGLRenderingContext;
	} catch {
		return false;
	}
}
