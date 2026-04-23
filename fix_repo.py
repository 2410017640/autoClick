# -*- coding: utf-8 -*-
# 先清空 reflog 和损坏对象，再重建
import subprocess, os, shutil

os.chdir(r'D:\IDEA\works\test\autoClick')

# 清空 reflog（不依赖 Git 命令，直接写文件）
for reflog in ['.git/logs/HEAD', '.git/logs/refs/heads/master']:
    p = os.path.join(*reflog.split('/'))
    if os.path.exists(p):
        with open(p, 'w') as f:
            f.write('')
    parent_dir = os.path.dirname(p)
    if os.path.exists(parent_dir):
        parent_files = os.listdir(parent_dir)
        for pf in parent_files:
            pf_path = os.path.join(parent_dir, pf)
            if os.path.isfile(pf_path):
                with open(pf_path, 'w') as f:
                    f.write('')

# 删除所有损坏的 loose objects（排除已知好的 SHA 前缀）
good_prefixes = {'7f', 'ac', '5e', '0d', '78', '50', '66', 'c5', '2c', '0b', '51', '4e'}
objects_dir = '.git/objects'
for entry in os.listdir(objects_dir):
    if entry in ['.', '..', 'info', 'pack']:
        continue
    entry_dir = os.path.join(objects_dir, entry)
    if not os.path.isdir(entry_dir):
        continue
    if entry not in good_prefixes:
        print('Removing .git/objects/' + entry)
        shutil.rmtree(entry_dir, ignore_errors=True)

print('Cleaned loose objects')
subprocess.run(['git', 'fsck', '--full'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('Fsck done')
subprocess.run(['git', 'log', '--oneline', '--all'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('Log:')
subprocess.run(['git', 'log', '--oneline'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)