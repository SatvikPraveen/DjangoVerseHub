// File: DjangoVerseHub/static/js/notifications.js

/**
 * Notifications system with WebSocket support
 * Handles real-time notifications, push notifications, and notification management
 */

class NotificationManager {
  constructor() {
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.notifications = [];
    this.unreadCount = 0;

    this.init();
  }

  init() {
    this.initWebSocket();
    this.initPushNotifications();
    this.bindEvents();
    this.loadNotifications();
    this.updateUI();
  }

  // WebSocket Management
  initWebSocket() {
    if (!window.WebSocket) {
      console.warn("WebSocket not supported");
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

    try {
      this.socket = new WebSocket(wsUrl);
      this.setupWebSocketHandlers();
    } catch (error) {
      console.error("WebSocket connection failed:", error);
    }
  }

  setupWebSocketHandlers() {
    this.socket.onopen = (event) => {
      console.log("WebSocket connected");
      this.reconnectAttempts = 0;
      this.updateConnectionStatus(true);
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleWebSocketMessage(data);
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };

    this.socket.onclose = (event) => {
      console.log("WebSocket disconnected");
      this.updateConnectionStatus(false);

      if (
        !event.wasClean &&
        this.reconnectAttempts < this.maxReconnectAttempts
      ) {
        setTimeout(() => this.reconnect(), this.reconnectDelay);
      }
    };

    this.socket.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }

  handleWebSocketMessage(data) {
    switch (data.type) {
      case "notification":
        this.addNotification(data.notification);
        break;
      case "notification_read":
        this.markAsRead(data.notification_id);
        break;
      case "notification_count":
        this.updateUnreadCount(data.count);
        break;
      case "ping":
        this.sendPong();
        break;
      default:
        console.log("Unknown WebSocket message type:", data.type);
    }
  }

  reconnect() {
    this.reconnectAttempts++;
    console.log(
      `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectDelay *= 1.5; // Exponential backoff
    this.initWebSocket();
  }

  sendPong() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: "pong" }));
    }
  }

  // Push Notifications
  async initPushNotifications() {
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      console.warn("Push notifications not supported");
      return;
    }

    // Check current permission
    if (Notification.permission === "granted") {
      this.registerServiceWorker();
    } else if (Notification.permission === "default") {
      this.showNotificationPermissionPrompt();
    }
  }

  async requestNotificationPermission() {
    try {
      const permission = await Notification.requestPermission();

      if (permission === "granted") {
        this.registerServiceWorker();
        this.showToast("Notifications enabled!", "success");
      } else {
        this.showToast("Notifications disabled", "warning");
      }

      return permission;
    } catch (error) {
      console.error("Error requesting notification permission:", error);
      return "denied";
    }
  }

  async registerServiceWorker() {
    try {
      const registration = await navigator.serviceWorker.register(
        "/static/js/cache-sw.js"
      );
      console.log("Service Worker registered:", registration);

      // Subscribe to push notifications
      await this.subscribeToPushNotifications(registration);
    } catch (error) {
      console.error("Service Worker registration failed:", error);
    }
  }

  async subscribeToPushNotifications(registration) {
    try {
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(
          window.VAPID_PUBLIC_KEY || ""
        ),
      });

      // Send subscription to server
      await this.sendSubscriptionToServer(subscription);
    } catch (error) {
      console.error("Push subscription failed:", error);
    }
  }

  async sendSubscriptionToServer(subscription) {
    try {
      const response = await fetch("/api/notifications/subscribe/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
        body: JSON.stringify(subscription),
      });

      if (response.ok) {
        console.log("Push subscription sent to server");
      }
    } catch (error) {
      console.error("Error sending subscription to server:", error);
    }
  }

  urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/\-/g, "+")
      .replace(/_/g, "/");
    const rawData = window.atob(base64);
    return new Uint8Array([...rawData].map((char) => char.charCodeAt(0)));
  }

  // Notification Management
  async loadNotifications() {
    try {
      const response = await fetch("/api/notifications/");
      const data = await response.json();

      this.notifications = data.results || [];
      this.unreadCount = data.unread_count || 0;
      this.updateUI();
    } catch (error) {
      console.error("Error loading notifications:", error);
    }
  }

  addNotification(notification) {
    // Add to beginning of array
    this.notifications.unshift(notification);

    // Limit to 50 notifications in memory
    if (this.notifications.length > 50) {
      this.notifications = this.notifications.slice(0, 50);
    }

    if (!notification.read) {
      this.unreadCount++;
    }

    this.updateUI();
    this.showNotificationToast(notification);

    // Show browser notification if permission granted
    if (Notification.permission === "granted") {
      this.showBrowserNotification(notification);
    }
  }

  async markAsRead(notificationId) {
    try {
      const response = await fetch(
        `/api/notifications/${notificationId}/read/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": this.getCsrfToken(),
          },
        }
      );

