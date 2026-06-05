def detect_application_category(project_root):
    """
    Scans pom.xml and Java files to determine application category
    Returns category name and confidence scores
    """
    scores = {category: 0 for category in APPLICATION_CATEGORIES}

    # Read pom.xml
    pom_content = ''
    pom_path = os.path.join(project_root, 'pom.xml')
    if os.path.exists(pom_path):
        with open(pom_path, 'r', errors='ignore') as f:
            pom_content = f.read().lower()

    # Read Java files (sample only for speed)
    java_content = ''
    files_scanned = 0
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]
        for filename in files:
            if filename.endswith('.java') and files_scanned < 20:
                try:
                    with open(os.path.join(root, filename), 'r', errors='ignore') as f:
                        java_content += f.read().lower()
                    files_scanned += 1
                except Exception:
                    pass

    combined_content = pom_content + java_content

    # Score each category
    for category, config in APPLICATION_CATEGORIES.items():
        for indicator in config['indicators']:
            if indicator.lower() in combined_content:
                scores[category] += 1

    # Pick highest scoring category
    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    # Only use detected category if we found at least one indicator
    if best_score == 0:
        return 'general', scores

    return best_category, scores

def score_overall(metrics, application_category):
    """Score metrics against the appropriate threshold profile"""

    # Get the right thresholds for this application type
    profile = THRESHOLD_PROFILES.get(
        application_category,
        THRESHOLD_PROFILES['general']
    )

    sub_char_scores = {}
    overall_weighted = 0
    total_weight = 0

    for sub_char_name, sub_char_config in WEIGHTS.items():
        result = score_sub_characteristic(
            sub_char_name,
            metrics,
            profile  # pass profile through
        )
        sub_char_scores[sub_char_name] = result
        overall_weighted += result['score'] * sub_char_config['weight']
        total_weight += sub_char_config['weight']

    overall_score = overall_weighted / total_weight if total_weight > 0 else 0

    return {
        'overall_score': round(overall_score, 1),
        'grade': score_to_grade(overall_score),
        'application_category': application_category,
        'profile_used': profile['description'],
        'sub_characteristics': sub_char_scores
    }

def score_sub_characteristic(sub_char_name, metrics, profile):
    sub_char = WEIGHTS[sub_char_name]
    metric_weights = sub_char['metrics']

    total_weight = 0
    weighted_score = 0
    breakdown = {}

    for metric_name, weight in metric_weights.items():
        if metric_name in metrics and metrics[metric_name] is not None:
            # Use profile thresholds instead of fixed ones
            if metric_name in profile:
                score = score_metric_with_thresholds(
                    metric_name,
                    metrics[metric_name],
                    profile[metric_name]
                )
                if score is not None:
                    weighted_score += score * weight
                    total_weight += weight
                    breakdown[metric_name] = {
                        'value': metrics[metric_name],
                        'score': round(score, 1),
                        'weight': weight,
                        'contribution': round(score * weight, 1),
                        'thresholds': profile[metric_name]
                    }

    final_score = (weighted_score / total_weight) if total_weight > 0 else 0
    return {
        'score': round(final_score, 1),
        'breakdown': breakdown
    }

def score_metric_with_thresholds(metric_name, value, thresholds):
    """Score a metric against provided thresholds rather than fixed ones"""
    higher_is_better = metric_name in HIGHER_IS_BETTER

    if higher_is_better:
        if value >= thresholds['excellent']:
            return 100
        elif value >= thresholds['good']:
            range_size = thresholds['excellent'] - thresholds['good']
            if range_size == 0:
                return 75
            return 75 + 25 * (value - thresholds['good']) / range_size
        elif value >= thresholds['fair']:
            range_size = thresholds['good'] - thresholds['fair']
            if range_size == 0:
                return 50
            return 50 + 25 * (value - thresholds['fair']) / range_size
        else:
            return max(0, 25 * value / thresholds['fair']) if thresholds['fair'] > 0 else 0
    else:
        if value <= thresholds['excellent']:
            return 100
        elif value <= thresholds['good']:
            range_size = thresholds['good'] - thresholds['excellent']
            if range_size == 0:
                return 75
            return 75 + 25 * (1 - (value - thresholds['excellent']) / range_size)
        elif value <= thresholds['fair']:
            range_size = thresholds['fair'] - thresholds['good']
            if range_size == 0:
                return 50
            return 50 + 25 * (1 - (value - thresholds['good']) / range_size)
        else:
            return max(0, 25 * (1 - (value - thresholds['fair']) / thresholds['fair'])) if thresholds['fair'] > 0 else 0
        
APPLICATION_CATEGORIES = {
    'simple_crud_api': {
        'description': 'Simple REST API with basic database operations',
        'indicators': [
            'spring-boot-starter-data-jpa',
            '@GetMapping',
            '@PostMapping',
            'CrudRepository',
            'JpaRepository'
        ]
    },
    'compute_intensive': {
        'description': 'CPU-heavy processing, algorithms, data transformation',
        'indicators': [
            'processing',
            'calculation',
            'algorithm',
            'batch',
            'scheduler',
            '@Scheduled'
        ]
    },
    'data_streaming': {
        'description': 'High throughput data ingestion or streaming',
        'indicators': [
            'kafka',
            'rabbitmq',
            'activemq',
            'spring-kafka',
            'spring-amqp',
            'StreamListener'
        ]
    },
    'microservice': {
        'description': 'Small focused service, part of a larger system',
        'indicators': [
            'spring-cloud',
            'feign',
            'ribbon',
            'eureka',
            'resilience4j'
        ]
    },
    'file_processing': {
        'description': 'Reads, writes, or transforms files',
        'indicators': [
            'MultipartFile',
            'FileInputStream',
            'FileOutputStream',
            'Files.write',
            'BufferedReader'
        ]
    }
}

