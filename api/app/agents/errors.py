class ProviderError(Exception):
    def __init__(self,code='AI_UNAVAILABLE'):
        self.code=code
        super().__init__(code)
