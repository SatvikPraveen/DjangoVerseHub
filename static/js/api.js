// File: DjangoVerseHub/static/js/api.js

/**
 * API Client for DjangoVerseHub
 * Handles all AJAX API calls with authentication, error handling, and caching
 */

class APIClient {
  constructor(baseURL = "/api/") {
    this.baseURL = baseURL;
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    this.requestQueue = new Map();
    this.retryAttempts = 3;
    this.retryDelay = 1000;

    this.init();
  }

  init() {
    this.setupInterceptors();
    this.bindEvents();
  }

  setupInterceptors() {
    // Add request interceptor for authentication
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-CSRFToken": this.getCsrfToken(),
      "X-Requested-With": "XMLHttpRequest",
    };

    // Add response interceptor for global error handling
    window.addEventListener("beforeunload", () => {
      this.abortAllRequests();
    });
  }

  bindEvents() {
    // Handle authentication events
    document.addEventListener("userLoggedIn", (event) => {
      this.clearCache();
      this.updateAuthHeaders(event.detail.token);
    });

    document.addEventListener("userLoggedOut", () => {
      this.clearCache();
      this.clearAuthHeaders();
    });
  }

  // Core HTTP Methods
  async get(endpoint, options = {}) {
    return this.request("GET", endpoint, null, options);
  }

  async post(endpoint, data = null, options = {}) {
    return this.request("POST", endpoint, data, options);
  }

  async put(endpoint, data = null, options = {}) {
    return this.request("PUT", endpoint, data, options);
  }

  async patch(endpoint, data = null, options = {}) {
    return this.request("PATCH", endpoint, data, options);
  }

  async delete(endpoint, options = {}) {
    return this.request("DELETE", endpoint, null, options);
  }

  // Main request method
  async request(method, endpoint, data = null, options = {}) {
    const config = this.buildRequestConfig(method, endpoint, data, options);

    // Check cache for GET requests
    if (method === "GET" && options.cache !== false) {
      const cached = this.getFromCache(config.cacheKey);
      if (cached) {
        return cached;
      }
    }

    // Deduplicate identical requests
    if (config.dedupe !== false) {
      const existing = this.requestQueue.get(config.cacheKey);
      if (existing) {
        return existing;
      }
    }

    // Create and execute request
    const requestPromise = this.executeRequest(config);

    // Store in request queue
    if (config.dedupe !== false) {
      this.requestQueue.set(config.cacheKey, requestPromise);
    }

    try {
      const response = await requestPromise;

      // Cache successful GET requests
      if (method === "GET" && options.cache !== false && response.ok) {
        this.setCache(config.cacheKey, response.data, config.cacheTTL);
      }

      return response;
    } finally {
      // Remove from request queue
      this.requestQueue.delete(config.cacheKey);
    }
  }

  buildRequestConfig(method, endpoint, data, options) {
    const url = this.buildURL(endpoint);
    const cacheKey = this.buildCacheKey(method, url, data);

    return {
      method,
      url,
      data,
      cacheKey,
      headers: { ...this.defaultHeaders, ...options.headers },
      timeout: options.timeout || 30000,
      retries: options.retries ?? this.retryAttempts,
      cacheTTL: options.cacheTTL || this.cacheTimeout,
      dedupe: options.dedupe,
      signal: options.signal || null,
    };
  }

  async executeRequest(config) {
    let attempt = 0;
    let lastError;

    while (attempt <= config.retries) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), config.timeout);

        const response = await fetch(config.url, {
          method: config.method,
          headers: config.headers,
          body: config.data ? JSON.stringify(config.data) : null,
          signal: config.signal || controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new APIError(
            response.status,
            response.statusText,
            await response.json().catch(() => null)
          );
        }

        const responseData = await response.json().catch(() => null);
        return {
          ok: true,
          status: response.status,
          data: responseData,
          headers: response.headers,
        };
      } catch (error) {
        lastError = error;
        attempt++;

        if (attempt <= config.retries && this.shouldRetry(error)) {
          await this.delay(this.retryDelay * Math.pow(2, attempt - 1));
          continue;
        }
        break;
      }
    }

    throw lastError;
  }

  // API Endpoints - Users
  async getUsers(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`users/?${query}`);
  }

  async getUser(userId) {
    return this.get(`users/${userId}/`);
  }

  async updateUser(userId, data) {
    return this.patch(`users/${userId}/`, data);
  }

  async getCurrentUser() {
    return this.get("users/me/");
  }

  async updateProfile(data) {
    return this.patch("profiles/me/", data);
  }

  async changePassword(data) {
    return this.post("users/change-password/", data);
  }

  // API Endpoints - Articles
  async getArticles(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`articles/?${query}`);
  }

  async getArticle(articleId) {
    return this.get(`articles/${articleId}/`);
  }

  async createArticle(data) {
    return this.post("articles/", data);
  }

  async updateArticle(articleId, data) {
    return this.patch(`articles/${articleId}/`, data);
  }

  async deleteArticle(articleId) {
    return this.delete(`articles/${articleId}/`);
  }

  async likeArticle(articleId) {
    return this.post(`articles/${articleId}/like/`);
  }

  async bookmarkArticle(articleId) {
    return this.post(`articles/${articleId}/bookmark/`);
  }

  // API Endpoints - Comments
  async getComments(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`comments/?${query}`);
  }

  async createComment(data) {
    return this.post("comments/", data);
  }

  async updateComment(commentId, data) {
    return this.patch(`comments/${commentId}/`, data);
  }

  async deleteComment(commentId) {
    return this.delete(`comments/${commentId}/`);
  }

  async likeComment(commentId) {
    return this.post(`comments/${commentId}/like/`);
  }

  // API Endpoints - Notifications
  async getNotifications(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`notifications/?${query}`);
  }

  async markNotificationRead(notificationId) {
    return this.post(`notifications/${notificationId}/read/`);
  }

  async markAllNotificationsRead() {
    return this.post("notifications/mark-all-read/");
  }

  async deleteNotification(notificationId) {
    return this.delete(`notifications/${notificationId}/`);
  }

  // API Endpoints - Search
  async search(query, type = "all") {
    const params = new URLSearchParams({ q: query, type });
    return this.get(`search/?${params}`);
  }

  async searchUsers(query) {
    return this.search(query, "users");
  }

  async searchArticles(query) {
    return this.search(query, "articles");
  }

  // File Upload
  async uploadFile(file, endpoint = "upload/") {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(this.buildURL(endpoint), {
      method: "POST",
      headers: {
        "X-CSRFToken": this.getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: formData,
    });

    if (!response.ok) {
      throw new APIError(response.status, response.statusText);
    }

    return response.json();
  }

  // Utility Methods
  buildURL(endpoint) {
    const cleanEndpoint = endpoint.startsWith("/")
      ? endpoint.slice(1)
      : endpoint;
    return `${this.baseURL}${cleanEndpoint}`;
  }

  buildCacheKey(method, url, data) {
    return `${method}:${url}:${data ? JSON.stringify(data) : ""}`;
  }

  getCsrfToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content") ||
      ""
    );
  }

  updateAuthHeaders(token) {
    this.defaultHeaders["Authorization"] = `Bearer ${token}`;
  }

  clearAuthHeaders() {
    delete this.defaultHeaders["Authorization"];
  }

  // Cache Management
  setCache(key, data, ttl) {
    this.cache.set(key, {
      data,
      expires: Date.now() + ttl,
    });
  }

  getFromCache(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() < cached.expires) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  clearCache() {
    this.cache.clear();
  }

  // Request Management
  abortAllRequests() {
    this.requestQueue.clear();
  }

  shouldRetry(error) {
    if (error instanceof APIError) {
      return error.status >= 500 || error.status === 429;
    }
    return error.name === "TypeError" || error.name === "AbortError";
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Custom Error Class
class APIError extends Error {
  constructor(status, statusText, data = null) {
    super(`API Error: ${status} ${statusText}`);
    this.name = "APIError";
    this.status = status;
    this.statusText = statusText;
    this.data = data;
  }
}

// AJAX Form Handler
class AjaxFormHandler {
  constructor(apiClient) {
    this.api = apiClient;
    this.init();
  }

  init() {
    document.addEventListener("submit", (event) => {
      const form = event.target;
      if (form.hasAttribute("data-ajax")) {
        event.preventDefault();
        this.handleFormSubmit(form);
      }
    });
  }

  async handleFormSubmit(form) {
    const submitBtn = form.querySelector('[type="submit"]');
    const originalText = submitBtn?.textContent;

    try {
      // Show loading state
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
      }

      // Get form data
      const formData = new FormData(form);
      const data = Object.fromEntries(formData);

      // Determine HTTP method and endpoint
      const method = form.getAttribute("data-method") || "POST";
      const endpoint =
        form.getAttribute("action") || form.getAttribute("data-endpoint");

      if (!endpoint) {
        throw new Error("No endpoint specified");
      }

      // Make API call
      let response;
      switch (method.toLowerCase()) {
        case "post":
          response = await this.api.post(endpoint, data);
          break;
        case "patch":
          response = await this.api.patch(endpoint, data);
          break;
        case "put":
          response = await this.api.put(endpoint, data);
          break;
        default:
          throw new Error(`Unsupported method: ${method}`);
      }

      // Handle success
      this.handleFormSuccess(form, response);
    } catch (error) {
      this.handleFormError(form, error);
    } finally {
      // Reset loading state
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
    }
  }

  handleFormSuccess(form, response) {
    // Clear form if specified
    if (form.hasAttribute("data-clear-on-success")) {
      form.reset();
    }

    // Show success message
    const message = form.getAttribute("data-success-message") || "Success!";
    this.showMessage(message, "success");

    // Redirect if specified
    const redirectUrl =
      form.getAttribute("data-redirect") || response.data?.redirect_url;
    if (redirectUrl) {
      setTimeout(() => {
        window.location.href = redirectUrl;
      }, 1000);
    }

    // Trigger custom event
    form.dispatchEvent(
      new CustomEvent("ajaxSuccess", {
        detail: { response, form },
      })
    );
  }

  handleFormError(form, error) {
    // Clear previous errors
    form.querySelectorAll(".is-invalid").forEach((el) => {
      el.classList.remove("is-invalid");
    });
    form.querySelectorAll(".invalid-feedback").forEach((el) => {
      el.textContent = "";
    });

    // Handle field-specific errors
    if (error instanceof APIError && error.data) {
      Object.entries(error.data).forEach(([field, messages]) => {
        const fieldEl = form.querySelector(`[name="${field}"]`);
        if (fieldEl) {
          fieldEl.classList.add("is-invalid");
          const feedback =
            fieldEl.parentNode.querySelector(".invalid-feedback");
          if (feedback) {
            feedback.textContent = Array.isArray(messages)
              ? messages[0]
              : messages;
          }
        }
      });
    }

    // Show general error message
    const message = error.message || "An error occurred";
    this.showMessage(message, "error");

    // Trigger custom event
    form.dispatchEvent(
      new CustomEvent("ajaxError", {
        detail: { error, form },
      })
    );
  }

  showMessage(message, type) {
    if (window.djangoVerseHub) {
      window.djangoVerseHub.showToast(message, type);
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  window.apiClient = new APIClient();
  window.ajaxFormHandler = new AjaxFormHandler(window.apiClient);
});

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = { APIClient, APIError, AjaxFormHandler };
}
