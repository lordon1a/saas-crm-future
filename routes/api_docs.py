from flask import Blueprint, jsonify, render_template_string, request


bp = Blueprint('api_docs', __name__)


def _openapi_spec(base_url: str):
    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'WhatsApp CRM Public API',
            'version': 'v1',
            'description': 'Public REST API for contacts, companies, deals, tasks, activities, OAuth and webhooks.',
        },
        'servers': [
            {'url': base_url.rstrip('/')},
        ],
        'tags': [
            {'name': 'Public API'},
            {'name': 'OAuth2'},
            {'name': 'Public Auth Management'},
        ],
        'components': {
            'securitySchemes': {
                'ApiKeyAuth': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'X-API-Key',
                },
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'OAuth2 Access Token',
                },
            },
            'schemas': {
                'Pagination': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer'},
                        'offset': {'type': 'integer'},
                        'total': {'type': 'integer'},
                    },
                },
                'ErrorResponse': {
                    'type': 'object',
                    'properties': {
                        'error': {'type': 'string'},
                        'message': {'type': 'string'},
                    },
                },
            },
        },
        'paths': {
            '/public/api/v1/contacts': {
                'get': {
                    'tags': ['Public API'],
                    'summary': 'List contacts',
                    'security': [{'ApiKeyAuth': []}, {'BearerAuth': []}],
                    'parameters': [
                        {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'default': 50}},
                        {'name': 'offset', 'in': 'query', 'schema': {'type': 'integer', 'default': 0}},
                    ],
                    'responses': {
                        '200': {'description': 'Success'},
                        '401': {'description': 'Invalid API credentials', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ErrorResponse'}}}},
                        '429': {'description': 'Rate limit exceeded'},
                    },
                }
            },
            '/public/api/v1/companies': {
                'get': {
                    'tags': ['Public API'],
                    'summary': 'List companies',
                    'security': [{'ApiKeyAuth': []}, {'BearerAuth': []}],
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}, '429': {'description': 'Rate limit exceeded'}},
                }
            },
            '/public/api/v1/deals': {
                'get': {
                    'tags': ['Public API'],
                    'summary': 'List deals',
                    'security': [{'ApiKeyAuth': []}, {'BearerAuth': []}],
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}, '429': {'description': 'Rate limit exceeded'}},
                }
            },
            '/public/api/v1/tasks': {
                'get': {
                    'tags': ['Public API'],
                    'summary': 'List tasks',
                    'security': [{'ApiKeyAuth': []}, {'BearerAuth': []}],
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}, '429': {'description': 'Rate limit exceeded'}},
                }
            },
            '/public/api/v1/activities': {
                'get': {
                    'tags': ['Public API'],
                    'summary': 'List activities',
                    'security': [{'ApiKeyAuth': []}, {'BearerAuth': []}],
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}, '429': {'description': 'Rate limit exceeded'}},
                }
            },
            '/public/oauth/authorize': {
                'get': {
                    'tags': ['OAuth2'],
                    'summary': 'OAuth2 authorization endpoint',
                    'parameters': [
                        {'name': 'response_type', 'in': 'query', 'required': True, 'schema': {'type': 'string', 'example': 'code'}},
                        {'name': 'client_id', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'redirect_uri', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'scope', 'in': 'query', 'required': False, 'schema': {'type': 'string', 'example': 'read'}},
                        {'name': 'state', 'in': 'query', 'required': False, 'schema': {'type': 'string'}},
                    ],
                    'responses': {
                        '302': {'description': 'Redirects to client callback with authorization code'},
                        '400': {'description': 'Invalid request'},
                    },
                }
            },
            '/public/oauth/token': {
                'post': {
                    'tags': ['OAuth2'],
                    'summary': 'OAuth2 token endpoint',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'required': ['grant_type', 'code', 'client_id', 'client_secret', 'redirect_uri'],
                                    'properties': {
                                        'grant_type': {'type': 'string', 'example': 'authorization_code'},
                                        'code': {'type': 'string'},
                                        'client_id': {'type': 'string'},
                                        'client_secret': {'type': 'string'},
                                        'redirect_uri': {'type': 'string'},
                                    },
                                }
                            }
                        },
                    },
                    'responses': {
                        '200': {'description': 'Access token issued'},
                        '400': {'description': 'Invalid grant'},
                        '401': {'description': 'Invalid client'},
                    },
                }
            },
            '/api/v1/public-auth/api-keys': {
                'post': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Create API key (agent session required)',
                    'responses': {'201': {'description': 'Created'}, '401': {'description': 'Unauthorized'}},
                },
                'get': {
                    'tags': ['Public Auth Management'],
                    'summary': 'List API keys (agent session required)',
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}},
                },
            },
            '/api/v1/public-auth/oauth-clients': {
                'post': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Create OAuth client (agent session required)',
                    'responses': {'201': {'description': 'Created'}, '401': {'description': 'Unauthorized'}},
                },
                'get': {
                    'tags': ['Public Auth Management'],
                    'summary': 'List OAuth clients (agent session required)',
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}},
                },
            },
            '/api/v1/public-auth/webhooks': {
                'post': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Create webhook subscription (agent session required)',
                    'responses': {'201': {'description': 'Created'}, '401': {'description': 'Unauthorized'}},
                },
                'get': {
                    'tags': ['Public Auth Management'],
                    'summary': 'List webhook subscriptions (agent session required)',
                    'responses': {'200': {'description': 'Success'}, '401': {'description': 'Unauthorized'}},
                },
            },
            '/api/v1/public-auth/webhooks/{id}': {
                'put': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Update webhook subscription',
                    'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                    'responses': {'200': {'description': 'Updated'}, '404': {'description': 'Not found'}},
                },
                'delete': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Delete webhook subscription',
                    'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                    'responses': {'200': {'description': 'Deleted'}, '404': {'description': 'Not found'}},
                },
            },
            '/api/v1/public-auth/webhooks/{id}/deliveries': {
                'get': {
                    'tags': ['Public Auth Management'],
                    'summary': 'List webhook deliveries',
                    'parameters': [
                        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                        {'name': 'limit', 'in': 'query', 'required': False, 'schema': {'type': 'integer', 'default': 50}},
                    ],
                    'responses': {'200': {'description': 'Success'}, '404': {'description': 'Not found'}},
                }
            },
            '/api/v1/public-auth/webhooks/{id}/test': {
                'post': {
                    'tags': ['Public Auth Management'],
                    'summary': 'Trigger test webhook delivery',
                    'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                    'responses': {'200': {'description': 'Delivery attempted'}, '404': {'description': 'Not found'}},
                }
            },
        },
    }


@bp.route('/api/openapi.json', methods=['GET'])
def api_openapi_json():
    base_url = request.host_url.rstrip('/')
    return jsonify(_openapi_spec(base_url)), 200


@bp.route('/api/docs', methods=['GET'])
def api_docs_page():
    html = """
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>WhatsApp CRM API Docs</title>
    <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\" />
    <style>
      html, body { margin: 0; padding: 0; height: 100%; }
      #swagger-ui { height: 100%; }
    </style>
  </head>
  <body>
    <div id=\"swagger-ui\"></div>
    <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/api/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        defaultModelsExpandDepth: 1,
        persistAuthorization: true,
      });
    </script>
  </body>
</html>
    """
    return render_template_string(html)
