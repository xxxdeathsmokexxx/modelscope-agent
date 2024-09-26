import os

import requests
from jsonschema import RefResolver


def execute_api_call(url: str, method: str, headers: dict, params: dict,
                     data: dict, cookies: dict):
    try:
        if method == 'GET':
            response = requests.get(
                url, params=params, headers=headers, cookies=cookies)
        elif method == 'POST':
            response = requests.post(
                url, json=data, headers=headers, cookies=cookies)
        elif method == 'PUT':
            response = requests.put(
                url, json=data, headers=headers, cookies=cookies)
        elif method == 'DELETE':
            response = requests.delete(
                url, json=data, headers=headers, cookies=cookies)
        else:
            raise ValueError(f'Unsupported HTTP method: {method}')

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        raise Exception(
            f'An error occurred: {response.message}, with error {e}')


def parse_nested_parameters(param_name, param_info, parameters_list, content):
    param_type = param_info['type']
    param_description = param_info.get('description',
                                       f'用户输入的{param_name}')  # 按需更改描述
    param_required = param_name in content['required']
    try:
        if param_type == 'object':
            properties = param_info.get('properties')
            if properties:
                # If the argument type is an object and has a non-empty "properties" field,
                # its internal properties are parsed recursively
                for inner_param_name, inner_param_info in properties.items():
                    inner_param_type = inner_param_info['type']
                    inner_param_description = inner_param_info.get(
                        'description', f'用户输入的{param_name}.{inner_param_name}')
                    inner_param_required = param_name.split(
                        '.')[0] in content['required']

                    # Recursively call the function to handle nested objects
                    if inner_param_type == 'object':
                        parse_nested_parameters(
                            f'{param_name}.{inner_param_name}',
                            inner_param_info, parameters_list, content)
                    else:
                        parameters_list.append({
                            'name':
                            f'{param_name}.{inner_param_name}',
                            'description':
                            inner_param_description,
                            'required':
                            inner_param_required,
                            'type':
                            inner_param_type,
                            'enum':
                            inner_param_info.get('enum', '')
                        })
        else:
            # Non-nested parameters are added directly to the parameter list
            parameters_list.append({
                'name': param_name,
                'description': param_description,
                'required': param_required,
                'type': param_type,
                'enum': param_info.get('enum', '')
            })
    except Exception as e:
        raise ValueError(f'{e}:schema结构出错')


# openapi_schema_convert,register to tool_config.json
def extract_references(schema_content):
    references = []
    if isinstance(schema_content, dict):
        if '$ref' in schema_content:
            references.append(schema_content['$ref'])
        for key, value in schema_content.items():
            references.extend(extract_references(value))
    elif isinstance(schema_content, list):
        for item in schema_content:
            references.extend(extract_references(item))
    return references


def openapi_schema_convert(schema: dict, auth: dict = {}):
    config_data = {}

    resolver = RefResolver.from_schema(schema)
    servers = schema.get('servers', [])
    if servers:
        servers_url = servers[0].get('url')
    else:
        print('No URL found in the schema.')
        return config_data

    # Extract endpoints
    endpoints = schema.get('paths', {})
    description = schema.get('info', {}).get('description',
                                             'This is a api tool that ...')
    # Iterate over each endpoint and its contents
    for endpoint_path, methods in endpoints.items():
        for method, details in methods.items():
            parameters_list = []

            # put path parameters in parameters_list
            path_parameters = details.get('parameters', [])
            if isinstance(path_parameters, dict):
                path_parameters = [path_parameters]
            parameters_list.extend(path_parameters)

            summary = details.get('summary',
                                  'No summary').replace(' ', '_').lower()
            name = details.get('operationId', 'No operationId')
            url = f'{servers_url}{endpoint_path}'
            security = details.get('security', [{}])
            # Security (Bearer Token)
            authorization = ''
            if security:
                for sec in security:
                    if 'BearerAuth' in sec:
                        api_token = auth.get('apikey',
                                             os.environ.get('apikey', ''))
                        api_token_type = auth.get(
                            'apikey_type',
                            os.environ.get('apikey_type', 'Bearer'))
                        authorization = f'{api_token_type} {api_token}'
            if method.upper() == 'POST' or method.upper(
            ) == 'DELETE' or method.upper() == 'PUT':
                requestBody = details.get('requestBody', {})
                if requestBody:
                    for content_type, content_details in requestBody.get(
                            'content', {}).items():
                        schema_content = content_details.get('schema', {})
                        references = extract_references(schema_content)
                        for reference in references:
                            resolved_schema = resolver.resolve(reference)
                            content = resolved_schema[1]
                            for param_name, param_info in content[
                                    'properties'].items():
                                parse_nested_parameters(
                                    param_name, param_info, parameters_list,
                                    content)
                            X_DashScope_Async = requestBody.get(
                                'X-DashScope-Async', '')
                            if X_DashScope_Async == '':
                                config_entry = {
                                    'name': name,
                                    'description': description,
                                    'is_active': True,
                                    'is_remote_tool': True,
                                    'url': url,
                                    'method': method.upper(),
                                    'parameters': parameters_list,
                                    'header': {
                                        'Content-Type': content_type,
                                        'Authorization': authorization
                                    }
                                }
                            else:
                                config_entry = {
                                    'name': name,
                                    'description': description,
                                    'is_active': True,
                                    'is_remote_tool': True,
                                    'url': url,
                                    'method': method.upper(),
                                    'parameters': parameters_list,
                                    'header': {
                                        'Content-Type': content_type,
                                        'Authorization': authorization,
                                        'X-DashScope-Async': 'enable'
                                    }
                                }
                else:
                    config_entry = {
                        'name': name,
                        'description': description,
                        'is_active': True,
                        'is_remote_tool': True,
                        'url': url,
                        'method': method.upper(),
                        'parameters': [],
                        'header': {
                            'Content-Type': 'application/json',
                            'Authorization': authorization
                        }
                    }
            elif method.upper() == 'GET':
                config_entry = {
                    'name': name,
                    'description': description,
                    'is_active': True,
                    'is_remote_tool': True,
                    'url': url,
                    'method': method.upper(),
                    'parameters': parameters_list,
                    'header': {
                        'Authorization': authorization
                    }
                }
            else:
                raise 'method is not POST, GET PUT or DELETE'

            config_entry['details'] = details
            config_data[summary] = config_entry
    return config_data


