// File: DjangoVerseHub/static/js/main.js

/**
 * Main JavaScript file for DjangoVerseHub
 * Handles global functionality, theme management, and UI interactions
 */

class DjangoVerseHub {
  constructor() {
    this.init();
  }

  init() {
    this.bindEvents();
    this.initTheme();
    this.initTooltips();
    this.initModals();
    this.initAlerts();
    this.initForms();
    this.initSearch();
    this.initInfiniteScroll();
  }

  bindEvents() {
    document.addEventListener("DOMContentLoaded", () => {
      console.log("DjangoVerseHub initialized");
    });

    // Global click handler for dynamic elements
    document.addEventListener("click", this.handleGlobalClick.bind(this));

    // Global form submission handler
    document.addEventListener("submit", this.handleGlobalSubmit.bind(this));

    // Handle browser back/forward buttons
    window.addEventListener("popstate", this.handlePopState.bind(this));

    // Handle window resize
    window.addEventListener(
      "resize",
      this.debounce(this.handleResize.bind(this), 300)
    );

    // Handle scroll events
    window.addEventListener(
      "scroll",
      this.throttle(this.handleScroll.bind(this), 100)
    );
  }

  // Theme Management
  initTheme() {
    const savedTheme = localStorage.getItem("theme");
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;

    if (savedTheme) {
      this.setTheme(savedTheme);
    } else if (prefersDark) {
      this.setTheme("dark");
    }

    // Listen for theme changes
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", this.toggleTheme.bind(this));
    }
  }

  setTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    localStorage.setItem("theme", theme);

    // Update toggle button text
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
    }

    // Update meta theme-color
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute(
        "content",
        theme === "dark" ? "#212529" : "#0d6efd"
      );
    }

    // Trigger custom event
    document.dispatchEvent(
      new CustomEvent("themeChanged", { detail: { theme } })
    );
  }

  toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-bs-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    this.setTheme(newTheme);
  }

  // Tooltip Management
  initTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll(
      '[data-bs-toggle="tooltip"]'
    );
    const tooltipList = [...tooltipTriggerList].map(
      (tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl)
    );
  }

  // Modal Management
  initModals() {
    // Auto-focus first input in modals
    document.addEventListener("shown.bs.modal", (event) => {
      const modal = event.target;
      const firstInput = modal.querySelector("input, textarea, select");
      if (firstInput) {
        firstInput.focus();
      }
    });

    // Clear form data when modal is hidden
    document.addEventListener("hidden.bs.modal", (event) => {
      const modal = event.target;
      const form = modal.querySelector("form");
      if (form && form.getAttribute("data-clear-on-hide") !== "false") {
        form.reset();
        form.querySelectorAll(".is-invalid, .is-valid").forEach((el) => {
          el.classList.remove("is-invalid", "is-valid");
        });
      }
    });
  }

  // Alert Management
  initAlerts() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll(
      '.alert:not([data-auto-dismiss="false"])'
    );
    alerts.forEach((alert) => {
      setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
      }, 5000);
    });

    // Animate alert removal
    document.addEventListener("closed.bs.alert", (event) => {
      event.target.style.transition = "opacity 0.3s ease-out";
      event.target.style.opacity = "0";
    });
  }

  // Form Management
  initForms() {
    // Add floating label animation
    this.initFloatingLabels();

    // Add form validation
    this.initFormValidation();

    // Add file upload preview
    this.initFileUpload();

    // Add form auto-save
    this.initAutoSave();
  }

  initFloatingLabels() {
    const floatingInputs = document.querySelectorAll(
      ".form-floating input, .form-floating textarea"
    );
    floatingInputs.forEach((input) => {
      // Check if input has value on page load
      if (input.value) {
        input.classList.add("has-value");
      }

      input.addEventListener("input", () => {
        if (input.value) {
          input.classList.add("has-value");
        } else {
          input.classList.remove("has-value");
        }
      });
    });
  }

  initFormValidation() {
    // Real-time validation
    const forms = document.querySelectorAll(".needs-validation");
    forms.forEach((form) => {
      const inputs = form.querySelectorAll("input, textarea, select");
      inputs.forEach((input) => {
        input.addEventListener("blur", () => this.validateField(input));
        input.addEventListener("input", () => {
          if (input.classList.contains("is-invalid")) {
            this.validateField(input);
          }
        });
      });
    });
  }

  validateField(field) {
    const isValid = field.checkValidity();
    field.classList.toggle("is-valid", isValid);
    field.classList.toggle("is-invalid", !isValid);

    // Custom validation messages
    const feedback = field.parentNode.querySelector(".invalid-feedback");
    if (feedback && !isValid) {
      feedback.textContent =
        field.validationMessage || "Please provide a valid value.";
    }
  }

  initFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach((input) => {
      input.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file && file.type.startsWith("image/")) {
          this.previewImage(input, file);
        }
      });
    });
  }

  previewImage(input, file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      let preview = input.parentNode.querySelector(".image-preview");
      if (!preview) {
        preview = document.createElement("img");
        preview.className = "image-preview img-thumbnail mt-2";
        preview.style.maxWidth = "200px";
        preview.style.maxHeight = "200px";
        input.parentNode.appendChild(preview);
      }
      preview.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  initAutoSave() {
    const autoSaveForms = document.querySelectorAll('[data-auto-save="true"]');
    autoSaveForms.forEach((form) => {
      const inputs = form.querySelectorAll("input, textarea, select");
      inputs.forEach((input) => {
        input.addEventListener(
          "input",
          this.debounce(() => {
            this.autoSaveForm(form);
          }, 2000)
        );
      });
    });
  }

  autoSaveForm(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    // Save to localStorage
    const key = `autosave_${form.id || "form"}`;
    localStorage.setItem(key, JSON.stringify(data));

    // Show save indicator
    this.showToast("Draft saved", "info", 2000);
  }

  // Search Management
  initSearch() {
    const searchInput = document.querySelector("#global-search");
    if (searchInput) {
      searchInput.addEventListener(
        "input",
        this.debounce((e) => {
          this.performSearch(e.target.value);
        }, 300)
      );
    }
  }

  performSearch(query) {
    if (query.length < 2) return;

    // Show loading state
    const searchResults = document.querySelector("#search-results");
    if (searchResults) {
      searchResults.innerHTML =
        '<div class="text-center p-3"><div class="spinner-border spinner-border-sm"></div> Searching...</div>';
    }

    // Perform API call
    fetch(`/api/search/?q=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => this.displaySearchResults(data))
      .catch((error) => console.error("Search error:", error));
  }

  displaySearchResults(data) {
    const searchResults = document.querySelector("#search-results");
    if (!searchResults) return;

    if (data.results && data.results.length > 0) {
      const html = data.results
        .map(
          (result) => `
                <div class="search-result p-2 border-bottom">
                    <a href="${result.url}" class="text-decoration-none">
                        <h6 class="mb-1">${result.title}</h6>
                        <p class="mb-0 text-muted small">${result.description}</p>
                    </a>
                </div>
            `
        )
        .join("");
      searchResults.innerHTML = html;
    } else {
      searchResults.innerHTML =
        '<div class="text-center p-3 text-muted">No results found</div>';
    }
  }

  // Infinite Scroll
  initInfiniteScroll() {
    const scrollContainers = document.querySelectorAll(
      '[data-infinite-scroll="true"]'
    );
    scrollContainers.forEach((container) => {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              this.loadMoreContent(container);
            }
          });
        },
        { threshold: 0.1 }
      );

      const trigger = container.querySelector(".infinite-scroll-trigger");
      if (trigger) {
        observer.observe(trigger);
      }
    });
  }

  loadMoreContent(container) {
    const url = container.getAttribute("data-load-url");
    const page =
      parseInt(container.getAttribute("data-current-page") || "1") + 1;

    if (!url) return;

    // Show loading
    const trigger = container.querySelector(".infinite-scroll-trigger");
    if (trigger) {
      trigger.innerHTML =
        '<div class="text-center p-3"><div class="spinner-border"></div></div>';
    }

    fetch(`${url}?page=${page}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.results && data.results.length > 0) {
          // Append new content
          const content = container.querySelector(".infinite-scroll-content");
          if (content) {
            content.insertAdjacentHTML("beforeend", data.html);
          }

          container.setAttribute("data-current-page", page);

          // Reset trigger
          if (data.has_next) {
            trigger.innerHTML =
              '<div class="text-center p-2">Load more...</div>';
          } else {
            trigger.remove();
          }
        } else {
          trigger.remove();
        }
      })
      .catch((error) => {
        console.error("Load more error:", error);
        trigger.innerHTML =
          '<div class="text-center p-2 text-danger">Error loading content</div>';
      });
  }

  // Event Handlers
  handleGlobalClick(event) {
    const target = event.target;

    // Handle copy to clipboard
    if (target.matches("[data-copy]")) {
      event.preventDefault();
      this.copyToClipboard(target.getAttribute("data-copy"));
    }

    // Handle like/unlike buttons
    if (target.matches(".btn-like, .btn-unlike")) {
      event.preventDefault();
      this.handleLikeButton(target);
    }

    // Handle follow/unfollow buttons
    if (target.matches(".btn-follow, .btn-unfollow")) {
      event.preventDefault();
      this.handleFollowButton(target);
    }
  }

  handleGlobalSubmit(event) {
    const form = event.target;

    // Handle AJAX forms
    if (form.hasAttribute("data-ajax")) {
      event.preventDefault();
      this.submitFormAjax(form);
    }

    // Handle forms with loading states
    if (form.hasAttribute("data-loading")) {
      this.showFormLoading(form);
    }
  }

  handlePopState(event) {
    // Handle browser navigation
    if (event.state && event.state.page) {
      this.loadPage(event.state.page);
    }
  }

  handleResize() {
    // Handle responsive adjustments
    this.adjustLayout();
  }

  handleScroll() {
    // Handle scroll-based features
    this.updateScrollProgress();
    this.handleStickyElements();
  }

  // Utility Methods
  copyToClipboard(text) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        this.showToast("Copied to clipboard!", "success", 2000);
      })
      .catch(() => {
        this.showToast("Failed to copy", "error", 2000);
      });
  }

  showToast(message, type = "info", duration = 3000) {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) return;

    const toastId = `toast-${Date.now()}`;
    const toast = document.createElement("div");
    toast.id = toastId;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute("role", "alert");

    toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

    toastContainer.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, { delay: duration });
    bsToast.show();

    toast.addEventListener("hidden.bs.toast", () => {
      toast.remove();
    });
  }

  showLoading() {
    const spinner = document.getElementById("loading-spinner");
    if (spinner) {
      spinner.classList.remove("d-none");
    }
  }

  hideLoading() {
    const spinner = document.getElementById("loading-spinner");
    if (spinner) {
      spinner.classList.add("d-none");
    }
  }

  // Utility functions
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  throttle(func, limit) {
    let inThrottle;
    return function () {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }

  // CSRF Token helper
  getCsrfToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")
    );
  }

  // API helper
  async apiCall(url, options = {}) {
    const defaultOptions = {
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.getCsrfToken(),
      },
    };

    const response = await fetch(url, { ...defaultOptions, ...options });

    if (!response.ok) {
      throw new Error(`API call failed: ${response.statusText}`);
    }

    return response.json();
  }
}

// Initialize DjangoVerseHub when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  window.djangoVerseHub = new DjangoVerseHub();
});

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = DjangoVerseHub;
}
