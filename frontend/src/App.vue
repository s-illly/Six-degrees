<script setup>
import { ref, onMounted } from "vue";
import { api, setToken, getToken, clearToken } from "./api";
import GraphView from "./components/GraphView.vue";

const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const loggedIn = ref(!!getToken());

async function handleLogin() {
  error.value = "";
  loading.value = true;
  try {
    const res = await api.login(email.value, password.value);
    if (!res?.access_token) throw new Error("No access_token returned from backend");
    setToken(res.access_token);
    loggedIn.value = true;
  } catch (e) {
    error.value = e.message || "Login failed";
  } finally {
    loading.value = false;
  }
}

function handleLogout() {
  clearToken();
  loggedIn.value = false;
}

onMounted(() => {
  loggedIn.value = !!getToken();
});
</script>

<template>
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
      <section v-if="!loggedIn" class="mx-auto w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm" aria-label="Login Form">
        <h1 class="text-lg font-bold">Sign in</h1>
        <p class="mt-1 text-sm text-gray-600">Use your account email and password.</p>

        <form @submit.prevent="handleLogin" class="mt-5 space-y-4">
          <div>
            <label for="email" class="block text-sm font-semibold text-gray-800">Email</label>
            <input
              id="email"
              v-model="email"
              type="email"
              placeholder="you@example.com"
              autocomplete="username"
              required
              aria-required="true"
              class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label for="password" class="block text-sm font-semibold text-gray-800">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="••••••••"
              autocomplete="current-password"
              required
              aria-required="true"
              class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <button
            class="inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            :disabled="loading"
          >
            <span v-if="loading">Signing in…</span>
            <span v-else>Sign in</span>
          </button>
        </form>

        <p v-if="error" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{{ error }}</p>
      </section>

      <GraphView v-else />
    </main>
  </div>
</template>