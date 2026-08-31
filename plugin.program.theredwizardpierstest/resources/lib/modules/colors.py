import xbmcaddon

FILE = 'colors.json'
COLORS = ['aliceblue', 'antiquewhite', 'aqua', 'azure', 'bisque', 'black', 'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse', 'chocolate', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgreen', 'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen', 'darkslateblue', 'darkslategray', 'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'green', 'greenyellow', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen', 'lenonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgrey', 'lightgreen', 'lightpink', 'lightsalmon', 'lightseagreen', 'lightskyblue', 'lightslategray', 'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue', 'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite', 'navy', 'none', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered', 'orchid', 'palengoldenrod', 'palegreen', 'paleturquoise', 'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'snow', 'springgreen', 'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke', 'yellow', 'yellowgreen']
    

class Colors:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.setting = self.addon.getSetting
        self.file = FILE
        self.colors = COLORS
        self.color1 = self.get_color('color1')
        self.color2 = self.get_color('color2')
        self.color3 = self.get_color('color3')
        self.color4 = self.get_color('color4')
    
    def get_color(self, color: str) -> str:
        color_index = int(self.setting(color))
        return COLORS[color_index]
    
    def color_text1(self, string: str) -> str:
        if '[B]' in string or '[/B]' in string:
            return f'[COLOR {self.color1}]{string}[/COLOR]'
        else:
            return f'[B][COLOR {self.color1}]{string}[/COLOR][/B]'
    
    def color_text2(self, string: str) -> str:
        if '[B]' in string or '[/B]' in string:
            return f'[COLOR {self.color2}]{string}[/COLOR]'
        else:
            return f'[B][COLOR {self.color2}]{string}[/COLOR][/B]'

    def color_text3(self, string: str) -> str:
        if '[B]' in string or '[/B]' in string:
            return f'[COLOR {self.color3}]{string}[/COLOR]'
        else:
            return f'[B][COLOR {self.color3}]{string}[/COLOR][/B]'

    def color_text4(self, string: str) -> str:
        if '[B]' in string or '[/B]' in string:
            return f'[COLOR {self.color4}]{string}[/COLOR]'
        else:
            return f'[B][COLOR {self.color4}]{string}[/COLOR][/B]'
        
colors = Colors()
