<!--
  SpeechToText.svelte - Microphone button with Web Speech API.

  Uses SpeechRecognition for continuous speech-to-text. Shows red
  pulse animation when recording. Gracefully hides if API unavailable.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Mic, MicOff } from 'lucide-svelte';
	import { onMount } from 'svelte';

	interface SpeechToTextProps {
		onTranscript: (text: string) => void;
		disabled?: boolean;
	}

	let { onTranscript, disabled = false }: SpeechToTextProps = $props();

	let supported = $state(false);
	let recording = $state(false);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let recognition: any = $state(null);

	onMount(() => {
		const SpeechRecognitionCtor =
			(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
		if (SpeechRecognitionCtor) {
			supported = true;
			const rec = new SpeechRecognitionCtor();
			rec.continuous = true;
			rec.interimResults = true;
			rec.lang = navigator.language || 'en-US';

			let finalTranscript = '';

			rec.onresult = (event: any) => {
				let interim = '';
				for (let i = event.resultIndex; i < event.results.length; i++) {
					const result = event.results[i];
					if (result.isFinal) {
						finalTranscript += result[0].transcript;
					} else {
						interim += result[0].transcript;
					}
				}
				if (interim) {
					onTranscript(interim);
				}
				if (finalTranscript) {
					onTranscript(finalTranscript);
					finalTranscript = '';
				}
			};

			rec.onerror = (event: any) => {
				console.warn('[SpeechToText] Error:', event.error);
				recording = false;
			};

			rec.onend = () => {
				recording = false;
			};

			recognition = rec;
		}
	});

	function toggle() {
		if (!recognition || disabled) return;

		if (recording) {
			recognition.stop();
			recording = false;
		} else {
			try {
				recognition.start();
				recording = true;
			} catch {
				// Already started
				recording = false;
			}
		}
	}
</script>

{#if supported}
	<button
		type="button"
		onclick={toggle}
		disabled={disabled}
		class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors
			{recording
			? 'bg-danger/15 text-danger animate-pulse'
			: 'text-text-secondary hover:bg-surface-secondary hover:text-text-primary'}
			disabled:cursor-not-allowed disabled:opacity-40"
		aria-label={recording ? 'Stop recording' : 'Start voice input'}
		title={recording ? 'Stop recording' : 'Voice input'}
	>
		{#if recording}
			<MicOff size={16} />
		{:else}
			<Mic size={16} />
		{/if}
	</button>
{/if}
