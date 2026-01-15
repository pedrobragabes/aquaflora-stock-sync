"""
AquaFlora Stock Sync - Custom Exceptions
Specific exception classes for better error handling and debugging.
"""


class AquaFloraError(Exception):
    """Base exception for all AquaFlora Stock Sync errors."""
    
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}
    
    def __str__(self):
        base = super().__str__()
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base} [{context_str}]"
        return base


class ParserError(AquaFloraError):
    """Errors during CSV parsing from Athos ERP."""
    
    def __init__(self, message: str, line_number: int = None, filename: str = None):
        context = {}
        if line_number:
            context["line"] = line_number
        if filename:
            context["file"] = filename
        super().__init__(message, context)
        self.line_number = line_number
        self.filename = filename


class EnrichmentError(AquaFloraError):
    """Errors during product enrichment (brand detection, SEO generation)."""
    
    def __init__(self, message: str, sku: str = None):
        context = {"sku": sku} if sku else {}
        super().__init__(message, context)
        self.sku = sku


class WooCommerceError(AquaFloraError):
    """Errors from WooCommerce API calls."""
    
    def __init__(self, message: str, status_code: int = None, sku: str = None):
        context = {}
        if status_code:
            context["status"] = status_code
        if sku:
            context["sku"] = sku
        super().__init__(message, context)
        self.status_code = status_code
        self.sku = sku
    
    @property
    def is_client_error(self) -> bool:
        """4xx errors - client should not retry."""
        return self.status_code and 400 <= self.status_code < 500
    
    @property
    def is_server_error(self) -> bool:
        """5xx errors - server issue, may retry."""
        return self.status_code and self.status_code >= 500
    
    @property
    def is_retryable(self) -> bool:
        """Check if error is worth retrying."""
        return self.is_server_error or self.status_code in (408, 429)  # Timeout, Rate limit


class SyncError(AquaFloraError):
    """Errors during the sync process."""
    
    def __init__(self, message: str, products_affected: int = None):
        context = {"products": products_affected} if products_affected else {}
        super().__init__(message, context)
        self.products_affected = products_affected


class DatabaseError(AquaFloraError):
    """Errors with SQLite database operations."""
    
    def __init__(self, message: str, table: str = None, sku: str = None):
        context = {}
        if table:
            context["table"] = table
        if sku:
            context["sku"] = sku
        super().__init__(message, context)
        self.table = table
        self.sku = sku


class ConfigurationError(AquaFloraError):
    """Errors in configuration (missing .env values, etc)."""
    
    def __init__(self, message: str, setting: str = None):
        context = {"setting": setting} if setting else {}
        super().__init__(message, context)
        self.setting = setting


class SchedulerError(AquaFloraError):
    """Errors with the APScheduler job scheduling."""
    
    def __init__(self, message: str, job_id: str = None):
        context = {"job_id": job_id} if job_id else {}
        super().__init__(message, context)
        self.job_id = job_id
