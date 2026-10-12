/* Dashboard access token stays in this browser tab and is used only for local API requests. */
(() => {
  const originalFetch = window.fetch.bind(window);
  const configRequest = originalFetch('/api/config', { cache: 'no-store' })
    .then(response => response.ok ? response.json() : {})
    .catch(() => ({}));

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, window.location.href);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/') || url.pathname === '/api/config') {
      return originalFetch(input, init);
    }

    const config = await configRequest;
    if (!config.auth_required) return originalFetch(input, init);

    let token = sessionStorage.getItem('cda-access-token') || '';
    const askForToken = () => {
      token = window.prompt('Enter the CodeDebugArena dashboard access token:') || '';
      if (token) sessionStorage.setItem('cda-access-token', token);
      else sessionStorage.removeItem('cda-access-token');
    };
    if (!token) askForToken();

    const authorizedFetch = () => {
      const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined));
      headers.set('Authorization', `Bearer ${token}`);
      return originalFetch(input, { ...init, headers });
    };

    let response = await authorizedFetch();
    if (response.status === 401) {
      sessionStorage.removeItem('cda-access-token');
      askForToken();
      if (token) response = await authorizedFetch();
    }
    return response;
  };
})();

