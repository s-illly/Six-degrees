const API_BASE = "http://127.0.0.1:8000";

export function getToken() {
    return localStorage.getItem("token");
}

export function setToken(token) {
    localStorage.setItem("token", token);
}

export function clearToken() {
    localStorage.removeItem("token");
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Try to parse JSON no matter what
  let data = null;
  try {
    data = await res.json();
  } catch {
    // non-json response
  }

  if (!res.ok) {
    const msg = data?.detail || `Request failed (${res.status})`;
    throw new Error(msg);
  }

  return data;
}


export const api = {
    login: (email, password) => request("/login", { method: "POST", body: { email, password }}),
    graph: () => request("/graph"),
    connectionsList: () => request("/connections"),
    addConnection: ({ linkedin_slug, full_name = "" }) =>
      request("/connections", { method: "POST", body: { linkedin_slug, full_name } }),
    me: () => request("/me"),
};

