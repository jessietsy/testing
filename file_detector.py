import os
JAVA_JUNK = ['target', '.git', 'build', '.gradle', '.idea', '__MACOSX']

def detect_java_files(extract_path):
    result = {
        'build_system': None,
        'java_files': [],
        'entry_points': [],
        'project_root': None,
        'errors': []
    }

    all_files = []
    for root, dirs, files in os.walk(extract_path):
        dirs[:] = [d for d in dirs if d not in JAVA_JUNK]
        if 'pom.xml' in files or 'build.gradle' in files or 'build.gradle.kts' in files:
            result['project_root'] = root

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, extract_path)
            all_files.append((rel_path, full_path))
        
    # Detect build system
    filenames = [file[0].replace('\\', '/') for file in all_files] # compatability fix
    if any(f.endswith('pom.xml') for f in filenames):
        result['build_system'] = 'maven'
    if any(f.endswith('build.gradle') or f.endswith('build.gradle.kts') for f in filenames):
        result['buil_system'] = 'gradle'

    # Detect Java files and entry points
    for rel_path, full_path in all_files:
        if rel_path.endswith('.java'):
            result['java_files'].append(rel_path)
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'public static void main' in content:
                        result['entry_points'].append(rel_path)
            
            except Exception as e:
                result['errors'].append(f"Error reading {rel_path}: {str(e)}")

    if not result['build_system']:
        result['errors'].append("No build system detected. Please include a pom.xml or build.gradle file.")
    if not result['entry_points']:
        result['errors'].append("No entry points detected. Please include at least one Java file with a main method.")

    return result

# print(detect_java_files('uploads/project'))