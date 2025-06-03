import os
from collections import defaultdict

PROJECT_PATH = r"C:\Users\Lenovo\OneDrive\桌面\project2025\my_perspective_app"

def count_lines_in_file(file_path):
    """统计单个文件的代码行数,跳过空行和注释行"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        count = 0
        in_multiline_comment = False
        
        for line in lines:
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
                
            # 处理多行注释
            if '"""' in line or "'''" in line:
                in_multiline_comment = not in_multiline_comment
                continue
                
            if in_multiline_comment:
                continue
                
            # 跳过单行注释
            if line.startswith('#') or line.startswith('//'):
                continue
                
            count += 1
            
        return count
    except Exception as e:
        print(f"无法读取文件 {file_path}: {str(e)}")
        return 0

def count_lines_in_directory(directory):
    """递归统计目录中所有代码文件的行数"""
    # 定义要统计的文件类型，根据项目需要可以调整
    file_extensions = {'.py'}
        
    stats = defaultdict(int)
    total_lines = 0
    
    for root, _, files in os.walk(directory):
        # 跳过隐藏目录和特定目录
        if any(part.startswith('.') for part in root.split(os.sep)):
            continue
        if 'node_modules' in root or 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in file_extensions:
                file_path = os.path.join(root, file)
                lines = count_lines_in_file(file_path)
                stats[ext] += lines
                total_lines += lines
                print(f"正在统计: {os.path.relpath(file_path, directory)} - {lines} 行")
                
    return stats, total_lines

def main():
    print(f"\n开始统计项目代码行数...")
    print(f"项目路径: {PROJECT_PATH}")
    print("-" * 50)
    
    stats, total = count_lines_in_directory(PROJECT_PATH)
    
    print("\n代码统计结果:")
    print("-" * 30)
    for ext, count in sorted(stats.items()):
        print(f"{ext[1:]:>10} 文件: {count:>8} 行")
    print("-" * 30)
    print(f"总计: {total:>15} 行")

if __name__ == '__main__':
    main()