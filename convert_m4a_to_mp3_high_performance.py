import os
import glob
import subprocess
import threading
import queue
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import psutil
import signal
import sys

class HighPerformanceConverter:
    def __init__(self, input_dir, output_dir=None, max_files=None, sample_rate=16000, max_workers=None):
        self.input_dir = input_dir
        self.output_dir = output_dir if output_dir else input_dir
        self.max_files = max_files
        self.sample_rate = sample_rate
        
        # 自动检测最佳线程数
        if max_workers is None:
            cpu_count = psutil.cpu_count(logical=False)  # 物理核心数
            self.max_workers = min(cpu_count * 2, 16)  # 不超过16个线程
        else:
            self.max_workers = max_workers
            
        # 统计信息
        self.stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_time': 0,
            'start_time': time.time()
        }
        
        # 错误收集
        self.failed_files = []
        self.lock = threading.Lock()
        
        # 优雅退出处理
        self.shutdown = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        print(f"\n收到退出信号 {signum}，正在安全关闭...")
        self.shutdown = True
        
    def check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, check=True, timeout=10)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def get_file_list(self):
        """获取需要转换的文件列表"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 查找所有m4a文件
        m4a_pattern = os.path.join(self.input_dir, "**/*.m4a")
        all_files = glob.glob(m4a_pattern, recursive=True)
        
        if not all_files:
            m4a_pattern = os.path.join(self.input_dir, "*.m4a")
            all_files = glob.glob(m4a_pattern)
            
        if not all_files:
            return []
        
        # 排序并限制数量
        all_files.sort()
        if self.max_files:
            all_files = all_files[:self.max_files]
        
        # 过滤掉已存在的文件
        todo_files = []
        for input_file in all_files:
            output_file = self._get_output_path(input_file)
            if not os.path.exists(output_file):
                todo_files.append((input_file, output_file))
            else:
                self.stats['skipped'] += 1
                
        return todo_files
    
    def _get_output_path(self, input_file):
        """获取输出文件路径"""
        rel_path = os.path.relpath(input_file, self.input_dir)
        output_path = os.path.join(self.output_dir, rel_path)
        return str(Path(output_path).with_suffix('.mp3'))
    
    def convert_single_file(self, input_file, output_file):
        """转换单个文件"""
        if self.shutdown:
            return None
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 构建ffmpeg命令
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ar', str(self.sample_rate),
            '-ab', '128k',
            '-ac', '1',  # 单声道
            '-y',
            '-loglevel', 'error',  # 只显示错误
            '-nostats',  # 不显示统计信息
            output_file
        ]
        
        start_time = time.time()
        try:
            # 设置超时防止卡死
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            conversion_time = time.time() - start_time
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'input': os.path.basename(input_file),
                    'output': os.path.basename(output_file),
                    'time': conversion_time
                }
            else:
                return {
                    'status': 'failed',
                    'input': os.path.basename(input_file),
                    'error': result.stderr.strip(),
                    'time': conversion_time
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'failed',
                'input': os.path.basename(input_file),
                'error': 'Timeout (>5min)',
                'time': time.time() - start_time
            }
        except Exception as e:
            return {
                'status': 'failed',
                'input': os.path.basename(input_file),
                'error': str(e),
                'time': time.time() - start_time
            }
    
    def print_progress(self, current, total, result=None):
        """打印进度信息"""
        percentage = (current / total) * 100
        elapsed = time.time() - self.stats['start_time']
        
        if current > 0:
            eta = (elapsed / current) * (total - current)
            eta_str = f"ETA: {eta/60:.1f}min"
        else:
            eta_str = "ETA: --"
        
        status_line = f"[{current:4d}/{total}] {percentage:5.1f}% | "
        status_line += f"✓{self.stats['success']:3d} ✗{self.stats['failed']:3d} ⊘{self.stats['skipped']:3d} | "
        status_line += f"{eta_str} | {self.max_workers} threads"
        
        if result:
            if result['status'] == 'success':
                status_line += f" | ✓ {result['input']} ({result['time']:.1f}s)"
            else:
                status_line += f" | ✗ {result['input']} - {result['error'][:50]}"
        
        print(f"\r{status_line:<120}", end="", flush=True)
    
    def convert_batch(self):
        """批量转换文件"""
        print(f"初始化高性能转换器...")
        print(f"  输入目录: {self.input_dir}")
        print(f"  输出目录: {self.output_dir}")
        print(f"  线程数: {self.max_workers}")
        print(f"  采样率: {self.sample_rate} Hz")
        
        # 检查ffmpeg
        if not self.check_ffmpeg():
            print("错误: 未找到ffmpeg或ffmpeg不可用")
            return False
        
        # 获取文件列表
        print("扫描文件...")
        file_list = self.get_file_list()
        
        if not file_list:
            print("没有找到需要转换的m4a文件")
            return False
        
        total_files = len(file_list) + self.stats['skipped']
        print(f"找到 {len(file_list)} 个待转换文件 ({self.stats['skipped']} 个已跳过)")
        print(f"开始批量转换...\n")
        
        # 多线程转换
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(self.convert_single_file, input_file, output_file): (input_file, output_file)
                for input_file, output_file in file_list
            }
            
            # 处理完成的任务
            for future in as_completed(futures):
                if self.shutdown:
                    print("\n正在取消剩余任务...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                result = future.result()
                completed += 1
                
                if result:
                    with self.lock:
                        if result['status'] == 'success':
                            self.stats['success'] += 1
                        else:
                            self.stats['failed'] += 1
                            self.failed_files.append({
                                'file': result['input'],
                                'error': result['error']
                            })
                        
                        self.stats['total_time'] += result['time']
                
                self.print_progress(completed, len(file_list), result)
        
        print("\n")  # 换行
        self.print_summary()
        return True
    
    def print_summary(self):
        """打印转换总结"""
        total_elapsed = time.time() - self.stats['start_time']
        
        print("="*80)
        print("转换完成!")
        print(f"总用时: {total_elapsed/60:.2f} 分钟")
        print(f"成功转换: {self.stats['success']} 个文件")
        print(f"转换失败: {self.stats['failed']} 个文件")
        print(f"跳过文件: {self.stats['skipped']} 个文件")
        
        if self.stats['success'] > 0:
            avg_time = self.stats['total_time'] / self.stats['success']
            print(f"平均转换时间: {avg_time:.2f} 秒/文件")
            print(f"转换速度: {self.stats['success']/(total_elapsed/60):.1f} 文件/分钟")
        
        if self.failed_files:
            print(f"\n失败的文件:")
            for item in self.failed_files[:10]:  # 只显示前10个
                print(f"  - {item['file']}: {item['error']}")
            if len(self.failed_files) > 10:
                print(f"  ... 还有 {len(self.failed_files) - 10} 个失败文件")
        
        print("="*80)

def main():
    """主函数"""
    # 配置参数
    input_directory = "/speed-scratch/qiaoyu/speed-hpc/project/discogs-vi-dataset/music_dir"
    output_directory = "/speed-scratch/qiaoyu/speed-hpc/project/discogs-vi-dataset/music_dir"  # 或设为其他目录
    max_files = None  # None表示转换所有文件，或设置具体数字如1000
    max_workers = None  # None表示自动检测，或手动设置如8
    
    print("高性能M4A到MP3转换器")
    print("="*80)
    
    # 创建转换器
    converter = HighPerformanceConverter(
        input_dir=input_directory,
        output_dir=output_directory,
        max_files=max_files,
        sample_rate=16000,
        max_workers=max_workers
    )
    
    # 开始转换
    success = converter.convert_batch()
    
    if success:
        print("转换任务完成!")
    else:
        print("转换任务失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()
