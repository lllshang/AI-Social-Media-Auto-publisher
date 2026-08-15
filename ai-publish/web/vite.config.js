import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 缓存破坏器：拦截 chunk 加载失败 → 清缓存 + 带 cache-buster 强制 reload。
// 同时在 dev (index.html) 与 build (transformIndexHtml) 两条路径都注入，避免 build 后失效。
const RELOAD_GUARD_SCRIPT = `
(function () {
  // 启动回合计数（防 reload 死循环）
  try {
    var K = '__app_reload_rounds';
    sessionStorage.setItem(K, String((Number(sessionStorage.getItem(K)) || 0) + 1));
    if (Number(sessionStorage.getItem(K)) > 3) {
      sessionStorage.removeItem(K);
      return;
    }
  } catch (e) {}

  var recovered = false;
  var lastRecoverAt = 0;
  function tryRecover(tag) {
    var now = Date.now();
    if (recovered || now - lastRecoverAt < 5000) return;
    recovered = true;
    lastRecoverAt = now;
    try {
      console.warn('[app-reload] recover:', tag);
      if (window.caches && window.caches.keys) {
        window.caches.keys().then(function (keys) {
          keys.forEach(function (k) { window.caches.delete(k); });
        });
      }
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.getRegistrations().then(function (regs) {
          regs.forEach(function (r) { r.unregister(); });
        });
      }
    } catch (e) {}
    var url = location.pathname + '?_t=' + Date.now() + '#' + encodeURIComponent(location.hash || '');
    try { location.replace(url); } catch (e) { location.reload(); }
  }

  function matchesRecover(msg) {
    if (!msg) return false;
    var s = String(msg);
    return (
      s.indexOf('dynamically imported module') >= 0 ||
      s.indexOf('Loading chunk') >= 0 ||
      s.indexOf('Loading CSS chunk') >= 0 ||
      s.indexOf('Failed to fetch') >= 0 ||
      s.indexOf('Importing a module script failed') >= 0
    );
  }

  // Banner:每次页面加载都打印,看到这一行就 100% 拿到最新 HTML(不走 disk cache)
  try { console.log('[app-reload] guard loaded @', new Date().toISOString(), 'h=', location.href); } catch (e) {}

  // 兜底 1:窗口加载 15 秒后,如果 #app 仍是空,说明 JS 卡死/没加载,显示可见错误
  setTimeout(function () {
    try {
      var host = document.getElementById('app') || document.body;
      if (host && host.childElementCount === 0) {
        var html = '<div style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;font-family:system-ui;background:#fff;color:#333;padding:24px;text-align:center;">'
          + '<div style="font-size:18px;font-weight:600;margin-bottom:12px;color:#c00">⚠ 应用未能在 15s 内初始化</div>'
          + '<div style="font-size:14px;color:#666;max-width:520px;line-height:1.6">可能是浏览器缓存了旧的 entry chunk,请:</div>'
          + '<ol style="font-size:14px;color:#666;max-width:520px;text-align:left;line-height:1.8">'
          + '<li>F12 打开开发者工具</li>'
          + '<li>切到 Application → Storage → <b>Clear site data</b></li>'
          + '<li>关闭这个标签页,重新打开 <code>https://150.158.23.10/app/</code></li>'
          + '<li>若仍空白,请尝试无痕窗口或别的浏览器</li>'
          + '</ol>'
          + '<div id="__app_reload_extra" style="margin-top:20px;font-size:12px;color:#999;word-break:break-all"></div>'
          + '</div>';
        host.innerHTML = html;
        var extra = document.getElementById('__app_reload_extra');
        if (extra) extra.textContent = 'UA:' + navigator.userAgent + ' @ ' + location.href;
      }
    } catch (e) {}
  }, 15000);

  window.addEventListener('error', function (ev) {
    var msg = String((ev && ev.error && ev.error.message) || (ev && ev.message) || '');
    var src = '';
    try { if (ev && ev.target && ev.target.src) src = String(ev.target.src); } catch (e) {}
    if (matchesRecover(msg)) {
      tryRecover('error:' + msg);
    } else if (src && src.indexOf('/app/assets/') >= 0) {
      tryRecover('res:' + src);
    }
  }, true);

  window.addEventListener('unhandledrejection', function (ev) {
    var msg = String((ev && ev.reason && ev.reason.message) || (ev && ev.reason) || '');
    if (matchesRecover(msg)) tryRecover('rej:' + msg);
  });
})();
`

export default defineConfig({
  plugins: [
    vue(),
    {
      // build 阶段：把兜底脚本注入到生成出的 index.html 的 <head>
      name: 'inject-reload-guard',
      transformIndexHtml: {
        order: 'pre',
        handler(html) {
          // 只在 /app 入口（生产 SPA）注入
          if (html.includes('id="app"')) {
            return html.replace(
              '</head>',
              `<script>${RELOAD_GUARD_SCRIPT}</script></head>`
            )
          }
          return html
        },
      },
    },
  ],
  base: '/app/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
