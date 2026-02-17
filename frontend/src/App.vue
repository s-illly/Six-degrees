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
  <div class="min-h-screen font-sans">
    <header class="flex justify-between items-center px-4 py-3 border-b border-gray-200 bg-white" role="banner">
      <div class="font-bold text-xl" aria-label="App Title">Six Degrees</div>
      <button v-if="loggedIn" class="px-4 py-2 rounded border border-gray-300 bg-white hover:bg-gray-50 transition" @click="handleLogout" aria-label="Logout">Logout</button>
    </header>

    <main class="flex justify-center items-start p-6" role="main">
      <div v-if="!loggedIn" class="max-w-md w-full border border-gray-200 rounded-xl p-6 bg-white shadow" aria-label="Login Form">
        <h2 class="text-lg font-semibold mb-4">Login</h2>

        <form @submit.prevent="handleLogin" class="flex flex-col gap-4">
          <div>
            <label for="email" class="block text-sm mb-1">Email</label>
            <input
              id="email"
              v-model="email"
              type="email"
              placeholder="you@example.com"
              autocomplete="username"
              required
              aria-required="true"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-gray-900 focus:outline-none text-base"
            />
          </div>

          <div>
            <label for="password" class="block text-sm mb-1">Password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="••••••••"
              autocomplete="current-password"
              required
              aria-required="true"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-gray-900 focus:outline-none text-base"
            />
          </div>

          <button class="mt-2 px-4 py-2 rounded-lg border border-gray-900 bg-gray-900 text-white font-medium transition hover:bg-gray-700 disabled:opacity-60 disabled:cursor-not-allowed" type="submit" :disabled="loading">
            <span v-if="loading">Signing in...</span>
            <span v-else>Sign in</span>
          </button>
        </form>

        <p v-if="error" class="text-red-600 mt-3" role="alert">{{ error }}</p>
      </div>

      <GraphView v-else />
    </main>
  </div>
</template>