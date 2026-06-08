import re

def categorise_endpoint(method, path):
    """Determine the category of an endpoint based on method and path"""
    
    # Check file operations first since they're most specific
    for pattern in ENDPOINT_CATEGORIES['file_operation']['patterns']:
        if re.search(pattern, path, re.IGNORECASE):
            return 'file_operation'
    
    # Check search operations
    for pattern in ENDPOINT_CATEGORIES['search']['patterns']:
        if re.search(pattern, path, re.IGNORECASE):
            return 'search'
    
    # Then check by HTTP method
    if method.upper() == 'POST':
        return 'create'
    elif method.upper() in ['PUT', 'PATCH']:
        return 'update'
    elif method.upper() == 'DELETE':
        return 'delete'
    elif method.upper() == 'GET':
        # Distinguish list vs single item reads
        if re.search(r'/\d+$|/[a-f0-9-]{36}$', path):
            return 'simple_read'
        else:
            return 'list_read'
    
    return 'simple_read'  # fallback


def score_to_grade(score):
    if score >= 90:
        return 'A'
    elif score >= 75:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 40:
        return 'D'
    else:
        return 'F'

def score_metric_with_thresholds(metric_name, value, thresholds):
    higher_is_better = metric_name in HIGHER_IS_BETTER

    if higher_is_better:
        if value >= thresholds['excellent']:
            return 100
        elif value >= thresholds['good']:
            range_size = thresholds['excellent'] - thresholds['good']
            return 75 + 25 * (value - thresholds['good']) / range_size if range_size > 0 else 75
        elif value >= thresholds['fair']:
            range_size = thresholds['good'] - thresholds['fair']
            return 50 + 25 * (value - thresholds['fair']) / range_size if range_size > 0 else 50
        else:
            return max(0, 25 * value / thresholds['fair']) if thresholds['fair'] > 0 else 0
    else:
        if value <= thresholds['excellent']:
            return 100
        elif value <= thresholds['good']:
            range_size = thresholds['good'] - thresholds['excellent']
            return 75 + 25 * (1 - (value - thresholds['excellent']) / range_size) if range_size > 0 else 75
        elif value <= thresholds['fair']:
            range_size = thresholds['fair'] - thresholds['good']
            return 50 + 25 * (1 - (value - thresholds['good']) / range_size) if range_size > 0 else 50
        else:
            return max(0, 25 * (1 - (value - thresholds['fair']) / thresholds['fair'])) if thresholds['fair'] > 0 else 0

def score_endpoint(endpoint_data):
    """Score a single endpoint against its category thresholds"""
    category = endpoint_data['category']
    metrics = endpoint_data['metrics']
    thresholds = ENDPOINT_CATEGORIES.get(
        category,
        ENDPOINT_CATEGORIES['simple_read']
    )['thresholds']

    weighted_score = 0
    total_weight = 0
    metric_scores = {}

    for metric_name, weight in ENDPOINT_METRIC_WEIGHTS.items():
        value = metrics.get(metric_name)
        if value is not None and metric_name in thresholds:
            score = score_metric_with_thresholds(
                metric_name, value, thresholds[metric_name]
            )
            metric_scores[metric_name] = round(score, 1)
            weighted_score += score * weight
            total_weight += weight

    final_score = weighted_score / total_weight if total_weight > 0 else 0

    return {
        'score': round(final_score, 1),
        'grade': score_to_grade(final_score),
        'metric_scores': metric_scores
    }

def score_resource_utilisation(docker_metrics):
    """Score CPU and memory from Docker stats — application wide not per endpoint"""
    cpu_thresholds = {
        'excellent': 30,
        'good': 60,
        'fair': 85,
        'poor': float('inf')
    }
    memory_thresholds = {
        'excellent': 256,
        'good': 512,
        'fair': 1024,
        'poor': float('inf')
    }

    cpu_score = score_metric_with_thresholds(
        'cpu_average_percent',
        docker_metrics.get('cpu_average_percent', 0),
        cpu_thresholds
    )
    memory_score = score_metric_with_thresholds(
        'memory_average_mb',
        docker_metrics.get('memory_average_mb', 0),
        memory_thresholds
    )

    return round(cpu_score * 0.5 + memory_score * 0.5, 1)

