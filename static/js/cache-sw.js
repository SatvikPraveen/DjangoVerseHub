// File: DjangoVerseHub/static/js/cache-sw.js

/**
 * Service Worker for DjangoVerseHub
 * Handles caching, offline functionality, and push notifications
 */

const CACHE_NAME = "djangoversehub-v1";
const STATIC_CACHE = "djangoversehub-static-v1";
const DYNAMIC_CACHE = "djangoversehub-dynamic-v1";

// URLs to cache on install
const STATIC_ASSETS = [
  "/",
  "/static/css/main.css",
  "/static/css/auth.css",
  "/static/css/profile.css",
  "/static/js/main.js",
  "/static/js/api.js",
  "/static/js/notifications.js",
  "/static/images/logo.svg",
  "/offline/",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
  "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css",
];

// URLs that should always be fetched from network
const NETWORK_FIRST = ["/api/", "/ws/", "/admin/"];

// URLs that should be cached first
const CACHE_FIRST = ["/static/", "https://cdn.jsdelivr.net"];

self.addEventListener("install", (event) => {
  console.log("Service Worker installing...");

  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("Caching static assets");
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log("Static assets cached successfully");
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error("Error caching static assets:", error);
      })
  );
});

self.addEventListener("activate", (event) => {
  console.log("Service Worker activating...");

  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => {
              return (
                cacheName.startsWith("djangoversehub-") &&
                cacheName !== CACHE_NAME &&
                cacheName !== STATIC_CACHE &&
                cacheName !== DYNAMIC_CACHE
              );
            })
            .map((cacheName) => {
              console.log("Deleting old cache:", cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => {
        console.log("Service Worker activated");
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") {
    return;
  }

  // Skip chrome-extension and other non-http protocols
  if (!url.protocol.startsWith("http")) {
    return;
  }

  event.respondWith(handleFetch(request));
});

async function handleFetch(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;

  try {
    // Network-first strategy for API calls
    if (NETWORK_FIRST.some((pattern) => pathname.startsWith(pattern))) {
      return await networkFirst(request);
    }

    // Cache-first strategy for static assets
    if (CACHE_FIRST.some((pattern) => pathname.startsWith(pattern))) {
      return await cacheFirst(request);
    }

    // Stale-while-revalidate for HTML pages
    if (request.headers.get("accept")?.includes("text/html")) {
      return await staleWhileRevalidate(request);
    }

    // Default to network-first
    return await networkFirst(request);
  } catch (error) {
    console.error("Fetch error:", error);
    return await handleOffline(request);
  }
}

async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      // Cache successful responses
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.log("Network failed, trying cache:", request.url);
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
      return cachedResponse;
    }

    throw error;
  }
}

async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);

  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.error("Cache-first failed:", error);
    throw error;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(DYNAMIC_CACHE);
  const cachedResponse = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        cache.put(request, networkResponse.clone());
      }
      return networkResponse;
    })
    .catch((error) => {
      console.error("Network fetch failed:", error);
      return null;
    });

  // Return cached version immediately, update cache in background
  if (cachedResponse) {
    fetchPromise.catch(() => {}); // Prevent unhandled promise rejection
    return cachedResponse;
  }

  // If no cached version, wait for network
  const networkResponse = await fetchPromise;
  if (networkResponse) {
    return networkResponse;
  }

  throw new Error("No cached response and network failed");
}

