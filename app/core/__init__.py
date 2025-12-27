"""Core application primitives (settings, database, security)."""

# Patch bcrypt for passlib compatibility (bcrypt 4.x removed __about__)
# This must run before passlib imports bcrypt
import bcrypt
if not hasattr(bcrypt, '__about__'):
    class _About:
        __version__ = bcrypt.__version__
    bcrypt.__about__ = _About()
