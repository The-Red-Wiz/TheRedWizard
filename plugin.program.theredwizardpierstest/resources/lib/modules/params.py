from urllib.parse import parse_qsl

class Params:
    def __init__(self, paramstring):
        self.params = dict(parse_qsl(paramstring))
        
    
    def get_params(self):
        return self.params
    
    def get_name(self):
        try: return self.params['name']
        except KeyError: return None
        except TypeError: return None
    
    def get_name2(self):
        try: return self.params['name2']
        except KeyError: return None
        except TypeError: return None
    
    def get_version(self):
        try: return self.params['version']
        except KeyError: return None
        except TypeError: return None
    
    def get_url(self):
        try: return self.params['url']
        except KeyError: return None
        except TypeError: return None
    
    def get_mode(self):
        try: return int(self.params['mode'])
        except KeyError: return None
        except TypeError: return None
    
    def get_icon(self):
        try: return self.params['icon']
        except KeyError: return None
        except TypeError: return None
    
    def get_fanart(self):
        try: return self.params['fanart']
        except KeyError: return None
        except TypeError: return None
    
    def get_description(self):
        try: return self.params['description']
        except KeyError: return None
        except TypeError: return None