def get_parameter_value(parameter: dict, parameters: dict):
    if parameter['name'] in parameters:
        return parameters[parameter['name']]
    elif parameter.get('required', False):
        raise ValueError(f"Missing required parameter {parameter['name']}")
    else:
        return (parameter.get('schema', {}) or {}).get('default', '')


if __name__ == '__main__':
    openapi_schema = {
        'openapi': '3.0.1',
        'info': {
            'title': 'TODO Plugin',
            'description':
            'A plugin that allows the user to create and manage a TODO list using ChatGPT. ',
            'version': 'v1'
        },
        'servers': [{
            'url': 'http://localhost:5003'
        }],
        'paths': {
            '/todos/{username}': {
                'get': {
                    'operationId':
                    'getTodos',
                    'summary':
                    'Get the list of todos',
                    'parameters': [{
                        'in': 'path',
                        'name': 'username',
                        'schema': {
                            'type': 'string'
                        },
                        'required': True,
                        'description': 'The name of the user.'
                    }],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        '$ref':
                                        '#/components/schemas/getTodosResponse'
                                    }
                                }
                            }
                        }
                    }
                },
                'post': {
                    'operationId':
                    'addTodo',
                    'summary':
                    'Add a todo to the list',
                    'parameters': [{
                        'in': 'path',
                        'name': 'username',
                        'schema': {
                            'type': 'string'
                        },
                        'required': True,
                        'description': 'The name of the user.'
                    }],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref':
                                    '#/components/schemas/addTodoRequest'
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'OK'
                        }
                    }
                },
                'delete': {
                    'operationId':
                    'deleteTodo',
                    'summary':
                    'Delete a todo from the list',
                    'parameters': [{
                        'in': 'path',
                        'name': 'username',
                        'schema': {
                            'type': 'string'
                        },
                        'required': True,
                        'description': 'The name of the user.'
                    }],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref':
                                    '#/components/schemas/deleteTodoRequest'
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'OK'
                        }
                    }
                }
            }
        },
        'components': {
            'schemas': {
                'getTodosResponse': {
                    'type': 'object',
                    'properties': {
                        'todos': {
                            'type': 'array',
                            'items': {
                                'type': 'string'
                            },
                            'description': 'The list of todos.'
                        }
                    }
                },
                'addTodoRequest': {
                    'type': 'object',
                    'required': ['todo'],
                    'properties': {
                        'todo': {
                            'type': 'string',
                            'description': 'The todo to add to the list.',
                            'required': True
                        }
                    }
                },
                'deleteTodoRequest': {
                    'type': 'object',
                    'required': ['todo_idx'],
                    'properties': {
                        'todo_idx': {
                            'type': 'integer',
                            'description': 'The index of the todo to delete.',
                            'required': True
                        }
                    }
                }
            }
        }
    }
    result = openapi_schema_convert(openapi_schema, {})
    print(result)
