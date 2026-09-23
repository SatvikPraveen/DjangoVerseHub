// File: DjangoVerseHub/static/js/notifications.js
/**
 * Real-time notifications client (no dependencies).
 *
 * - Connects to /ws/notifications/ and reconnects with exponential backoff.
 * - Keeps the navbar badge (#notificationsDropdown .badge) in sync.
 * - Shows a toast for each incoming notification (uses window.djangoVerseHub.showToast
 *   when available, otherwise a tiny built-in toast).
 * - Wires [data-notification-action="mark-read|delete|mark-all-read"] buttons and the
 *   live feed on the notifications pages.
 *
 * Protocol: see apps/notifications/consumers.py.
 */
(function (window, document) {
  "use strict";

  if (window.NotificationClient) return; // guard against double inclusion

  var DEFAULT_ENDPOINTS = {
    markRead: "/notifications/api/0/read/",
    del: "/notifications/api/0/delete/",
    markAllRead: "/notifications/api/read-all/",
    unreadCount: "/notifications/api/unread-count/",
  };

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function getCsrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute("content");
    return getCookie("csrftoken") || "";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function NotificationClient(options) {
    options = options || {};
    var page = document.getElementById("notification-page");
    var data = page ? page.dataset : {};

    this.endpoints = {
      markRead: data.markReadUrlTemplate || DEFAULT_ENDPOINTS.markRead,
      del: data.deleteUrlTemplate || DEFAULT_ENDPOINTS.del,
      markAllRead: data.markAllReadUrl || DEFAULT_ENDPOINTS.markAllRead,
      unreadCount: data.unreadCountUrl || DEFAULT_ENDPOINTS.unreadCount,
    };
    this.wsPath = options.wsPath || "/ws/notifications/";
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
    this.baseDelay = options.baseDelay || 1000;
    this.maxDelay = options.maxDelay || 30000;
    this.reconnectTimer = null;
    this.closedByUs = false;
    this.unreadCount = this.readBadgeValue();
    this.enabled = !!document.getElementById("notificationsDropdown") || !!page;

    this.bindEvents();
    if (this.enabled) this.connect();
  }

  // ------------------------------------------------------------ WebSocket
  NotificationClient.prototype.connect = function () {
    if (!("WebSocket" in window)) return;
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) return;

    var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    var url = protocol + "//" + window.location.host + this.wsPath;
    var self = this;

    try {
      this.socket = new WebSocket(url);
    } catch (err) {
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = function () {
      self.reconnectAttempts = 0;
      self.setConnectionStatus(true);
      self.send({ action: "get_unread_count" });
    };
    this.socket.onmessage = function (event) {
      var message;
      try {
        message = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      self.handleMessage(message);
    };
    this.socket.onclose = function (event) {
      self.setConnectionStatus(false);
      if (!self.closedByUs && event.code !== 1000) self.scheduleReconnect();
    };
    this.socket.onerror = function () {
      // onclose follows and handles the retry
    };
  };

  NotificationClient.prototype.scheduleReconnect = function () {
    if (this.reconnectTimer || this.reconnectAttempts >= this.maxReconnectAttempts) return;
    var delay = Math.min(this.maxDelay, this.baseDelay * Math.pow(2, this.reconnectAttempts));
    delay += Math.floor(Math.random() * 500); // jitter so clients do not stampede
    this.reconnectAttempts += 1;
    var self = this;
    this.reconnectTimer = window.setTimeout(function () {
      self.reconnectTimer = null;
      self.connect();
    }, delay);
  };

  NotificationClient.prototype.close = function () {
    this.closedByUs = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    if (this.socket) this.socket.close(1000);
  };

  NotificationClient.prototype.send = function (payload) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  };

  NotificationClient.prototype.handleMessage = function (message) {
    switch (message.type) {
      case "notification":
        this.onNotification(message.notification || {});
        break;
      case "unread_count":
        this.setUnreadCount(message.count);
        break;
      case "notification_read":
        if (message.success) this.markItemRead(message.notification_id);
        break;
      case "all_read":
        this.markAllItemsRead();
        break;
      case "pong":
      default:
        break;
    }
  };

  // ------------------------------------------------------------- Actions
  NotificationClient.prototype.request = function (url, method) {
    return fetch(url, {
      method: method || "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
    });
  };

  NotificationClient.prototype.markRead = function (id) {
    var self = this;
    if (this.send({ action: "mark_read", notification_id: id })) {
      this.markItemRead(id);
      return Promise.resolve(true);
    }
    return this.request(this.endpoints.markRead.replace("/0/", "/" + id + "/"))
      .then(function (res) {
        if (!res.ok) return false;
        return res.json().then(function (body) {
          self.markItemRead(id);
          if (typeof body.unread_count === "number") self.setUnreadCount(body.unread_count);
          return true;
        });
      })
      .catch(function () { return false; });
  };

  NotificationClient.prototype.markAllRead = function () {
    var self = this;
    if (this.send({ action: "mark_all_read" })) {
      this.markAllItemsRead();
      return Promise.resolve(true);
    }
    return this.request(this.endpoints.markAllRead)
      .then(function (res) {
        if (res.ok) {
          self.markAllItemsRead();
          self.setUnreadCount(0);
        }
        return res.ok;
      })
      .catch(function () { return false; });
  };

  NotificationClient.prototype.remove = function (id) {
    var self = this;
    return this.request(this.endpoints.del.replace("/0/", "/" + id + "/"), "DELETE")
      .then(function (res) {
        if (!res.ok) return false;
        return res.json().then(function (body) {
          var item = self.findItem(id);
          if (item) item.remove();
          if (typeof body.unread_count === "number") self.setUnreadCount(body.unread_count);
          self.refreshEmptyState();
          return true;
        });
      })
      .catch(function () { return false; });
  };

  NotificationClient.prototype.bindEvents = function () {
    var self = this;
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-notification-action]");
      if (!button) return;
      var action = button.dataset.notificationAction;
      var id = button.dataset.id || (button.closest("[data-notification-id]") || {}).dataset;
      if (id && typeof id === "object") id = id.notificationId;

      if (action === "mark-read" && id) {
        event.preventDefault();
        self.markRead(id);
      } else if (action === "delete" && id) {
        event.preventDefault();
        self.remove(id);
      } else if (action === "mark-all-read") {
        event.preventDefault();
        self.markAllRead();
      }
    });

    var form = document.getElementById("mark-all-read-form");
    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        self.markAllRead();
      });
    }

    // Keep the socket alive through tab suspensions.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && self.enabled) self.connect();
    });
    window.addEventListener("beforeunload", function () { self.close(); });
  };

  // -------------------------------------------------------------- Badge
  NotificationClient.prototype.badgeElements = function () {
    var nodes = Array.prototype.slice.call(document.querySelectorAll("[data-notification-badge], #unread-count-badge"));
    var nav = document.getElementById("notificationsDropdown");
    if (nav) {
      var badge = nav.querySelector(".badge");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger";
        badge.hidden = true;
        nav.appendChild(badge);
      }
      nodes.push(badge);
    }
    return nodes;
  };

  NotificationClient.prototype.readBadgeValue = function () {
    var nav = document.getElementById("notificationsDropdown");
    var badge = nav && nav.querySelector(".badge");
    var n = badge ? parseInt(badge.textContent, 10) : 0;
    return isNaN(n) ? 0 : n;
  };

  NotificationClient.prototype.setUnreadCount = function (count) {
    count = Math.max(0, parseInt(count, 10) || 0);
    this.unreadCount = count;
    this.badgeElements().forEach(function (badge) {
      badge.textContent = count > 99 ? "99+" : String(count);
      badge.hidden = count === 0;
    });
    var markAll = document.getElementById("mark-all-read");
    if (markAll) markAll.disabled = count === 0;
    var title = document.title.replace(/^\(\d+\+?\)\s*/, "");
    document.title = count > 0 ? "(" + (count > 99 ? "99+" : count) + ") " + title : title;
  };

  // ---------------------------------------------------------- List items
  NotificationClient.prototype.findItem = function (id) {
    return document.querySelector('[data-notification-id="' + id + '"]');
  };

  NotificationClient.prototype.markItemRead = function (id) {
    var item = this.findItem(id);
    if (!item) return;
    item.classList.remove("unread", "list-group-item-light", "bg-light");
    var dot = item.querySelector(".unread-dot");
    if (dot) dot.remove();
    var btn = item.querySelector('[data-notification-action="mark-read"]');
    if (btn) btn.remove();
  };

  NotificationClient.prototype.markAllItemsRead = function () {
    var self = this;
    document.querySelectorAll("[data-notification-id]").forEach(function (item) {
      self.markItemRead(item.dataset.notificationId);
    });
    this.setUnreadCount(0);
  };

  NotificationClient.prototype.refreshEmptyState = function () {
    var list = document.querySelector("[data-live-list], #notification-list");
    var empty = document.querySelector("[data-live-empty], #no-notifications");
    if (!list || !empty) return;
    empty.hidden = list.children.length > 0;
  };

  NotificationClient.prototype.onNotification = function (notification) {
    this.setUnreadCount(this.unreadCount + 1);
    this.showToast(notification);
    this.prependToLiveList(notification);
    this.prependToDropdown(notification);
  };

  NotificationClient.prototype.prependToLiveList = function (n) {
    var list = document.querySelector("[data-live-list]");
    if (!list) return;
    var item = document.createElement("li");
    item.className = "list-group-item notification-item list-group-item-light unread";
    item.dataset.notificationId = n.id;
    var sender = n.sender ? n.sender.display_name || n.sender.username : "System";
    item.innerHTML =
      '<div class="d-flex justify-content-between align-items-start gap-2">' +
      '<div class="min-w-0">' +
      '<span class="fw-semibold">' + escapeHtml(sender) + "</span> " +
      '<span class="badge text-bg-' + escapeHtml(n.color || "primary") + '">' + escapeHtml(n.notification_type || "") + "</span>" +
      '<p class="mb-1"><a href="' + escapeHtml(n.url || "#") + '" class="text-reset text-decoration-none">' + escapeHtml(n.message) + "</a></p>" +
      '<div class="small d-flex gap-3">' +
      '<button type="button" class="btn btn-link btn-sm p-0" data-notification-action="mark-read" data-id="' + escapeHtml(n.id) + '">Mark as read</button>' +
      '<button type="button" class="btn btn-link btn-sm p-0 text-danger" data-notification-action="delete" data-id="' + escapeHtml(n.id) + '">Delete</button>' +
      "</div></div>" +
      '<small class="text-muted text-nowrap"><span class="unread-dot text-primary me-1">&#9679;</span>just now</small>' +
      "</div>";
    list.insertBefore(item, list.firstChild);
    this.refreshEmptyState();
  };

  NotificationClient.prototype.prependToDropdown = function (n) {
    var nav = document.getElementById("notificationsDropdown");
    var menu = nav && nav.parentElement && nav.parentElement.querySelector(".dropdown-menu");
    if (!menu) return;
    var header = menu.querySelector(".dropdown-header");
    var link = document.createElement("a");
    link.href = n.url || "/notifications/";
    link.className = "dropdown-item bg-light";
    link.innerHTML =
      '<div class="d-flex"><div class="flex-shrink-0 me-2"><i class="bi bi-' + escapeHtml(n.icon || "bell") +
      " text-" + escapeHtml(n.color || "primary") + '"></i></div>' +
      '<div class="flex-grow-1"><p class="mb-1 small">' + escapeHtml(n.message) + "</p>" +
      '<small class="text-muted">just now</small></div></div>';
    var emptyState = menu.querySelector(".dropdown-item-text");
    if (emptyState) emptyState.remove();
    if (header && header.nextSibling) menu.insertBefore(link, header.nextSibling);
    else menu.appendChild(link);
  };

  // --------------------------------------------------------------- Toasts
  NotificationClient.prototype.showToast = function (n) {
    var text = n.message || "You have a new notification";
    var type = n.color || "primary";
    if (window.djangoVerseHub && typeof window.djangoVerseHub.showToast === "function" && document.querySelector(".toast-container")) {
      window.djangoVerseHub.showToast(escapeHtml(text), type, 5000);
      return;
    }
    var region = document.getElementById("dvh-notification-toasts");
    if (!region) {
      region = document.createElement("div");
      region.id = "dvh-notification-toasts";
      region.setAttribute("aria-live", "polite");
      region.style.cssText = "position:fixed;top:1rem;right:1rem;z-index:1090;display:flex;flex-direction:column;gap:.5rem;max-width:320px;";
      document.body.appendChild(region);
    }
    var toast = document.createElement("a");
    toast.href = n.url || "/notifications/";
    toast.className = "dvh-toast";
    toast.style.cssText = "display:block;padding:.75rem 1rem;border-radius:.5rem;background:#212529;color:#fff;text-decoration:none;box-shadow:0 .5rem 1rem rgba(0,0,0,.25);opacity:0;transition:opacity .25s;";
    toast.textContent = text;
    region.appendChild(toast);
    window.requestAnimationFrame(function () { toast.style.opacity = "1"; });
    window.setTimeout(function () {
      toast.style.opacity = "0";
      window.setTimeout(function () { toast.remove(); }, 300);
    }, 5000);
  };

  NotificationClient.prototype.setConnectionStatus = function (connected) {
    document.querySelectorAll("[data-connection-status], .connection-status").forEach(function (el) {
      el.classList.toggle("connected", connected);
      el.textContent = connected ? "Connected" : "Reconnecting...";
      el.title = connected ? "Connected" : "Disconnected";
    });
  };

  window.NotificationClient = NotificationClient;

  function boot() {
    if (!window.notificationClient) window.notificationClient = new NotificationClient();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})(window, document);
