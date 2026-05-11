import anthropic
client = anthropic.Anthropic()

def format_code_samples(samples):
    pass

def prompt(build_system, code_samples, metrics):
    return f"""
    You are a software quality evaluator. Evaluate the following Java project against the ISO/IEC 25010 Performance Efficiency criteria

    ISO/IEC 25010 Performance Efficiency has three sub-charateristics:
    1. Time Behaviour:
    2. Rsource Utilisation:
    3. Capacity:

    Measured metrics:
    {metrics}

    Code snippets:
    {code_samples}

    Provide your evaluation in the following JSON format exactly, with no additional text outside the JSON:
    {{}}

    """
