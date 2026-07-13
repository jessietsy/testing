import os

def collect_entity_source(project_root):
    """Collect source of Java entity classes"""
    entity_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in ['target', 'build', '.git', 'test']]
        for filename in files:
            if filename.endswith('.java'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', errors='ignore') as f:
                        content = f.read()
                        if '@Entity' in content:
                            entity_files.append(f"// {filename}\n{content}")

                except Exception:
                    pass
    return entity_files


