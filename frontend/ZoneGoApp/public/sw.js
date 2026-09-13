// Deliberately empty of caching. Chrome only asks for a service worker to
// exist before it offers to install the app; it does not ask it to store
// anything. A worker that cached would serve an old build after a deploy and
// no amount of reloading would fix it — the worst possible failure during a
// live demo. This one claims control and then stays out of the way.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => {})