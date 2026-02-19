<script setup>
import { ref, onMounted } from "vue";
import { setToken, getToken, clearToken, API_BASE } from "./api";
import GraphView from "./components/GraphView.vue";
import { Analytics } from '@vercel/analytics/vue';

const authError = ref("");
const authLoading = ref(false);
const loggedIn = ref(!!getToken());

function startLinkedInLogin() {
  authError.value = "";
  authLoading.value = true;
  window.location.href = `${API_BASE}/auth/linkedin/start`;
}

function handleLogout() {
  clearToken();
  loggedIn.value = false;
}

onMounted(() => {
  loggedIn.value = !!getToken();

  // Handle LinkedIn auth callback redirect: .../auth/callback?token=...
  const url = new URL(window.location.href);
  const token = url.searchParams.get("token");
  if (token) {
    setToken(token);
    loggedIn.value = true;
    authLoading.value = false;
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.toString());
  }
});
</script>

<template>
  <Analytics />
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <header class="sticky top-0 z-10 border-b border-gray-200 bg-white" role="banner">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div class="text-lg font-bold" aria-label="App Title">Six Degrees</div>
        <button
          v-if="loggedIn"
          class="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50"
          @click="handleLogout"
          aria-label="Logout"
        >
          Logout
        </button>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl px-4 py-6" role="main">
      <section v-if="!loggedIn" class="mx-auto w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm" aria-label="LinkedIn login">
        <h1 class="text-lg font-bold">Sign in</h1>
        <p class="mt-1 text-sm text-gray-600">Sign in with LinkedIn to access the app.</p>

        <button
          class="mt-5 inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          @click="startLinkedInLogin"
          :disabled="authLoading"
        >
          <span v-if="authLoading">Redirecting…</span>
          <span v-else>Continue with LinkedIn</span>
        </button>

        <p v-if="authError" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ authError }}</p>
      </section>

      <GraphView v-else />
    </main>
  </div>
</template>