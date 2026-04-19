#!/usr/bin/env python3
"""
简单的系统音频录制测试脚本
功能：录制3秒系统音频并保存为WAV文件
"""

import subprocess
import numpy as np
import wave
import os
import time

def record_system_audio(duration=3, sample_rate=44100, output_file="test_system.wav"):
    """录制系统音频"""
    print(f"[测试] 开始录制 {duration} 秒系统音频...")
    
    # 录制原始音频数据
    raw_file = "test_system.raw"
    
    # 使用实际的监视器名称（从 pactl 输出获取）
    monitor_name = "alsa_output.pci-0000_10_00.1.hdmi-stereo-extra2.monitor"
    
    cmd = [
        'parec',
        '-d', monitor_name,
        '--format=s16le',
        '--rate=' + str(sample_rate),
        '--channels=1'
    ]
    
    try:
        # 执行录制命令
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        # 读取指定时长的数据
        start_time = time.time()
        data = b''
        
        while time.time() - start_time < duration:
            chunk = process.stdout.read(4096)  # 每次读取 4096 字节
            if not chunk:
                break
            data += chunk
        
        # 终止进程
        process.terminate()
        process.wait()
        
        if not data:
            print("[错误] 未录制到音频数据")
            return False
        
        print(f"[测试] 录制完成，获取到 {len(data)} 字节数据")
        
        # 保存原始数据
        with open(raw_file, 'wb') as f:
            f.write(data)
        print(f"[测试] 原始数据已保存到 {raw_file}")
        
        # 转换为numpy数组
        samples = np.frombuffer(data, dtype=np.int16)
        print(f"[测试] 转换为 {len(samples)} 个样本")
        
        # 保存为WAV文件
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16位
            wf.setframerate(sample_rate)
            wf.writeframes(samples.tobytes())
        
        print(f"[测试] WAV文件保存成功: {output_file}")
        print(f"[测试] 音频时长: {len(samples)/sample_rate:.1f}秒")
        
        # 清理临时文件
        if os.path.exists(raw_file):
            os.remove(raw_file)
            print(f"[测试] 清理临时文件: {raw_file}")
        
        return True
        
    except Exception as e:
        print(f"[错误] 处理失败: {e}")
        return False

def main():
    """主函数"""
    print("===== 系统音频录制测试 =====")
    
    # 测试录制
    success = record_system_audio(duration=3, output_file="test_system_audio.wav")
    
    if success:
        print("\n[测试] 测试完成！")
        print("[测试] 音频文件已保存到: test_system_audio.wav")
    else:
        print("\n[测试] 测试失败！")
    
    # 显示当前目录文件
    print("\n[测试] 当前目录文件:")
    for file in os.listdir('.'):
        if file.endswith('.wav'):
            size = os.path.getsize(file) / 1024
            print(f"  - {file} ({size:.1f} KB)")

if __name__ == "__main__":
    main()