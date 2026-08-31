from urllib.request import Request, urlopen
import re


class XmlParser:
    def __init__(self, xml_content):
        self.xml_content = xml_content

    def parse_builds(self):
        build_pattern = re.compile(r"<build>(.*?)</build>", re.DOTALL)
        sub_element_patterns = {
            "name": re.compile(r"<name>(.*?)</name>"),
            "version": re.compile(r"<version>(.*?)</version>"),
            "kodi": re.compile(r"<kodi>(.*?)</kodi>"),
            "size": re.compile(r"<size>(.*?)</size>"),
            "url": re.compile(r"<url>(.*?)</url>"),
            "icon": re.compile(r"<icon>(.*?)</icon>"),
            "fanart": re.compile(r"<fanart>(.*?)</fanart>"),
            "description": re.compile(r"<description>(.*?)</description>"),
            "preview": re.compile(r"<preview>(.*?)</preview>")
        }
        return self.parse(build_pattern, sub_element_patterns)
    
    def parse_videos(self):
        video_pattern = re.compile(r"<video>(.*?)</video>", re.DOTALL)
        sub_element_patterns = {
            "name": re.compile(r"<name>(.*?)</name>"),
            "section": re.compile(r"<section>(.*?)</section>"),
            "url": re.compile(r"<url>(.*?)</url>"),
            "icon": re.compile(r"<icon>(.*?)</icon>"),
            "fanart": re.compile(r"<fanart>(.*?)</fanart>"),
            "description": re.compile(r"<description>(.*?)</description>")
        }
        return self.parse(video_pattern, sub_element_patterns)
        
    def parse(self, main_pattern, sub_patterns: list):
        items = main_pattern.findall(self.xml_content)
        parsed_items = []
        for item in items:
            data = {}
            for key, pattern in sub_patterns.items():
                match = pattern.search(item)
                data[key] = match.group(1) if match else ''
            parsed_items.append(data)
        return parsed_items


class TextParser:
    def __init__(self, text_content):
        self.text_content = text_content
        self.plugin_pattern = (
            r'id="(?P<id>.*?)".*?\n'
            r'version="(?P<version>.*?)".*?\n'
            r'zip="(?P<zip>.*?)"'
        )
        
        self.build_pattern = (
            r'name="(?P<name>.*?)".*?\n'
            r'version="(?P<version>.*?)".*?\n'
            r'url="(?P<url>.*?)".*?\n'
            r'minor="(?P<minor>.*?)".*?\n'
            r'gui="(?P<gui>.*?)".*?\n'
            r'kodi="(?P<kodi>.*?)".*?\n'
            r'theme="(?P<theme>.*?)".*?\n'
            r'icon="(?P<icon>.*?)".*?\n'
            r'fanart="(?P<fanart>.*?)".*?\n'
            r'preview="(?P<preview>.*?)".*?\n'
            r'adult="(?P<adult>.*?)".*?\n'
            r'info="(?P<info>.*?)".*?\n'
            r'description="(?P<description>.*?)"'
        )
        
        self.video_pattern = (
            r'name="(?P<name>.*?)".*?\n'
            r'section="(?P<section>.*?)".*?\n'
            r'url="(?P<url>.*?)".*?\n'
            r'icon="(?P<icon>.*?)".*?\n'
            r'fanart="(?P<fanart>.*?)".*?\n'
            r'description="(?P<description>.*?)"'
        )
    
    def parse_builds(self):
        build_matches = re.finditer(self.build_pattern, self.text_content)
        return [match.groupdict() for match in build_matches]
    
    def parse_videos(self):
        video_matches = re.finditer(self.video_pattern, self.text_content)
        return [match.groupdict() for match in video_matches]
    
    def parse_plugin(self):
        plugin_match = re.search(self.plugin_pattern, self.text_content)
        return plugin_match.groupdict() if plugin_match else {}


def get_page(url):
    if url.startswith('https://www.dropbox.com'):
        url = url.replace('dl=0', 'dl=1')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    request = Request(url, headers=headers)
    with urlopen(request) as response:
        return response.read().decode('utf-8')