THRESHOLD_PROFILES = {
    'simple_crud_api': {
        'description': 'Simple CRUD REST API',
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
        'cpu_average_percent': {
            'excellent': 20,
            'good': 45,
            'fair': 70,
            'poor': float('inf')
        },
        'memory_average_mb': {
            'excellent': 256,
            'good': 512,
            'fair': 1024,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            'excellent': 0.1,
            'good': 1.0,
            'fair': 3.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            'excellent': 100,
            'good': 50,
            'fair': 20,
            'poor': 0
        }
    },

    'compute_intensive': {
        'description': 'Compute-heavy processing application',
        # Higher CPU thresholds are expected and acceptable
        'avg_response_time_ms': {
            'excellent': 500,
            'good': 2000,
            'fair': 10000,
            'poor': float('inf')
        },
        'p95_response_time_ms': {
            'excellent': 1000,
            'good': 5000,
            'fair': 20000,
            'poor': float('inf')
        },
        'cpu_average_percent': {
            # High CPU is expected here
            'excellent': 70,
            'good': 85,
            'fair': 95,
            'poor': float('inf')
        },
        'memory_average_mb': {
            # May need more memory for large datasets
            'excellent': 512,
            'good': 1024,
            'fair': 2048,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            'excellent': 0.1,
            'good': 1.0,
            'fair': 3.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            # Lower RPS expected due to heavy processing
            'excellent': 20,
            'good': 10,
            'fair': 5,
            'poor': 0
        }
    },

    'data_streaming': {
        'description': 'High throughput data streaming application',
        'avg_response_time_ms': {
            'excellent': 50,
            'good': 150,
            'fair': 500,
            'poor': float('inf')
        },
        'p95_response_time_ms': {
            'excellent': 100,
            'good': 300,
            'fair': 1000,
            'poor': float('inf')
        },
        'cpu_average_percent': {
            'excellent': 40,
            'good': 65,
            'fair': 85,
            'poor': float('inf')
        },
        'memory_average_mb': {
            'excellent': 512,
            'good': 1024,
            'fair': 2048,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            # Streaming apps should have very low failure rates
            'excellent': 0.01,
            'good': 0.1,
            'fair': 1.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            'excellent': 500,
            'good': 200,
            'fair': 100,
            'poor': 0
        }
    },

    'microservice': {
        'description': 'Microservice — small focused service',
        # Stricter response time since microservices chain together
        # latency compounds across service calls
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
        'cpu_average_percent': {
            'excellent': 15,
            'good': 35,
            'fair': 60,
            'poor': float('inf')
        },
        'memory_average_mb': {
            # Microservices should be lightweight
            'excellent': 128,
            'good': 256,
            'fair': 512,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            'excellent': 0.01,
            'good': 0.5,
            'fair': 2.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            'excellent': 200,
            'good': 100,
            'fair': 40,
            'poor': 0
        }
    },

    'file_processing': {
        'description': 'File reading, writing or transformation',
        'avg_response_time_ms': {
            # File operations are inherently slower
            'excellent': 1000,
            'good': 5000,
            'fair': 15000,
            'poor': float('inf')
        },
        'p95_response_time_ms': {
            'excellent': 2000,
            'good': 10000,
            'fair': 30000,
            'poor': float('inf')
        },
        'cpu_average_percent': {
            'excellent': 30,
            'good': 60,
            'fair': 85,
            'poor': float('inf')
        },
        'memory_average_mb': {
            # File processing may buffer large files
            'excellent': 512,
            'good': 1024,
            'fair': 2048,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            'excellent': 0.1,
            'good': 1.0,
            'fair': 5.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            'excellent': 30,
            'good': 15,
            'fair': 5,
            'poor': 0
        }
    },

    # Fallback if category cannot be determined
    'general': {
        'description': 'General Java application',
        'avg_response_time_ms': {
            'excellent': 200,
            'good': 500,
            'fair': 2000,
            'poor': float('inf')
        },
        'p95_response_time_ms': {
            'excellent': 400,
            'good': 1000,
            'fair': 4000,
            'poor': float('inf')
        },
        'cpu_average_percent': {
            'excellent': 30,
            'good': 60,
            'fair': 85,
            'poor': float('inf')
        },
        'memory_average_mb': {
            'excellent': 256,
            'good': 512,
            'fair': 1024,
            'poor': float('inf')
        },
        'failure_rate_percent': {
            'excellent': 0.1,
            'good': 1.0,
            'fair': 5.0,
            'poor': float('inf')
        },
        'requests_per_second': {
            'excellent': 50,
            'good': 25,
            'fair': 10,
            'poor': 0
        }
    }
}