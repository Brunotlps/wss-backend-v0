# Layer: Infra / Media Delivery / Storage

**Owns:** #54 (videos public URLs), #74 (certificate PDF public URLs).
**Theme:** `protected-media`. **Phase 0** (foundational — closes 2 Blocking PII/paid-content leaks).

## Problem (shared root cause)

Nginx serves `/media/` directly as public, guessable, cacheable URLs. The DRF permission layer
(`IsEnrolled`, `IsCertificateOwner`) therefore protects only JSON metadata — the actual bytes are
fetchable by anyone who guesses/shares the URL. Filenames are predictable (video path; certificate
filename = the public verification code).

## Canonical pattern — protected delivery via X-Accel-Redirect

Serve files only through an authenticated Django view that re-runs the access check and hands off
to Nginx via an `internal` location.

```nginx
# nginx.conf — make media non-public, served only on internal redirect
location /protected/ {
    internal;
    alias /app/media/;
}
# remove the public `location /media/ { ... expires 7d; Cache-Control public }`
```

```python
# view: authenticated, runs the same object permission, then delegates to Nginx
class VideoFileView(APIView):
    permission_classes = [IsAuthenticated, IsEnrolled]

    def get(self, request: Request, pk: int) -> HttpResponse:
        video = get_object_or_404(Video, pk=pk)
        self.check_object_permissions(request, video)
        response = HttpResponse(status=200)
        response["X-Accel-Redirect"] = f"/protected/{video.file.name}"
        response["Content-Type"] = ""  # let Nginx set it
        return response
```

**Alternative (when S3 is enabled):** pre-signed, short-TTL URLs; never `AWS_DEFAULT_ACL =
'public-read'`, never `AWS_QUERYSTRING_AUTH = False` (see `config/settings/production.py:110-127`).

## Steps

1. **Storage paths:** store under non-guessable names (UUID), decouple certificate filename from
   the public verification `code` (#74).
2. **Serializers:** stop exposing raw `file`/`thumbnail`/`pdf_file`/`pdf_url`; expose only the
   protected-view URL (or nothing for non-enrolled users). Coordinates with `03-serializers`.
3. **Nginx:** make `/media/{videos,certificates}/` `internal`; deploy requires
   `--force-recreate` (bind mount by inode — see project memory `infra-nginx-bind-mount-gotcha`).
4. **Cloudflare:** large video uploads already bypass via `upload.nousflow.com.br`; confirm the
   protected GET path stays under the 100MB proxy or uses the same bypass for downloads.

## Order / dependencies

- Do alongside `04-permissions` (#55/#56): the protected view must enforce the corrected
  `IsEnrolled`/`is_free_preview` logic, else the bypass just moves to the new endpoint.

## Done criteria

- [x] Anonymous/non-enrolled GET of a video/certificate file URL → 401/403 (not the bytes). — #54/#74, PR #99, deployed+validated 2026-06-17.
- [x] No raw `/media/...` path is reachable without going through the authenticated view. — `/media/videos/` and `/media/certificates/` are `internal` in nginx.conf.
- [x] Serializers no longer return a directly-fetchable media URL to non-owners. — `stream_url`/`download_url` only, both gated.
- [x] Tests: enrolled user downloads OK; non-enrolled denied; revoked certificate denied (#81). — #81 (revoked → 410) shipped PR #134, 2026-06-23~25.