def score_all_endpoints(per_endpoint_metrics, docker_metrics):
    """
    Score all endpoints individually then roll up into
    ISO sub-characteristic scores and overall score
    """
    endpoint_scores = {}

    for key, ep_data in per_endpoint_metrics.items():
        # Only score endpoints that actually received requests
        if ep_data['metrics'].get('total_requests', 0) > 0:
            endpoint_scores[key] = {
                **ep_data,
                'scoring': score_endpoint(ep_data)
            }

    if not endpoint_scores:
        return {
            'overall_score': 0,
            'grade': 'F',
            'sub_characteristics': {},
            'endpoint_scores': {},
            'note': 'No endpoints received requests'
        }

    # Time behaviour — average of avg_response_time scores across endpoints
    time_scores = [
        ep['scoring']['metric_scores'].get('avg_response_time_ms', 0)
        for ep in endpoint_scores.values()
        if ep['metrics'].get('avg_response_time_ms', 0) > 0
    ]

    # Capacity — average of failure_rate scores across endpoints
    capacity_scores = [
        ep['scoring']['metric_scores'].get('failure_rate_percent', 0)
        for ep in endpoint_scores.values()
    ]

    # Resource utilisation — application wide from Docker
    resource_score = score_resource_utilisation(docker_metrics)

    time_behaviour_score = round(
        sum(time_scores) / len(time_scores), 1
    ) if time_scores else 0

    capacity_score = round(
        sum(capacity_scores) / len(capacity_scores), 1
    ) if capacity_scores else 0

    # Weighted rollup into overall score
    overall = (
        time_behaviour_score * SUB_CHARACTERISTIC_WEIGHTS['time_behaviour'] +
        resource_score * SUB_CHARACTERISTIC_WEIGHTS['resource_utilisation'] +
        capacity_score * SUB_CHARACTERISTIC_WEIGHTS['capacity']
    )

    return {
        'overall_score': round(overall, 1),
        'grade': score_to_grade(overall),
        'sub_characteristics': {
            'time_behaviour': {
                'score': time_behaviour_score,
                'grade': score_to_grade(time_behaviour_score),
                'note': 'Average of response time scores across all endpoints'
            },
            'resource_utilisation': {
                'score': resource_score,
                'grade': score_to_grade(resource_score),
                'note': 'CPU and memory usage under load'
            },
            'capacity': {
                'score': capacity_score,
                'grade': score_to_grade(capacity_score),
                'note': 'Average of failure rate scores across all endpoints'
            }
        },
        'endpoint_scores': endpoint_scores
    }


HIGHER_IS_BETTER = {'requests_per_second'}

ENDPOINT_CATEGORIES = {
    'simple_read': {
        'description': 'Simple data retrieval by ID',
        'patterns': [
            r'/api/\w+/\d+$',        # /api/product/1
            r'/api/\w+/[^/]+$',      # /api/user/abc
        ],
        'methods': ['GET'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 50,
                'good': 150,
                'fair': 400,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 100,
                'good': 300,
                'fair': 800,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'list_read': {
        'description': 'Retrieving a list or collection',
        'patterns': [
            r'/api/\w+s$',           # /api/products
            r'/api/\w+$',            # /api/users
        ],
        'methods': ['GET'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 100,
                'good': 300,
                'fair': 800,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 200,
                'good': 600,
                'fair': 1500,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'search': {
        'description': 'Search or filter operation',
        'patterns': [
            r'/search',
            r'/filter',
            r'/query',
            r'/find'
        ],
        'methods': ['GET'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 200,
                'good': 500,
                'fair': 1500,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 400,
                'good': 1000,
                'fair': 3000,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'create': {
        'description': 'Creating a new resource',
        'patterns': [r'.*'],
        'methods': ['POST'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 100,
                'good': 300,
                'fair': 800,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 200,
                'good': 600,
                'fair': 1500,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'update': {
        'description': 'Updating an existing resource',
        'patterns': [r'.*'],
        'methods': ['PUT', 'PATCH'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 100,
                'good': 300,
                'fair': 800,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 200,
                'good': 600,
                'fair': 1500,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'delete': {
        'description': 'Deleting a resource',
        'patterns': [r'.*'],
        'methods': ['DELETE'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 50,
                'good': 150,
                'fair': 400,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 100,
                'good': 300,
                'fair': 800,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 3.0,
                'poor': float('inf')
            }
        }
    },
    'file_operation': {
        'description': 'File upload, download or image operation',
        'patterns': [
            r'/image',
            r'/file',
            r'/upload',
            r'/download',
            r'/attachment'
        ],
        'methods': ['GET', 'POST', 'PUT'],
        'thresholds': {
            'avg_response_time_ms': {
                'excellent': 500,
                'good': 1500,
                'fair': 5000,
                'poor': float('inf')
            },
            'p95_response_time_ms': {
                'excellent': 1000,
                'good': 3000,
                'fair': 10000,
                'poor': float('inf')
            },
            'failure_rate_percent': {
                'excellent': 0.1,
                'good': 1.0,
                'fair': 5.0,
                'poor': float('inf')
            }
        }
    }
}
# Weights for scoring each endpoint
# response time weighted most heavily
ENDPOINT_METRIC_WEIGHTS = {
    'avg_response_time_ms': 0.35,
    'p95_response_time_ms': 0.40,
    'failure_rate_percent': 0.25
}

# Weights for rolling up sub-characteristic scores
SUB_CHARACTERISTIC_WEIGHTS = {
    'time_behaviour': 0.45,
    'resource_utilisation': 0.35,
    'capacity': 0.20
}
