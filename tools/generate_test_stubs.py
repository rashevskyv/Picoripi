import os
import ast

def generate_stubs(src_dir, tests_dir):
    os.makedirs(tests_dir, exist_ok=True)
    count = 0
    
    for root, dirs, files in os.walk(src_dir):
        # Skip unnecessary directories
        dirs[:] = [d for d in dirs if d not in ('venv', 'env', 'tests', 'test', '.git', '.gemini', '__pycache__', 'dist', 'build', 'tools', 'node_modules')]
        
        for f in files:
            if not f.endswith('.py') or f in ('__init__.py', 'setup.py', 'noxfile.py'):
                continue
                
            path = os.path.join(root, f)
            rel_dir = os.path.relpath(root, src_dir)
            
            # Form target test directory and file names. Example: core -> tests/test_core
            target_dir = tests_dir
            if rel_dir != '.':
                parts = [p for p in rel_dir.split(os.sep) if p]
                for p in parts:
                    target_dir = os.path.join(target_dir, f"test_{p}")
            
            os.makedirs(target_dir, exist_ok=True)
            
            # Make sure we have an __init__.py in all tests subdirectories
            init_target = target_dir
            while init_target != tests_dir:
                init_file = os.path.join(init_target, '__init__.py')
                if not os.path.exists(init_file):
                    open(init_file, 'w').close()
                init_target = os.path.dirname(init_target)
            
            # The test file itself
            test_file_path = os.path.join(target_dir, f'test_{f}')
            
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    tree = ast.parse(file.read())
                    
                funcs = []
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        funcs.append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                funcs.append(f"{node.name}_{item.name}")
                
                if not funcs:
                    continue
                
                # If test file doesn't exist, create it with stubs
                if not os.path.exists(test_file_path):
                    with open(test_file_path, 'w', encoding='utf-8') as tfile:
                        tfile.write(f"import pytest\n")
                        original_rel = os.path.relpath(path, src_dir).replace('\\', '/')
                        tfile.write(f"# Auto-generated test file for {original_rel}\n\n")
                        for func in funcs:
                            safe_name = func.replace('__', '')
                            if not safe_name: safe_name = "func"
                            tfile.write(f"def test_{safe_name}():\n    # TODO: Implement test\n    pytest.skip('Auto-generated stub')\n\n")
                    count += len(funcs)
            except Exception as e:
                pass
                
    print(f"Generated {count} test stubs across the project.")

if __name__ == '__main__':
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    generate_stubs(project_root, os.path.join(project_root, 'tests'))
