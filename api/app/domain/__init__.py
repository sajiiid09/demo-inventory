"""The pure domain layer — every rule about money, in five small files.

No database, no I/O, no datetime.now(). The current date is always an explicit
`as_of` argument (ADR-011). If a number on screen disagrees with DOMAIN.md,
the bug is here or in the service that called here — nowhere else.
"""
