import ast

code = '''class GetWeatherTool:
    name = "get_weather"
    description = "Get current weather for a location (mock implementation)"
    category = "web_research"
    risk_level = "low"
    parameters = [
        {"name": "location", "type": "string", "description": "Location (city, country)", "required": True},
        {"name": "units", "type": "string", "description": "Units (metric/imperial)", "required": False, "default": "metric"}
    ]

    def execute(self, **kwargs):
        location = kwargs.get("location", "")
        units = kwargs.get("units", "metric")
        
        return {
            "success": True,
            "data": {
                "location": location,
                "temperature": "22°C" if units == "metric" else "72°F",
                "condition": "Sunny",
                "humidity": "65%"
            }
        }
'''

try:
    tree = ast.parse(code)
    print('Test class parsed successfully')
except SyntaxError as e:
    print(f'SyntaxError: {e}')
    print(f'Line {e.lineno}: {e.msg}')