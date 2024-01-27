import random

class FakeWriter:
    def get_extra_info(self, _):
        return str(random.randbytes(10))
    
    def is_closing(self):
        return False
    
    def write(self, *args, **kwargs):
        pass