async function handleOffline(request) {
  const url = new URL(request.url);

  // Return offline page for HTML requests
  if (request.headers.get("accept")?.includes("text/html")) {
    const offlineResponse = await caches.match("/offline/");
    if (offlineResponse) {
      return offlineResponse;
    }
  }

  // Return placeholder for images
  if (request.headers.get("accept")?.includes("image/")) {
    return new Response(
      '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150"><rect width="200" height="150" fill="#f8f9fa"/><text x="100" y="75" text-anchor="middle" fill="#6c757d">Image unavailable</text></svg>',
      {
        headers: {
          "Content-Type": "image/svg+xml",
          "Cache-Control": "no-cache",
        },
      }
    );
  }

  // Return error response
  return new Response(
    JSON.stringify({ error: "Network unavailable", offline: true }),
    {
      status: 503,
      statusText: "Service Unavailable",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );
}

// Push notification handling
self.addEventListener("push", (event) => {
  console.log("Push notification received");

  if (!event.data) {
    return;
  }

  try {
    const data = event.data.json();

    const options = {
      body: data.body || data.message || "New notification",
      icon: data.icon || "/static/images/logo.svg",
      badge: data.badge || "/static/images/logo.svg",
      image: data.image,
      data: data.data || {},
      actions: data.actions || [],
      requireInteraction: data.requireInteraction || false,
      silent: data.silent || false,
      tag: data.tag || "default",
      timestamp: Date.now(),
      vibrate: data.vibrate || [200, 100, 200],
    };

    event.waitUntil(
      self.registration.showNotification(
        data.title || "DjangoVerseHub",
        options
      )
    );
  } catch (error) {
    console.error("Error handling push notification:", error);

    // Fallback notification
    event.waitUntil(
      self.registration.showNotification("DjangoVerseHub", {
        body: "You have a new notification",
        icon: "/static/images/logo.svg",
      })
    );
  }
});

// Notification click handling
self.addEventListener("notificationclick", (event) => {
  console.log("Notification clicked");

  event.notification.close();

  const data = event.notification.data || {};
  const url = data.url || "/";

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // Check if there's already a window/tab open with the target URL
        for (let client of clientList) {
          if (client.url === url && "focus" in client) {
            return client.focus();
          }
        }

        // If no existing window, open a new one
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
      .catch((error) => {
        console.error("Error handling notification click:", error);
      })
  );
});

// Background sync (for future implementation)
self.addEventListener("sync", (event) => {
  console.log("Background sync triggered:", event.tag);

  switch (event.tag) {
    case "sync-comments":
      event.waitUntil(syncComments());
      break;
    case "sync-articles":
      event.waitUntil(syncArticles());
      break;
    default:
      console.log("Unknown sync tag:", event.tag);
  }
});

async function syncComments() {
  try {
    // Implementation for syncing pending comments
    console.log("Syncing comments...");

    const pendingComments = await getStoredData("pending-comments");
    if (pendingComments && pendingComments.length > 0) {
      for (const comment of pendingComments) {
        try {
          const response = await fetch("/api/comments/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": comment.csrfToken,
            },
            body: JSON.stringify(comment.data),
          });

          if (response.ok) {
            console.log("Comment synced successfully");
            await removeStoredData("pending-comments", comment.id);
          }
        } catch (error) {
          console.error("Error syncing comment:", error);
        }
      }
    }
  } catch (error) {
    console.error("Error in syncComments:", error);
  }
}

async function syncArticles() {
  try {
    // Implementation for syncing pending articles
    console.log("Syncing articles...");

    // Similar implementation to syncComments
  } catch (error) {
    console.error("Error in syncArticles:", error);
  }
}

// IndexedDB helpers for offline storage
async function getStoredData(key) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("DjangoVerseHubDB", 1);

    request.onerror = () => reject(request.error);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("offline-data")) {
        db.createObjectStore("offline-data", { keyPath: "id" });
      }
    };

    request.onsuccess = (event) => {
      const db = event.target.result;
      const transaction = db.transaction(["offline-data"], "readonly");
      const store = transaction.objectStore("offline-data");
      const getRequest = store.get(key);

      getRequest.onsuccess = () => {
        resolve(getRequest.result ? getRequest.result.data : null);
      };

      getRequest.onerror = () => reject(getRequest.error);
    };
  });
}

async function removeStoredData(key, id) {
  // Implementation for removing specific items from stored data
  const data = await getStoredData(key);
  if (data) {
    const filtered = data.filter((item) => item.id !== id);
    await storeData(key, filtered);
  }
}

async function storeData(key, data) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("DjangoVerseHubDB", 1);

    request.onsuccess = (event) => {
      const db = event.target.result;
      const transaction = db.transaction(["offline-data"], "readwrite");
      const store = transaction.objectStore("offline-data");

      store.put({ id: key, data: data });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    };
  });
}

console.log("Service Worker script loaded");
