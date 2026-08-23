# Cloudflare redirects — SITE_SEAL_v1

## Always Use HTTPS
SSL/TLS → Edge Certificates → Always Use HTTPS = On

## www → apex 301
Rules → Redirect Rules:

Filter: `(http.host eq "www.dualiscapax.ai")`
Dynamic URL: `concat("https://dualiscapax.ai", http.request.uri.path)`
Status: 301 · Preserve query: On

## Verify
```bash
curl -sI https://www.dualiscapax.ai/ | grep -iE 'HTTP/|location:'
# 301 Location: https://dualiscapax.ai/
```

Edge seal complete only when probes pass.
