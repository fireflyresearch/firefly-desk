<!--
  Redirect: /admin/sso-mappings → /admin/sso
  SSO attribute mappings are managed within the Single Sign-On page.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/admin/sso', { replaceState: true });
	});
</script>
