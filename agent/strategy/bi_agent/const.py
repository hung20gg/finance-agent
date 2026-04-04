TEXT2SQL_TOOL_NAME = "sql_generator"
TEXT2CHART_TOOL_NAME = "chart_generator"

TEXT2SQL_TOOL = {
    "type": "function",
    "function": {
        "name": TEXT2SQL_TOOL_NAME,
        "description": "Giving task for SQL Agent to generate the data",
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "Detailed task for SQL Agent to generate the data",
                },
                "query_mode":
                {
                    "type": "string",
                    "description": "The expected output format, can be 'entity' for single value or 'tuple' for multiple values.",
                    "enum": ["entity", "tuple"]
                },
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Expected column for output. Should be in English",
                }
            },
            "required": ["request", "columns"],
            "additionalProperties": False,
        },
        "strict": True,
    }
    
}

TEXT2CHART_TOOL = {
    "type": "function",
    "function": {
        "name": TEXT2CHART_TOOL_NAME,
        "description": "Giving task for Chart Agent to generate the chart corresponding to the data",
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "Request for data visualization",
                },

                "data": {
                    "type": "object",
                    "description": "Column-based data where each key is a column name and each value is an array of values",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                        "type": ["string", "number", "null"]
                        }
                    }
                },

                "chart_type": {
                    "type": "string",
                    "description": "Type of chart to be generated",
                }
            },
            "required": ["data", "chart_type"],
            "additionalProperties": False,
        },
        "strict": True,
    }
}
