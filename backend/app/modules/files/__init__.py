"""Files module: MIME sniff, object storage, ClamAV scan queue.

``models`` defines the ``attachment`` table (its DDL lives in migration ``0002``).
``mime`` sniffs with libmagic and holds the type allowlist.
``storage`` wraps the MinIO/S3 backend behind the ``ObjectStorage`` protocol.
``scanner`` runs the ClamAV/clamd scan in the worker and returns a ``ScanVerdict``.
``queue`` enqueues the ``scan_attachment`` job in arq with an idempotent job id.
"""