      if (response.ok) {
        // Update local state
        const notification = this.notifications.find(
          (n) => n.id === notificationId
        );
        if (notification && !notification.read) {
          notification.read = true;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
          this.updateUI();
        }
      }
    } catch (error) {
      console.error("Error marking notification as read:", error);
    }
  }

  async markAllAsRead() {
    try {
      const response = await fetch("/api/notifications/mark-all-read/", {
        method: "POST",
        headers: {
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        // Update all notifications to read
        this.notifications.forEach((n) => (n.read = true));
        this.unreadCount = 0;
        this.updateUI();
        this.showToast("All notifications marked as read", "success");
      }
    } catch (error) {
      console.error("Error marking all notifications as read:", error);
    }
  }

  async deleteNotification(notificationId) {
    try {
      const response = await fetch(`/api/notifications/${notificationId}/`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        // Remove from local array
        const index = this.notifications.findIndex(
          (n) => n.id === notificationId
        );
        if (index > -1) {
          const notification = this.notifications[index];
          this.notifications.splice(index, 1);

          if (!notification.read) {
            this.unreadCount = Math.max(0, this.unreadCount - 1);
          }

          this.updateUI();
        }
      }
    } catch (error) {
      console.error("Error deleting notification:", error);
    }
  }

  // UI Management
  updateUI() {
    this.updateBadge();
    this.updateDropdown();
  }

  updateBadge() {
    const badges = document.querySelectorAll(".notification-badge");
    badges.forEach((badge) => {
      if (this.unreadCount > 0) {
        badge.textContent = this.unreadCount > 99 ? "99+" : this.unreadCount;
        badge.classList.remove("d-none");
      } else {
        badge.classList.add("d-none");
      }
    });
  }

  updateDropdown() {
    const dropdown = document.querySelector(".notification-dropdown");
    if (!dropdown) return;

    const container = dropdown.querySelector(".notification-list") || dropdown;

    if (this.notifications.length === 0) {
      container.innerHTML = `
                <div class="text-center p-3 text-muted">
                    <i class="bi bi-bell fs-1 mb-2 d-block"></i>
                    <p class="mb-0">No notifications yet</p>
                </div>
            `;
      return;
    }

    const html = this.notifications
      .slice(0, 10)
      .map(
        (notification) => `
            <div class="notification-item dropdown-item d-flex align-items-start p-3 ${
              notification.read ? "" : "bg-light"
            }" 
                 data-notification-id="${notification.id}">
                <div class="flex-shrink-0 me-3">
                    <i class="bi ${this.getNotificationIcon(
                      notification.type
                    )} text-${this.getNotificationColor(
          notification.type
        )}"></i>
                </div>
                <div class="flex-grow-1 min-w-0">
                    <p class="mb-1 fw-semibold">${this.escapeHtml(
                      notification.title
                    )}</p>
                    <p class="mb-1 text-muted small">${this.escapeHtml(
                      notification.message
                    )}</p>
                    <small class="text-muted">${this.timeAgo(
                      notification.created_at
                    )}</small>
                </div>
                <div class="flex-shrink-0 ms-2">
                    <button class="btn btn-sm btn-outline-secondary btn-delete-notification" 
                            data-notification-id="${
                              notification.id
                            }" title="Delete">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        `
      )
      .join("");

    // Add header and footer
    const fullHtml = `
            <div class="dropdown-header d-flex justify-content-between align-items-center">
                <span>Notifications</span>
                ${
                  this.unreadCount > 0
                    ? `<button class="btn btn-sm btn-outline-primary btn-mark-all-read">Mark all read</button>`
                    : ""
                }
            </div>
            ${html}
            <div class="dropdown-divider"></div>
            <div class="text-center p-2">
                <a href="/notifications/" class="btn btn-sm btn-primary">View all notifications</a>
            </div>
        `;

    container.innerHTML = fullHtml;
  }

  updateConnectionStatus(connected) {
    const indicator = document.querySelector(".connection-status");
    if (indicator) {
      indicator.classList.toggle("connected", connected);
      indicator.title = connected ? "Connected" : "Disconnected";
    }
  }

  updateUnreadCount(count) {
    this.unreadCount = count;
    this.updateBadge();
  }

  // Event Handlers
  bindEvents() {
    // Notification dropdown clicks
    document.addEventListener("click", (event) => {
      const target = event.target;

      // Mark as read when clicked
      if (target.closest(".notification-item")) {
        const item = target.closest(".notification-item");
        const notificationId = item.dataset.notificationId;
        this.markAsRead(parseInt(notificationId));
      }

      // Delete notification
      if (target.closest(".btn-delete-notification")) {
        event.stopPropagation();
        const btn = target.closest(".btn-delete-notification");
        const notificationId = btn.dataset.notificationId;
        this.deleteNotification(parseInt(notificationId));
      }

      // Mark all as read
      if (target.closest(".btn-mark-all-read")) {
        event.stopPropagation();
        this.markAllAsRead();
      }

      // Enable notifications button
      if (target.closest(".btn-enable-notifications")) {
        event.preventDefault();
        this.requestNotificationPermission();
      }
    });
  }

  // Notification Display
  showNotificationToast(notification) {
    const toast = this.createToast({
      title: notification.title,
      message: notification.message,
      type: this.getNotificationColor(notification.type),
      duration: 5000,
    });

    this.showToast(toast);
  }

  showBrowserNotification(notification) {
    const options = {
      body: notification.message,
      icon: "/static/images/logo.svg",
      badge: "/static/images/logo.svg",
      tag: `notification-${notification.id}`,
      requireInteraction: false,
      data: {
        id: notification.id,
        url: notification.url,
      },
    };

    const browserNotification = new Notification(notification.title, options);

    browserNotification.onclick = () => {
      window.focus();
      if (notification.url) {
        window.location.href = notification.url;
      }
      browserNotification.close();
      this.markAsRead(notification.id);
    };

    // Auto-close after 5 seconds
    setTimeout(() => browserNotification.close(), 5000);
  }

  showNotificationPermissionPrompt() {
    const prompt = document.createElement("div");
    prompt.className =
      "alert alert-info alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3";
    prompt.style.zIndex = "9999";
    prompt.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="bi bi-bell me-2"></i>
                <div class="flex-grow-1">
                    <strong>Enable notifications?</strong>
                    <div class="small">Get notified about new messages and updates</div>
                </div>
                <button class="btn btn-sm btn-primary me-2 btn-enable-notifications">Enable</button>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

    document.body.appendChild(prompt);

    // Auto-remove after 10 seconds
    setTimeout(() => {
      if (prompt.parentNode) {
        prompt.remove();
      }
    }, 10000);
  }

  // Utility Methods
  getNotificationIcon(type) {
    const icons = {
      like: "bi-heart-fill",
      comment: "bi-chat-fill",
      follow: "bi-person-plus-fill",
      mention: "bi-at",
      system: "bi-gear-fill",
      warning: "bi-exclamation-triangle-fill",
      success: "bi-check-circle-fill",
      error: "bi-x-circle-fill",
      info: "bi-info-circle-fill",
    };
    return icons[type] || "bi-bell-fill";
  }

  getNotificationColor(type) {
    const colors = {
      like: "danger",
      comment: "primary",
      follow: "success",
      mention: "warning",
      system: "secondary",
      warning: "warning",
      success: "success",
      error: "danger",
      info: "info",
    };
    return colors[type] || "primary";
  }

  escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

    return date.toLocaleDateString();
  }

  getCsrfToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")
    );
  }

  showToast(message, type = "info", duration = 3000) {
    if (window.djangoVerseHub) {
      window.djangoVerseHub.showToast(message, type, duration);
    }
  }

  createToast(options) {
    return {
      title: options.title,
      message: options.message,
      type: options.type || "info",
      duration: options.duration || 3000,
    };
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  window.notificationManager = new NotificationManager();
});

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = NotificationManager;
}
