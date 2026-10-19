class ProviderError(Exception):
    def __init__(self,code='AI_UNAVAILABLE',http_status=None):
        self.code=code
        self.http_status=http_status
        super().__init__(code)
